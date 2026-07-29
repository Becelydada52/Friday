from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QComboBox
)
from PySide6.QtGui import QTextCursor, QFont

# Forward reference to worker classes which are defined in the main app module.
# These will be available at runtime when the panel classes are used.

class ChatPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.history: list[dict] = []
        self.worker = None  # type: ignore
        layout = QVBoxLayout(self)
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Модель:"))
        self.model_box = QComboBox()
        self.model_box.setEditable(True)
        self.model_box.addItems(["qwen2.5-coder:7b", "llama3.1:8b", "deepseek-coder-v2:16b"])
        top_bar.addWidget(self.model_box)
        layout.addLayout(top_bar)
        self.chat_view = QTextEdit()
        self.chat_view.setReadOnly(True)
        self.chat_view.setFont(QFont("Consolas", 10))
        layout.addWidget(self.chat_view, stretch=1)
        input_bar = QHBoxLayout()
        self.input_line = QLineEdit()
        self.input_line.setPlaceholderText("Напиши сообщение агенту и нажми Enter...")
        self.input_line.returnPressed.connect(self.send_message)
        self.send_btn = QPushButton("Отправить")
        self.send_btn.clicked.connect(self.send_message)
        input_bar.addWidget(self.input_line, stretch=1)
        input_bar.addWidget(self.send_btn)
        layout.addLayout(input_bar)
    def append_text(self, text: str, newline_before=False):
        cursor = self.chat_view.textCursor()
        cursor.movePosition(QTextCursor.End)
        if newline_before:
            cursor.insertText("\n")
        cursor.insertText(text)
        self.chat_view.setTextCursor(cursor)
        self.chat_view.ensureCursorVisible()
    def send_message(self):
        text = self.input_line.text().strip()
        if not text or (self.worker and self.worker.isRunning()):
            return
        self.input_line.clear()
        self.history.append({"role": "user", "content": text})
        self.append_text(f"\n\n> {text}\n", newline_before=False)
        self.append_text("\nАгент: ")
        model = self.model_box.currentText().strip()
        self.worker = OllamaWorker(model, self.history)
        self.worker.token_received.connect(self._on_token)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self._assistant_buffer = ""
        self.send_btn.setEnabled(False)
        self.worker.start()
    def _on_token(self, token: str):
        self._assistant_buffer += token
        self.append_text(token)
    def _on_finished(self):
        self.history.append({"role": "assistant", "content": self._assistant_buffer})
        self.send_btn.setEnabled(True)
    def _on_error(self, msg: str):
        self.append_text(f"\n[Ошибка соединения с Ollama: {msg}]\n")
        self.send_btn.setEnabled(True)

class TerminalPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None  # type: ignore
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Вывод команд"))
        self.output_view = QTextEdit()
        self.output_view.setReadOnly(True)
        self.output_view.setFont(QFont("Consolas", 10))
        self.output_view.setStyleSheet("background-color: #101418; color: #d0d0d0;")
        layout.addWidget(self.output_view, stretch=1)
        input_bar = QHBoxLayout()
        self.cmd_line = QLineEdit()
        self.cmd_line.setPlaceholderText("Команда для выполнения (например: git status)")
        self.cmd_line.returnPressed.connect(self.run_command)
        self.run_btn = QPushButton("Выполнить")
        self.run_btn.clicked.connect(self.run_command)
        input_bar.addWidget(self.cmd_line, stretch=1)
        input_bar.addWidget(self.run_btn)
        layout.addLayout(input_bar)
    def run_command(self):
        cmd = self.cmd_line.text().strip()
        if not cmd or (self.worker and self.worker.isRunning()):
            return
        self.output_view.append(f"\n$ {cmd}")
        self.cmd_line.clear()
        self.run_btn.setEnabled(False)
        self.worker = CommandWorker(cmd)
        self.worker.line_received.connect(self.output_view.append)
        self.worker.finished_ok.connect(self._on_finished)
        self.worker.start()
    def _on_finished(self, code: int):
        self.output_view.append(f"[процесс завершён, код {code}]")
        self.run_btn.setEnabled(True)