"""
pool_store.py —— API 池持久化
每个 API 新增 trigger_cmd 字段：用户用这个命令触发调用
数据结构：
{
  "pools": {
    "vvhan": {
      "desc": "韩小韩API",
      "enabled": true,
      "apis": {
        "随机壁纸": {
          "url": "...",
          "type": "image",
          "desc": "...",
          "trigger_cmd": "壁纸",   ← 用户发 /壁纸 就触发
          "json_path": null,
          "arg_key": null,
          "arg_hint": null,
          "headers": {},           ← 自定义请求头
          "extra_params": {},      ← 固定附加参数
          "nsfw": false,
          "enabled": true
        }
      }
    }
  },
  "nsfw_enabled": false
}
"""
from __future__ import annotations
import json, os

DEFAULT_POOLS: dict = {
    "vvhan": {
        "desc": "韩小韩 API（国内稳定）",
        "enabled": True,
        "apis": {
            "看看腿":     {"url":"https://api.vvhan.com/api/girl/tui",         "type":"image","desc":"随机美腿","trigger_cmd":"看看腿",    "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":True, "enabled":True},
            "看看腹肌":   {"url":"https://api.vvhan.com/api/girl/fuji",        "type":"image","desc":"随机腹肌","trigger_cmd":"看看腹肌",  "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":True, "enabled":True},
            "随机壁纸":   {"url":"https://api.vvhan.com/api/wallpaper/acg",    "type":"image","desc":"随机ACG壁纸","trigger_cmd":"随机壁纸","json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "随机风景":   {"url":"https://api.vvhan.com/api/wallpaper/views",  "type":"image","desc":"随机风景","trigger_cmd":"随机风景",  "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "摸鱼日历":   {"url":"https://api.vvhan.com/api/moyu",             "type":"image","desc":"摸鱼日历","trigger_cmd":"摸鱼",      "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "60s读世界":  {"url":"https://api.vvhan.com/api/60s",              "type":"image","desc":"每日60s","trigger_cmd":"60s",       "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "随机二次元": {"url":"https://api.vvhan.com/api/acgimg",           "type":"image","desc":"随机二次元","trigger_cmd":"二次元",  "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "随机表情包": {"url":"https://api.vvhan.com/api/meme",             "type":"image","desc":"随机表情包","trigger_cmd":"表情包",  "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "每日一言":   {"url":"https://api.vvhan.com/api/ian/rand",         "type":"json", "desc":"每日一言","trigger_cmd":"一言",      "json_path":"content","arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "彩虹屁":     {"url":"https://api.vvhan.com/api/text/caihongpi",   "type":"json", "desc":"彩虹屁","trigger_cmd":"彩虹屁",      "json_path":"content","arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "土味情话":   {"url":"https://api.vvhan.com/api/text/love",        "type":"json", "desc":"土味情话","trigger_cmd":"情话",      "json_path":"content","arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "舔狗日记":   {"url":"https://api.vvhan.com/api/text/dog",         "type":"json", "desc":"舔狗日记","trigger_cmd":"舔狗",      "json_path":"content","arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "天气":       {"url":"https://api.vvhan.com/api/weather",          "type":"json", "desc":"天气查询","trigger_cmd":"天气",      "json_path":None,"arg_key":"city","arg_hint":"城市名，如：北京","headers":{},"extra_params":{},"nsfw":False,"enabled":True},
        }
    },
    "樱花随机图": {
        "desc": "樱花解析随机图",
        "enabled": True,
        "apis": {
            "樱花二次元": {"url":"https://www.dmoe.cc/random.php","type":"image","desc":"随机二次元","trigger_cmd":"樱花","json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
        }
    },
}

# 预设模板（供 Web 面板「从模板导入」使用）
PRESET_TEMPLATES: dict[str, dict] = {
    "vvhan（韩小韩API）": DEFAULT_POOLS["vvhan"],
    "樱花随机图": DEFAULT_POOLS["樱花随机图"],
    "搏天API": {
        "desc": "搏天 API 合集",
        "enabled": True,
        "apis": {
            "搏天壁纸":   {"url":"https://api.btstu.cn/sjbz/?lx=dongman",  "type":"image","desc":"随机动漫壁纸","trigger_cmd":"搏天壁纸", "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
            "搏天美女":   {"url":"https://api.btstu.cn/sjbz/?lx=meizi",    "type":"image","desc":"随机美女壁纸","trigger_cmd":"搏天美女", "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":True, "enabled":True},
            "随机头像":   {"url":"https://api.btstu.cn/sjtx/api.php",      "type":"image","desc":"随机头像",  "trigger_cmd":"随机头像",  "json_path":None,"arg_key":None,"arg_hint":None,"headers":{},"extra_params":{},"nsfw":False,"enabled":True},
        }
    },
}


class PoolStore:
    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, "api_pools.json")
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}
        if not self._data.get("pools"):
            self._data = {"pools": {}, "nsfw_enabled": False}
            self._save()


    def _save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @property
    def nsfw_enabled(self) -> bool:
        return bool(self._data.get("nsfw_enabled", False))

    @nsfw_enabled.setter
    def nsfw_enabled(self, v: bool):
        self._data["nsfw_enabled"] = v
        self._save()

    @property
    def pools(self) -> dict:
        return self._data.get("pools", {})

    def get_trigger_map(self) -> dict[str, tuple[str, str]]:
        """返回 {trigger_cmd: (pool_name, api_name)}，用于命令匹配"""
        result = {}
        for pool_name, pool in self.pools.items():
            if not pool.get("enabled", True):
                continue
            for api_name, api in pool.get("apis", {}).items():
                if not api.get("enabled", True):
                    continue
                cmd = (api.get("trigger_cmd") or api_name).strip()
                if cmd:
                    result[cmd] = (pool_name, api_name)
        return result

    def get_all_active_apis(self) -> dict[str, dict]:
        result = {}
        for pool_name, pool in self.pools.items():
            if not pool.get("enabled", True):
                continue
            for api_name, api in pool.get("apis", {}).items():
                if api.get("enabled", True):
                    result[api_name] = {**api, "pool": pool_name}
        return result

    def find_api(self, api_name: str) -> tuple[str | None, dict | None]:
        for pool_name, pool in self.pools.items():
            if api_name in pool.get("apis", {}):
                return pool_name, pool["apis"][api_name]
        return None, None

    def find_by_trigger(self, cmd: str) -> tuple[str | None, str | None, dict | None]:
        """按触发命令查找，返回 (pool_name, api_name, api_info)"""
        for pool_name, pool in self.pools.items():
            if not pool.get("enabled", True):
                continue
            for api_name, api in pool.get("apis", {}).items():
                if not api.get("enabled", True):
                    continue
                trigger = (api.get("trigger_cmd") or api_name).strip()
                if trigger == cmd:
                    return pool_name, api_name, api
        return None, None, None

    # ── 池操作 ────────────────────────────────────────────

    def add_pool(self, name: str, desc: str = "") -> bool:
        if name in self.pools:
            return False
        self._data["pools"][name] = {"desc": desc, "enabled": True, "apis": {}}
        self._save()
        return True

    def delete_pool(self, name: str) -> bool:
        if name not in self.pools:
            return False
        del self._data["pools"][name]
        self._save()
        return True

    def toggle_pool(self, name: str):
        if name not in self.pools:
            return None
        cur = self.pools[name].get("enabled", True)
        self._data["pools"][name]["enabled"] = not cur
        self._save()
        return not cur

    def update_pool(self, name: str, new_name: str, desc: str) -> bool:
        pools = self._data["pools"]
        if name not in pools:
            return False
        data = pools.pop(name)
        data["desc"] = desc
        # 保持插入顺序：重建 dict
        new_pools = {}
        for k, v in list(pools.items()):
            new_pools[k] = v
        new_pools = {new_name: data, **{k: v for k, v in pools.items()}}
        self._data["pools"] = new_pools
        self._save()
        return True


    # ── API 操作 ──────────────────────────────────────────

    def _normalize_api(self, info: dict) -> dict:
        # rand_args 可以是列表或逗号分隔字符串
        rand_args = info.get("rand_args") or []
        if isinstance(rand_args, str):
            rand_args = [s.strip() for s in rand_args.split(",") if s.strip()]
        return {
            "url":          (info.get("url") or "").strip(),
            "type":         info.get("type", "image"),
            "desc":         info.get("desc", ""),
            "trigger_cmd":  (info.get("trigger_cmd") or "").strip(),
            "json_path":    info.get("json_path") or None,
            "arg_key":      info.get("arg_key") or None,
            "arg_hint":     info.get("arg_hint") or None,
            "rand_args":       rand_args,
            "output_template": info.get("output_template") or "",
            "headers":         info.get("headers") or {},
            "extra_params":    info.get("extra_params") or {},
            "nsfw":         bool(info.get("nsfw", False)),
            "enabled":      bool(info.get("enabled", True)),
        }

    def add_api(self, pool_name: str, api_name: str, info: dict) -> bool:
        if pool_name not in self.pools:
            return False
        self._data["pools"][pool_name]["apis"][api_name] = self._normalize_api(info)
        self._save()
        return True

    def update_api(self, pool_name: str, old_name: str, new_name: str, info: dict) -> bool:
        apis = self._data["pools"].get(pool_name, {}).get("apis", {})
        if old_name not in apis:
            return False
        old_info = apis.pop(old_name)
        normalized = self._normalize_api(info)
        normalized["enabled"] = old_info.get("enabled", True)
        apis[new_name] = normalized
        self._save()
        return True

    def delete_api(self, pool_name: str, api_name: str) -> bool:
        apis = self._data["pools"].get(pool_name, {}).get("apis", {})
        if api_name not in apis:
            return False
        del apis[api_name]
        self._save()
        return True

    def toggle_api(self, pool_name: str, api_name: str):
        apis = self._data["pools"].get(pool_name, {}).get("apis", {})
        if api_name not in apis:
            return None
        cur = apis[api_name].get("enabled", True)
        apis[api_name]["enabled"] = not cur
        self._save()
        return not cur

    def batch_import_apis(self, pool_name: str, api_list: list) -> int:
        if pool_name not in self.pools:
            return 0
        count = 0
        for item in api_list:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            url  = (item.get("url")  or "").strip()
            if name and url:
                self.add_api(pool_name, name, item)
                count += 1
        return count

    def export_pool(self, pool_name: str) -> list:
        apis = self.pools.get(pool_name, {}).get("apis", {})
        return [{"name": k, **v} for k, v in apis.items()]

    def to_dict(self) -> dict:
        return self._data

