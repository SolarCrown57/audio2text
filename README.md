# Audio2Text - 实时音频转字幕

一个全栈实时音频转文字系统，支持捕获浏览器标签页音频并实时显示字幕。

## 系统架构

```
┌─────────────────┐     WebSocket      ┌─────────────────┐     DashScope API     ┌─────────────────┐
│  Edge 浏览器扩展  │ ──────────────────▶ │  Python 服务端   │ ◀──────────────────▶ │   阿里云语音识别   │
│  (音频捕获)      │     PCM 音频流      │  (中转处理)      │      实时识别         │   (Paraformer)   │
└─────────────────┘                    └────────┬────────┘                       └─────────────────┘
                                                │
                                                │ 事件总线
                                                ▼
                                       ┌─────────────────┐
                                       │  PyQt6 字幕窗口  │
                                       │  (悬浮显示)      │
                                       └─────────────────┘
```

## 功能特性

- **浏览器音频捕获**：使用 Edge 扩展的 tabCapture API 捕获任意标签页音频
- **实时语音识别**：对接阿里云 DashScope Paraformer 实时语音识别
- **悬浮字幕窗口**：透明背景、置顶显示、可拖拽、支持鼠标穿透
- **多标签页支持**：可同时捕获多个标签页的音频

## 快速开始

### 1. 安装 Python 依赖

```bash
cd server
pip install -r requirements.txt
```

### 2. 配置阿里云 API Key

```bash
cd server
cp .env.example .env
# 编辑 .env 文件，填入你的 DASHSCOPE_API_KEY
```

获取 API Key: https://dashscope.console.aliyun.com/apiKey

### 3. 安装 Edge 扩展

1. 打开 Edge 浏览器，访问 `edge://extensions/`
2. 开启"开发人员模式"
3. 点击"加载解压缩的扩展"
4. 选择 `edge-extension` 文件夹
5. 注意：需要先将 `icons/icon.svg` 转换为 PNG 格式（参见 icons/README.md）

### 4. 启动服务

```bash
cd server
python main.py
```

### 5. 使用

1. 在 Edge 中打开任意有音频的网页（如 YouTube、Bilibili）
2. 点击扩展图标
3. 点击"开始捕获音频"
4. 字幕窗口将实时显示识别结果

## 项目结构

```
test-audio2text/
├── edge-extension/          # Edge 浏览器扩展
│   ├── manifest.json        # 扩展配置
│   ├── background.js        # Service Worker
│   ├── offscreen.html/js    # 音频处理
│   ├── popup.html/js        # 弹出窗口
│   └── icons/               # 扩展图标
│
├── server/                  # Python 服务端
│   ├── main.py              # 主入口
│   ├── websocket_server.py  # WebSocket 服务器
│   ├── speech_recognizer.py # 语音识别封装
│   ├── subtitle_window.py   # PyQt6 字幕窗口
│   ├── event_bus.py         # 事件总线
│   ├── requirements.txt     # Python 依赖
│   └── .env.example         # 环境变量示例
│
└── README.md                # 本文件
```

## 技术栈

- **前端扩展**：JavaScript, Manifest V3, Web Audio API, WebSocket
- **后端服务**：Python 3.10+, asyncio, websockets
- **语音识别**：阿里云 DashScope (Paraformer-Realtime)
- **桌面 UI**：PyQt6

## 常见问题

### Q: 捕获音频后听不到声音？
A: 扩展代码中已将音频流同时连接到 `audioContext.destination`，确保用户能听到声音。如果仍有问题，请检查系统音量设置。

### Q: 字幕延迟很高？
A: 正常延迟在 200-500ms 左右。如果延迟过高，请检查网络连接和阿里云 API 响应时间。

### Q: 如何调整字幕窗口位置？
A: 直接拖拽字幕窗口即可。右键系统托盘图标可以锁定位置（启用鼠标穿透）。

## 开发说明

### 仅运行服务器（无 UI）

```bash
python main.py --no-ui
```

### 调试模式

在 `speech_recognizer.py` 中可以看到识别结果的日志输出。

## License

MIT
