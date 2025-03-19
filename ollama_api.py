import json
import requests
import atexit
from typing import List, Dict, Tuple, Optional
import logging
import time
import psutil

class OllamaAPI:
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip('/')
        self.running_models = set()
        
        # Настройка логирования
        self.logger = logging.getLogger('OllamaAPI')
        self.logger.setLevel(logging.INFO)
        
        # Добавляем обработчик для файла
        fh = logging.FileHandler('ollama_api.log')
        fh.setLevel(logging.INFO)
        
        # Добавляем обработчик для консоли
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Создаем форматтер
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Добавляем обработчики в логгер
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
        # Регистрируем функцию очистки при выходе
        atexit.register(self.cleanup)
        
        self.logger.info("OllamaAPI initialized with host: %s", host)
        
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

    def generate(self, model: str, prompt: str, system: str = "", **kwargs) -> str:
        """Генерация ответа от модели с расширенными параметрами"""
        try:
            start_time = time.time()
            self.logger.info(f"Starting generation with model {model}")
            
            # Мониторинг ресурсов
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Базовые параметры
            data = {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "num_predict": kwargs.get('max_tokens', 2048),
                    "top_k": kwargs.get('top_k', 40),
                    "top_p": kwargs.get('top_p', 0.9),
                    "repeat_penalty": kwargs.get('repeat_penalty', 1.1),
                    "presence_penalty": kwargs.get('presence_penalty', 0.0),
                    "frequency_penalty": kwargs.get('frequency_penalty', 0.0),
                    "tfs_z": kwargs.get('tfs_z', 1.0),
                    "mirostat": kwargs.get('mirostat', 0),
                    "mirostat_tau": kwargs.get('mirostat_tau', 5.0),
                    "mirostat_eta": kwargs.get('mirostat_eta', 0.1),
                }
            }
            
            # Добавляем системный промпт если есть
            if system:
                data["system"] = system
                
            # Добавляем seed если указан
            if 'seed' in kwargs:
                data["options"]["seed"] = kwargs['seed']
                
            # Добавляем stop последовательности если указаны
            if 'stop' in kwargs:
                data["options"]["stop"] = kwargs['stop']

            # Отправляем запрос
            response = requests.post(
                f"{self.host}/api/generate",
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            # Собираем метрики
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            generation_time = end_time - start_time
            memory_used = final_memory - initial_memory
            
            # Логируем метрики
            self.logger.info(
                "Generation completed - Time: %.2fs, Memory: %.2fMB, Tokens: %d",
                generation_time,
                memory_used,
                len(response.json().get('response', '').split())
            )
            
            return response.json()['response']

        except requests.exceptions.RequestException as e:
            self.logger.error("API Error: %s", str(e))
            raise Exception(f"Ошибка API: {str(e)}")
        except Exception as e:
            self.logger.error("Generation Error: %s", str(e))
            raise Exception(f"Ошибка генерации: {str(e)}")

    def generate_stream(self, model: str, prompt: str, system: str = "", **kwargs):
        """Потоковая генерация ответа от модели с расширенными параметрами"""
        try:
            start_time = time.time()
            self.logger.info(f"Starting streaming generation with model {model}")
            
            # Мониторинг ресурсов
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024
            
            # Базовые параметры
            data = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": kwargs.get('temperature', 0.7),
                    "num_predict": kwargs.get('max_tokens', 2048),
                    "top_k": kwargs.get('top_k', 40),
                    "top_p": kwargs.get('top_p', 0.9),
                    "repeat_penalty": kwargs.get('repeat_penalty', 1.1),
                    "presence_penalty": kwargs.get('presence_penalty', 0.0),
                    "frequency_penalty": kwargs.get('frequency_penalty', 0.0),
                    "tfs_z": kwargs.get('tfs_z', 1.0),
                    "mirostat": kwargs.get('mirostat', 0),
                    "mirostat_tau": kwargs.get('mirostat_tau', 5.0),
                    "mirostat_eta": kwargs.get('mirostat_eta', 0.1),
                }
            }
            
            if system:
                data["system"] = system
                
            if 'seed' in kwargs:
                data["options"]["seed"] = kwargs['seed']
                
            if 'stop' in kwargs:
                data["options"]["stop"] = kwargs['stop']

            total_tokens = 0
            chunk_times = []
            
            with requests.post(
                f"{self.host}/api/generate",
                json=data,
                stream=True,
                timeout=30
            ) as response:
                response.raise_for_status()
                chunk_start = time.time()
                
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk_data = json.loads(line)
                            if 'response' in chunk_data:
                                # Считаем токены и время чанка
                                chunk_tokens = len(chunk_data['response'].split())
                                total_tokens += chunk_tokens
                                chunk_time = time.time() - chunk_start
                                chunk_times.append(chunk_time)
                                chunk_start = time.time()
                                
                                yield chunk_data['response']
                                
                        except json.JSONDecodeError:
                            continue

            # Собираем финальные метрики
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            total_time = end_time - start_time
            memory_used = final_memory - initial_memory
            avg_chunk_time = sum(chunk_times) / len(chunk_times) if chunk_times else 0
            
            # Логируем метрики стриминга
            self.logger.info(
                "Streaming completed - Total Time: %.2fs, Avg Chunk Time: %.3fs, Memory: %.2fMB, Tokens: %d",
                total_time,
                avg_chunk_time,
                memory_used,
                total_tokens
            )

        except requests.exceptions.RequestException as e:
            self.logger.error("Streaming API Error: %s", str(e))
            raise Exception(f"Ошибка API: {str(e)}")
        except Exception as e:
            self.logger.error("Streaming Generation Error: %s", str(e))
            raise Exception(f"Ошибка генерации: {str(e)}")

    def stop_all_models(self):
        """Остановка всех запущенных моделей"""
        for model in list(self.running_models):  # Используем копию списка, так как он будет изменяться
            try:
                if self.stop_model(model):
                    logging.info(f"Модель {model} успешно остановлена")
                else:
                    logging.warning(f"Не удалось остановить модель {model}")
            except Exception as e:
                logging.error(f"Ошибка при остановке модели {model}: {str(e)}")

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