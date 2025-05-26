"""
Настройки стилей интерфейса
"""

# Цвета
BACKGROUND_COLOR = "#FFFFFF"
BORDER_COLOR = "#E0E0E0"
HOVER_BORDER_COLOR = "#BDBDBD"
HOVER_BACKGROUND_COLOR = "#FAFAFA"
SELECTION_COLOR = "#E3F2FD"
PRIMARY_COLOR = "#2196F3"
SECONDARY_COLOR = "#757575"
SYSTEM_MESSAGE_COLOR = "#1565C0"
USER_MESSAGE_COLOR = "#2962FF"

# Шрифты
FONT_FAMILY = "'Segoe UI', Arial, sans-serif"
FONT_SIZE = "14px"
FONT_SIZE_SMALL = "12px"

# Размеры
PADDING = "8px"
PADDING_SMALL = "4px"
BORDER_RADIUS = "8px"
BORDER_RADIUS_SMALL = "4px"
SPACING = "10px"

# QSS Шаблоны
MESSAGE_WIDGET_STYLE = f"""
    MessageWidget {{
        background-color: {BACKGROUND_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: {BORDER_RADIUS};
        margin: 5px;
    }}
    MessageWidget:hover {{
        border-color: {HOVER_BORDER_COLOR};
        background-color: {HOVER_BACKGROUND_COLOR};
    }}
"""

TEXT_EDIT_STYLE = f"""
    QTextEdit {{
        background-color: {BACKGROUND_COLOR};
        border: none;
        padding: {PADDING};
        font-family: {FONT_FAMILY};
        font-size: {FONT_SIZE};
        line-height: 1.4;
        selection-background-color: {SELECTION_COLOR};
    }}
"""

MODEL_SETTINGS_STYLE = f"""
    QGroupBox {{
        background-color: {BACKGROUND_COLOR};
        border: 1px solid {BORDER_COLOR};
        border-radius: {BORDER_RADIUS_SMALL};
        margin-top: 12px;
        padding-top: 16px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: {PADDING_SMALL} {PADDING};
        background-color: #F5F5F5;
        border: 1px solid {BORDER_COLOR};
        border-radius: {BORDER_RADIUS_SMALL};
    }}
    QSpinBox, QDoubleSpinBox {{
        padding: {PADDING_SMALL};
        border: 1px solid {BORDER_COLOR};
        border-radius: {BORDER_RADIUS_SMALL};
    }}
    QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: {PRIMARY_COLOR};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {PRIMARY_COLOR};
        background-color: {SELECTION_COLOR};
    }}
    QTextEdit {{
        border: 1px solid {BORDER_COLOR};
        border-radius: {BORDER_RADIUS_SMALL};
        padding: {PADDING_SMALL};
    }}
    QTextEdit:focus {{
        border-color: {PRIMARY_COLOR};
        background-color: {SELECTION_COLOR};
    }}
    QLabel[tooltip] {{
        color: {SECONDARY_COLOR};
        font-style: italic;
    }}
"""