import logging
import sys
import os
from PyQt6.QtWidgets import QApplication

from chat_window import ChatWindow
from system_optimizer import OllamaOptimizer

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def setup_ollama_environment():
    """Настройка окружения Ollama перед запуском"""
    try:
        logging.info("Настройка оптимальных параметров Ollama...")

        # Получаем оптимальную конфигурацию
        optimizer = OllamaOptimizer()
        config = optimizer.get_optimal_settings()

        # Применяем серверные настройки
        server_settings = config.get('server', {})
        for key, value in server_settings.items():
            os.environ[key] = str(value)
            logging.info(f"Установлена переменная окружения: {key}={value}")

        # Логируем информацию о системе
        system_info = optimizer.detector.system_info
        logging.info(f"Обнаружено оборудование: {system_info}")

        # Логируем примененные настройки
        logging.info("Применены оптимальные настройки:")
        for category, settings in config.items():
            if category != 'system_info':
                logging.info(f"  {category}: {settings}")

        return True

    except Exception as e:
        logging.error(f"Ошибка настройки окружения Ollama: {e}")
        return False

def main():
    try:
        # Настраиваем окружение Ollama
        if not setup_ollama_environment():
            logging.warning("Не удалось применить оптимальные настройки, продолжаем с настройками по умолчанию")

        app = QApplication(sys.argv)
        app.setStyle("Fusion")

        window = ChatWindow()
        window.show()

        return app.exec()
    except Exception as e:
        logging.critical(f"Критическая ошибка: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
