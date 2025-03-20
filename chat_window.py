import logging
import sys
import time

from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QComboBox, QLabel,
    QSplitter, QFrame, QScrollArea, QSpinBox, QDoubleSpinBox,
    QMessageBox, QGroupBox, QFormLayout
)

from lmstudio_settings import LmStudioSettings
from ollama_api import OllamaAPI
from ollama_settings import OllamaSettings

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)


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
        if not text.strip() and not performance_info:
            logging.info(
                f"Добавление обычного сообщения performance_info:{performance_info} text: {text}")
            return

        sender = "Вы" if is_user else "Ассистент"
        color = "#2962FF" if is_user else "#00838F"
        bg_color = "#F5F5F5" if is_user else "#FFFFFF"

        # Основной контейнер сообщения
        message_html = (
            f'<div style="margin: {"10px" if is_user else "25px"} 0; '
            f'padding: 12px; background-color: {bg_color}; '
            f'border-radius: 8px; border: 1px solid #E0E0E0;">'
        )

        # Заголовок сообщения (имя отправителя)
        if not performance_info:
            message_html += (
                f'<div style="font-weight: bold; color: {color}; '
                f'margin-bottom: 8px;"><br>{sender}</div>'
            )
        else:
            message_html += (
                f'<div style="font-weight: bold; color: {color}; '
                f'margin-bottom: 8px;"><br></div>'
            )

        # Текст сообщения
        if text.strip():
            message_html += (
                f'<div style="white-space: pre-wrap; margin-left: 10px;">'
                f'{text.strip()}</div>'
            )

        # Информация о производительности
        if not is_user and performance_info:
            tokens_per_sec = performance_info.get("tokens", 0) / max(
                performance_info.get("total_time", 1), 0.1
            )
            message_html += (
                f'<div style="margin-top: 10px; padding: 5px; '
                f'background-color: #FAFAFA; border-top: 1px solid #E0E0E0; '
                f'font-size: 12px; color: #757575;">'
                f'⚡ Время: {performance_info.get("total_time", 0):.2f}с | '
                f'🔄 Токенов: {performance_info.get("tokens", 0)} '
                f'({tokens_per_sec:.1f} т/с) | '
                f'⚙️ Модель: {performance_info.get("model", "неизвестно")}'
                f'</div>'
            )

        message_html += '</div>'
        self._insert_message_safely(message_html)
        # log_prefix = "Пользователь" if is_user else "Ассистент"
        # logging.info(f"{log_prefix} message_html: {message_html}")

    def add_message_chunk(self, chunk: str):
        """
        Добавление части сообщения в режиме потоковой генерации
        """
        # logging.info(
        #     f"Добавление части сообщения: {chunk}, is_system_message: {self.is_system_message}")
        if not chunk or self.is_system_message:
            return

        # Инициализация нового сообщения, если это первый чанк
        if self.response_start_pos is None:
            self.response_start_pos = self.textCursor().position()
            self.current_message_html = (
                '<div style="margin: 25px 0; padding: 12px; '
                'background-color: #FFFFFF; border-radius: 8px; '
                'border: 1px solid #E0E0E0;">'
                '<div style="white-space: pre-wrap; margin-left: 10px;">'
            )
            self._insert_message_safely(self.current_message_html)

        # Добавляем пробел перед чанком, если нужно
        if chunk and not chunk.startswith(' ') and not self.current_message_html.endswith(' '):
            chunk = ' ' + chunk

        # Вставляем чанк
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(chunk)
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
            self.current_message_html += '</div></div>'
            cursor = self.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertHtml('</div></div>')
            self.response_start_pos = None
            self.current_message_html = ""


class ModelSettings(QFrame):
    """Панель настроек модели"""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Создаем скролл для настроек
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Создаем контейнер для настроек
        container = QWidget()
        settings_layout = QVBoxLayout(container)
        settings_layout.setSpacing(10)

        # Заголовок
        header = QLabel("Настройки модели")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        settings_layout.addWidget(header)

        # Базовые настройки
        basic_group = QGroupBox("Базовые настройки")
        basic_layout = QFormLayout()

        # Температура
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0.0, 2.0)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        self.temp_spin.setToolTip(
            "Контролирует случайность генерации (0.0 - детерминированная, 2.0 - максимально случайная)")
        basic_layout.addRow("Температура:", self.temp_spin)

        # Максимальное количество токенов
        self.tokens_spin = QSpinBox()
        self.tokens_spin.setRange(1, 4096)
        self.tokens_spin.setValue(2048)
        self.tokens_spin.setToolTip("Максимальное количество токенов в ответе")
        basic_layout.addRow("Макс. токенов:", self.tokens_spin)

        basic_group.setLayout(basic_layout)
        settings_layout.addWidget(basic_group)

        # Продвинутые настройки
        advanced_group = QGroupBox("Продвинутые настройки")
        advanced_layout = QFormLayout()

        # Top-K
        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 100)
        self.top_k_spin.setValue(40)
        self.top_k_spin.setToolTip(
            "Количество токенов для выборки (больше значение - более разнообразные ответы)")
        advanced_layout.addRow("Top-K:", self.top_k_spin)

        # Top-P
        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.0, 1.0)
        self.top_p_spin.setSingleStep(0.05)
        self.top_p_spin.setValue(0.9)
        self.top_p_spin.setToolTip(
            "Порог вероятности для выборки токенов (меньше значение - более консервативные ответы)")
        advanced_layout.addRow("Top-P:", self.top_p_spin)

        # Repeat Penalty
        self.repeat_penalty_spin = QDoubleSpinBox()
        self.repeat_penalty_spin.setRange(1.0, 2.0)
        self.repeat_penalty_spin.setSingleStep(0.1)
        self.repeat_penalty_spin.setValue(1.1)
        self.repeat_penalty_spin.setToolTip(
            "Штраф за повторение токенов (больше значение - меньше повторений)")
        advanced_layout.addRow("Repeat Penalty:", self.repeat_penalty_spin)

        # Presence Penalty
        self.presence_penalty_spin = QDoubleSpinBox()
        self.presence_penalty_spin.setRange(-2.0, 2.0)
        self.presence_penalty_spin.setSingleStep(0.1)
        self.presence_penalty_spin.setValue(0.0)
        self.presence_penalty_spin.setToolTip("Штраф за использование существующих токенов")
        advanced_layout.addRow("Presence Penalty:", self.presence_penalty_spin)

        # Frequency Penalty
        self.frequency_penalty_spin = QDoubleSpinBox()
        self.frequency_penalty_spin.setRange(-2.0, 2.0)
        self.frequency_penalty_spin.setSingleStep(0.1)
        self.frequency_penalty_spin.setValue(0.0)
        self.frequency_penalty_spin.setToolTip("Штраф за частое использование токенов")
        advanced_layout.addRow("Frequency Penalty:", self.frequency_penalty_spin)

        # TFS-Z
        self.tfs_z_spin = QDoubleSpinBox()
        self.tfs_z_spin.setRange(0.0, 2.0)
        self.tfs_z_spin.setSingleStep(0.1)
        self.tfs_z_spin.setValue(1.0)
        self.tfs_z_spin.setToolTip("Параметр хвостового свободного сэмплирования")
        advanced_layout.addRow("TFS-Z:", self.tfs_z_spin)

        advanced_group.setLayout(advanced_layout)
        settings_layout.addWidget(advanced_group)

        # Mirostat настройки
        mirostat_group = QGroupBox("Mirostat настройки")
        mirostat_layout = QFormLayout()

        # Mirostat mode
        self.mirostat_spin = QSpinBox()
        self.mirostat_spin.setRange(0, 2)
        self.mirostat_spin.setValue(0)
        self.mirostat_spin.setToolTip("Режим Mirostat (0 - выкл, 1 - v1, 2 - v2)")
        mirostat_layout.addRow("Mirostat режим:", self.mirostat_spin)

        # Mirostat tau
        self.mirostat_tau_spin = QDoubleSpinBox()
        self.mirostat_tau_spin.setRange(0.0, 10.0)
        self.mirostat_tau_spin.setSingleStep(0.1)
        self.mirostat_tau_spin.setValue(5.0)
        self.mirostat_tau_spin.setToolTip("Целевая энтропия Mirostat")
        mirostat_layout.addRow("Mirostat tau:", self.mirostat_tau_spin)

        # Mirostat eta
        self.mirostat_eta_spin = QDoubleSpinBox()
        self.mirostat_eta_spin.setRange(0.0, 1.0)
        self.mirostat_eta_spin.setSingleStep(0.01)
        self.mirostat_eta_spin.setValue(0.1)
        self.mirostat_eta_spin.setToolTip("Скорость обучения Mirostat")
        mirostat_layout.addRow("Mirostat eta:", self.mirostat_eta_spin)

        mirostat_group.setLayout(mirostat_layout)
        settings_layout.addWidget(mirostat_group)

        # Системный промпт
        system_group = QGroupBox("Системный промпт")
        system_layout = QVBoxLayout()
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("Введите системный промпт...")
        self.system_prompt.setMaximumHeight(100)
        system_layout.addWidget(self.system_prompt)
        system_group.setLayout(system_layout)
        settings_layout.addWidget(system_group)

        # Добавляем растягивающийся элемент в конец
        settings_layout.addStretch()

        # Устанавливаем контейнер в скролл
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Стилизация
        self.setStyleSheet("""
            QGroupBox {
                background-color: #FFFFFF;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 16px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QSpinBox, QDoubleSpinBox {
                padding: 4px;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover {
                border-color: #2196F3;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border-color: #2196F3;
                background-color: #E3F2FD;
            }
            QTextEdit {
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                padding: 4px;
            }
            QTextEdit:focus {
                border-color: #2196F3;
                background-color: #E3F2FD;
            }
            QLabel[tooltip] {
                color: #757575;
                font-style: italic;
            }
        """)

    def get_parameters(self) -> dict:
        """Получение всех параметров модели"""
        return {
            'temperature': self.temp_spin.value(),
            'max_tokens': self.tokens_spin.value(),
            'top_k': self.top_k_spin.value(),
            'top_p': self.top_p_spin.value(),
            'repeat_penalty': self.repeat_penalty_spin.value(),
            'presence_penalty': self.presence_penalty_spin.value(),
            'frequency_penalty': self.frequency_penalty_spin.value(),
            'tfs_z': self.tfs_z_spin.value(),
            'mirostat': self.mirostat_spin.value(),
            'mirostat_tau': self.mirostat_tau_spin.value(),
            'mirostat_eta': self.mirostat_eta_spin.value(),
            'system': self.system_prompt.toPlainText().strip()
        }


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


class MessageThread(QThread):
    """Поток для отправки и получения сообщений"""
    message_chunk = pyqtSignal(str)  # Сигнал для частей ответа
    finished = pyqtSignal()  # Сигнал о завершении
    error = pyqtSignal(str)  # Сигнал об ошибке

    def __init__(self, api, model, prompt, system, **kwargs):
        super().__init__()
        self.api = api
        self.model = model
        self.prompt = prompt
        self.system = system
        self.kwargs = kwargs  # Сохраняем все дополнительные параметры

    def run(self):
        try:
            # Генерируем ответ с обработкой чанков
            for chunk in self.api.generate_stream(
                    model=self.model,
                    prompt=self.prompt,
                    system=self.system,
                    **self.kwargs  # Передаем все параметры
            ):
                if chunk:
                    self.message_chunk.emit(chunk)
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

    def closeEvent(self, event):
        """Обработка события закрытия окна"""
        if not hasattr(self, 'initialization_complete') or not self.initialization_complete:
            logging.warning("Попытка закрыть окно во время инициализации")
            event.ignore()
            return

        try:
            # Останавливаем все запущенные модели
            logging.info("Остановка всех моделей перед закрытием...")
            self.api.stop_all_models()

            # Останавливаем таймер обновления
            if hasattr(self, 'update_timer') and self.update_timer is not None:
                self.update_timer.stop()

            # Очищаем потоки
            if hasattr(self, 'model_thread') and self.model_thread is not None:
                self.model_thread.quit()
                self.model_thread.wait()
                self.model_thread = None

            if hasattr(self, 'message_thread') and self.message_thread is not None:
                self.message_thread.quit()
                self.message_thread.wait()
                self.message_thread = None

        except Exception as e:
            logging.error(f"Ошибка при закрытии приложения: {str(e)}")

        event.accept()


class ChatWindow(QMainWindow):
    settings_requested = pyqtSignal()

    def __init__(self):
        self.logger = logging.getLogger('OllamaAPI')
        self.message_thread = None
        self.total_tokens = None
        self.generation_start_time = None
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

        try:
            # Останавливаем все запущенные модели
            logging.info("Остановка всех моделей перед закрытием...")
            self.api.stop_all_models()

            # Останавливаем таймер обновления
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()

            # Очищаем потоки
            if hasattr(self, 'model_thread'):
                self.model_thread.quit()
                self.model_thread.wait()

            if hasattr(self, 'message_thread'):
                self.message_thread.quit()
                self.message_thread.wait()

        except Exception as e:
            logging.error(f"Ошибка при закрытии приложения: {str(e)}")

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
            self.start_model_btn.setEnabled(False)
            self.start_model_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                }
                QPushButton:hover { background-color: #45a049; }
                QPushButton:pressed { background-color: #3d8b40; }
                QPushButton:disabled { background-color: #BDBDBD; }
            """)
            model_controls.addWidget(self.start_model_btn)

            self.stop_model_btn = QPushButton("⏹ Остановить")
            self.stop_model_btn.clicked.connect(self.stop_model)
            self.stop_model_btn.setEnabled(False)
            self.stop_model_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px;
                }
                QPushButton:hover { background-color: #da190b; }
                QPushButton:pressed { background-color: #d32f2f; }
                QPushButton:disabled { background-color: #BDBDBD; }
            """)
            model_controls.addWidget(self.stop_model_btn)

            left_layout.addLayout(model_controls)

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

            left_layout.addLayout(settings_layout)

            # Добавляем группу для кнопки настроек LmStudio
            lmstudio_group = QGroupBox("Настройки LmStudio")
            lmstudio_layout = QVBoxLayout()

            self.lmstudio_btn = QPushButton("🔧 Настройки LmStudio")
            self.lmstudio_btn.setToolTip("Открыть настройки LmStudio для текущей модели")
            self.lmstudio_btn.clicked.connect(self.show_lmstudio_settings)

            lmstudio_layout.addWidget(self.lmstudio_btn)
            lmstudio_group.setLayout(lmstudio_layout)
            settings_layout.addWidget(lmstudio_group)  # Добавляем группу в layout

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

            # Добавляем обработку клавиши Enter
            self.message_input.installEventFilter(self)

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
                    logging.info(
                        f"Автоматически выбрана первая доступная модель: {self.current_model}")
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

    def show_lmstudio_settings(self):
        """Показывает окно настроек LMStudio"""
        try:
            settings_dialog = LmStudioSettings(self)
            settings_dialog.show()
        except Exception as e:
            self.logger.error(f"Ошибка при открытии", str(e), exc_info=True)
            logging.error(f"Ошибка при открытии")

    def update_model_status(self, status: str, is_error: bool = False):
        """Обновление статуса модели"""
        color = "#D32F2F" if is_error else "#2E7D32"
        self.model_status.setText(f"Статус: {status}")
        self.model_status.setStyleSheet(f"color: {color}; margin-top: 5px;")

    def _update_buttons_state(self, is_running: bool):
        """Обновление состояния кнопок в зависимости от состояния модели"""
        if is_running:
            # Модель запущена
            self.start_model_btn.setEnabled(False)
            self.stop_model_btn.setEnabled(True)
            self.model_combo.setEnabled(True)  # Разрешаем смену модели на лету
            # Активируем кнопку отправки
            send_button = self.findChild(QPushButton, "send_button")
            if send_button:
                send_button.setEnabled(True)
        else:
            # Модель остановлена
            self.start_model_btn.setEnabled(True)
            self.stop_model_btn.setEnabled(False)
            self.model_combo.setEnabled(True)
            # Деактивируем кнопку отправки
            send_button = self.findChild(QPushButton, "send_button")
            if send_button:
                send_button.setEnabled(False)

    def check_model_availability(self):
        """Проверка доступности модели"""
        if not self.current_model:
            # Деактивируем кнопку отправки
            send_button = self.findChild(QPushButton, "send_button")
            if send_button:
                send_button.setEnabled(False)
                QApplication.processEvents()
            return False

        try:
            # Проверяем, запущена ли уже модель
            is_running = self.api.is_model_running(self.current_model)

            if is_running:
                self.chat_history.add_system_message(f"✅ Модель {self.current_model} активна")
                self.update_model_status(f"Модель активна: {self.current_model}")
                # Активируем кнопку отправки
                send_button = self.findChild(QPushButton, "send_button")
                if send_button:
                    send_button.setEnabled(True)
                    QApplication.processEvents()
                self._update_buttons_state(True)
                return True
            else:
                # Пробуем запустить модель автоматически
                success = self.api.run_model(self.current_model)
                if success:
                    self.chat_history.add_system_message(
                        f"✅ Модель {self.current_model} запущена автоматически")
                    self.update_model_status(f"Модель активна: {self.current_model}")
                    send_button = self.findChild(QPushButton, "send_button")
                    if send_button:
                        send_button.setEnabled(True)
                        QApplication.processEvents()
                    self._update_buttons_state(True)
                    return True
                else:
                    self.chat_history.add_system_message(
                        f"❌ Не удалось запустить модель {self.current_model}")
                    self.update_model_status(f"Ошибка запуска модели", True)
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

            # Временно отключаем кнопки во время проверки
            self.start_model_btn.setEnabled(False)
            self.stop_model_btn.setEnabled(False)

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
        text = self.message_input.toPlainText().strip()
        if not text:
            logging.info("Сообщение пустое, не отправляем")
            return
        logging.info(f"Отправка сообщения: {text}")
        logging.info(f"Отправка сообщения модели {self.current_model}")
        # Блокируем кнопку отправки и поле ввода
        self.message_input.setReadOnly(True)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(False)
        # Добавляем сообщение пользователя
        self.chat_history.add_message(text, True)
        self.message_input.clear()
        # Обновляем статус
        self.update_model_status(f"Генерация ответа...")
        try:
            # Получаем все параметры модели
            params = self.model_settings.get_parameters()
            # Сохраняем время начала генерации
            self.generation_start_time = time.time()
            self.total_tokens = 0
            # Создаем и запускаем поток для обработки сообщения
            self.message_thread = MessageThread(
                self.api,
                self.current_model,
                text,
                params.pop('system'),  # Извлекаем системный промпт
                **params  # Передаем все остальные параметры
            )
            # Подключаем сигналы
            self.message_thread.message_chunk.connect(self.on_message_chunk)
            self.message_thread.finished.connect(self.on_message_complete)
            self.message_thread.error.connect(self.on_message_error)
            # Запускаем поток
            self.message_thread.start()
        except Exception as e:
            logging.error(f"Ошибка при отправке сообщения: {e}")
            self.on_message_error(str(e))

    def on_message_chunk(self, chunk: str):
        """Обработка части ответа от модели"""
        self.chat_history.add_message_chunk(chunk)
        self.total_tokens += 1  # Увеличиваем счетчик токенов

    def on_message_complete(self):
        """Обработка завершения генерации ответа"""
        # Собираем информацию о производительности
        total_time = time.time() - self.generation_start_time
        performance_info = {
            'total_time': total_time,
            'tokens': self.total_tokens,
            'model': self.current_model
        }

        # Добавляем информацию о производительности в текущее сообщение
        # Вместо создания нового сообщения
        self.message_thread.performance_info = performance_info  # Сохраняем данные

        # Обновляем последнее сообщение (можно реализовать через сохранение ссылки)
        # Для простоты: перезаписываем последнее сообщение
        # ВАЖНО: эта часть требует доработки для корректного обновления
        # (например, хранить список сообщений и обновлять последний элемент)
        # Временное решение:
        # Добавляем пустую строку и информацию о производительности
        self.chat_history.add_message("", False, performance_info)

        # Разблокируем интерфейс
        self.message_input.setReadOnly(False)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(True)
        self.update_model_status(f"Готова к работе: {self.current_model}")

        # Отключаем поток
        if hasattr(self, 'message_thread'):
            self.message_thread.deleteLater()
            self.message_thread = None

    def on_message_error(self, error_msg: str):
        """Обработка ошибки при генерации ответа"""
        logging.error(f"Ошибка генерации ответа: {error_msg}")
        self.update_model_status(f"Ошибка генерации", True)
        self.chat_history.add_message(f"❌ Ошибка: {error_msg}", False)

        # Разблокируем интерфейс
        self.message_input.setReadOnly(False)
        send_button = self.findChild(QPushButton, "send_button")
        if send_button:
            send_button.setEnabled(True)

        # Проверяем доступность модели после ошибки
        if not self.check_model_availability():
            self.chat_history.add_message(
                "⚠️ Модель недоступна. Попробуйте:\n"
                "1. Проверить статус Ollama\n"
                "2. Перезапустить модель\n"
                "3. Переустановить модель",
                False
            )

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
        self.start_model_btn.setEnabled(False)

        try:
            logging.info(f"Остановка модели: {self.current_model}")
            self.chat_history.add_message(f"🛑 Остановка модели {self.current_model}...", False)
            self.update_model_status("Остановка модели...")

            # Создаем и запускаем поток
            self.model_thread = ModelThread(self.api, 'stop', self.current_model)
            self.model_thread.operation_complete.connect(self.on_model_operation_complete)
            self.model_thread.start()

            # Обновляем состояние API
            if self.current_model in self.api.running_models:
                self.api.running_models.remove(self.current_model)

        except Exception as e:
            error_msg = str(e)
            logging.error(f"Ошибка остановки модели: {error_msg}")
            self.update_model_status("Ошибка остановки", True)
            self.chat_history.add_message(f"❌ Ошибка остановки модели: {error_msg}", False)
            self.stop_model_btn.setEnabled(True)
            self.model_combo.setEnabled(False)

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

    def eventFilter(self, obj, event):
        """Обработка событий для поля ввода"""
        if obj is self.message_input and event.type() == event.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                if event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter - новая строка
                    return False
                else:
                    # Enter - отправка сообщения
                    self.send_message()
                    return True
        return super().eventFilter(obj, event)
