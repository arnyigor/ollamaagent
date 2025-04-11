import sys
import json
import requests
import logging
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QTextEdit,
                             QComboBox, QMessageBox, QProgressBar, QDialog)
from PyQt6.QtCore import QThread, pyqtSignal, QObject, Qt
from PyQt6.QtGui import QFont

# --- Настройка логирования ---
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    filename='jan_client.log',  # Указываем имя файла
                    filemode='w',  # 'w' для перезаписи лога при каждом запуске, 'a' для добавления
                    encoding='utf-8')  # Явно указываем кодировку UTF-8
logger = logging.getLogger(__name__)

# --- Глобальные параметры ---
JAN_SERVER_URL = "http://localhost:1337/v1"  # Измените, если ваш сервер JAN на другом порту/адресе
DEFAULT_MODEL = "DeepSeek-Coder-V2-Lite-Instruct-Q4_K_M"  # Модель по умолчанию
REQUEST_TIMEOUT = 10  # Тайм-аут для запросов в секундах

# --- Thread для выполнения сетевых запросов ---
class JanWorker(QObject):
    """Выполняет сетевые запросы к JAN Server в отдельном потоке."""
    result_received = pyqtSignal(str)  # Сигнал для получения результатов от потока
    error_occurred = pyqtSignal(str)    # Сигнал для ошибок
    models_received = pyqtSignal(list)  # Сигнал для списка моделей
    ready = pyqtSignal(bool)  # Сигнал о готовности
    request_finished = pyqtSignal()  # Сигнал об окончании любого запроса

    def __init__(self, jan_server_url, default_model):
        super().__init__()
        self.jan_server_url = jan_server_url
        self.default_model = default_model
        self.is_ready = False
        self.current_model = None  # Текущая выбранная модель
        logger.info(f"JanWorker создан с URL: {jan_server_url}, Model: {default_model}")

    def check_server(self):
        """Проверяет, доступен ли сервер."""
        logger.info(f"Начало проверки сервера (предполагается доступность) по адресу: {self.jan_server_url}")
        self.is_ready = True  # Предполагаем, что сервер доступен
        self.ready.emit(True)
        self.request_finished.emit()
        logger.info("Проверка сервера завершена (предполагается доступность).")

    def get_models(self):
        """Получает список доступных моделей с сервера."""
        logger.info(f"Начало получения списка моделей с сервера: {self.jan_server_url}/models")
        try:
            url = f"{self.jan_server_url}/models"
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            models_data = response.json()

            if isinstance(models_data, dict) and models_data.get("object") == "list" and "data" in models_data:
                models = [model["id"] for model in models_data["data"]]
                self.models_received.emit(models)
                logger.info(f"Получен список моделей: {models}")
            else:
                error_message = "Неверный формат ответа от сервера (ожидался список моделей в формате ListModelsResponseDto)."
                self.error_occurred.emit(error_message)
                logger.error(error_message)

        except requests.exceptions.RequestException as e:
            error_message = f"Ошибка при получении списка моделей: {e}"
            self.error_occurred.emit(error_message)
            logger.error(error_message, exc_info=True)  # Логируем исключение с трассировкой
        except json.JSONDecodeError as e:
            error_message = f"Ошибка декодирования JSON: {e}"
            self.error_occurred.emit(error_message)
            logger.error(error_message, exc_info=True)  # Логируем исключение с трассировкой
        finally:
            self.request_finished.emit()
            logger.info("Получение списка моделей завершено.")

    def send_message(self, message):
        """Отправляет сообщение на сервер и получает ответ."""
        logger.info(f"Отправка сообщения: {message} с использованием модели: {self.current_model or self.default_model}")
        try:
            url = f"{self.jan_server_url}/chat/completions"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": self.current_model or self.default_model,  # Используем текущую модель или модель по умолчанию
                "messages": [{"role": "user", "content": message}],
                "max_tokens": 200  # Увеличиваем max_tokens
            }
            response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            response_json = response.json()
            self.result_received.emit(json.dumps(response_json, indent=4, ensure_ascii=False))  # Отправляем форматированный JSON
            logger.info(f"Сообщение успешно отправлено и получен ответ: {response_json}")

        except requests.exceptions.RequestException as e:
            error_message = f"Ошибка отправки сообщения: {e}"
            self.error_occurred.emit(error_message)
            logger.error(error_message, exc_info=True)  # Логируем исключение с трассировкой
        except json.JSONDecodeError as e:
            error_message = f"Ошибка декодирования JSON: {e}\nСодержимое ответа: {response.text}"
            self.error_occurred.emit(error_message)
            logger.error(error_message, exc_info=True)  # Логируем исключение с трассировкой
        finally:
            self.request_finished.emit()
            logger.info("Отправка сообщения завершена.")

    def set_current_model(self, model):
        """Устанавливает текущую используемую модель."""
        self.current_model = model
        logger.info(f"Установлена текущая модель: {model}")

# --- Главное окно приложения ---
class JanSettingsWindow(QDialog):
    def __init__(self):
        try:
            super().__init__()
            self.jan_server_url = JAN_SERVER_URL
            self.default_model = DEFAULT_MODEL
            self.setWindowTitle("JAN Server Client")
            self.setGeometry(100, 100, 800, 600)  # Увеличиваем размер окна
            logger.info("MainWindow создан.")

            self.init_ui()
            self.start_worker_thread()
        except Exception as e:
            logging.error(f"Ошибка при открытии настроек Jan: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть настройки: {str(e)}")

    def init_ui(self):
        """Инициализирует пользовательский интерфейс."""
        logger.info("Инициализация UI...")
        self.layout = QVBoxLayout()

        # --- Верхняя панель:  Адрес сервера, Статус, Кнопка проверки ---
        top_layout = QHBoxLayout()
        self.server_label = QLabel("Сервер JAN:")
        logger.debug("Создан QLabel 'Сервер JAN:'")
        top_layout.addWidget(self.server_label)
        self.server_address_edit = QLineEdit(self.jan_server_url)
        logger.debug(f"Создан QLineEdit с адресом: {self.jan_server_url}")
        self.server_address_edit.textChanged.connect(self.update_server_address)  # Обработчик изменения адреса сервера
        top_layout.addWidget(self.server_address_edit)

        self.status_label = QLabel("Статус: Ожидание...")
        logger.debug("Создан QLabel 'Статус: Ожидание...'")
        self.status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        top_layout.addWidget(self.status_label)

        self.check_button = QPushButton("Проверить сервер")
        logger.debug("Создан QPushButton 'Проверить сервер'")
        self.check_button.clicked.connect(self.check_server)
        top_layout.addWidget(self.check_button)

        self.layout.addLayout(top_layout)

        # --- Выбор модели ---
        model_layout = QHBoxLayout()
        self.model_label = QLabel("Модель:")
        logger.debug("Создан QLabel 'Модель:'")
        model_layout.addWidget(self.model_label)
        self.model_combo = QComboBox()
        logger.debug("Создан QComboBox для выбора модели")
        model_layout.addWidget(self.model_combo)

        self.refresh_models_button = QPushButton("Обновить список моделей")
        logger.debug("Создан QPushButton 'Обновить список моделей'")
        self.refresh_models_button.clicked.connect(self.refresh_models)
        model_layout.addWidget(self.refresh_models_button)

        self.layout.addLayout(model_layout)

        # --- Текстовое поле для ввода сообщения ---
        self.message_label = QLabel("Сообщение:")
        logger.debug("Создан QLabel 'Сообщение:'")
        self.layout.addWidget(self.message_label)
        self.message_input = QTextEdit()
        logger.debug("Создан QTextEdit для ввода сообщения")
        self.layout.addWidget(self.message_input)

        # --- Кнопка отправки ---
        self.send_button = QPushButton("Отправить")
        logger.debug("Создан QPushButton 'Отправить'")
        self.send_button.clicked.connect(self.send_message)
        self.layout.addWidget(self.send_button)

        # --- Текстовое поле для отображения ответа ---
        self.response_label = QLabel("Ответ:")
        logger.debug("Создан QLabel 'Ответ:'")
        self.layout.addWidget(self.response_label)
        self.response_output = QTextEdit()
        logger.debug("Создан QTextEdit для отображения ответа")
        self.response_output.setReadOnly(True)  # Только для чтения
        self.layout.addWidget(self.response_output)

        # --- Индикатор загрузки ---
        self.progress_bar = QProgressBar()
        logger.debug("Создан QProgressBar для индикатора загрузки")
        self.progress_bar.setRange(0, 0)  # Режим "занято"
        self.progress_bar.hide()
        self.layout.addWidget(self.progress_bar)

        self.setLayout(self.layout)
        self.disable_input()  # Отключаем ввод пока не проверим сервер
        logger.info("Инициализация UI завершена.")

    def start_worker_thread(self):
        """Запускает поток для работы с JAN Server."""
        self.worker_thread = QThread()
        self.worker = JanWorker(self.jan_server_url, self.default_model)
        self.worker.moveToThread(self.worker_thread)

        # --- Подключение сигналов ---
        self.worker.result_received.connect(self.display_result)
        self.worker.error_occurred.connect(self.display_error)
        self.worker.models_received.connect(self.populate_model_combo)
        self.worker.ready.connect(self.set_server_status)
        self.worker.request_finished.connect(self.hide_progress)

        self.model_combo.currentIndexChanged.connect(self.set_current_model)  # Выбор модели в комбобоксе

        # --- Запуск проверки сервера при старте приложения ---
        self.worker_thread.started.connect(self.worker.check_server)
        self.check_button.clicked.connect(self.check_server)
        self.refresh_models_button.clicked.connect(self.worker.get_models)

        self.send_button.clicked.connect(self.send_message)  # Непосредственно вызываем send_message, а не через сигнал

        self.worker_thread.start()
        logger.info("Worker thread запущен.")

    def update_server_address(self, address):
        """Обновляет адрес сервера."""
        logger.info(f"Попытка обновления адреса сервера на: {address}")
        self.jan_server_url = address
        self.worker.jan_server_url = address  # Обновляем адрес в рабочем потоке
        logger.info(f"Адрес сервера обновлен: {self.jan_server_url}")

    def check_server(self):
        """Запускает проверку доступности сервера."""
        logger.info("Запуск проверки сервера вручную.")
        self.status_label.setText("Статус: Проверка...")
        logger.debug("Установлен текст статуса: 'Статус: Проверка...'")
        self.show_progress()
        self.worker_thread.started.emit()  # Еще раз чтобы убедиться, что сигнал отправлен

    def refresh_models(self):
        """Запускает запрос на обновление списка моделей."""
        logger.info("Запуск обновления списка моделей вручную.")
        self.show_progress()
        self.worker.get_models()  # Вызываем метод непосредственно, а не через сигнал

    def send_message(self):
        """Отправляет сообщение на сервер."""
        message = self.message_input.toPlainText()
        if message:
            logger.info(f"Отправка сообщения из GUI: {message}")
            self.show_progress()
            self.worker.send_message(message)  # Вызываем метод непосредственно, а не через сигнал
        else:
            logger.warning("Попытка отправить пустое сообщение.")
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, введите сообщение.")

    def set_server_status(self, is_ready):
        """Обновляет статус сервера и включает/отключает ввод."""
        if is_ready:
            self.status_label.setText("Статус: Подключен")
            logger.debug("Установлен текст статуса: 'Статус: Подключен'")
            self.status_label.setStyleSheet("color: green;")
            self.enable_input()
            self.refresh_models()  # Обновляем список моделей сразу после подключения
            logger.info("Сервер подключен. Включен ввод.")
        else:
            self.status_label.setText("Статус: Не подключен")
            logger.debug("Установлен текст статуса: 'Статус: Не подключен'")
            self.status_label.setStyleSheet("color: red;")
            self.disable_input()
            logger.warning("Сервер не подключен. Ввод отключен.")

    def populate_model_combo(self, models):
        """Заполняет комбобокс списком моделей."""
        logger.info(f"Заполнение комбобокса моделями: {models}")
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model)  # Добавляем модели в комбобокс
            logger.debug(f"Добавлена модель в комбобокс: {model}")
        # Выбираем модель по умолчанию, если она есть в списке
        if self.default_model in models:
            index = models.index(self.default_model)
            self.model_combo.setCurrentIndex(index)
            logger.info(f"Модель по умолчанию '{self.default_model}' выбрана в комбобоксе.")
        else:
            # Если модели по умолчанию нет в списке, выбираем первую модель
            if models:
                self.model_combo.setCurrentIndex(0)
                logger.warning(f"Модель по умолчанию '{self.default_model}' не найдена. Выбрана первая модель: {models[0]}")
            else:
                logger.warning("Список моделей пуст.")

    def set_current_model(self, index):
        """Устанавливает текущую модель в worker."""
        model = self.model_combo.itemText(index)
        self.worker.set_current_model(model)  # Устанавливаем текущую модель в рабочем потоке
        logger.info(f"Выбрана модель в GUI: {model}")

    def display_result(self, result):
        """Отображает результат в текстовом поле."""
        self.response_output.setText(result)
        logger.info("Результат отображен в GUI.")

    def display_error(self, error_message):
        """Отображает сообщение об ошибке."""
        QMessageBox.critical(self, "Ошибка", error_message)
        self.status_label.setText("Статус: Ошибка")
        logger.debug("Установлен текст статуса: 'Статус: Ошибка'")
        self.status_label.setStyleSheet("color: red;")
        logger.error(f"Ошибка: {error_message}")

    def show_progress(self):
        """Показывает индикатор загрузки."""
        self.progress_bar.show()
        self.disable_input()  # Блокируем ввод, пока идет запрос
        logger.info("Показан индикатор загрузки. Ввод отключен.")

    def hide_progress(self):
        """Скрывает индикатор загрузки."""
        self.progress_bar.hide()
        if self.worker.is_ready:
            self.enable_input()  # Разблокируем ввод, если сервер готов
            logger.info("Индикатор загрузки скрыт. Ввод включен.")
        else:
            logger.warning("Индикатор загрузки скрыт, но ввод остается отключенным, т.к. сервер не готов.")

    def enable_input(self):
        """Включает поля ввода и кнопки."""
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.model_combo.setEnabled(True)
        self.refresh_models_button.setEnabled(True)
        self.check_button.setEnabled(True)
        self.server_address_edit.setEnabled(True)
        logger.info("Ввод включен.")

    def disable_input(self):
        """Отключает поля ввода и кнопки."""
        self.message_input.setEnabled(False)
        self.send_button.setEnabled(False)
        self.model_combo.setEnabled(False)
        self.refresh_models_button.setEnabled(False)
        self.check_button.setEnabled(False)
        self.server_address_edit.setEnabled(False)
        logger.info("Ввод отключен.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = JanSettingsWindow()
    main_window.show()
    logger.info("Приложение запущено.")
    sys.exit(app.exec())