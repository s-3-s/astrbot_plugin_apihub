<div align="center">

# ⚡ API HUB

**AstrBot API 池管理插件**

`s-3-s/astrbot_plugin_apihub`

</div>

---

## 简介

通过 Web 面板管理 API 池，每个接口可设置触发命令词，用户直接发送命令即可调用。支持图片、文字、JSON、视频、音频等多种返回类型，支持随机参数列表、自定义输出模板。

---

## 安装

```bash
cd /AstrBot/data/plugins
git clone https://github.com/s-3-s/astrbot_plugin_apihub
```

在 AstrBot WebUI 重载插件。

---

## Web 面板

```
http://服务器IP:6789
```

如使用内网穿透，访问对应的外网地址。

> ⚠️ Docker 部署需要确保 6789 端口已映射或做了内网穿透。

---

## Bot 命令

| 命令 | 说明 |
|------|------|
| `/api 列表` | 查看全部命令 |
| `/api 列表 <池名>` | 查看指定池 |
| `/api 随机` | 随机调用一个接口 |
| `/api 状态` | 查看运行状态 |
| `/<触发词>` | 调用接口 |
| `/<触发词> 2` | 调用2次（最多3次） |
| `/<触发词> <参数>` | 带参数调用 |

---

## Web 面板功能

| 功能 | 说明 |
|------|------|
| 池管理 | 新建、编辑、删除、启用/禁用 |
| 接口管理 | 添加、编辑、删除、启用/禁用、多选批量操作 |
| 触发词 | 每个接口单独设置命令词 |
| 随机参数列表 | 逗号分隔，每次调用随机选一个 |
| 输出模板 | 用 `{路径}` 格式提取 JSON 字段，支持多行 |
| 调试台 | 在面板直接测试接口，预览结果 |
| 音频支持 | 自动下载音频文件，30秒后清理临时文件 |
| 批量导入/导出 | JSON 数组格式 |
| NSFW 开关 | 右上角全局控制 |

---

## 输出模板示例

对于天气接口返回的 JSON，模板可以这样写：

```
🌤 天气：{data.city_list.condition.fcondition}
🌡 温度：{data.city_list.condition.ftemp}°C
💧 湿度：{data.city_list.condition.fhumidity}%
💨 风向：{data.city_list.condition.fwind_dir}
```

---

## Docker 网络说明

Docker 容器内的端口与宿主机隔离，需要映射或内网穿透才能访问面板：

```bash
docker run -d \
  --name astrbot \
  -p 6185:6185 \
  -p 6789:6789 \
  -v /root/astrbot/data:/AstrBot/data \
  soulter/astrbot:latest
```

---

## 支持的返回类型

| 类型 | 说明 |
|------|------|
| `image` | 图片，支持 URL 和字节流 |
| `video` | 视频，自动下载后发送 |
| `audio` | 音频，自动下载后发送，支持 mp3/ogg/wav/aac |
| `json` | JSON 数据，支持 `{路径}` 输出模板 |
| `text` | 纯文本，支持输出模板 |
| `random` | 随机图片 |

---

## 文件结构

```
astrbot_plugin_apihub/
├── main.py           # 插件主逻辑
├── pool_store.py     # 数据持久化
├── api_fetcher.py    # HTTP 请求
├── web_panel.html    # Web 管理面板
├── _conf_schema.json # 配置项
├── metadata.yaml
└── data/
    └── api_pools.json
```
