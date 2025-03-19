import logging
import sys

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from chat_window import ChatWindow

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


class OllamaChat:
    def __init__(self):
        # Проверяем, существует ли уже экземпляр QApplication
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication(sys.argv)

        # Устанавливаем стиль
        self.app.setStyle("Fusion")

        # Создаем главное окно
        self.chat_window = None
        self.settings_window = None

        # Таймер для проверки видимости окна
        self.visibility_timer = QTimer()
        self.visibility_timer.timeout.connect(self.check_visibility)
        self.visibility_timer.start(1000)  # Проверка каждую секунду

    def check_visibility(self):
        """Проверка видимости окна"""
        if self.chat_window and not self.chat_window.isVisible():
            logging.warning("Окно чата не видимо, пытаемся показать")
            self.chat_window.show()
            self.chat_window.raise_()
            self.chat_window.activateWindow()

    def show_settings(self):
        """Показать окно настроек"""
        if self.settings_window:
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()

    def run(self):
        """Запуск приложения"""
        try:
            # Создаем главное окно
            self.chat_window = ChatWindow()
            self.chat_window.settings_requested.connect(self.show_settings)

            # Запускаем главный цикл
            exit_code = self.app.exec()
            logging.info(f"Приложение завершило работу с кодом: {exit_code}")
            return exit_code

        except Exception as e:
            logging.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
            return 1


if __name__ == "__main__":
    chat = OllamaChat()
    sys.exit(chat.run())
