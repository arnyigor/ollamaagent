from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QScrollArea, QWidget, QLabel,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QTextEdit, QCheckBox, QPushButton, QHBoxLayout
)

MODEL_SETTINGS_STYLE = """
    QFrame {
        background-color: #FFFFFF;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
        padding: 10px;
    }
    
    QGroupBox {
        font-weight: bold;
        border: 1px solid #E0E0E0;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 15px;
    }
    
    QGroupBox::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 3px;
    }
    
    QSpinBox, QDoubleSpinBox {
        padding: 5px;
        border: 1px solid #E0E0E0;
        border-radius: 4px;
    }
    
    QTextEdit {
        border: 1px solid #E0E0E0;
        border-radius: 4px;
        padding: 5px;
    }
"""

class ModelSettings(QFrame):
    """Панель настроек модели"""

    settings_saved = pyqtSignal(dict)  # Сигнал с сохраненными настройками

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

        # Настройки аппаратного обеспечения
        hardware_group = QGroupBox("Настройки аппаратного обеспечения")
        hardware_layout = QFormLayout()

        # Количество потоков
        self.num_thread_spin = QSpinBox()
        self.num_thread_spin.setRange(1, 64)
        self.num_thread_spin.setValue(4)
        self.num_thread_spin.setToolTip("Количество потоков процессора для использования")
        hardware_layout.addRow("Количество потоков:", self.num_thread_spin)

        # Количество GPU
        self.num_gpu_spin = QSpinBox()
        self.num_gpu_spin.setRange(0, 8)
        self.num_gpu_spin.setValue(1)
        self.num_gpu_spin.setToolTip("Количество GPU для использования (0 - только CPU)")
        hardware_layout.addRow("Количество GPU:", self.num_gpu_spin)

        # Основной GPU
        self.main_gpu_spin = QSpinBox()
        self.main_gpu_spin.setRange(0, 7)
        self.main_gpu_spin.setValue(0)
        self.main_gpu_spin.setToolTip("Индекс основного GPU")
        hardware_layout.addRow("Основной GPU:", self.main_gpu_spin)

        # Слои GPU
        self.gpu_layers_spin = QSpinBox()
        self.gpu_layers_spin.setRange(0, 100)
        self.gpu_layers_spin.setValue(0)
        self.gpu_layers_spin.setToolTip("Количество слоев для загрузки на GPU")
        hardware_layout.addRow("Слои GPU:", self.gpu_layers_spin)

        # Контекст
        self.num_ctx_spin = QSpinBox()
        self.num_ctx_spin.setRange(512, 32768)
        self.num_ctx_spin.setValue(2048)
        self.num_ctx_spin.setToolTip("Максимальный размер контекста")
        hardware_layout.addRow("Контекст:", self.num_ctx_spin)

        # Низкая память VRAM
        self.low_vram_check = QCheckBox()
        self.low_vram_check.setChecked(False)
        self.low_vram_check.setToolTip("Включить режим низкой памяти VRAM")
        hardware_layout.addRow("Низкая память VRAM:", self.low_vram_check)

        # Rope frequency base
        self.rope_freq_base_spin = QDoubleSpinBox()
        self.rope_freq_base_spin.setRange(0.0, 10000.0)
        self.rope_freq_base_spin.setSingleStep(100.0)
        self.rope_freq_base_spin.setValue(10000.0)
        self.rope_freq_base_spin.setToolTip("Базовая частота RoPE")
        hardware_layout.addRow("RoPE freq base:", self.rope_freq_base_spin)

        # Rope frequency scale
        self.rope_freq_scale_spin = QDoubleSpinBox()
        self.rope_freq_scale_spin.setRange(0.0, 100.0)
        self.rope_freq_scale_spin.setSingleStep(0.1)
        self.rope_freq_scale_spin.setValue(1.0)
        self.rope_freq_scale_spin.setToolTip("Масштаб частоты RoPE")
        hardware_layout.addRow("RoPE freq scale:", self.rope_freq_scale_spin)

        hardware_group.setLayout(hardware_layout)
        settings_layout.addWidget(hardware_group)

        # Системный промпт
        system_group = QGroupBox("Системный промпт")
        system_layout = QVBoxLayout()
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("Введите системный промпт...")
        self.system_prompt.setMaximumHeight(100)
        system_layout.addWidget(self.system_prompt)
        system_group.setLayout(system_layout)
        settings_layout.addWidget(system_group)

        # Кнопка сохранения настроек
        save_button = QPushButton("Сохранить настройки")
        save_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        save_button.clicked.connect(self.save_settings)
        settings_layout.addWidget(save_button)

        # Добавляем растягивающийся элемент в конец
        settings_layout.addStretch()

        # Устанавливаем контейнер в скролл
        scroll.setWidget(container)
        layout.addWidget(scroll)

        # Стилизация
        self.setStyleSheet(MODEL_SETTINGS_STYLE)

    def save_settings(self):
        """Сохранение настроек модели"""
        settings = self.get_parameters()
        print(f"Сохранение настроек модели: {settings}")
        self.settings_saved.emit(settings)
        # Можно добавить визуальную обратную связь
        print("Настройки модели сохранены")

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
            'num_thread': self.num_thread_spin.value(),
            'num_gpu': self.num_gpu_spin.value(),
            'main_gpu': self.main_gpu_spin.value(),
            'gpu_layers': self.gpu_layers_spin.value(),
            'num_ctx': self.num_ctx_spin.value(),
            'low_vram': self.low_vram_check.isChecked(),
            'rope_frequency_base': self.rope_freq_base_spin.value(),
            'rope_frequency_scale': self.rope_freq_scale_spin.value(),
            'system': self.system_prompt.toPlainText().strip()
        }

    def load_settings(self, settings: dict):
        """Загрузка настроек в интерфейс"""
        try:
            if 'temperature' in settings:
                self.temp_spin.setValue(settings['temperature'])
            if 'max_tokens' in settings:
                self.tokens_spin.setValue(settings['max_tokens'])
            if 'top_k' in settings:
                self.top_k_spin.setValue(settings['top_k'])
            if 'top_p' in settings:
                self.top_p_spin.setValue(settings['top_p'])
            if 'repeat_penalty' in settings:
                self.repeat_penalty_spin.setValue(settings['repeat_penalty'])
            if 'presence_penalty' in settings:
                self.presence_penalty_spin.setValue(settings['presence_penalty'])
            if 'frequency_penalty' in settings:
                self.frequency_penalty_spin.setValue(settings['frequency_penalty'])
            if 'tfs_z' in settings:
                self.tfs_z_spin.setValue(settings['tfs_z'])
            if 'mirostat' in settings:
                self.mirostat_spin.setValue(settings['mirostat'])
            if 'mirostat_tau' in settings:
                self.mirostat_tau_spin.setValue(settings['mirostat_tau'])
            if 'mirostat_eta' in settings:
                self.mirostat_eta_spin.setValue(settings['mirostat_eta'])
            if 'num_thread' in settings:
                self.num_thread_spin.setValue(settings['num_thread'])
            if 'num_gpu' in settings:
                self.num_gpu_spin.setValue(settings['num_gpu'])
            if 'main_gpu' in settings:
                self.main_gpu_spin.setValue(settings['main_gpu'])
            if 'gpu_layers' in settings:
                self.gpu_layers_spin.setValue(settings['gpu_layers'])
            if 'num_ctx' in settings:
                self.num_ctx_spin.setValue(settings['num_ctx'])
            if 'low_vram' in settings:
                self.low_vram_check.setChecked(settings['low_vram'])
            if 'rope_frequency_base' in settings:
                self.rope_freq_base_spin.setValue(settings['rope_frequency_base'])
            if 'rope_frequency_scale' in settings:
                self.rope_freq_scale_spin.setValue(settings['rope_frequency_scale'])
            if 'system' in settings:
                self.system_prompt.setPlainText(settings['system'])
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")