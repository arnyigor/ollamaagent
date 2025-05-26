from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame, QVBoxLayout, QScrollArea, QWidget, QLabel,
    QGroupBox, QFormLayout, QDoubleSpinBox, QSpinBox,
    QTextEdit
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
        self.setStyleSheet(MODEL_SETTINGS_STYLE)

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