"""
Audio2Text 服务端主入口
启动 WebSocket 服务器，接收音频流并进行实时语音识别
"""

import asyncio
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 检查 API Key
if not os.getenv('DASHSCOPE_API_KEY'):
    print("错误: 请在 .env 文件中配置 DASHSCOPE_API_KEY")
    print("参考 .env.example 文件")
    sys.exit(1)

from websocket_server import WebSocketServer
from subtitle_window import SubtitleApp


async def main():
    """主函数"""
    # 创建 WebSocket 服务器
    host = os.getenv('WS_HOST', 'localhost')
    port = int(os.getenv('WS_PORT', 8765))

    server = WebSocketServer(host, port)

    print(f"Audio2Text 服务启动中...")
    print(f"WebSocket 服务器: ws://{host}:{port}")
    print("等待浏览器扩展连接...")
    print("-" * 40)

    # 启动服务器
    await server.start()


def run_with_ui():
    """带 UI 的运行模式"""
    import threading
    from PyQt6.QtWidgets import QApplication

    # 创建 Qt 应用
    app = QApplication(sys.argv)

    # 创建字幕窗口
    subtitle_app = SubtitleApp()

    # 在后台线程运行 asyncio 事件循环
    def run_server():
        asyncio.run(main())

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # 运行 Qt 事件循环
    sys.exit(app.exec())


def run_server_only():
    """仅服务器模式（无 UI）"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n服务已停止")


if __name__ == '__main__':
    # 检查是否需要 UI
    if '--no-ui' in sys.argv:
        run_server_only()
    else:
        run_with_ui()
