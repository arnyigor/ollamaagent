import logging
import sys
import time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from ui_settings import TEXT_EDIT_STYLE, MESSAGE_WIDGET_STYLE, MODEL_SETTINGS_STYLE
from workers import ModelThread, MessageThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel,
    QSplitter, QFrame, QScrollArea, QSpinBox, QDoubleSpinBox,
    QMessageBox, QGroupBox, QFormLayout, QCheckBox, QDialog
)

from jan_settings import JanSettingsWindow
from ollama_api import OllamaAPI
from ollama_settings import OllamaSettings
from widgets.model_settings import ModelSettings

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


class MessageWidget(QFrame):
    """Виджет для отображения одного сообщения в чате"""

    def __init__(self, text: str, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

        # Заголовок сообщения (User/Assistant)
        # header = QLabel("Вы" if is_user else "Ассистент")
        # header.setStyleSheet(
        #     "font-weight: bold; color: #2962FF;" if is_user else "font-weight: bold; color: #00838F;")
        # layout.addWidget(header)

        # Текст сообщения в QTextEdit
        message = QTextEdit()
        message.setReadOnly(True)
        message.setPlainText(text)
        message.setFrameStyle(QFrame.Shape.NoFrame)
        message.setStyleSheet(TEXT_EDIT_STYLE)

        # Автоматическая высота
        doc_height = message.document().size().height()
        message.setFixedHeight(int(min(doc_height + 20, 400)))
        message.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(message)

        # Стилизация фрейма
        self.setStyleSheet(MESSAGE_WIDGET_STYLE)


class ChatHistory(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.response_start_pos = None
        self.current_message_html = ""
        self.is_system_message = False

    def add_system_message(self, text: str):
        """
        Добавление системного сообщения (например, о запуске модели)
        """
        self.is_system_message = True
        message_html = (
            f'<div style="margin: 10px 0; padding: 8px; '
            f'background-color: #E3F2FD; border-radius: 8px; '
            f'color: #1565C0; font-style: italic;">{text}</div>'
        )
        self._insert_message_safely(message_html)
        self.is_system_message = False

    def add_message(self, text: str, is_user: bool = False, performance_info: dict = None):
        """
        Добавление обычного сообщения (от пользователя или ассистента)
        """
        # Этот метод теперь используется только для сообщений пользователя
        if not is_user:
            return

        if not text.strip():
            return

        sender = "Вы"
        color = "#2962FF"
        bg_color = "#F5F5F5"

        message_html = (
            f'<div style="margin: 10px 0; padding: 12px; background-color: {bg_color}; '
            f'border-radius: 8px; border: 1px solid #E0E0E0;">'
            f'<div style="font-weight: bold; color: {color}; margin-bottom: 8px;"><br>{sender}</div>'
            f'<div style="white-space: pre-wrap; margin-left: 10px;">{text.strip()}<br></div>'
            f'</div>'
        )
        self._insert_message_safely(message_html)

    def add_performance_info(self, performance_info: dict):
        """
        Добавление информации о производительности отдельно от сообщения
        """
        if not performance_info:
            return

        tokens_per_sec = performance_info.get("tokens", 0) / max(
            performance_info.get("total_time", 1), 0.1
        )
        info_html = (
            f'<div style="margin-top: 15px; margin-left: 25px; padding: 8px; background-color: #FFFFFF; '
            f'border-radius: 6px; border: 1px solid #E0E0E0; font-size: 12px; color: #757575;">'
            f'⚡ Время: {performance_info.get("total_time", 0):.2f}с | '
            f'🔄 Токенов: {performance_info.get("tokens", 0)} '
            f'({tokens_per_sec:.1f} т/с) | '
            f'⚙️ Модель: {performance_info.get("model", "неизвестно")}'
            f'</div>'
        )
        # Добавляем перевод строки перед информацией
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText('\n')
        self._insert_message_safely(info_html)
        # log_prefix = "Пользователь" if is_user else "Ассистент"
        # logging.info(f"{log_prefix} message_html: {message_html}")

    def add_extended_performance_info(self, stats: dict):
        """
        Добавление расширенной информации о производительности
        """
        if not stats:
            return

        # Рассчитываем скорость генерации
        output_tokens = stats.get("output_tokens", 0)
        total_time = stats.get("total_time", 1)
        tokens_per_sec = output_tokens / max(total_time, 0.1)

        # Рассчитываем время до первого токена
        ttft = stats.get("time_to_first_token", 0)

        info_html = (
            f'<div style="margin-top: 15px; margin-left: 25px; padding: 10px; background-color: #E8F5E8; '
            f'border-radius: 8px; border: 1px solid #4CAF50; font-size: 12px; color: #2E7D32;">'
            f'📊 <b>Расширенная статистика:</b><br>'
            f'⏱️ Общее время: {total_time:.2f}с | '
            f'⚡ TTFT: {ttft:.3f}с | '
            f'📥 Входные токены: {stats.get("input_tokens", 0)} | '
            f'📤 Выходные токены: {output_tokens} | '
            f'🔄 Всего токенов: {stats.get("total_tokens", 0)} | '
            f'⚡ Скорость: {tokens_per_sec:.1f} т/с | '
            f'🧠 Память: {stats.get("memory_used", 0):.1f}MB | '
            f'⚙️ Модель: {stats.get("model", "неизвестно")}'
            f'</div>'
        )

        # Добавляем перевод строки перед информацией
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText('\n')
        self._insert_message_safely(info_html)

    def add_message_chunk(self, chunk: str):
        """
        Добавление части сообщения в режиме потоковой генерации
        """
        if not chunk or self.is_system_message:
            return

        # Инициализация нового сообщения, если это первый чанк
        if self.response_start_pos is None:
            self.response_start_pos = self.textCursor().position()
            self.current_message_text = ""

        # Вставляем чанк как есть, без добавления пробелов
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        
        # Обрабатываем пустой чанк как сигнал завершения
        if chunk == '':
            self.finish_chunked_message()
            return
            
        cursor.insertText(chunk)
        self.current_message_text += chunk
        self._scroll_to_bottom()

    def _insert_message_safely(self, html: str):
        """
        Безопасная вставка HTML в чат
        """
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(html)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        """
        Прокрутка чата вниз
        """
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        QApplication.processEvents()

    def finish_chunked_message(self):
        """
        Завершение потокового сообщения
        """
        if self.response_start_pos is not None:
            # Добавляем перевод строки после сообщения
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText('\n')
            self._scroll_to_bottom()
            self.response_start_pos = None
            self.current_message_text = ""





class ChatWindow(QMainWindow):
    settings_requested = pyqtSignal()

    def __init__(self):
        self.message_thread = None
        self.messages = []
        self.current_response = ""
        self.total_tokens = 0
        self.generation_start_time = None
        # Инициализируем статистику сессии
        self.session_stats = {
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_generations': 0,
            'total_time': 0.0
        }
        try:
            super().__init__(None)  # Явно указываем отсутствие родителя

            # Устанавливаем флаги окна
            self.setWindowFlags(
                Qt.WindowType.Window |
                Qt.WindowType.WindowMinMaxButtonsHint |
                Qt.WindowType.WindowCloseButtonHint
            )

            # Базовая настройка окна
            self.setWindowTitle("Ollama Chat")
            self.resize(1200, 800)
            self.setMinimumSize(800, 600)

            # Центрируем окно на экране
            screen = QApplication.primaryScreen().geometry()
            self.setGeometry(
                (screen.width() - 1200) // 2,
                (screen.height() - 800) // 2,
                1200, 800
            )

            # Инициализация API
            self.api = OllamaAPI()
            self.current_model = None

            # Проверка доступности API
            is_available, version = self.api.is_available()
            if not is_available:
                raise Exception(f"Ollama недоступен: {version}")
            logging.info(f"API инициализирован (версия: {version})")

            # Создаем центральный виджет
            central_widget = QWidget(self)
            self.setCentralWidget(central_widget)

            # Создаем главный layout
            main_layout = QHBoxLayout()
            central_widget.setLayout(main_layout)
            main_layout.setContentsMargins(0, 0, 0, 0)

            # Обрабатываем события после создания layout
            QApplication.processEvents()

            # Проверяем видимость после инициализации
            if not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()
                QApplication.processEvents()

            # Защита от закрытия во время инициализации
            self.initialization_complete = False

            # Продолжаем инициализацию интерфейса
            self._initialize_interface(main_layout)

            # Отмечаем, что инициализация завершена
            self.initialization_complete = True

        except Exception as e:
            logging.error(f"Ошибка инициализации окна: {str(e)}", exc_info=True)
            raise

    def closeEvent(self, a0):
        """Обработка события закрытия окна"""
        try:
            if not hasattr(self, 'initialization_complete') or not self.initialization_complete:
                logging.warning("Попытка закрыть окно во время инициализации")
                if hasattr(a0, 'ignore'):
                    a0.ignore()
                return

            # Останавливаем все запущенные модели
            logging.info("Остановка всех моделей перед закрытием...")
            self.api.stop_all_models()

            # Останавливаем таймер обновления
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()

            # Очищаем потоки
            if hasattr(self, 'message_thread') and self.message_thread is not None:
                self.message_thread.quit()
                self.message_thread.wait()

            if hasattr(a0, 'accept'):
                a0.accept()
        except Exception as e:
            logging.error(f"Ошибка при закрытии приложения: {str(e)}")
            if hasattr(a0, 'accept'):
                a0.accept()

    def eventFilter(self, a0, a1):
        """Обработка событий для поля ввода"""
        try:
            if a0 == self.message_input and a1.type() == a1.Type.KeyPress:
                key_event = a1
                if hasattr(key_event, 'key') and hasattr(key_event, 'modifiers'):
                    if key_event.key() == Qt.Key.Key_Return and not (key_event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                        self.send_message()
                        return True
        except Exception as e:
            logging.warning(f"Ошибка в eventFilter: {e}")
        return super().eventFilter(a0, a1)

    def _initialize_interface(self, main_layout):
        """Инициализация интерфейса"""
        try:
            # Создаем сплиттер
            splitter = QSplitter(Qt.Orientation.Horizontal)
            main_layout.addWidget(splitter)

            # Левая панель
            left_panel = QWidget()
            left_layout = QVBoxLayout(left_panel)
            left_layout.setContentsMargins(10, 10, 10, 10)

            # Выбор модели
            model_label = QLabel("Выберите модель:")
            self.model_combo = QComboBox()
            self.model_combo.addItem("Загрузка моделей...")
            left_layout.addWidget(model_label)
            left_layout.addWidget(self.model_combo)

            # Статус модели
            self.model_status = QLabel("Статус: Не выбрана")
            self.model_status.setStyleSheet("""
                QLabel {
                    color: #757575;
                    margin-top: 5px;
                    padding: 5px;
                    border-radius: 4px;
                    background-color: #F5F5F5;
                }
            """)
            left_layout.addWidget(self.model_status)

            # Кнопки настроек
            settings_layout = QHBoxLayout()

            # Кнопка настроек модели
            model_settings_btn = QPushButton("⚙ Модель")
            model_settings_btn.clicked.connect(self._toggle_model_settings)
            model_settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #1976D2; }
                QPushButton:pressed { background-color: #1565C0; }
            """)
            settings_layout.addWidget(model_settings_btn)

            # Кнопка настроек Ollama
            ollama_settings_btn = QPushButton("⚙ Ollama")
            ollama_settings_btn.clicked.connect(self._show_ollama_settings)
            ollama_settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: #673AB7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #5E35B1; }
                QPushButton:pressed { background-color: #512DA8; }
            """)
            settings_layout.addWidget(ollama_settings_btn)

            # Кнопка оптимизации
            optimize_btn = QPushButton("🔧 Оптимизация")
            optimize_btn.clicked.connect(self._show_optimization_info)
            optimize_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF9800;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #F57C00; }
                QPushButton:pressed { background-color: #EF6C00; }
            """)
            settings_layout.addWidget(optimize_btn)

            # Кнопка настроек Ollama
            jan_settings_btn = QPushButton("⚙ Jan")
            # jan_settings_btn.clicked.connect(self._show_jan_settings)
            jan_settings_btn.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #5E35B1; }
                QPushButton:pressed { background-color: #512DA8; }
            """)
            settings_layout.addWidget(jan_settings_btn)

            # Кнопка статистики сессии
            stats_btn = QPushButton("📊 Статистика")
            stats_btn.clicked.connect(self._show_session_stats)
            stats_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                    margin-top: 10px;
                }
                QPushButton:hover { background-color: #45a049; }
                QPushButton:pressed { background-color: #3d8b40; }
            """)
            settings_layout.addWidget(stats_btn)

            left_layout.addLayout(settings_layout)

            left_layout.addStretch()

            try:
                # --- Настройка автоматического запуска модели ---
                self.auto_start_model_checkbox = QCheckBox("Автоматически запускать модель")
                self.auto_start_model_checkbox.setChecked(True)  # По умолчанию включено
                left_layout.addWidget(self.auto_start_model_checkbox)
            except Exception as e:
                logging.error(f"Ошибка при создании QCheckBox: {str(e)}")

            left_panel.setMinimumWidth(200)
            left_panel.setMaximumWidth(300)
            splitter.addWidget(left_panel)

            # Центральная панель (чат)
            chat_panel = QWidget()
            chat_layout = QVBoxLayout(chat_panel)
            chat_layout.setContentsMargins(10, 10, 10, 10)

            self.chat_history = ChatHistory()
            chat_layout.addWidget(self.chat_history)

            # Поле ввода и кнопка отправки
            input_layout = QHBoxLayout()
            input_layout.setSpacing(10)

            self.message_input = QTextEdit()
            self.message_input.setPlaceholderText("Введите сообщение...")
            self.message_input.setMaximumHeight(100)
            self.message_input.setStyleSheet("""
                QTextEdit {
                    background-color: white;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 8px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 14px;
                    line-height: 1.4;
                }
                QTextEdit:focus {
                    border-color: #2962FF;
                }
            """)

            # Добавляем обработку клавиши Enter
            self.message_input.installEventFilter(self)

            # Кнопки управления
            buttons_layout = QHBoxLayout()
            buttons_layout.setSpacing(10)

            send_button = QPushButton("Отправить")
            send_button.setObjectName("send_button")  # Добавляем имя для поиска
            send_button.setMinimumWidth(100)
            send_button.setEnabled(False)  # Изначально кнопка неактивна
            send_button.setStyleSheet("""
                QPushButton {
                    background-color: #2962FF;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #1E88E5;
                }
                QPushButton:pressed {
                    background-color: #1565C0;
                }
                QPushButton:disabled {
                    background-color: #BDBDBD;
                }
            """)
            send_button.clicked.connect(self.send_message)
            buttons_layout.addWidget(send_button)

            # Кнопка остановки генерации
            self.stop_generation_button = QPushButton("⏹ Стоп")
            self.stop_generation_button.setMinimumWidth(80)
            self.stop_generation_button.setEnabled(False)  # Изначально отключена
            self.stop_generation_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #d32f2f;
                }
                QPushButton:disabled {
                    background-color: #BDBDBD;
                }
            """)
            self.stop_generation_button.clicked.connect(self.stop_generation)
            buttons_layout.addWidget(self.stop_generation_button)

            input_layout.addWidget(self.message_input)
            input_layout.addLayout(buttons_layout)
            chat_layout.addLayout(input_layout)

            splitter.addWidget(chat_panel)

            # Правая панель (настройки)
            self.model_settings = ModelSettings()
            self.model_settings.setMinimumWidth(250)
            self.model_settings.setMaximumWidth(350)
            self.model_settings.settings_saved.connect(self.on_model_settings_saved)

            # Загружаем текущие настройки из API в интерфейс
            current_settings = self.api.get_current_settings()
            runtime_settings = current_settings.get('runtime_settings', {})
            model_settings = current_settings.get('model_settings', {})

            # Объединяем настройки для загрузки в интерфейс
            interface_settings = {**runtime_settings, **model_settings}
            self.model_settings.load_settings(interface_settings)

            splitter.addWidget(self.model_settings)

            # Настраиваем размеры сплиттера
            splitter.setStretchFactor(0, 0)  # Левая панель - фиксированная
            splitter.setStretchFactor(1, 1)  # Центральная панель - растягивается
            splitter.setStretchFactor(2, 0)  # Правая панель - фиксированная

            # Подключаем сигналы
            self.model_combo.currentTextChanged.connect(self.on_model_changed)

            # Таймер обновления моделей
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_models)
            self.update_timer.start(5000)  # Каждые 5 секунд

            # Первое обновление списка моделей
            # self.update_models()

        except Exception as ui_error:
            logging.error(f"Ошибка создания интерфейса: {str(ui_error)}")
            raise

    def update_models(self):
        """Обновление списка моделей"""
        if not hasattr(self, 'initialization_complete') or not self.initialization_complete:
            logging.warning("Пропуск обновления моделей - инициализация не завершена")
            return

        try:
            # Сохраняем текущую модель
            current = self.model_combo.currentText().split(" (")[
                0] if self.model_combo.currentText() else None

            # Получаем новый список моделей
            models = self.api.get_models()
            if not isinstance(models, list):
                raise ValueError("Неверный формат данных моделей")

            # Если список моделей не изменился, пропускаем обновление
            new_models = set(
                model['name'] for model in models if isinstance(model, dict) and 'name' in model)
            current_models = set(self.model_combo.itemText(i).split(" (")[0]
                                 for i in range(self.model_combo.count()))

            if new_models == current_models and current in new_models:
                return  # Пропускаем обновление, если список не изменился

            # Защита от одновременного обновления
            self.model_combo.blockSignals(True)

            try:
                # Очищаем и обновляем список
                self.model_combo.clear()

                if not models:
                    self.model_combo.addItem("Нет установленных моделей")
                    self.update_model_status("Нет моделей", True)
                    self.current_model = None
                    return

                # Добавляем модели в список
                for model in models:
                    if not isinstance(model, dict) or 'name' not in model:
                        continue

                    name = model.get('name', '')
                    size = model.get('size', 'Размер неизвестен')

                    if not name:
                        continue

                    # Модель считается готовой к работе, если она установлена
                    # Загрузка в память происходит при первом запросе генерации
                    status = " (Готова)"

                    self.model_combo.addItem(f"{name}{status} ({size})")

                    # Добавляем в список доступных моделей
                    self.api.running_models.add(name)

                # Восстанавливаем выбранную модель или выбираем первую
                if current and current in new_models:
                    index = self.model_combo.findText(current, Qt.MatchFlag.MatchStartsWith)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                        self.current_model = current
                        # Модель готова к работе
                        self.update_model_status(f"Модель готова: {current}")
                        logging.info(f"Восстановлена ранее выбранная модель: {current}")
                elif self.model_combo.count() > 0:
                    # Автоматически выбираем первую доступную модель
                    self.model_combo.setCurrentIndex(0)
                    self.current_model = self.model_combo.currentText().split(" (")[0]
                    self.update_model_status(f"Модель готова: {self.current_model}")
                    logging.info(f"Автоматически выбрана первая доступная модель: {self.current_model}")

            finally:
                self.model_combo.blockSignals(False)
                self.model_combo.setEnabled(True)

        except Exception as e:
            logging.error(f"Ошибка при обновлении списка моделей: {str(e)}")
            self.model_combo.clear()
            self.model_combo.addItem(f"Ошибка: {str(e)}")
            self.update_model_status("Ошибка обновления", True)
            self.current_model = None
            # Отключаем кнопку отправки при ошибке
            send_button = self.findChild(QPushButton, "send_button")
            if send_button:
                send_button.setEnabled(False)

    def update_model_status(self, status: str, is_error: bool = False):
        """Обновление статуса модели"""
        color = "#D32F2F" if is_error else "#2E7D32"
        self.model_status.setText(f"Статус: {status}")
        self.model_status.setStyleSheet(f"color: {color}; margin-top: 5px;")

    def _update_buttons_state(self, is_available: bool):
        """Обновление состояния кнопок в зависимости от доступности модели"""
        # Активируем/деактивируем кнопку отправки
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(is_available)

    def check_model_availability(self):
        """Проверка доступности модели"""
        if not self.current_model:
            QApplication.processEvents()
            return False

        try:
            # Проверяем, установлена ли модель (доступна для использования)
            models = self.api.get_models()
            model_names = [model['name'] for model in models]

            if self.current_model in model_names:
                # Модель установлена и доступна для генерации
                # Загрузка в память произойдет при первом запросе
                self.chat_history.add_system_message(f"✅ Модель {self.current_model} готова к работе")
                self.update_model_status(f"Модель готова: {self.current_model}")
                # Активируем кнопку отправки
                send_button = self.findChild(QPushButton, "send_button")
                if send_button:
                    send_button.setEnabled(True)
                    QApplication.processEvents()
                self._update_buttons_state(True)
                return True
            else:
                self.chat_history.add_system_message(
                    f"❌ Модель {self.current_model} не установлена")
                self.update_model_status(f"Модель не установлена", True)
                self._update_buttons_state(False)
                return False

        except Exception as e:
            error_msg = str(e)
            self.chat_history.add_system_message(f"❌ Ошибка при проверке модели: {error_msg}")
            self.update_model_status(f"Ошибка: {error_msg[:50]}...", True)
            self._update_buttons_state(False)
            return False

    def on_model_changed(self, model_text: str):
        """Обработка смены модели"""
        try:
            if not model_text or "Нет установленных моделей" in model_text or "Ошибка:" in model_text:
                self.current_model = None
                self.update_model_status("Не выбрана", True)
                self.chat_history.add_system_message("⚠️ Модель не выбрана")
                self._update_buttons_state(False)
                return

            try:
                self.current_model = model_text.split(" (")[0]
                if not self.current_model:
                    raise ValueError("Пустое имя модели")
                logging.info(f"Выбрана модель: {self.current_model}")
            except Exception as e:
                logging.error(f"Ошибка при получении имени модели: {str(e)}")
                self.current_model = None
                self.update_model_status("Ошибка выбора модели", True)
                self._update_buttons_state(False)
                return

            self.chat_history.add_system_message(f"🔄 Проверка модели: {self.current_model}")
            self.update_model_status("Проверка модели...")

            # Модель проверяется автоматически

            if self.check_model_availability():
                # Состояние кнопок уже обновлено в check_model_availability
                pass
            else:
                self.chat_history.add_system_message(
                    "⚠️ Рекомендации:\n"
                    "1. Проверьте, что Ollama запущен\n"
                    "2. Попробуйте перезапустить Ollama\n"
                    "3. Проверьте наличие свободной памяти\n"
                    "4. Проверьте журнал Ollama на наличие ошибок"
                )
                self._update_buttons_state(False)

        except Exception as e:
            logging.error(f"Ошибка при смене модели: {str(e)}")
            self.update_model_status("Ошибка смены модели", True)
            self._update_buttons_state(False)

    def send_message(self):
        """Отправка сообщения"""
        if not self.current_model:
            logging.warning("Попытка отправки сообщения без выбранной модели")
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите модель")
            return
        messages = self.message_input.toPlainText().strip()
        if not messages:
            logging.info("Сообщение пустое, не отправляем")
            return
        logging.info(f"Отправка сообщения: {messages}")
        logging.info(f"Отправка сообщения модели {self.current_model}")
        # Блокируем кнопку отправки и поле ввода
        self.message_input.setReadOnly(True)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(False)
        # Включаем кнопку остановки
        self.stop_generation_button.setEnabled(True)
        # Добавляем сообщение пользователя
        self.chat_history.add_message(messages, True)
        self.message_input.clear()
        # Обновляем статус
        self.update_model_status(f"Генерация ответа...")
        try:
            # Получаем все параметры модели
            params = self.model_settings.get_parameters()
            logging.info(f"Параметры модели для генерации: {params}")
            # Сохраняем время начала генерации
            self.generation_start_time = time.time()
            self.total_tokens = 0
            # Создаем и запускаем поток для обработки сообщения
            self.message_thread = MessageThread(
                self.api,
                self.current_model,
                self.messages,
                **params
            )
            self.messages.append({"role": "user", "content": messages})
            # Подключаем сигналы
            self.message_thread.message_chunk.connect(self.on_message_chunk)
            self.message_thread.finished.connect(self.on_message_complete)
            self.message_thread.error.connect(self.on_message_error)
            self.message_thread.performance_info.connect(
                lambda perf: self.chat_history.add_performance_info(perf))
            # Подключаем сигнал расширенной статистики с проверкой
            try:
                self.message_thread.extended_stats.connect(self.on_extended_stats)
            except Exception as e:
                logging.warning(f"Не удалось подключить сигнал extended_stats: {e}")
            # Запускаем поток
            self.message_thread.start()
        except Exception as e:
            import traceback
            error_msg = f"Ошибка при отправке сообщения: {e}\n{traceback.format_exc()}"
            logging.error(error_msg)
            self.on_message_error(error_msg)

    def on_message_chunk(self, chunk: str):
        self.current_response += chunk
        """Обработка части ответа от модели"""
        self.chat_history.add_message_chunk(chunk)
        if self.total_tokens is not None:
            self.total_tokens += 1  # Увеличиваем счетчик токенов

    def on_message_complete(self):
        """Обработка завершения генерации ответа"""
        # Собираем информацию о производительности
        if self.generation_start_time is not None:
            total_time = time.time() - self.generation_start_time
        else:
            total_time = 0.0

        performance_info = {
            'total_time': total_time,
            'tokens': self.total_tokens or 0,
            'model': self.current_model
        }

        # Добавляем информацию о производительности в текущее сообщение
        # Вместо создания нового сообщения
        # Сохраняем данные для использования в add_message

        # Обновляем последнее сообщение (можно реализовать через сохранение ссылки)
        # Для простоты: перезаписываем последнее сообщение
        # ВАЖНО: эта часть требует доработки для корректного обновления
        # (например, хранить список сообщений и обновлять последний элемент)
        # Добавляем сообщение ассистента в историю
        self.chat_history.add_message(self.current_response, False, performance_info)
        self.messages.append({"role": "assistant", "content": self.current_response})
        self.current_response = ""

        # Разблокируем интерфейс
        #self.chat_history.add_message("", False, self.message_thread.performance_info)
        self.message_input.setReadOnly(False)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(True)
        # Отключаем кнопку остановки
        self.stop_generation_button.setEnabled(False)
        self.update_model_status(f"Готова к работе: {self.current_model}")

        # Отключаем поток
        if hasattr(self, 'message_thread') and self.message_thread is not None:
            self.message_thread.deleteLater()
            self.message_thread = None

    def on_extended_stats(self, stats: dict):
        """Обработка расширенной статистики"""
        # Обновляем общую статистику сессии
        if not hasattr(self, 'session_stats'):
            self.session_stats = {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_generations': 0,
                'total_time': 0.0
            }

        self.session_stats['total_input_tokens'] += stats.get('input_tokens', 0)
        self.session_stats['total_output_tokens'] += stats.get('output_tokens', 0)
        self.session_stats['total_generations'] += 1
        self.session_stats['total_time'] += stats.get('total_time', 0.0)

        # Обновляем отображение расширенной статистики
        self.chat_history.add_extended_performance_info(stats)

    def on_message_error(self, error_msg: str):
        """Обработка ошибки при генерации ответа"""
        import traceback
        trace = traceback.format_exc()
        print(f"Ошибка генерации ответа: {error_msg}\n{trace}")
        logging.error(f"Ошибка генерации ответа: {error_msg}\n{trace}")
        self.update_model_status(f"Ошибка генерации", True)
        self.chat_history.add_message(f"❌ Ошибка: {error_msg}\n{trace}", False)

        # Разблокируем интерфейс
        self.message_input.setReadOnly(False)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(True)
        # Отключаем кнопку остановки
        self.stop_generation_button.setEnabled(False)

        # Проверяем доступность модели после ошибки
        if not self.check_model_availability():
            self.chat_history.add_message(
                "⚠️ Модель недоступна. Попробуйте:\n"
                "1. Проверить статус Ollama\n"
                "2. Перезапустить модель\n"
                "3. Переустановить модель",
                False
            )


    def stop_generation(self):
        """Остановка текущей генерации"""
        if hasattr(self, 'message_thread') and self.message_thread is not None:
            logging.info("Остановка генерации по запросу пользователя")
            self.message_thread.cancel()
            self.chat_history.add_system_message("⏹️ Генерация остановлена")
            # Разблокируем интерфейс
            self.message_input.setReadOnly(False)
            send_button = self.findChild(QPushButton, "send_button")
            if send_button:
                send_button.setEnabled(True)
            self.stop_generation_button.setEnabled(False)
            self.update_model_status(f"Готова к работе: {self.current_model}")

    def on_model_settings_saved(self, settings: dict):
        """Обработка сохранения настроек модели"""
        try:
            logging.info(f"Настройки модели сохранены: {settings}")

            # Синхронизируем с системными настройками
            sync_result = self.api.sync_with_user_settings(settings)

            if sync_result['needs_restart']:
                self.chat_history.add_system_message(
                    f"🔄 Критические параметры изменены: {', '.join(sync_result['critical_params_changed'])}"
                )
                self.chat_history.add_system_message("🔄 Перезапуск сервера Ollama...")
                self.update_model_status("Перезапуск сервера...")

                # Проверяем статус сервера после перезапуска
                import time
                time.sleep(3)

                # Проверяем доступность API
                is_available, version = self.api.is_available()
                if is_available:
                    self.chat_history.add_system_message("✅ Сервер Ollama перезапущен и готов к работе")
                    self.update_model_status(f"Модель готова: {self.current_model}")
                else:
                    self.chat_history.add_system_message("⚠️ Сервер Ollama не отвечает после перезапуска")
                    self.update_model_status("Ошибка сервера", True)
            else:
                self.chat_history.add_system_message("✅ Настройки модели применены")

            # Обновляем локальные настройки модели
            self.model_settings.load_settings(settings)

        except Exception as e:
            logging.error(f"Ошибка при сохранении настроек модели: {str(e)}")
            self.chat_history.add_system_message(f"❌ Ошибка применения настроек: {str(e)}")

    def _toggle_model_settings(self):
        """Показать/скрыть панель настроек модели"""
        if self.model_settings.isVisible():
            self.model_settings.hide()
        else:
            self.model_settings.show()

    def _show_ollama_settings(self):
        """Открыть окно настроек Ollama"""
        try:
            settings_dialog = OllamaSettings(self)
            settings_dialog.show()  # Используем show() вместо exec()
        except Exception as e:
            logging.error(f"Ошибка при открытии настроек Ollama: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть настройки: {str(e)}")

    def _show_optimization_info(self):
        """Показать информацию об оптимизации"""
        try:
            # Получаем информацию об оптимизации
            optimization_info = self.api.get_current_settings()

            # Создаем диалоговое окно
            dialog = QDialog(self)
            dialog.setWindowTitle("Информация об оптимизации")
            dialog.setMinimumWidth(600)
            dialog.setMinimumHeight(400)

            layout = QVBoxLayout(dialog)

            # Системная информация
            system_group = QGroupBox("Системные характеристики")
            system_layout = QFormLayout()

            system_info = optimization_info.get('system_info', {})
            system_layout.addRow("Платформа:", QLabel(str(system_info.get('platform', 'Неизвестно'))))
            system_layout.addRow("Процессор:", QLabel(str(system_info.get('processor', 'Неизвестно'))))
            system_layout.addRow("Ядер CPU:", QLabel(str(system_info.get('cpu_count', 'Неизвестно'))))
            system_layout.addRow("Память (ГБ):", QLabel(str(system_info.get('memory_gb', 'Неизвестно'))))
            system_layout.addRow("GPU:", QLabel(str(system_info.get('gpu', 'Неизвестно'))))
            system_layout.addRow("Память GPU (ГБ):", QLabel(str(system_info.get('gpu_memory_gb', 'Неизвестно'))))

            system_group.setLayout(system_layout)
            layout.addWidget(system_group)

            # Серверные настройки
            server_group = QGroupBox("Серверные настройки")
            server_layout = QFormLayout()

            server_settings = optimization_info.get('server_settings', {})
            for key, value in server_settings.items():
                server_layout.addRow(key + ":", QLabel(str(value)))

            server_group.setLayout(server_layout)
            layout.addWidget(server_group)

            # Runtime настройки
            runtime_group = QGroupBox("Runtime настройки")
            runtime_layout = QFormLayout()

            runtime_settings = optimization_info.get('runtime_settings', {})
            for key, value in runtime_settings.items():
                runtime_layout.addRow(key + ":", QLabel(str(value)))

            runtime_group.setLayout(runtime_layout)
            layout.addWidget(runtime_group)

            # Настройки модели
            model_group = QGroupBox("Настройки модели")
            model_layout = QFormLayout()

            model_settings = optimization_info.get('model_settings', {})
            for key, value in model_settings.items():
                model_layout.addRow(key + ":", QLabel(str(value)))

            model_group.setLayout(model_layout)
            layout.addWidget(model_group)

            # Кнопки
            buttons_layout = QHBoxLayout()

            reload_btn = QPushButton("🔄 Перезагрузить оптимизацию")
            reload_btn.clicked.connect(lambda: self._reload_optimization(dialog))
            buttons_layout.addWidget(reload_btn)

            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(dialog.accept)
            buttons_layout.addWidget(close_btn)

            layout.addLayout(buttons_layout)

            dialog.exec()

        except Exception as e:
            logging.error(f"Ошибка при отображении информации об оптимизации: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось отобразить информацию об оптимизации: {str(e)}")

    def _reload_optimization(self, dialog):
        """Перезагрузка оптимизации"""
        try:
            if self.api.reload_optimization():
                QMessageBox.information(self, "Успешно", "Оптимизация перезагружена")
                # Обновляем информацию в диалоге
                self._show_optimization_info()
                dialog.accept()
            else:
                QMessageBox.warning(self, "Ошибка", "Не удалось перезагрузить оптимизацию")
        except Exception as e:
            logging.error(f"Ошибка при перезагрузке оптимизации: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Ошибка при перезагрузке: {str(e)}")

    def _apply_user_settings_to_server(self):
        """Применение пользовательских настроек к серверу"""
        try:
            # Получаем текущие настройки модели
            user_settings = self.model_settings.get_parameters()

            # Синхронизируем с системными настройками
            sync_result = self.api.sync_with_user_settings(user_settings)

            if sync_result['needs_restart']:
                self.chat_history.add_system_message(
                    f"🔄 Критические параметры изменены: {', '.join(sync_result['critical_params_changed'])}"
                )
                self.chat_history.add_system_message("🔄 Применение настроек к серверу...")
                self.update_model_status("Применение настроек...")

                # Проверяем статус сервера
                import time
                time.sleep(2)

                # Проверяем доступность API
                is_available, version = self.api.is_available()
                if is_available:
                    self.chat_history.add_system_message("✅ Настройки применены к серверу")
                    self.update_model_status(f"Модель готова: {self.current_model}")
                else:
                    self.chat_history.add_system_message("⚠️ Сервер не отвечает после применения настроек")
                    self.update_model_status("Ошибка сервера", True)
            else:
                self.chat_history.add_system_message("✅ Настройки модели применены")

        except Exception as e:
            logging.error(f"Ошибка при применении настроек к серверу: {str(e)}")
            self.chat_history.add_system_message(f"❌ Ошибка применения настроек: {str(e)}")


    def _show_jan_settings(self):
        """Открыть окно настроек Ollama"""
        try:
            # Сохраняем ссылку на окно как атрибут класса
            if not hasattr(self, '_jan_settings_window'):
                self._jan_settings_window = JanSettingsWindow()
            self._jan_settings_window.show()
            self._jan_settings_window.raise_()  # Поднимаем окно на передний план
            self._jan_settings_window.activateWindow()  # Активируем окно
        except Exception as e:
            logging.error(f"Ошибка при открытии настроек Jan: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось открыть настройки: {str(e)}")

    def _show_session_stats(self):
        """Показать статистику сессии"""
        try:
            if not hasattr(self, 'session_stats') or not self.session_stats.get('total_generations', 0):
                QMessageBox.information(self, "Статистика сессии", "Пока нет данных о генерациях")
                return

            stats = self.session_stats

            # Создаем диалоговое окно
            dialog = QDialog(self)
            dialog.setWindowTitle("Статистика сессии")
            dialog.setMinimumWidth(500)
            dialog.setMinimumHeight(300)

            layout = QVBoxLayout(dialog)

            # Заголовок
            title_label = QLabel("📊 Общая статистика сессии")
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
            layout.addWidget(title_label)

            # Статистика
            stats_group = QGroupBox("Показатели")
            stats_layout = QFormLayout()

            total_generations = stats.get('total_generations', 0)
            total_input = stats.get('total_input_tokens', 0)
            total_output = stats.get('total_output_tokens', 0)
            total_time = stats.get('total_time', 0.0)

            avg_time = total_time / total_generations if total_generations > 0 else 0
            avg_input = total_input / total_generations if total_generations > 0 else 0
            avg_output = total_output / total_generations if total_generations > 0 else 0
            total_tokens = total_input + total_output

            stats_layout.addRow("Генераций:", QLabel(str(total_generations)))
            stats_layout.addRow("Входных токенов:", QLabel(f"{total_input:,}"))
            stats_layout.addRow("Выходных токенов:", QLabel(f"{total_output:,}"))
            stats_layout.addRow("Всего токенов:", QLabel(f"{total_tokens:,}"))
            stats_layout.addRow("Общее время:", QLabel(f"{total_time:.2f}с"))
            stats_layout.addRow("Среднее время:", QLabel(f"{avg_time:.2f}с"))
            stats_layout.addRow("Средний ввод:", QLabel(f"{avg_input:.0f} токенов"))
            stats_layout.addRow("Средний вывод:", QLabel(f"{avg_output:.0f} токенов"))

            stats_group.setLayout(stats_layout)
            layout.addWidget(stats_group)

            # Кнопки
            buttons_layout = QHBoxLayout()

            reset_btn = QPushButton("🔄 Сбросить статистику")
            reset_btn.clicked.connect(lambda: self._reset_session_stats(dialog))
            buttons_layout.addWidget(reset_btn)

            close_btn = QPushButton("Закрыть")
            close_btn.clicked.connect(dialog.accept)
            buttons_layout.addWidget(close_btn)

            layout.addLayout(buttons_layout)

            dialog.exec()

        except Exception as e:
            logging.error(f"Ошибка при отображении статистики сессии: {str(e)}")
            QMessageBox.warning(self, "Ошибка", f"Не удалось отобразить статистику: {str(e)}")

    def _reset_session_stats(self, dialog):
        """Сброс статистики сессии"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите сбросить всю статистику сессии?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.session_stats = {
                'total_input_tokens': 0,
                'total_output_tokens': 0,
                'total_generations': 0,
                'total_time': 0.0
            }
            self.chat_history.add_system_message("📊 Статистика сессии сброшена")
            dialog.accept()

    def clear_chat(self):
        """Очистка истории чата"""
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            "Вы уверены, что хотите очистить историю чата?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Очищаем историю чата
            self.chat_history.clear()
