import logging
import subprocess
import sys

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel,
    QSplitter, QFrame, QScrollArea, QSpinBox, QDoubleSpinBox,
    QMessageBox
)

from ollama_api import OllamaAPI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
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
        header = QLabel("Вы" if is_user else "Ассистент")
        header.setStyleSheet(
            "font-weight: bold; color: #2962FF;" if is_user else "font-weight: bold; color: #00838F;")
        layout.addWidget(header)

        # Текст сообщения в QTextEdit
        message = QTextEdit()
        message.setReadOnly(True)
        message.setPlainText(text)
        message.setFrameStyle(QFrame.Shape.NoFrame)
        message.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                border: none;
                padding: 8px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.4;
                selection-background-color: #E3F2FD;
            }
        """)
        
        # Автоматическая высота
        doc_height = message.document().size().height()
        message.setFixedHeight(int(min(doc_height + 20, 400)))
        message.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        layout.addWidget(message)

        # Стилизация фрейма
        self.setStyleSheet("""
            MessageWidget {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
                margin: 5px;
            }
            MessageWidget:hover {
                border-color: #BDBDBD;
                background-color: #FAFAFA;
            }
        """)


class ChatHistory(QScrollArea):
    """Виджет для отображения истории чата"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)

        # Основной контейнер
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Текстовое поле для истории чата
        self.chat_text = QTextEdit()
        self.chat_text.setReadOnly(True)
        self.chat_text.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        layout.addWidget(self.chat_text)

        self.setWidget(container)
        
        # Стилизация скролла
        self.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: white;
            }
            QScrollBar:vertical {
                border: none;
                background: #F5F5F5;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #BDBDBD;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
        """)

    def add_message(self, text: str, is_user: bool = False):
        """Добавление нового сообщения в чат"""
        # Форматируем сообщение
        sender = "Вы" if is_user else "Ассистент"
        color = "#2962FF" if is_user else "#00838F"
        
        # Добавляем сообщение в формате HTML
        message_html = f"""
            <div style="margin-bottom: 10px;">
                <div style="font-weight: bold; color: {color};">{sender}:</div>
                <div style="margin-left: 10px; white-space: pre-wrap;">{text}</div>
            </div>
        """
        
        # Добавляем сообщение в конец
        cursor = self.chat_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertHtml(message_html)
        
        # Прокручиваем к последнему сообщению
        self.chat_text.verticalScrollBar().setValue(
            self.chat_text.verticalScrollBar().maximum()
        )

    def clear(self):
        """Очистка истории чата"""
        self.chat_text.clear()


class ModelSettings(QFrame):
    """Панель настроек модели"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Заголовок
        header = QLabel("Настройки модели")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        # Температура
        temp_layout = QHBoxLayout()
        temp_label = QLabel("Температура:")
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        temp_layout.addWidget(temp_label)
        temp_layout.addWidget(self.temp_spin)
        layout.addLayout(temp_layout)

        # Максимальное количество токенов
        tokens_layout = QHBoxLayout()
        tokens_label = QLabel("Макс. токенов:")
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1, 4096)
        self.tokens_spin.setValue(2048)
        tokens_layout.addWidget(tokens_label)
        tokens_layout.addWidget(self.tokens_spin)
        layout.addLayout(tokens_layout)

        # Системный промпт
        layout.addWidget(QLabel("Системный промпт:"))
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("Введите системный промпт...")
        self.system_prompt.setMaximumHeight(100)
        layout.addWidget(self.system_prompt)

        layout.addStretch()

        # Стилизация
        self.setStyleSheet("""
            ModelSettings {
                background-color: #F5F5F5;
                border-radius: 8px;
                padding: 10px;
            }
        """)


class ModelThread(QThread):
    """Поток для работы с моделью"""
    operation_complete = pyqtSignal(bool, str)  # Сигнал о завершении операции (успех, сообщение)
    
    def __init__(self, api, operation, model_name):
        super().__init__()
        self.api = api
        self.operation = operation  # 'start' или 'stop'
        self.model_name = model_name
        
    def run(self):
        """Выполнение операции в отдельном потоке"""
        try:
            if self.operation == 'start':
                success = self.api.run_model(self.model_name)
                if success:
                    self.operation_complete.emit(True, "Модель успешно запущена")
                else:
                    self.operation_complete.emit(False, "Не удалось запустить модель")
            elif self.operation == 'stop':
                success = self.api.stop_model(self.model_name)
                if success:
                    self.operation_complete.emit(True, "Модель успешно остановлена")
                else:
                    self.operation_complete.emit(False, "Не удалось остановить модель")
        except Exception as e:
            self.operation_complete.emit(False, str(e))


class ChatWindow(QMainWindow):
    settings_requested = pyqtSignal()
    
    def __init__(self):
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
    
    def closeEvent(self, event):
        """Обработка события закрытия окна"""
        if not hasattr(self, 'initialization_complete') or not self.initialization_complete:
            logging.warning("Попытка закрыть окно во время инициализации")
            event.ignore()
            return
        
        event.accept()
    
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
            
            # Кнопки управления моделью
            model_controls = QHBoxLayout()
            self.start_model_btn = QPushButton("▶ Запустить")
            self.start_model_btn.clicked.connect(self.start_model)
            self.start_model_btn.setEnabled(False)  # Изначально кнопка неактивна
            model_controls.addWidget(self.start_model_btn)
            
            self.stop_model_btn = QPushButton("⏹ Остановить")
            self.stop_model_btn.clicked.connect(self.stop_model)
            self.stop_model_btn.setEnabled(False)
            model_controls.addWidget(self.stop_model_btn)
            
            left_layout.addLayout(model_controls)
            left_layout.addStretch()
            
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
            
            send_button = QPushButton("Отправить")
            send_button.setMinimumWidth(100)
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
            
            input_layout.addWidget(self.message_input)
            input_layout.addWidget(send_button)
            chat_layout.addLayout(input_layout)
            
            splitter.addWidget(chat_panel)
            
            # Правая панель (настройки)
            self.model_settings = ModelSettings()
            self.model_settings.setMinimumWidth(250)
            self.model_settings.setMaximumWidth(350)
            splitter.addWidget(self.model_settings)
            
            # Настраиваем размеры сплиттера
            splitter.setStretchFactor(0, 0)  # Левая панель - фиксированная
            splitter.setStretchFactor(1, 1)  # Центральная панель - растягивается
            splitter.setStretchFactor(2, 0)  # Правая панель - фиксированная
            
            # Создаем меню
            self.create_menu()
            
            # Подключаем сигналы
            self.model_combo.currentTextChanged.connect(self.on_model_changed)
            
            # Таймер обновления моделей
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self.update_models)
            self.update_timer.start(5000)  # Каждые 5 секунд
            
            # Первое обновление списка моделей
            self.update_models()
            
        except Exception as ui_error:
            logging.error(f"Ошибка создания интерфейса: {str(ui_error)}")
            raise
            
    def create_menu(self):
        """Создание главного меню"""
        menubar = self.menuBar()

        # Меню Файл
        file_menu = menubar.addMenu("Файл")

        new_chat = QAction("Новый чат", self)
        new_chat.setShortcut("Ctrl+N")
        new_chat.triggered.connect(self.new_chat)
        file_menu.addAction(new_chat)

        settings = QAction("Настройки", self)
        settings.setShortcut("Ctrl+,")
        settings.triggered.connect(self.show_settings)
        file_menu.addAction(settings)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Меню Правка
        edit_menu = menubar.addMenu("Правка")

        clear_chat = QAction("Очистить чат", self)
        clear_chat.triggered.connect(self.clear_chat)
        edit_menu.addAction(clear_chat)

    def update_models(self):
        """Обновление списка моделей"""
        if not hasattr(self, 'initialization_complete') or not self.initialization_complete:
            logging.warning("Пропуск обновления моделей - инициализация не завершена")
            return
            
        try:
            # Сохраняем текущую модель
            current = self.model_combo.currentText().split(" (")[0] if self.model_combo.currentText() else None
            
            # Получаем новый список моделей
            models = self.api.get_models()
            if not isinstance(models, list):
                raise ValueError("Неверный формат данных моделей")
                
            # Если список моделей не изменился, пропускаем обновление
            new_models = set(model['name'] for model in models if isinstance(model, dict) and 'name' in model)
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
                    self.start_model_btn.setEnabled(False)
                    return
                
                # Добавляем модели в список
                for model in models:
                    if not isinstance(model, dict) or 'name' not in model:
                        continue
                        
                    name = model.get('name', '')
                    size = model.get('size', 'Размер неизвестен')
                    
                    if not name:
                        continue
                    
                    # Проверяем, запущена ли модель
                    is_running = self.api.is_model_running(name)
                    status = " (Запущена)" if is_running else ""
                    
                    self.model_combo.addItem(f"{name}{status} ({size})")
                    
                    # Если модель запущена, добавляем её в список запущенных
                    if is_running:
                        self.api.running_models.add(name)
                
                # Восстанавливаем выбранную модель или выбираем первую
                if current and current in new_models:
                    index = self.model_combo.findText(current, Qt.MatchFlag.MatchStartsWith)
                    if index >= 0:
                        self.model_combo.setCurrentIndex(index)
                        self.current_model = current
                        # Проверяем состояние модели
                        if self.api.is_model_running(current):
                            self.update_model_status(f"Модель активна: {current}")
                            self.start_model_btn.setEnabled(False)
                            self.stop_model_btn.setEnabled(True)
                            self.model_combo.setEnabled(False)
                        else:
                            self.update_model_status(f"Модель выбрана: {current}")
                            self.start_model_btn.setEnabled(True)
                            self.stop_model_btn.setEnabled(False)
                        logging.info(f"Восстановлена ранее выбранная модель: {current}")
                elif self.model_combo.count() > 0:
                    self.model_combo.setCurrentIndex(0)
                    self.current_model = self.model_combo.currentText().split(" (")[0]
                    logging.info(f"Автоматически выбрана первая доступная модель: {self.current_model}")
                    # Проверяем состояние первой модели
                    if self.api.is_model_running(self.current_model):
                        self.update_model_status(f"Модель активна: {self.current_model}")
                        self.start_model_btn.setEnabled(False)
                        self.stop_model_btn.setEnabled(True)
                        self.model_combo.setEnabled(False)
                    else:
                        self.update_model_status(f"Модель выбрана: {self.current_model}")
                        self.start_model_btn.setEnabled(True)
                        self.stop_model_btn.setEnabled(False)
                
            finally:
                self.model_combo.blockSignals(False)
                self.model_combo.setEnabled(True)

        except Exception as e:
            logging.error(f"Ошибка при обновлении списка моделей: {str(e)}")
            self.model_combo.clear()
            self.model_combo.addItem(f"Ошибка: {str(e)}")
            self.update_model_status("Ошибка обновления", True)
            self.current_model = None
            self.start_model_btn.setEnabled(False)

    def update_model_status(self, status: str, is_error: bool = False):
        """Обновление статуса модели"""
        color = "#D32F2F" if is_error else "#2E7D32"
        self.model_status.setText(f"Статус: {status}")
        self.model_status.setStyleSheet(f"color: {color}; margin-top: 5px;")

    def check_model_availability(self):
        """Проверка доступности модели"""
        if not self.current_model:
            return False

        try:
            self.chat_history.add_message("🔄 Проверка модели...", False)

            # Пробуем отправить тестовый запрос
            response = self.api.generate(
                model=self.current_model,
                prompt="test",
                system="You are a helpful AI assistant. Please respond with 'OK' to confirm you are working.",
                temperature=0.7,
                max_tokens=10
            )

            # Проверяем ответ
            if response and response.strip():
                self.chat_history.add_message(f"✅ Тестовый запрос успешен. Ответ: {response}",
                                              False)
                return True
            else:
                self.chat_history.add_message("❌ Модель не вернула ответ", False)
                self.update_model_status("Ошибка: нет ответа", True)
                return False

        except Exception as e:
            error_msg = str(e)
            self.chat_history.add_message(f"❌ Ошибка при проверке модели: {error_msg}", False)
            self.update_model_status(f"Ошибка: {error_msg[:50]}...", True)
            return False

    def on_model_changed(self, model_text: str):
        """Обработка смены модели"""
        try:
            if not model_text or "Нет установленных моделей" in model_text or "Ошибка:" in model_text:
                self.current_model = None
                self.update_model_status("Не выбрана", True)
                self.chat_history.add_message("⚠️ Модель не выбрана", False)
                self.start_model_btn.setEnabled(False)
                self.stop_model_btn.setEnabled(False)
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
                return

            self.chat_history.add_message(f"🔄 Загрузка модели: {self.current_model}", False)
            self.update_model_status("Проверка модели...")
            
            # Отключаем элементы управления на время проверки
            self.model_combo.setEnabled(False)
            self.start_model_btn.setEnabled(False)
            self.stop_model_btn.setEnabled(False)
            
            if self.check_model_availability():
                self.update_model_status(f"Готова к работе: {self.current_model}")
                self.chat_history.add_message(
                    f"✅ Модель {self.current_model} успешно загружена и готова к работе", False)
                self.start_model_btn.setEnabled(True)
            else:
                self.chat_history.add_message(
                    "⚠️ Рекомендации:\n"
                    "1. Проверьте, что Ollama запущен\n"
                    "2. Попробуйте перезапустить Ollama\n"
                    "3. Проверьте наличие свободной памяти\n"
                    "4. Проверьте журнал Ollama на наличие ошибок",
                    False
                )
                self.start_model_btn.setEnabled(True)
        except Exception as e:
            logging.error(f"Ошибка при смене модели: {str(e)}")
            self.update_model_status("Ошибка смены модели", True)
        finally:
            self.model_combo.setEnabled(True)

    def send_message(self):
        """Отправка сообщения"""
        if not self.current_model:
            logging.warning("Попытка отправки сообщения без выбранной модели")
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите модель")
            return

        text = self.message_input.toPlainText().strip()
        if not text:
            return

        logging.info(f"Отправка сообщения модели {self.current_model}")

        # Добавляем сообщение пользователя
        self.chat_history.add_message(text, True)
        self.message_input.clear()

        # Обновляем статус
        self.update_model_status(f"Генерация ответа...")

        try:
            # Получаем настройки
            temperature = self.model_settings.temp_spin.value()
            max_tokens = self.model_settings.tokens_spin.value()
            system_prompt = self.model_settings.system_prompt.toPlainText().strip()

            logging.info(
                f"Настройки запроса: temp={temperature}, max_tokens={max_tokens}, system_prompt={system_prompt}")

            # Логируем настройки в чат
            self.chat_history.add_message(
                f"*Настройки запроса:*\n"
                f"- Модель: {self.current_model}\n"
                f"- Температура: {temperature}\n"
                f"- Макс. токенов: {max_tokens}\n"
                f"- Системный промпт: {system_prompt if system_prompt else 'не задан'}",
                False
            )

            # Генерируем ответ
            logging.info("Отправка запроса к API...")
            response = self.api.generate(
                model=self.current_model,
                prompt=text,
                system=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logging.info("Ответ получен")

            # Обновляем статус
            self.update_model_status(f"Готова к работе: {self.current_model}")

            # Добавляем ответ в чат
            self.chat_history.add_message(response, False)

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Ошибка генерации ответа: {error_msg}")
            self.update_model_status(f"Ошибка генерации", True)
            self.chat_history.add_message(f"❌ Ошибка: {error_msg}", False)

            # Проверяем доступность модели после ошибки
            if not self.check_model_availability():
                self.chat_history.add_message(
                    "⚠️ Модель недоступна. Попробуйте:\n"
                    "1. Проверить статус Ollama\n"
                    "2. Перезапустить модель\n"
                    "3. Переустановить модель",
                    False
                )

    def new_chat(self):
        """Создание нового чата"""
        pass

    def show_settings(self):
        """Показать окно настроек"""
        self.settings_requested.emit()

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

    def start_model(self):
        """Запуск модели"""
        if not self.current_model:
            logging.warning("Попытка запуска без выбранной модели")
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите модель")
            return

        # Защита от повторного запуска
        self.start_model_btn.setEnabled(False)
        self.model_combo.setEnabled(False)

        try:
            logging.info(f"Запуск модели: {self.current_model}")
            self.chat_history.add_message(
                f"🚀 Запуск модели {self.current_model}...\n"
                "⚠️ Это может занять некоторое время (30-60 секунд).\n"
                "Пожалуйста, подождите...", False)
            self.update_model_status("Запуск модели (это может занять время)...")

            # Создаем и запускаем поток
            self.model_thread = ModelThread(self.api, 'start', self.current_model)
            self.model_thread.operation_complete.connect(self.on_model_operation_complete)
            self.model_thread.start()

            # Запускаем таймер для обновления точек загрузки
            self.loading_timer = QTimer()
            self.loading_dots = 0
            self.loading_timer.timeout.connect(self.update_loading_status)
            self.loading_timer.start(500)  # Каждые 500 мс

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Ошибка запуска модели: {error_msg}")
            self.update_model_status("Ошибка запуска", True)
            self.chat_history.add_message(f"❌ Ошибка запуска модели: {error_msg}", False)
            self.start_model_btn.setEnabled(True)
            self.stop_model_btn.setEnabled(False)
            self.model_combo.setEnabled(True)

    def update_loading_status(self):
        """Обновление статуса загрузки"""
        self.loading_dots = (self.loading_dots + 1) % 4
        dots = "." * self.loading_dots
        self.update_model_status(f"Запуск модели{dots}")

    def on_model_operation_complete(self, success: bool, message: str):
        """Обработка завершения операции с моделью"""
        # Останавливаем таймер загрузки, если он есть
        if hasattr(self, 'loading_timer') and self.loading_timer.isActive():
            self.loading_timer.stop()

        if success:
            if "запущена" in message:
                self.update_model_status(f"Модель активна: {self.current_model}")
                self.chat_history.add_message("✅ " + message, False)
                self.stop_model_btn.setEnabled(True)
                self.start_model_btn.setEnabled(False)
                self.model_combo.setEnabled(False)
                logging.info(f"Модель {self.current_model} успешно запущена")
            else:  # остановлена
                self.update_model_status(f"Модель выбрана: {self.current_model}")
                self.chat_history.add_message("✅ " + message, False)
                self.start_model_btn.setEnabled(True)
                self.stop_model_btn.setEnabled(False)
                self.model_combo.setEnabled(True)
                logging.info(f"Модель {self.current_model} успешно остановлена")
        else:
            error_msg = message
            if "запуск" in self.model_status.text().lower():
                self.update_model_status("Ошибка запуска", True)
                self.start_model_btn.setEnabled(True)
                self.stop_model_btn.setEnabled(False)
                self.model_combo.setEnabled(True)
            else:
                self.update_model_status("Ошибка остановки", True)
                self.stop_model_btn.setEnabled(True)
                self.model_combo.setEnabled(False)
            self.chat_history.add_message(f"❌ Ошибка: {error_msg}", False)
            logging.error(f"Ошибка операции с моделью: {error_msg}")

        # Отключаем поток
        if hasattr(self, 'model_thread'):
            self.model_thread.operation_complete.disconnect()
            self.model_thread = None

    def stop_model(self):
        """Остановка модели"""
        if not self.current_model:
            return

        # Защита от повторной остановки
        self.stop_model_btn.setEnabled(False)

        try:
            logging.info(f"Остановка модели: {self.current_model}")
            self.chat_history.add_message(f"🛑 Остановка модели {self.current_model}...", False)
            self.update_model_status("Остановка модели...")

            # Создаем и запускаем поток
            self.model_thread = ModelThread(self.api, 'stop', self.current_model)
            self.model_thread.operation_complete.connect(self.on_model_operation_complete)
            self.model_thread.start()

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Ошибка остановки модели: {error_msg}")
            self.update_model_status("Ошибка остановки", True)
            self.chat_history.add_message(f"❌ Ошибка остановки модели: {error_msg}", False)
            self.stop_model_btn.setEnabled(True)
            self.model_combo.setEnabled(False)
