<div align="center">

# ⚡ API HUB

**AstrBot API 池管理插件**

[![版本](https://img.shields.io/badge/版本-1.0.0-blue)](https://github.com/s-3-s/astrbot_plugin_apihub)
[![作者](https://img.shields.io/badge/作者-s--3--s-green)](https://github.com/s-3-s)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

通过 Web 面板可视化管理 API 池，支持触发词动态注册，一条命令调用任意接口。

</div>

---

## ✨ 功能特性

- 🗂️ **API 池管理** — 分组管理接口，支持启用/禁用整个池
- ⚡ **触发词动态注册** — 每个接口设置独立命令词，O(1) 极速匹配
- 🌐 **Web 可视化面板** — 浏览器直接管理，无需改代码
- 🎲 **随机参数列表** — 自动从列表随机选值填入参数
- 📝 **自定义输出模板** — 灵活提取 JSON 字段，支持数组遍历
- 🔢 **多次调用** — 一条命令并发调用多次，最多3次
- 🔞 **NSFW 开关** — 全局控制敏感内容
- 🖼️ **多媒体支持** — 图片、视频、音频、文字、JSON 全支持

---

## 📦 安装

### 方式一：通过 AstrBot WebUI 上传 ZIP

在 AstrBot WebUI → 插件管理 → 上传插件，上传 ZIP 包即可。

### 方式二：Git 克隆

```bash
cd /AstrBot/data/plugins
git clone https://github.com/s-3-s/astrbot_plugin_apihub
```

重载插件后生效。

---

## 🖥️ Web 管理面板

插件启动后，访问：

```
http://服务器IP:6789
```

如使用内网穿透，访问对应外网地址。

> ⚠️ **Docker 部署**需确保 6789 端口已映射：
> ```bash
> docker run -d --name astrbot \
>   -p 6185:6185 -p 6789:6789 \
>   -v /root/astrbot/data:/AstrBot/data \
>   soulter/astrbot:latest
> ```

---

## 💬 Bot 命令

| 命令 | 说明 |
|------|------|
| `/api 列表` | 查看全部可用命令 |
| `/api 列表 <池名>` | 查看指定池的命令 |
| `/api 随机` | 随机调用一个接口 |
| `/api 随机 <池名>` | 从指定池随机调用 |
| `/api 状态` | 查看运行状态 |
| `/<触发词>` | 直接调用接口 |
| `/<触发词> <参数>` | 带参数调用，如 `/天气 北京` |
| `/<触发词> <次数>` | 调用多次，如 `/壁纸 3` |
| `/<触发词> <参数> <次数>` | 带参数多次调用，如 `/天气 北京 2` |

---

## 🎛️ 面板功能说明

### 接口配置字段

| 字段 | 说明 |
|------|------|
| API 名称 | 接口的唯一标识名 |
| 触发命令 | 用户发送的命令词（留空则使用 API 名称） |
| 请求 URL | 接口地址，参数通过下方字段配置，不要直接拼在 URL 里 |
| 返回类型 | 见下方类型说明 |
| JSON 取值路径 | 从 JSON 中提取单个值，如 `data.url` |
| 参数 Key | 用户传入参数的字段名，如 `city` |
| 参数提示 | 提示用户填写什么参数，如 `城市名，如：北京` |
| 随机参数列表 | 逗号分隔的值列表，每次调用随机选一个填入参数 Key |
| 输出模板 | 自定义输出格式，支持多行和数组遍历（见下方说明） |
| 自定义请求头 | JSON 格式，如 `{"Authorization":"Bearer xxx"}` |
| 固定附加参数 | JSON 格式，每次请求都会带上，如 `{"format":"json"}` |
| NSFW | 标记为敏感内容，需在面板开启 NSFW 开关才可使用 |

### 支持的返回类型

| 类型 | 说明 |
|------|------|
| `image` | 图片，支持字节流和 URL |
| `video` | 视频，插件自动下载后发送，30秒后删除临时文件 |
| `audio` | 音频，自动下载，支持 mp3/ogg/wav/aac |
| `json` | JSON 数据，配合输出模板使用 |
| `text` | 纯文本，配合输出模板使用 |
| `random` | 随机图片 |

---

## 📝 输出模板语法

输出模板用于将接口返回的 JSON 格式化为可读文字，支持以下语法：

### 1. 取单个值

```
{路径}
```

示例：

```
今日天气：{data.condition.fcondition}
温度：{data.condition.ftemp}°C
湿度：{data.condition.fhumidity}%
```

路径用 `.` 分隔多层嵌套，如 `data.city_list.condition.ftemp`。

---

### 2. 取数组指定下标

```
{data[0].字段}
```

示例（取最新一条）：

```
最新状态：{data[0].context}
时间：{data[0].time}
```

---

### 3. 块遍历（推荐）

对数组每一条记录输出完整一块，块内所有字段同属一条记录：

```
{% for 列表路径[*] %}
每条记录的模板内容
{% end %}
```

- `[*]` — 正序（旧→新）
- `[~]` — 倒序（新→旧，最新在最上面）
- 块内用 `{字段名}` 直接引用当前条目的字段

**示例：快递物流**

```
📦 快递物流信息
━━━━━━━━━━━━━━━━
{% for data[~] %}
🕐 {time}  📍 {location}
📋 {context}
─────────────
{% end %}
```

输出效果：

```
📦 快递物流信息
━━━━━━━━━━━━━━━━
🕐 2025-11-21 09:37:54  📍 北京***
📋 您的快件已送达至【***】
─────────────
🕐 2025-11-21 08:04:31  📍 北京***
📋 您的快件正在派送中
─────────────
...
```

---

### 4. 混合使用

可以在模板中同时使用普通取值和块遍历：

```
🚚 快递查询结果（共{data.total}条）
{% for data.list[~] %}
【{time}】{context}
{% end %}
```

---

## 📥 批量导入格式

JSON 数组，每项字段：

```json
[
  {
    "name": "随机壁纸",
    "url": "https://api.vvhan.com/api/wallpaper/acg",
    "type": "image",
    "trigger_cmd": "壁纸",
    "desc": "随机ACG壁纸",
    "json_path": null,
    "arg_key": null,
    "arg_hint": null,
    "rand_args": [],
    "output_template": "",
    "headers": {},
    "extra_params": {},
    "nsfw": false
  }
]
```

---

## 🗂️ 文件结构

```
astrbot_plugin_apihub/
├── main.py            # 插件主逻辑
├── pool_store.py      # 数据持久化
├── api_fetcher.py     # HTTP 请求封装
├── web_panel.html     # Web 管理面板
├── _conf_schema.json  # AstrBot 配置项
├── metadata.yaml      # 插件元信息
├── requirements.txt   # 依赖
└── data/
    └── api_pools.json # 运行时生成的池数据
```

---

## ⚙️ 插件配置

在 AstrBot WebUI → 插件管理 → API HUB → 配置：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| Web 管理面板端口 | `6789` | 与内网穿透映射的内网端口一致 |

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

<div align="center">
Made with ❤️ by <a href="https://github.com/s-3-s">s-3-s</a>
</div>
