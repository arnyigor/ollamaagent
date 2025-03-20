import re
import sys
from PyQt6.QtCore import Qt, QRegularExpression
from PyQt6.QtGui import QTextCharFormat, QColor, QSyntaxHighlighter
from PyQt6.QtWidgets import QApplication, QTextEdit, QVBoxLayout, QWidget

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.code_format = QTextCharFormat()
        self.code_format.setBackground(QColor(240, 240, 240))

        # Паттерны для поиска блоков кода
        self.patterns = [
            (QRegularExpression(r"```([\s\S]*?)```"), 3, 3),  # Тройные кавычки
            (QRegularExpression(r"`([^`]*)`"), 1, 1)          # Одинарные кавычки
        ]

    def highlightBlock(self, text):
        for pattern, start_len, end_len in self.patterns:
            matches = pattern.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                start = match.capturedStart() + start_len
                length = match.capturedLength() - start_len - end_len
                self.setFormat(start, length, self.code_format)

class CodeTextEdit(QTextEdit):
    def __init__(self):
        super().__init__()
        self.processor = CodeProcessor()
        self.highlighter = PythonHighlighter(self.document())
        self.textChanged.connect(self.process_code_blocks)
        self._processing = False

    def process_code_blocks(self):
        if self._processing:
            return
        self._processing = True

        cursor = self.textCursor()
        cursor.beginEditBlock()

        original = self.toPlainText()
        processed = self.processor.process(original)

        if processed != original:
            cursor.select(cursor.SelectionType.Document)
            cursor.insertText(processed)

        cursor.endEditBlock()
        self._processing = False

class CodeProcessor:
    @staticmethod
    def process(text):
        # Удаляем тройные кавычки
        text = re.sub(r"```([\s\S]*?)```", r"\1", text)
        # Удаляем одинарные кавычки
        text = re.sub(r"`([^`]*)`", r"\1", text)
        return text

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QWidget()
    layout = QVBoxLayout()

    text_edit = CodeTextEdit()
    text_edit.setPlainText("""
        Примеры кода:
        `print("Hello")` → станет без кавычек
        ```def func():
            print("Multiline")``` → содержимое без ```
        Смешанный `код` и текст
    """)

    layout.addWidget(text_edit)
    window.setLayout(layout)
    window.show()
    sys.exit(app.exec())