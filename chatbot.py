import logging
import sys

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QVBoxLayout, QWidget,
    QComboBox, QMessageBox, QPushButton
)
from ollama import Client, chat as ollama_chat

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("chatbot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ChatWorker(QThread):
    partial_response = pyqtSignal(str)
    full_response = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, model, messages):
        super().__init__()
        self.model = model
        self.messages = messages
        logger.debug(f"ChatWorker created for model: {model}")

    def run(self):
        logger.info(f"Starting chat request processing for model: {self.model}")
        try:
            stream = ollama_chat(
                model=self.model,
                messages=self.messages,
                stream=True
            )
            buffer = ""
            for chunk in stream:
                if 'message' in chunk:
                    content = chunk['message'].get('content', '')
                    buffer += content
                    self.partial_response.emit(content)
                    logger.debug(f"Received chunk: {content}")
            self.full_response.emit(buffer)
            logger.info(f"Full response received: {buffer}")
        except Exception as e:
            error_msg = f"Error during chat request: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error_occurred.emit(error_msg)


class ChatApp(QWidget):
    def __init__(self):
        super().__init__()
        logger.info("Initializing ChatApp")
        self.messages = []
        self.response_buffer = ""
        self.typing_visible = False
        self.init_ui()
        self.check_ollama_connection()

    def init_ui(self):
        logger.debug("Setting up UI components")
        self.setWindowTitle("Ollama Chat")
        self.layout = QVBoxLayout()
        # Панель инструментов
        self.toolbar = QVBoxLayout()
        self.model_selector = QComboBox(self)
        self.refresh_button = QPushButton("Обновить модели")
        self.refresh_button.clicked.connect(self.refresh_models)
        self.toolbar.addWidget(self.model_selector)
        self.toolbar.addWidget(self.refresh_button)
        self.layout.addLayout(self.toolbar)
        self.setLayout(self.layout)
        logger.debug("UI components initialized")

    def check_ollama_connection(self):
        logger.info("Checking Ollama server connection")
        try:
            client = Client()
            client.list()
            logger.info("Successfully connected to Ollama server")
        except Exception as e:
            error_msg = f"Ollama server connection failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Ошибка подключения",
                                 "Не удалось подключиться к серверу Ollama. Убедитесь, что он запущен.")
            sys.exit(1)

    def refresh_models(self):
        logger.info("Refreshing model list")
        try:
            client = Client()
            response = client.list()
            models = response.get('models', [])
            model_names = []

            for model in models:
                if hasattr(model, 'model'):
                    model_names.append(model.model)
                    logger.debug(f"Found model (class): {model.model}")
                elif isinstance(model, dict) and 'model' in model:
                    model_names.append(model['model'])
                    logger.debug(f"Found model (dict): {model['model']}")
                else:
                    logger.warning(f"Unexpected model format: {model}", stack_info=True)

            self.model_selector.clear()
            if model_names:
                self.model_selector.addItems(model_names)
                logger.info(f"Available models: {model_names}")
            else:
                self.model_selector.addItem("No models found")
                logger.warning("No valid models detected")

        except Exception as e:
            error_msg = f"Model refresh failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.warning(self, "Ошибка", error_msg)


if __name__ == "__main__":
    logger.info("Starting ChatBot application")
    app = QApplication(sys.argv)
    chat_app = ChatApp()
    chat_app.show()
    sys.exit(app.exec())
