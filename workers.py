import logging
import time

from PyQt6.QtCore import QThread, pyqtSignal


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
    performance_info = pyqtSignal(dict)  # Сигнал с информацией о производительности

    def __init__(self, api, model, messages, **kwargs):
        super().__init__()
        self.api = api
        self.model = model
        self.messages = messages
        self.kwargs = kwargs

    def run(self):
        try:
            # Формируем историю сообщений для отправки в API
            api_messages = self.messages

            # Отправляем запрос в API
            full_response = []
            start_time = time.time()
            for chunk in self.api.generate_stream(
                    model=self.model,
                    messages=api_messages,
                    **self.kwargs
            ):
                if chunk:
                    full_response.append(chunk)
                    self.message_chunk.emit(chunk)
            
            # Добавляем информацию о производительности
            if full_response:
                performance = {
                    "total_time": time.time() - start_time,
                    "tokens": sum(len(chunk.split()) for chunk in full_response),
                    "model": self.model
                }
                self.performance_info.emit(performance)
            
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