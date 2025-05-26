from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QTextEdit

TEXT_EDIT_STYLE = """
    QTextEdit {
        background-color: transparent;
        border: none;
        padding: 5px;
        font-size: 14px;
        color: #333;
    }
"""

MESSAGE_WIDGET_STYLE = """
    QFrame {
        background-color: #FFFFFF;
        border-radius: 8px;
        border: 1px solid #E0E0E0;
        margin: 5px 0;
        padding: 10px;
    }
"""

class MessageWidget(QFrame):
    """Виджет для отображения одного сообщения в чате"""

    def __init__(self, text: str, is_user: bool = False, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)

        layout = QVBoxLayout(self)
        layout.setSpacing(5)

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