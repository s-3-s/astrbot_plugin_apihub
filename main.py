"""API HUB —— API 池管理系统"""
from __future__ import annotations
import asyncio, base64, json, os, random, re, tempfile, time
import aiohttp, aiohttp.web as web
import astrbot.api.message_components as Comp
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from .api_fetcher import fetch, resolve_path
from .pool_store import PoolStore

_RE_CMD = re.compile(r"^/(\S+)\s*(.*)", re.DOTALL)
_SESSION: aiohttp.ClientSession | None = None

async def _session() -> aiohttp.ClientSession:
    global _SESSION
    if _SESSION is None or _SESSION.closed:
        _SESSION = aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"},
            connector=aiohttp.TCPConnector(limit=20, ttl_dns_cache=300, keepalive_timeout=30),
            timeout=aiohttp.ClientTimeout(total=20),
        )
    return _SESSION

def _render(tpl: str, data) -> str:
    """
    支持以下语法：
      {data.key}            取单个值
      {data[0].key}         取数组指定下标
      {% for data[*] %}     正序遍历块开始（旧→新）
      {% for data[~] %}     倒序遍历块开始（新→旧）
      {% end %}             遍历块结束
      块内可写任意行，每条记录输出完整一块
      块内用 {item.key} 或直接 {key} 引用当前项的字段
    """
    # ── 块级 for 标签处理 ────────────────────────────────
    FOR_PAT  = re.compile(r'\{%\s*for\s+(\S+?)\[(\*|~)\]\s*%\}')
    END_PAT  = re.compile(r'\{%\s*end\s*%\}')

    lines  = tpl.split("\n")
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        fm = FOR_PAT.match(line.strip())
        if fm:
            list_path = fm.group(1).rstrip(".")
            reverse   = fm.group(2) == "~"
            # 收集块内容直到 {% end %}
            block = []
            i += 1
            while i < len(lines) and not END_PAT.match(lines[i].strip()):
                block.append(lines[i])
                i += 1
            i += 1  # 跳过 {% end %}

            item_list = resolve_path(data, list_path) if list_path else data
            if isinstance(item_list, list):
                items = list(reversed(item_list)) if reverse else item_list
                for item in items:
                    for bline in block:
                        def _rep(mm, _i=item):
                            path = mm.group(1).strip()
                            # 支持 item.xxx 或直接 xxx
                            if path.startswith("item."):
                                path = path[5:]
                            v = resolve_path(_i, path)
                            return str(v) if v is not None else f"[{path}]"
                        result.append(re.sub(r'\{([^}]+)\}', _rep, bline))
            continue

        # ── 普通行 ───────────────────────────────────────
        def _r(mm):
            path = mm.group(1).strip()
            path_fixed = re.sub(r'\[(\d+)\]', r'.\1', path)
            v = resolve_path(data, path_fixed)
            return str(v) if v is not None else f"[{path}]"
        result.append(re.sub(r'\{([^}]+)\}', _r, line))
        i += 1

    return "\n".join(result)

@register("astrbot_plugin_apihub", "s-3-s",
          "API HUB：API 池可视化管理，触发词动态注册", "1.0.0",
          "https://github.com/s-3-s/astrbot_plugin_apihub")
class ApiPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config  = config
        cfg          = config or {}
        data_dir     = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(data_dir, exist_ok=True)
        self.store      = PoolStore(data_dir)
        self._runner    = None
        self.web_port   = int(cfg.get("web_port", 6789))
        self._vsem      = asyncio.Semaphore(2)
        self._html      = open(os.path.join(os.path.dirname(__file__), "web_panel.html"), encoding="utf-8").read()
        self._tc: dict[str, tuple[str, str]] = {}
        self._rebuild()
        logger.info(f"[APIHub] {len(self.store.pools)}个池，{len(self._tc)}个触发词")
        try:
            asyncio.get_event_loop().create_task(self._start_web())
        except Exception as e:
            logger.warning(f"[APIHub] Web面板启动失败: {e}")

    # ── 触发词缓存 O(1) ────────────────────────────────────

    def _rebuild(self):
        c = {}
        for pn, pool in self.store.pools.items():
            if not pool.get("enabled", True): continue
            for an, api in pool.get("apis", {}).items():
                if not api.get("enabled", True): continue
                cmd = (api.get("trigger_cmd") or an).strip()
                if cmd: c[cmd] = (pn, an)
                if an != cmd: c.setdefault(an, (pn, an))
        self._tc = c

    def _find(self, cmd: str):
        k = self._tc.get(cmd)
        if k:
            pn, an = k
            info = self.store.pools.get(pn, {}).get("apis", {}).get(an)
            if info: return pn, an, info
        return None, None, None

    # ── 命令入口 ───────────────────────────────────────────

    @filter.command_group("api")
    async def _grp(self): pass

    @filter.command("api")
    async def cmd_api(self, event: AstrMessageEvent):
        """/api 列表|随机|状态|<触发词> [参数] [次数]"""
        parts = event.message_obj.message_str.strip().split(None, 3)
        if len(parts) < 2:
            yield event.plain_result(self._help()); return
        sub  = parts[1].strip()
        rest = parts[2].strip() if len(parts) > 2 else ""

        if sub == "列表":
            yield event.plain_result(self._list(rest or None)); return
        if sub == "随机":
            async for m in self._rand(event, rest): yield m; return
        if sub == "状态":
            yield event.plain_result(self._status()); return

        arg, cnt = self._parse_cnt(rest)
        if cnt is None:
            yield event.plain_result("❗ 次数范围 1~3"); return
        pn, an, info = self._find(sub)
        if info is None:
            yield event.plain_result(f"❗ 未找到「{sub}」，发送 /api 列表 查看所有命令"); return
        async for m in self._dispatch(event, pn, an, info, arg, cnt): yield m

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def cmd_trigger(self, event: AstrMessageEvent):
        """监听所有消息，匹配触发词后拦截处理"""
        raw = event.message_obj.message_str.strip()
        m = _RE_CMD.match(raw)
        if not m: return
        cmd  = m.group(1).strip()
        rest = m.group(2).strip()
        if cmd == "api": return

        pn, an, info = self._find(cmd)
        if info is None: return

        event.stop_event()
        arg, cnt = self._parse_cnt(rest)
        if cnt is None:
            yield event.plain_result("❗ 次数范围 1~3"); return
        async for msg in self._dispatch(event, pn, an, info, arg, cnt): yield msg

    # ── 工具 ───────────────────────────────────────────────

    def _parse_cnt(self, rest: str) -> tuple:
        parts = rest.strip().rsplit(None, 1)
        cnt, arg = 1, rest.strip()
        if parts and parts[-1].isdigit():
            n = int(parts[-1])
            if n < 1 or n > 3: return "", None
            cnt = n
            arg = parts[0] if len(parts) > 1 else ""
        return arg.strip(), cnt

    def _build_params(self, info: dict, extra: str) -> tuple[dict, bool, str]:
        ak = info.get("arg_key")
        ra = [r for r in (info.get("rand_args") or []) if r]
        p  = {**(info.get("extra_params") or {})}
        if ak and extra:       p[ak] = extra
        elif ak and ra:        p[ak] = random.choice(ra)
        elif ak and not extra and not ra:
            hint = info.get("arg_hint") or ak
            cmd  = info.get("trigger_cmd") or ""
            return p, False, f"❗ 需要参数：{hint}\n例：/{cmd} {hint}"
        return p, True, ""

    async def _dispatch(self, event, pn, an, info, arg, cnt):
        if cnt == 1:
            async for m in self._call(event, pn, an, info, arg): yield m
        else:
            results = await asyncio.gather(
                *[self._collect(pn, an, info, arg) for _ in range(cnt)],
                return_exceptions=True
            )
            for comps in results:
                if isinstance(comps, list):
                    yield event.chain_result(comps)

    async def _collect(self, pn, an, info, arg) -> list:
        try:
            pool = self.store.pools.get(pn, {})
            if not pool.get("enabled", True) or not info.get("enabled", True):
                return [Comp.Plain(f"❌「{an}」已禁用")]
            p, ok, err = self._build_params(info, arg)
            if not ok: return [Comp.Plain(err)]
            rt, data = await fetch(info["url"], params=p or None, headers=info.get("headers") or {})
            return await self._build(rt, data, info)
        except Exception as e:
            return [Comp.Plain(f"❌ {an}：{e}")]

    async def _call(self, event, pn, an, info, arg):
        pool = self.store.pools.get(pn, {})
        if not pool.get("enabled", True) or not info.get("enabled", True):
            yield event.plain_result(f"❌「{an}」或其池已禁用"); return
        if info.get("nsfw") and not self.store.nsfw_enabled:
            yield event.plain_result(f"🔒「{an}」为 NSFW，请在 Web 面板开启"); return
        p, ok, err = self._build_params(info, arg)
        if not ok:
            yield event.plain_result(err); return
        try:
            rt, data = await fetch(info["url"], params=p or None, headers=info.get("headers") or {})
            yield event.chain_result(await self._build(rt, data, info))
        except aiohttp.ClientConnectorError:
            yield event.plain_result(f"❌「{an}」连接失败，检查 URL 或网络")
        except aiohttp.ServerTimeoutError:
            yield event.plain_result(f"❌「{an}」请求超时")
        except Exception as e:
            yield event.plain_result(f"❌ 错误：{e}")

    async def _rand(self, event, pool_filter=""):
        active = self.store.get_all_active_apis()
        if pool_filter:
            active = {k: v for k, v in active.items() if v.get("pool") == pool_filter}
        cands = [n for n, i in active.items()
                 if not i.get("arg_key") and (self.store.nsfw_enabled or not i.get("nsfw"))]
        if not cands:
            yield event.plain_result("❗ 没有可随机调用的 API"); return
        name = random.choice(cands)
        pn, info = self.store.find_api(name)
        if info:
            async for m in self._call(event, pn, name, info, ""):
                yield m

    # ── 响应构建 ────────────────────────────────────────────

    async def _build(self, rt, data, info) -> list:
        atype = info.get("type", "image")
        jp    = info.get("json_path")
        tpl   = (info.get("output_template") or "").replace("\\n", "\n")

        if rt == "image":
            return [Comp.Image.fromBytes(data)]

        if rt == "video":
            return await self._save_video(data)

        if atype == "audio":
            aurl = self._extract_url(data, jp, ("url","audio_url","audioUrl","src","mp3","voice"))
            if isinstance(data, str) and data.strip().startswith("http"):
                aurl = data.strip()
            return await self._dl_audio(aurl) if aurl else [Comp.Plain(f"⚠️ 无法解析音频地址\n{str(data)[:200]}")]

        if atype == "video":
            vurl = self._extract_url(data, jp, ("url","video_url","videoUrl","play_url","playUrl","src"))
            if isinstance(data, str) and data.strip().startswith("http"):
                vurl = data.strip()
            return await self._dl_video(vurl) if vurl else [Comp.Plain(f"⚠️ 无法解析视频地址\n{str(data)[:200]}")]

        if atype in ("image", "random"):
            url = self._extract_url(data, jp, ("url","data","imgurl","pic","image","src"))
            if isinstance(data, str) and data.strip().startswith("http"):
                url = data.strip()
            return [Comp.Image.fromURL(url)] if url else [Comp.Plain(f"⚠️ 无法解析图片\n{str(data)[:200]}")]

        # text / json
        if tpl and isinstance(data, (dict, list)):
            return [Comp.Plain(_render(tpl, data))]
        if isinstance(data, dict) and jp:
            v = resolve_path(data, jp)
            if isinstance(v, str) and v.startswith("http"):
                return [Comp.Image.fromURL(v)]
            return [Comp.Plain(str(v) if v is not None else f"⚠️ 路径「{jp}」无值")]
        if isinstance(data, dict):
            return [Comp.Plain(json.dumps(data, ensure_ascii=False, indent=2)[:800])]
        return [Comp.Plain(str(data)[:800])]

    def _extract_url(self, data, jp, keys):
        if isinstance(data, dict):
            if jp:
                v = resolve_path(data, jp)
                if isinstance(v, str) and v.startswith("http"): return v
            for k in keys:
                v = data.get(k)
                if not v and isinstance(data.get("data"), dict):
                    v = data["data"].get(k)
                if isinstance(v, str) and v.startswith("http"): return v
        elif isinstance(data, str) and data.strip().startswith("http"):
            return data.strip()
        return None

    async def _save_video(self, data: bytes) -> list:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(data); tmp.close()
        asyncio.get_event_loop().create_task(self._del(tmp.name))
        return [Comp.Video(file=tmp.name)]

    async def _dl_audio(self, url: str) -> list:
        """下载音频到临时文件，30秒后自动删除"""
        try:
            s = await _session()
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=30),
                             allow_redirects=True) as r:
                if r.status != 200: raise Exception(f"HTTP {r.status}")
                data = await r.read()
            if len(data) < 512: raise Exception("音频内容异常")
            # 根据 Content-Type 判断后缀
            suffix = ".mp3"
            ct = r.content_type or ""
            if "ogg" in ct or "opus" in ct: suffix = ".ogg"
            elif "wav" in ct: suffix = ".wav"
            elif "aac" in ct: suffix = ".aac"
            tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
            tmp.write(data); tmp.close()
            asyncio.get_event_loop().create_task(self._del(tmp.name))
            logger.info(f"[APIHub] 音频下载完成 {len(data)//1024}KB")
            return [Comp.Record(file=tmp.name)]
        except Exception as e:
            logger.warning(f"[APIHub] 音频下载失败: {e}")
            return [Comp.Plain(f"❌ 音频下载失败：{e}")]

    async def _dl_video(self, url: str) -> list:
        async with self._vsem:
            try:
                s = await _session()
                async with s.get(url, headers={"Referer": url, "Accept": "*/*"},
                                  timeout=aiohttp.ClientTimeout(total=60),
                                  allow_redirects=True) as r:
                    if r.status != 200: raise Exception(f"HTTP {r.status}")
                    data = await r.read()
                if len(data) < 1024: raise Exception("视频内容异常")
                tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
                tmp.write(data); tmp.close()
                logger.info(f"[APIHub] 视频下载完成 {len(data)//1024}KB")
                asyncio.get_event_loop().create_task(self._del(tmp.name))
                return [Comp.Video(file=tmp.name)]
            except Exception as e:
                logger.warning(f"[APIHub] 视频下载失败: {e}")
                return [Comp.Plain(f"❌ 视频下载失败：{e}\n链接：{url}")]

    @staticmethod
    async def _del(path: str, delay: int = 30):
        await asyncio.sleep(delay)
        try: os.unlink(path)
        except: pass

    # ── 文字输出 ────────────────────────────────────────────

    def _list(self, pool_filter=None) -> str:
        lines = ["⚡ API HUB 命令列表\n"]
        for pn, pool in self.store.pools.items():
            if pool_filter and pn != pool_filter: continue
            enabled = pool.get("enabled", True)
            status  = "✅ 启用" if enabled else "❌ 禁用"
            lines.append(f"📦 {pn}  {status}  共 {len(pool.get('apis', {}))} 个接口")
            lines.append("─" * 28)
            for an, api in pool.get("apis", {}).items():
                if not enabled:               tag = "❌"
                elif not api.get("enabled"):  tag = "⛔"
                elif api.get("nsfw") and not self.store.nsfw_enabled: tag = "🔒"
                else:                         tag = "✅"
                cmd  = api.get("trigger_cmd") or an
                ra   = api.get("rand_args") or []
                if api.get("arg_key"):
                    hint = f"  随机{len(ra)}项" if ra else f"  参数:{api.get('arg_hint') or api.get('arg_key')}"
                else:
                    hint = ""
                desc = f"  {api.get('desc','')}" if api.get("desc") else ""
                lines.append(f"  {tag} /{cmd}{hint}{desc}")
            lines.append("")
        lines.append("💡 用法：/<命令> [参数] [次数1-3]")
        return "\n".join(lines)

    def _status(self) -> str:
        pools = self.store.pools
        lines = [
            "📊 API HUB 状态",
            f"  池数量：{len(pools)}    触发词：{len(self._tc)}",
            f"  NSFW：{'✅ 开启' if self.store.nsfw_enabled else '❌ 关闭'}",
            f"  Web 面板：http://服务器IP:{self.web_port}", ""
        ]
        for pn, p in pools.items():
            s = "✅" if p.get("enabled", True) else "❌"
            lines.append(f"  {s} {pn}（{len(p.get('apis', {}))} 个接口）")
        return "\n".join(lines)

    def _help(self) -> str:
        return (
            "⚡ API HUB\n"
            "  /api 列表 [池名]     查看所有命令\n"
            "  /api 随机 [池名]     随机调用\n"
            "  /api 状态            运行状态\n"
            "  /<命令> [参数] [次数] 调用接口\n"
            f"  Web 面板：http://服务器IP:{self.web_port}"
        )

    # ── Web 服务 ────────────────────────────────────────────

    async def _start_web(self):
        app = web.Application()
        R   = app.router
        R.add_get("/",                  self._h_index)
        R.add_get("/api/data",          self._h_data)
        R.add_post("/api/nsfw",         self._h_nsfw)
        R.add_post("/api/pool/add",     self._h_pool_add)
        R.add_post("/api/pool/update",  self._h_pool_update)
        R.add_post("/api/pool/delete",  self._h_pool_delete)
        R.add_post("/api/pool/toggle",  self._h_pool_toggle)
        R.add_post("/api/item/add",     self._h_item_add)
        R.add_post("/api/item/update",  self._h_item_update)
        R.add_post("/api/item/delete",  self._h_item_delete)
        R.add_post("/api/item/toggle",  self._h_item_toggle)
        R.add_post("/api/item/test",    self._h_item_test)
        R.add_post("/api/batch/import", self._h_batch_import)
        R.add_get("/api/batch/export",  self._h_batch_export)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        await web.TCPSite(self._runner, "0.0.0.0", self.web_port).start()
        logger.info(f"[APIHub] Web 面板：http://0.0.0.0:{self.web_port}")

    def _ok(self, **kw): return web.json_response({"ok": True, **kw})
    def _err(self, msg, s=400): return web.json_response({"ok": False, "msg": msg}, status=s)

    async def _h_index(self, _):
        return web.Response(text=self._html, content_type="text/html")

    async def _h_data(self, _):
        return web.json_response({"pools": self.store.to_dict()["pools"], "nsfw_enabled": self.store.nsfw_enabled})

    async def _h_nsfw(self, req):
        b = await req.json()
        self.store.nsfw_enabled = bool(b.get("enabled", False))
        return self._ok(nsfw_enabled=self.store.nsfw_enabled)

    async def _h_pool_add(self, req):
        b = await req.json()
        name = (b.get("name") or "").strip()
        if not name: return self._err("池名不能为空")
        if not self.store.add_pool(name, b.get("desc", "")): return self._err(f"「{name}」已存在")
        self._rebuild(); return self._ok(msg=f"已创建「{name}」")

    async def _h_pool_update(self, req):
        b = await req.json()
        ok = self.store.update_pool(b.get("name",""), (b.get("new_name") or b.get("name","")).strip(), b.get("desc",""))
        if ok: self._rebuild()
        return self._ok() if ok else self._err("更新失败")

    async def _h_pool_delete(self, req):
        b = await req.json()
        ok = self.store.delete_pool(b.get("name",""))
        if ok: self._rebuild()
        return self._ok(msg="已删除") if ok else self._err("池不存在")

    async def _h_pool_toggle(self, req):
        b = await req.json()
        r = self.store.toggle_pool(b.get("name",""))
        if r is not None: self._rebuild()
        return self._ok(enabled=r) if r is not None else self._err("池不存在")

    async def _h_item_add(self, req):
        b = await req.json()
        pool = b.get("pool",""); name = (b.get("name") or "").strip()
        if not pool or not name: return self._err("池名和接口名不能为空")
        if not (b.get("url") or "").strip(): return self._err("URL不能为空")
        self.store.add_api(pool, name, b); self._rebuild()
        return self._ok(msg=f"已添加「{name}」")

    async def _h_item_update(self, req):
        b = await req.json()
        ok = self.store.update_api(b.get("pool",""), b.get("old_name",""),
                                   (b.get("name") or b.get("old_name","")).strip(), b)
        if ok: self._rebuild()
        return self._ok() if ok else self._err("接口不存在")

    async def _h_item_delete(self, req):
        b = await req.json()
        ok = self.store.delete_api(b.get("pool",""), b.get("name",""))
        if ok: self._rebuild()
        return self._ok(msg="已删除") if ok else self._err("接口不存在")

    async def _h_item_toggle(self, req):
        b = await req.json()
        r = self.store.toggle_api(b.get("pool",""), b.get("name",""))
        if r is not None: self._rebuild()
        return self._ok(enabled=r) if r is not None else self._err("接口不存在")

    async def _h_item_test(self, req):
        b       = await req.json()
        url     = (b.get("url") or "").strip()
        if not url: return self._err("URL不能为空")
        jp      = b.get("json_path") or None
        atype   = b.get("type", "image")
        ak      = b.get("arg_key") or None
        av      = b.get("arg_val") or None
        headers = b.get("headers") or {}
        params  = {**(b.get("extra_params") or {})}
        if ak and av: params[ak] = av
        try:
            t0 = time.time()
            rt, data = await fetch(url, params=params or None, headers=headers)
            ms = round((time.time()-t0)*1000)
            rj = data if isinstance(data, (dict, list)) else None
            if rt == "image":
                return self._ok(result_type="image", data=base64.b64encode(data).decode(), elapsed=ms)
            if isinstance(data, dict) and jp:
                v = resolve_path(data, jp)
                if isinstance(v, str) and v.startswith("http"):
                    return self._ok(result_type="image_url", data=v, raw=rj, elapsed=ms)
                return self._ok(result_type="text", data=str(v), raw=rj, elapsed=ms)
            if isinstance(data, dict):
                return self._ok(result_type="json", data=data, elapsed=ms)
            if isinstance(data, str) and data.strip().startswith("http") and atype in ("image","random"):
                return self._ok(result_type="image_url", data=data.strip(), raw=None, elapsed=ms)
            return self._ok(result_type="text", data=str(data)[:1000], raw=rj, elapsed=ms)
        except Exception as e:
            return self._err(f"请求失败：{e}")

    async def _h_batch_import(self, req):
        b = await req.json()
        pool = b.get("pool","")
        if not pool: return self._err("请指定池名")
        cnt = self.store.batch_import_apis(pool, b.get("apis", []))
        self._rebuild(); return self._ok(msg=f"已导入 {cnt} 个", count=cnt)

    async def _h_batch_export(self, req):
        pool = req.rel_url.query.get("pool","")
        return web.json_response(self.store.export_pool(pool) if pool else [])
