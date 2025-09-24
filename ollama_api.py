import atexit
import json
import logging
import time
import traceback
from typing import List, Dict, Tuple

import psutil
import requests

from system_optimizer import OllamaOptimizer


class OllamaAPI:
    def __init__(self, host: str = "http://localhost:11434"):
        self.host = host.rstrip('/')
        self.running_models = set()

        # Настройка логирования
        self.logger = logging.getLogger('OllamaAPI')
        self.logger.setLevel(logging.INFO)

        # Добавляем обработчик для файла
        fh = logging.FileHandler('ollama_api.log')
        fh.setLevel(logging.DEBUG)

        # Добавляем обработчик для консоли
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)

        # Создаем форматтер
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)

        # Добавляем обработчики в логгер
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

        # Автоматическая оптимизация
        self.optimizer = OllamaOptimizer()
        self.optimal_settings = self.optimizer.get_optimal_settings()

        # Применяем серверные настройки
        self.optimizer.apply_server_settings(self.optimal_settings)

        # Получаем runtime настройки
        self.default_runtime_settings = self.optimizer.get_runtime_settings(self.optimal_settings)
        self.default_model_settings = self.optimizer.get_model_settings(self.optimal_settings)

        # Регистрируем функцию очистки при выходе
        atexit.register(self.cleanup)

        self.logger.info("OllamaAPI initialized with host: %s", host)
        self.logger.info(f"Автоматическая оптимизация применена: {self.optimal_settings}")

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
                f"{self.host}/api/chat",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "test"}],
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

    def generate_stream(self, model: str, messages: List[Dict[str, str]], **kwargs):
        """Потоковая генерация ответа от модели с расширенными параметрами"""
        try:
            start_time = time.time()
            self.logger.info(f"Starting streaming generation with model {model}")

            # Мониторинг ресурсов
            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024

            # Подсчет входных токенов
            input_tokens = 0
            try:
                for message in messages:
                    if isinstance(message, dict) and isinstance(message.get('content'), str):
                        input_tokens += len(message['content'].split())
            except Exception as e:
                self.logger.warning(f"Ошибка при подсчете входных токенов: {e}")
                input_tokens = 0

            # Используем оптимальные настройки по умолчанию, но позволяем их переопределить
            runtime_settings = self.default_runtime_settings.copy()
            model_settings = self.default_model_settings.copy()

            # Применяем пользовательские настройки
            runtime_settings.update({
                key: value for key, value in kwargs.items()
                if key in runtime_settings
            })
            model_settings.update({
                key: value for key, value in kwargs.items()
                if key in model_settings
            })

            # Убираем дубликаты из kwargs, чтобы не передавать их дважды
            filtered_kwargs = {
                key: value for key, value in kwargs.items()
                if key not in runtime_settings and key not in model_settings
            }

            # Базовые параметры
            data = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    # Параметры генерации текста (из model_settings)
                    "temperature": model_settings.get('temperature', 0.7),
                    "num_predict": filtered_kwargs.get('max_tokens', model_settings.get('num_predict', 2048)),
                    "top_k": model_settings.get('top_k', 40),
                    "top_p": model_settings.get('top_p', 0.9),
                    "repeat_penalty": model_settings.get('repeat_penalty', 1.1),
                    "presence_penalty": model_settings.get('presence_penalty', 0.0),
                    "frequency_penalty": model_settings.get('frequency_penalty', 0.0),
                    "tfs_z": model_settings.get('tfs_z', 1.0),
                    "mirostat": model_settings.get('mirostat', 0),
                    "mirostat_tau": model_settings.get('mirostat_tau', 5.0),
                    "mirostat_eta": model_settings.get('mirostat_eta', 0.1),
                    # Параметры аппаратного обеспечения (из runtime_settings)
                    "num_thread": runtime_settings.get('num_thread', 4),
                    "num_gpu": runtime_settings.get('num_gpu', 1),
                    "main_gpu": runtime_settings.get('main_gpu', 0),
                    "gpu_layers": runtime_settings.get('gpu_layers', 0),
                    "num_ctx": runtime_settings.get('num_ctx', 2048),
                    "low_vram": runtime_settings.get('low_vram', False),
                    "rope_frequency_base": runtime_settings.get('rope_frequency_base', 10000.0),
                    "rope_frequency_scale": runtime_settings.get('rope_frequency_scale', 1.0),
                }
            }

            if kwargs['system']:
                data["system"] = kwargs['system']

            if 'seed' in kwargs:
                data["options"]["seed"] = kwargs['seed']

            if 'stop' in kwargs:
                data["options"]["stop"] = kwargs['stop']

            total_tokens = 0
            chunk_times = []
            chunk_data = None
            first_token_time = None
            output_tokens = 0

            logging.info(f"Отправка запроса к Ollama API с параметрами:")
            logging.info(f"  Модель: {model}")
            logging.info(f"  Сообщения: {len(messages)} шт.")
            logging.info(f"  Входные токены: {input_tokens}")
            logging.info(f"  Опции генерации: {data['options']}")
            if 'system' in data:
                logging.info(f"  Системный промпт: {data['system'][:100]}...")
            logging.debug(f"Request data: {data}")

            # Подробное логирование для диагностики
            self.logger.info(f"Текущие настройки оптимизации:")
            self.logger.info(f"  Runtime: {self.default_runtime_settings}")
            self.logger.info(f"  Model: {self.default_model_settings}")
            self.logger.info(f"  System info: {self.optimizer.detector.system_info}")

            # Увеличиваем таймаут для больших моделей и сложных запросов
            # Базовый таймаут + дополнительное время на основе размера модели и количества токенов
            base_timeout = 60  # 60 секунд базовый таймаут
            model_timeout = 30 if 'qwen3' in model.lower() else 15  # Дополнительное время для сложных моделей
            context_timeout = max(1, data['options'].get('num_ctx', 2048) // 1000)  # 1 секунда на 1000 токенов контекста
            total_timeout = base_timeout + model_timeout + context_timeout

            self.logger.info(f"Установлен таймаут: {total_timeout}с (модель: {model}, контекст: {data['options'].get('num_ctx', 2048)})")

            with requests.post(
                    f"{self.host}/api/chat",
                    json=data,
                    stream=True,
                    timeout=total_timeout
            ) as response:
                response.raise_for_status()
                chunk_start = time.time()

                for line in response.iter_lines():
                    if line:
                        try:
                            self.logger.debug(f"Raw response line: {line}")
                            chunk_data = json.loads(line)
                            self.logger.debug(f"Parsed chunk data: {chunk_data}")

                            if not isinstance(chunk_data, dict):
                                self.logger.error(f"Unexpected response format: {type(chunk_data)}")
                                continue

                            if isinstance(chunk_data, dict) and 'response' in chunk_data:
                                # Считаем токены и время чанка
                                chunk_tokens = len(chunk_data['response'].split())
                                output_tokens += chunk_tokens
                                chunk_time = time.time() - chunk_start
                                chunk_times.append(chunk_time)
                                chunk_start = time.time()

                                # Записываем время до первого токена
                                if first_token_time is None:
                                    first_token_time = time.time() - start_time

                                yield chunk_data['response']
                            elif isinstance(chunk_data, dict) and 'message' in chunk_data and 'content' in chunk_data['message']:
                                # Считаем токены для нового формата
                                chunk_tokens = len(chunk_data['message']['content'].split())
                                output_tokens += chunk_tokens
                                chunk_time = time.time() - chunk_start
                                chunk_times.append(chunk_time)
                                chunk_start = time.time()

                                # Записываем время до первого токена
                                if first_token_time is None:
                                    first_token_time = time.time() - start_time

                                yield chunk_data['message']['content']
                            else:
                                self.logger.warning(f"Missing 'response' or 'message.content' in chunk: {chunk_data}")

                        except json.JSONDecodeError as e:
                            self.logger.error(f"JSON decode error: {e}\nLine: {line}")
                            continue
                        except Exception as e:
                            self.logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
                            raise

            if chunk_data and 'response' in chunk_data:
                logging.debug(f"Response data: {chunk_data['response']}")

            # Собираем финальные метрики
            end_time = time.time()
            final_memory = process.memory_info().rss / 1024 / 1024
            total_time = end_time - start_time
            memory_used = final_memory - initial_memory
            avg_chunk_time = sum(chunk_times) / len(chunk_times) if chunk_times else 0

            # Логируем расширенные метрики стриминга
            self.logger.info(
                "Streaming completed - Total Time: %.2fs, TTFT: %.3fs, Input: %d, Output: %d, Memory: %.2fMB",
                total_time,
                first_token_time or 0,
                input_tokens,
                output_tokens
            )

            # Сохраняем статистику в атрибуте для доступа извне
            self.last_generation_stats = {
                'total_time': total_time,
                'time_to_first_token': first_token_time or 0,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens,
                'model': model,
                'memory_used': memory_used,
                'avg_chunk_time': avg_chunk_time
            }

        except requests.exceptions.Timeout as e:
            self.logger.error("Таймаут API: %s", str(e), stack_info=True)
            self.logger.info("Попытка восстановления с уменьшенными параметрами...")

            # Попытка восстановления с уменьшенными параметрами
            try:
                recovery_data = data.copy()
                recovery_data['options']['num_ctx'] = min(recovery_data['options']['num_ctx'], 1024)
                recovery_data['options']['num_predict'] = min(recovery_data['options']['num_predict'], 512)

                self.logger.info(f"Попытка восстановления с параметрами: {recovery_data['options']}")

                with requests.post(
                        f"{self.host}/api/chat",
                        json=recovery_data,
                        stream=True,
                        timeout=120  # Увеличенный таймаут для восстановления
                ) as response:
                    response.raise_for_status()

                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk_data = json.loads(line)
                                if isinstance(chunk_data, dict) and 'response' in chunk_data:
                                    yield chunk_data['response']
                                elif isinstance(chunk_data, dict) and 'message' in chunk_data and 'content' in chunk_data['message']:
                                    yield chunk_data['message']['content']
                            except json.JSONDecodeError:
                                continue

                self.logger.info("Восстановление успешно")
                return

            except Exception as recovery_error:
                self.logger.error("Восстановление не удалось: %s", str(recovery_error), stack_info=True)
                raise Exception(f"Ошибка API и восстановления: {str(e)} -> {str(recovery_error)}")

        except requests.exceptions.RequestException as e:
            self.logger.error("Streaming API Error: %s", str(e), stack_info=True)
            raise Exception(f"Ошибка API: {str(e)}")
        except Exception as e:
            print(f"Ошибка генерации: {e}\n{traceback.format_exc()}")
            self.logger.error("Streaming Generation Error: %s", str(e), stack_info=True)
            raise Exception(f"Ошибка генерации: {str(e)}")

    def stop_all_models(self):
        """Остановка всех запущенных моделей"""
        for model in list(
                self.running_models):  # Используем копию списка, так как он будет изменяться
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

    def get_optimization_info(self) -> Dict:
        """Получение информации об оптимизации"""
        return {
            'system_info': self.optimizer.detector.system_info,
            'optimal_settings': self.optimal_settings,
            'default_runtime_settings': self.default_runtime_settings,
            'default_model_settings': self.default_model_settings
        }

    def reload_optimization(self) -> bool:
        """Перезагрузка оптимизации (например, после изменения оборудования)"""
        try:
            self.optimizer = OllamaOptimizer()
            self.optimal_settings = self.optimizer.get_optimal_settings()
            self.optimizer.apply_server_settings(self.optimal_settings)
            self.default_runtime_settings = self.optimizer.get_runtime_settings(self.optimal_settings)
            self.default_model_settings = self.optimizer.get_model_settings(self.optimal_settings)

            self.logger.info(f"Оптимизация перезагружена: {self.optimal_settings}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка перезагрузки оптимизации: {e}")
            return False

    def sync_with_user_settings(self, user_settings: Dict) -> Dict:
        """Синхронизация с пользовательскими настройками модели"""
        try:
            sync_result = self.optimizer.sync_with_user_settings(user_settings)

            if sync_result['needs_restart']:
                # Применяем настройки к серверу
                self.optimizer.apply_settings_to_server(sync_result['settings'])

                # Перезапускаем сервер если нужно
                restart_success = self.optimizer.restart_server_if_needed(True)

                if restart_success:
                    # Обновляем локальные настройки после перезапуска
                    self.optimal_settings = sync_result['settings']
                    self.default_runtime_settings = self.optimizer.get_runtime_settings(self.optimal_settings)
                    self.default_model_settings = self.optimizer.get_model_settings(self.optimal_settings)
                else:
                    self.logger.warning("Сервер не удалось перезапустить, настройки применены локально")

            # Всегда обновляем локальные настройки
            self.optimal_settings = sync_result['settings']
            self.default_runtime_settings = self.optimizer.get_runtime_settings(self.optimal_settings)
            self.default_model_settings = self.optimizer.get_model_settings(self.optimal_settings)

            self.logger.info(f"Настройки синхронизированы: {sync_result}")
            return sync_result

        except Exception as e:
            self.logger.error(f"Ошибка синхронизации с пользовательскими настройками: {e}")
            return {'settings': self.optimal_settings, 'needs_restart': False, 'critical_params_changed': []}

    def get_current_settings(self) -> Dict:
        """Получение текущих настроек"""
        return {
            'system_info': self.optimizer.detector.system_info,
            'server_settings': self.optimal_settings.get('server', {}),
            'runtime_settings': self.default_runtime_settings,
            'model_settings': self.default_model_settings
        }

    def get_last_generation_stats(self) -> Dict:
        """Получение статистики последней генерации"""
        return getattr(self, 'last_generation_stats', {})
