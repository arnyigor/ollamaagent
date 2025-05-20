import logging
import sys
from PyQt6.QtWidgets import QApplication

from chat_window import ChatWindow

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def main():
    try:
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
