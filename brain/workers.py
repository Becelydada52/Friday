from PySide6.QtCore import QThread, Signal
import subprocess
import json
import requests

OLLAMA_URL = "http://localhost:11434/api/chat"


class OllamaWorker(QThread):
    """Стримит ответ модели по токенам, не блокируя UI."""
    token_received = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, model: str, messages: list[dict]):
        super().__init__()
        self.model = model
        self.messages = messages
        self._stop = False

    def run(self):
        try:
            with requests.post(
                OLLAMA_URL,
                json={"model": self.model, "messages": self.messages, "stream": True},
                stream=True,
                timeout=120,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if self._stop:
                        break
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        self.token_received.emit(content)
                    if chunk.get("done"):
                        break
            self.finished_ok.emit()
        except Exception as e:
            self.error.emit(str(e))

    def stop(self):
        self._stop = True


class CommandWorker(QThread):
    """Выполняет shell-команду и стримит stdout/stderr построчно."""
    line_received = Signal(str)
    finished_ok = Signal(int)

    def __init__(self, command: str):
        super().__init__()
        self.command = command

    def run(self):
        try:
            proc = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            for line in proc.stdout:
                self.line_received.emit(line.rstrip("\n"))
            proc.wait()
            self.finished_ok.emit(proc.returncode)
        except Exception as e:
            self.line_received.emit(f"[ошибка запуска] {e}")
            self.finished_ok.emit(-1)
