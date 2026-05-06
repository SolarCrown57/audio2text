"""
阿里云 DashScope 语音识别封装
使用 Paraformer 实时语音识别模型
"""

import os
import asyncio
from typing import Callable, Optional
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult


class SpeechRecognizerCallback(RecognitionCallback):
    """语音识别回调处理"""

    def __init__(self, tab_id: str, on_result: Callable[[str, bool], None]):
        self.tab_id = tab_id
        self.on_result = on_result
        self.current_sentence = ""

    def on_open(self) -> None:
        """连接打开"""
        print(f"[Tab {self.tab_id}] DashScope 连接已建立")

    def on_close(self) -> None:
        """连接关闭"""
        print(f"[Tab {self.tab_id}] DashScope 连接已关闭")

    def on_event(self, result: RecognitionResult) -> None:
        """收到识别事件"""
        try:
            sentence = result.get_sentence()
            if sentence:
                # DashScope SDK 返回 Sentence 对象（属性访问），兼容 dict 类型
                if hasattr(sentence, 'get'):
                    text = sentence.get('text', '')
                    is_end = sentence.get('end_time') is not None
                else:
                    text = getattr(sentence, 'text', '')
                    is_end = getattr(sentence, 'end_time', None) is not None

                if text:
                    self.current_sentence = text
                    self.on_result(text, is_end)

                    if is_end:
                        print(f"[Tab {self.tab_id}] 识别结果: {text}")
        except Exception as e:
            print(f"[Tab {self.tab_id}] 解析结果错误: {e}")

    def on_error(self, result: RecognitionResult) -> None:
        """识别错误"""
        print(f"[Tab {self.tab_id}] 识别错误: {result}")

    def on_complete(self) -> None:
        """识别完成"""
        print(f"[Tab {self.tab_id}] 识别任务完成")


class SpeechRecognizer:
    """语音识别器"""

    def __init__(
        self,
        tab_id: str,
        sample_rate: int = 16000,
        on_result: Optional[Callable[[str, bool], None]] = None
    ):
        self.tab_id = tab_id
        self.sample_rate = sample_rate
        self.on_result = on_result or (lambda text, is_final: None)
        self.recognition: Optional[Recognition] = None
        self._is_running = False

    async def start(self):
        """启动识别"""
        if self._is_running:
            return

        # 创建回调
        callback = SpeechRecognizerCallback(self.tab_id, self.on_result)

        # 创建识别实例
        self.recognition = Recognition(
            model='paraformer-realtime-v2',
            format='pcm',
            sample_rate=self.sample_rate,
            callback=callback
        )

        # 启动识别（在后台线程中运行）
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.recognition.start)

        self._is_running = True

    async def send_audio(self, audio_data: bytes):
        """发送音频数据"""
        if not self._is_running or not self.recognition:
            return

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.recognition.send_audio_frame,
                audio_data
            )
        except Exception as e:
            print(f"[Tab {self.tab_id}] 发送音频错误: {e}")

    async def stop(self):
        """停止识别"""
        if not self._is_running:
            return

        self._is_running = False

        if self.recognition:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self.recognition.stop)
            except Exception as e:
                print(f"[Tab {self.tab_id}] 停止识别错误: {e}")
            finally:
                self.recognition = None
