import logging
from PyQt6.QtWidgets import QPushButton, QVBoxLayout, QComboBox, QMessageBox, QDialog
from PyQt6.QtCore import pyqtSignal, QThread, QObject
import lmstudio as lms

class ModelLoaderWorker(QObject):
    models_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def load_models(self):
        try:
            models = lms.list_downloaded_models()
            self.models_loaded.emit(models)  # Передаем объекты моделей, а не только имена
        except Exception as e:
            self.error_occurred.emit(str(e))

class LmStudioSettings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки LmStudio")
        self.setMinimumWidth(200)
        self.logger = logging.getLogger('LmStudio')
        self.logger.setLevel(logging.DEBUG)
        self.current_model = None
        self.models = []  # Теперь храним объекты моделей
        self.model_names = []
        self.layout = QVBoxLayout()

        self.model_combo = QComboBox()
        self.model_combo.setEnabled(False)
        self.model_combo.currentIndexChanged.connect(self._update_button_state)
        self.layout.addWidget(self.model_combo)

        self.param_model_button = QPushButton("Данные модели")
        self.param_model_button.clicked.connect(self._show_settings)
        self.param_model_button.setEnabled(False)
        self.layout.addWidget(self.param_model_button)

        self.setLayout(self.layout)

        # Инициализация потока загрузки моделей
        self._load_models()

    def _load_models(self):
        self.worker = ModelLoaderWorker()
        self.thread = QThread()
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.load_models)
        self.worker.models_loaded.connect(self._on_models_loaded)
        self.thread.start()

    def _on_models_loaded(self, models):
        self.models = models  # Сохраняем объекты моделей
        self.model_names = [model.info.display_name for model in models]
        self.model_combo.clear()
        self.model_combo.addItems(self.model_names)
        self.model_combo.setEnabled(True)
        self.thread.quit()
        self.thread.wait()
        self._update_button_state()

    def _update_button_state(self):
        selected_model_name = self.model_combo.currentText()
        if not selected_model_name:
            self.current_model = None
            self.param_model_button.setEnabled(False)
            return

        # Ищем модель в списке объектов
        for model in self.models:
            if model.info.display_name == selected_model_name:
                self.current_model = model
                self.param_model_button.setEnabled(True)
                return

        self.current_model = None
        self.param_model_button.setEnabled(False)
        QMessageBox.warning(
            self,
            "Ошибка",
            f"Модель {selected_model_name} не найдена"
        )

    def _show_settings(self):
        if not self.current_model:
            QMessageBox.warning(self, "Ошибка", "Модель не выбрана")
            return

        try:
            info = self.current_model.info
            info_str = (
                f"Имя: {info.display_name}\n"
                f"Размер: {self.format_max_context_length(info.size_bytes)}\n"
                f"Количество параметров: {info.params_string}\n"
                f"Макс. контекст: {info.max_context_length // 1024}К\n"
                f"Архитектура: {info.architecture}\n"
                f"Была обучена для использования инструментов: {info.trained_for_tool_use}\n"
                f"Визуализация: {info.vision}"
            )
            QMessageBox.information(self, "Параметры модели", info_str)
        except Exception as e:
            self.logger.error(f"Ошибка: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Ошибка", "Не удалось получить данные модели")

    def format_max_context_length(self, max_context_length):
        # Преобразование байт в килобайты
        kilobytes = max_context_length / 1024
        if kilobytes < 1024:
            return f"{kilobytes:.2f} КБ"
        else:
            megabytes = kilobytes / 1024
            return f"{megabytes:.2f} МБ"