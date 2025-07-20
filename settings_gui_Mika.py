import sys
import json
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, 
    QSlider, QPushButton, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon


class SettingsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки Пятницы")
        self.setWindowIcon(QIcon("assets/friday_icon.png"))  # Путь к иконке
        self.setFixedSize(400, 400)
        
        # Центрируем окно
        screen_geometry = QApplication.primaryScreen().geometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        
        # Загружаем настройки
        self.settings = QSettings("FridayAssistant", "Settings")
        self.load_settings()
        
        # Создаём интерфейс
        self.init_ui()
        
        # Применяем тему по умолчанию
        self.apply_theme(self.settings.value("theme", "Dark"))

    def init_ui(self):
       
        central_widget = QWidget()
        layout = QVBoxLayout()
    
    # Выбор темы
        self.theme_label = QLabel("Тема:")
        self.theme_combobox = QComboBox()
        self.theme_combobox.addItems(["Dark", "Light", "System"])
        self.theme_combobox.setCurrentText(self.settings.value("theme", "Dark"))
        self.theme_combobox.currentTextChanged.connect(self.apply_theme)
    
    # Громкость голоса
        self.volume_label = QLabel(f"Громкость голоса: {self.settings.value('voice_volume', 50)}%")
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.settings.value("voice_volume", 50)))
        self.volume_slider.valueChanged.connect(
            lambda v: self.volume_label.setText(f"Громкость голоса: {v}%")
        )
    
    # Скорость речи (исправлено)
        self.speed_label = QLabel(f"Скорость речи: {self.settings.value('speech_speed', 1.0)}x")
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)  # 0.5x - 2.0x
        self.speed_slider.setValue(int(float(self.settings.value("speech_speed", 1.0)) * 100))  
        self.speed_slider.valueChanged.connect(
            lambda v: self.speed_label.setText(f"Скорость речи: {v / 100:.1f}x")
        )
    
    # Чувствительность микрофона
        self.mic_label = QLabel(f"Чувствительность микрофона: {self.settings.value('mic_sensitivity', 4000)}")
        self.mic_slider = QSlider(Qt.Orientation.Horizontal)
        self.mic_slider.setRange(1000, 6000)
        self.mic_slider.setValue(int(self.settings.value("mic_sensitivity", 4000)))
        self.mic_slider.valueChanged.connect(
            lambda v: self.mic_label.setText(f"Чувствительность микрофона: {v}")
        )
    
    # Автозагрузка
        self.autostart_checkbox = QCheckBox("Запускать при старте системы")
        self.autostart_checkbox.setChecked(self.settings.value("autostart", False, type=bool))
    
    # Кнопки
        self.save_button = QPushButton("Сохранить")
        self.save_button.clicked.connect(self.save_settings)
    
    # Добавляем элементы в layout
        layout.addWidget(self.theme_label)
        layout.addWidget(self.theme_combobox)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.speed_label)
        layout.addWidget(self.speed_slider)
        layout.addWidget(self.mic_label)
        layout.addWidget(self.mic_slider)
        layout.addWidget(self.autostart_checkbox)
        layout.addWidget(self.save_button)
    
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def apply_theme(self, theme_name):
        """Применяет выбранную тему (Dark/Light/System)."""
        if theme_name == "Dark":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #2D2D2D;
                    color: #FFFFFF;
                }
                QLabel, QCheckBox {
                    color: #FFFFFF;
                }
                QSlider::groove:horizontal {
                    background: #505050;
                    height: 8px;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #1E90FF;
                    width: 16px;
                    margin: -4px 0;
                    border-radius: 8px;
                }
            """)
        elif theme_name == "Light":
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #F5F5F5;
                    color: #000000;
                }
                QLabel, QCheckBox {
                    color: #000000;
                }
                QSlider::groove:horizontal {
                    background: #C0C0C0;
                    height: 8px;
                    border-radius: 4px;
                }
                QSlider::handle:horizontal {
                    background: #1E90FF;
                    width: 16px;
                    margin: -4px 0;
                    border-radius: 8px;
                }
            """)
        else:  # System (стандартный стиль ОС)
            self.setStyleSheet("")

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def load_settings(self):
        """Загружает настройки из QSettings (или создаёт дефолтные)."""
        if not self.settings.contains("voice_volume"):
            self.settings.setValue("voice_volume", 50)
            self.settings.setValue("speech_speed", 1.0)
            self.settings.setValue("mic_sensitivity", 4000)
            self.settings.setValue("theme", "Dark")
            self.settings.setValue("autostart", False)

    def save_settings(self):
        """Сохраняет настройки и применяет их к ассистенту."""
        self.settings.setValue("voice_volume", self.volume_slider.value())
        self.settings.setValue("speech_speed", self.speed_slider.value() / 100)
        self.settings.setValue("mic_sensitivity", self.mic_slider.value())
        self.settings.setValue("theme", self.theme_combobox.currentText())
        self.settings.setValue("autostart", self.autostart_checkbox.isChecked())
        
        # Здесь можно добавить вызов метода ассистента для применения настроек
        if self.parent():
            self.parent().apply_settings(self.settings)
        
        self.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())