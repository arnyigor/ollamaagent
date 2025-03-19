import json
import requests
import atexit
from typing import List, Dict, Tuple, Optional

class OllamaAPI:
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip('/')
        self.running_models = set()
        # Регистрируем функцию очистки при выходе
        atexit.register(self.cleanup)
        
    def cleanup(self):
        """Остановка всех запущенных моделей при выходе"""
        for model in list(self.running_models):
            try:
                self.stop_model(model)
            except Exception as e:
                print(f"Ошибка при остановке модели {model}: {e}")
                
    def get_models(self) -> List[Dict[str, str]]:
        """Получение списка установленных моделей"""
        try:
            response = requests.get(f"{self.host}/api/tags")
            response.raise_for_status()
            data = response.json()
            
            models = []
            for model in data.get('models', []):
                name = model.get('name', '')
                size = model.get('size', 'Размер неизвестен')
                if name:
                    models.append({
                        "name": name,
                        "size": size
                    })
            return models
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ошибка при получении списка моделей: {str(e)}")

    def run_model(self, model: str) -> bool:
        """Запуск модели"""
        try:
            # Проверяем, не запущена ли уже модель
            if self.is_model_running(model):
                self.running_models.add(model)
                return True
                
            # Отправляем тестовый запрос для запуска модели
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": model,
                    "prompt": "test",
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                self.running_models.add(model)
                return True
            return False
            
        except requests.exceptions.Timeout:
            # Для некоторых моделей это нормально
            self.running_models.add(model)
            return True
        except Exception as e:
            raise Exception(f"Ошибка запуска модели: {str(e)}")

    def stop_model(self, model: str) -> bool:
        """Остановка модели"""
        try:
            # В новом API нет прямого метода для остановки модели
            # Модель выгружается автоматически после истечения keep_alive
            self.running_models.discard(model)
            return True
        except Exception as e:
            raise Exception(f"Ошибка остановки модели: {str(e)}")

    def generate(self, model: str, prompt: str, system: str = "", temperature: float = 0.7, max_tokens: int = 2048) -> str:
        """Генерация ответа от модели"""
        try:
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            if system:
                data["system"] = system
            
            response = requests.post(
                f"{self.host}/api/generate",
                json=data,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get('response', '').strip()
            
        except requests.exceptions.Timeout:
            raise Exception("Превышено время ожидания ответа от модели")
        except Exception as e:
            raise Exception(f"Ошибка при генерации ответа: {str(e)}")

    def is_available(self) -> Tuple[bool, str]:
        """Проверка доступности Ollama"""
        try:
            response = requests.get(f"{self.host}/api/version")
            response.raise_for_status()
            data = response.json()
            return True, f"ollama version is {data.get('version', 'unknown')}"
        except requests.exceptions.ConnectionError:
            return False, "Ollama не найден или недоступен"
        except requests.exceptions.Timeout:
            return False, "Таймаут при проверке версии"
        except Exception as e:
            return False, str(e)

    def is_model_running(self, model: str) -> bool:
        """Проверка, запущена ли модель"""
        try:
            # Используем API для получения списка запущенных моделей
            response = requests.get(f"{self.host}/api/ps")
            if response.status_code != 200:
                return False
                
            data = response.json()
            running_models = data.get('models', [])
            
            # Проверяем, есть ли наша модель в списке запущенных
            return any(m.get('name') == model for m in running_models)
        except Exception:
            return False 