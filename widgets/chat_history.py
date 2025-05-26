from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTextEdit, QApplication
from PyQt6.QtGui import QTextCursor

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
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText('\n')
        self._insert_message_safely(info_html)

    def add_message_chunk(self, chunk: str):
        """
        Добавление части сообщения в режиме потоковой генерации
        """
        if not chunk or self.is_system_message:
            return

        if self.response_start_pos is None:
            self.response_start_pos = self.textCursor().position()
            self.current_message_text = ""

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
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
        cursor.movePosition(QTextCursor.MoveOperation.End)
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
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText('\n')
            self._scroll_to_bottom()
            self.response_start_pos = None
            self.current_message_text = ""