# Audio2Text 服务端

实时音频转文字服务，接收浏览器扩展发送的音频流，调用阿里云 DashScope API 进行语音识别。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

1. 复制 `.env.example` 为 `.env`
2. 填入你的阿里云 DashScope API Key

```bash
cp .env.example .env
# 编辑 .env 文件，填入 DASHSCOPE_API_KEY
```

## 运行

```bash
python main.py
```

服务将在 `ws://localhost:8765` 启动 WebSocket 服务器。
