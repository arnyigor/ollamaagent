import logging
import os
import platform
import psutil
import subprocess
import sys
from typing import Dict, Tuple, Optional


class SystemDetector:
    """Автоматическое определение характеристик системы для оптимизации Ollama"""

    def __init__(self):
        self.logger = logging.getLogger('SystemDetector')
        self.system_info = self._detect_system()

    def _detect_system(self) -> Dict:
        """Определение характеристик системы"""
        try:
            info = {
                'platform': platform.system(),
                'processor': platform.processor(),
                'cpu_count': os.cpu_count(),
                'memory_gb': round(psutil.virtual_memory().total / (1024**3), 1),
                'architecture': platform.architecture()[0],
            }

            # Определяем GPU
            gpu_info = self._detect_gpu()
            info.update(gpu_info)

            self.logger.info(f"Обнаружена система: {info}")
            return info

        except Exception as e:
            self.logger.error(f"Ошибка определения системы: {e}")
            return {
                'platform': 'unknown',
                'processor': 'unknown',
                'cpu_count': 1,
                'memory_gb': 4.0,
                'architecture': 'unknown',
                'gpu': 'none'
            }

    def _detect_gpu(self) -> Dict:
        """Определение GPU в системе"""
        try:
            if sys.platform == "darwin":  # macOS
                return self._detect_macos_gpu()
            elif sys.platform == "win32":
                return self._detect_windows_gpu()
            else:  # Linux
                return self._detect_linux_gpu()
        except Exception as e:
            self.logger.warning(f"Ошибка определения GPU: {e}")
            return {'gpu': 'unknown', 'gpu_memory_gb': 0}

    def _detect_macos_gpu(self) -> Dict:
        """Определение GPU на macOS"""
        try:
            # Проверяем наличие Apple Silicon
            if platform.machine() == 'arm64':
                # Apple Silicon Mac
                try:
                    # Получаем информацию о GPU из system_profiler
                    result = subprocess.run(
                        ['system_profiler', 'SPDisplaysDataType'],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if result.returncode == 0:
                        output = result.stdout.lower()
                        if 'apple m' in output:
                            # Определяем тип Apple Silicon
                            if 'm1' in output:
                                gpu_memory = 8  # M1/M2
                            elif 'm3' in output:
                                gpu_memory = 8  # M3
                            elif 'm4' in output:
                                gpu_memory = 16  # M4
                            else:
                                gpu_memory = 8  # Default для Apple Silicon

                            return {
                                'gpu': 'apple_silicon',
                                'gpu_memory_gb': gpu_memory,
                                'gpu_type': 'integrated'
                            }
                except:
                    pass

                # Fallback: проверяем Intel Mac
                return {
                    'gpu': 'intel_iris',
                    'gpu_memory_gb': 1.5,  # Intel Iris Graphics
                    'gpu_type': 'integrated'
                }
            else:
                # Intel Mac
                return {
                    'gpu': 'intel_uhd',
                    'gpu_memory_gb': 1.5,
                    'gpu_type': 'integrated'
                }

        except Exception as e:
            self.logger.warning(f"Ошибка определения GPU macOS: {e}")
            return {'gpu': 'unknown', 'gpu_memory_gb': 0, 'gpu_type': 'unknown'}

    def _detect_windows_gpu(self) -> Dict:
        """Определение GPU на Windows"""
        try:
            import wmi
            w = wmi.WMI()
            gpus = w.Win32_VideoController()

            if gpus:
                gpu = gpus[0]  # Берем первую GPU
                gpu_name = gpu.Name.lower()
                gpu_memory = int(gpu.AdapterRAM) / (1024**3) if gpu.AdapterRAM else 0

                gpu_type = 'discrete' if gpu_memory > 2 else 'integrated'

                return {
                    'gpu': 'nvidia' if 'nvidia' in gpu_name else 'amd' if 'amd' in gpu_name else 'intel',
                    'gpu_memory_gb': round(gpu_memory, 1),
                    'gpu_type': gpu_type
                }

        except Exception as e:
            self.logger.warning(f"Ошибка определения GPU Windows: {e}")

        return {'gpu': 'unknown', 'gpu_memory_gb': 0, 'gpu_type': 'unknown'}

    def _detect_linux_gpu(self) -> Dict:
        """Определение GPU на Linux"""
        try:
            # Проверяем NVIDIA
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    memory_str = result.stdout.strip()
                    memory_gb = round(int(memory_str) / 1024, 1)
                    return {
                        'gpu': 'nvidia',
                        'gpu_memory_gb': memory_gb,
                        'gpu_type': 'discrete'
                    }
            except:
                pass

            # Проверяем AMD
            try:
                result = subprocess.run(['lspci'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0 and 'amd' in result.stdout.lower():
                    return {
                        'gpu': 'amd',
                        'gpu_memory_gb': 2.0,  # Предполагаемая память
                        'gpu_type': 'discrete'
                    }
            except:
                pass

        except Exception as e:
            self.logger.warning(f"Ошибка определения GPU Linux: {e}")

        return {'gpu': 'unknown', 'gpu_memory_gb': 0, 'gpu_type': 'unknown'}


class OllamaOptimizer:
    """Система оптимизации параметров Ollama"""

    def __init__(self):
        self.detector = SystemDetector()
        self.logger = logging.getLogger('OllamaOptimizer')

    def get_optimal_settings(self) -> Dict:
        """Получение оптимальных настроек для текущей системы"""
        system = self.detector.system_info

        # Базовые настройки
        settings = {
            'server': {},
            'runtime': {},
            'model': {}
        }

        # Оптимизация на основе CPU
        cpu_settings = self._optimize_for_cpu(system)
        settings['server'].update(cpu_settings['server'])
        settings['runtime'].update(cpu_settings['runtime'])

        # Оптимизация на основе GPU
        gpu_settings = self._optimize_for_gpu(system)
        settings['server'].update(gpu_settings['server'])
        settings['runtime'].update(gpu_settings['runtime'])

        # Оптимизация на основе памяти
        memory_settings = self._optimize_for_memory(system)
        settings['server'].update(memory_settings['server'])
        settings['runtime'].update(memory_settings['runtime'])

        # Модель-специфичные настройки
        model_settings = self._get_model_specific_settings()
        settings['model'].update(model_settings)

        self.logger.info(f"Сгенерированы оптимальные настройки: {settings}")
        return settings

    def _optimize_for_cpu(self, system: Dict) -> Dict:
        """Оптимизация для CPU"""
        cpu_count = system.get('cpu_count', 1)

        # Для Intel Mac Mini 2018 (обычно 6 ядер) - оптимизированные настройки
        if system['platform'] == 'Darwin' and 'intel' in system.get('processor', '').lower():
            return {
                'server': {
                    'OLLAMA_NUM_PARALLEL': '1',
                    'OLLAMA_MAX_LOADED_MODELS': '1',
                    'OLLAMA_CPU_THREADS': str(min(cpu_count, 4)),  # Ограничиваем до 4 потоков для стабильности
                    'OLLAMA_MAX_QUEUE': '1',  # Ограничиваем очередь запросов
                    'OLLAMA_RUNNERS_DIR': '/tmp/ollama-runners'  # Используем tmpfs для ускорения
                },
                'runtime': {
                    'num_thread': min(cpu_count, 4),  # Ограничиваем потоки для стабильности
                    'num_ctx': 512,  # Уменьшаем контекст для скорости
                    'num_predict': 256,  # Ограничиваем длину ответа
                    'num_batch': 1,  # Минимальный батч для стабильности
                    'num_keep': 0  # Не сохраняем контекст между запросами
                }
            }
        else:
            # Общие настройки для других систем
            return {
                'server': {
                    'OLLAMA_NUM_PARALLEL': str(min(cpu_count // 2, 2)),
                    'OLLAMA_MAX_LOADED_MODELS': '1',
                    'OLLAMA_CPU_THREADS': str(cpu_count)
                },
                'runtime': {
                    'num_thread': cpu_count,
                    'num_ctx': 4096 if cpu_count > 4 else 2048
                }
            }

    def _optimize_for_gpu(self, system: Dict) -> Dict:
        """Оптимизация для GPU"""
        gpu = system.get('gpu', 'none')
        gpu_memory = system.get('gpu_memory_gb', 0)

        if gpu == 'apple_silicon':
            return {
                'server': {
                    'OLLAMA_FLASH_ATTENTION': '1',
                    'OLLAMA_LOW_VRAM': 'false'
                },
                'runtime': {
                    'num_gpu': 1,
                    'gpu_layers': -1,  # Использовать GPU по максимуму
                    'low_vram': False
                }
            }
        elif gpu == 'nvidia' and gpu_memory > 4:
            return {
                'server': {
                    'OLLAMA_FLASH_ATTENTION': '1',
                    'OLLAMA_LOW_VRAM': 'false'
                },
                'runtime': {
                    'num_gpu': 1,
                    'gpu_layers': -1,
                    'low_vram': False
                }
            }
        elif gpu_memory > 0:
            # Интегрированная графика или слабая дискретная
            return {
                'server': {
                    'OLLAMA_LOW_VRAM': 'true'
                },
                'runtime': {
                    'num_gpu': 0,  # Использовать CPU
                    'low_vram': True
                }
            }
        else:
            # Нет GPU
            return {
                'server': {
                    'OLLAMA_LOW_VRAM': 'true'
                },
                'runtime': {
                    'num_gpu': 0,
                    'low_vram': True
                }
            }

    def _optimize_for_memory(self, system: Dict) -> Dict:
        """Оптимизация для памяти"""
        memory_gb = system.get('memory_gb', 4)

        if memory_gb <= 8:
            # Ограниченная память
            return {
                'server': {
                    'OLLAMA_KEEP_ALIVE': '5m',
                    'OLLAMA_MAX_LOADED_MODELS': '1'
                },
                'runtime': {
                    'num_ctx': 1024,
                    'num_predict': 512
                }
            }
        elif memory_gb <= 16:
            # Средний объем памяти - оптимизация для Intel Mac Mini 2018
            return {
                'server': {
                    'OLLAMA_KEEP_ALIVE': '5m',  # Уменьшаем время удержания для экономии памяти
                    'OLLAMA_MAX_LOADED_MODELS': '1'
                },
                'runtime': {
                    'num_ctx': 1024,  # Уменьшаем контекст для стабильности
                    'num_predict': 512  # Уменьшаем максимальную длину ответа
                }
            }
        else:
            # Много памяти
            return {
                'server': {
                    'OLLAMA_KEEP_ALIVE': '30m',
                    'OLLAMA_MAX_LOADED_MODELS': '2'
                },
                'runtime': {
                    'num_ctx': 4096,
                    'num_predict': 2048
                }
            }

    def _get_model_specific_settings(self) -> Dict:
        """Модель-специфичные настройки - оптимизированные для Intel Mac Mini 2018"""
        return {
            'temperature': 0.1,  # Уменьшаем для более детерминированных ответов
            'top_k': 20,  # Уменьшаем для более быстрой генерации
            'top_p': 0.7,  # Уменьшаем для более быстрой генерации
            'repeat_penalty': 1.2,  # Увеличиваем для предотвращения повторов
            'presence_penalty': 0.0,
            'frequency_penalty': 0.0,
            'tfs_z': 1.0,
            'mirostat': 0,  # Отключаем для скорости
            'mirostat_tau': 5.0,
            'mirostat_eta': 0.1,
            'seed': -1,  # Случайное зерно
            'num_predict': 256,  # Ограничиваем длину ответа
            'num_ctx': 512,  # Уменьшаем контекст для скорости
            'num_batch': 1,  # Минимальный батч для стабильности
            'num_keep': 0  # Не сохраняем контекст
        }

    def apply_server_settings(self, settings: Dict) -> bool:
        """Применение серверных настроек"""
        try:
            server_settings = settings.get('server', {})

            for key, value in server_settings.items():
                os.environ[key] = value
                self.logger.info(f"Установлена переменная окружения: {key}={value}")

            return True

        except Exception as e:
            self.logger.error(f"Ошибка применения серверных настроек: {e}")
            return False

    def get_runtime_settings(self, settings: Dict) -> Dict:
        """Получение runtime настроек для API"""
        return settings.get('runtime', {})

    def get_model_settings(self, settings: Dict) -> Dict:
        """Получение настроек модели"""
        return settings.get('model', {})

    def save_config(self, settings: Dict, filename: str = 'ollama_config.json') -> bool:
        """Сохранение конфигурации в файл"""
        try:
            import json

            config = {
                'system_info': self.detector.system_info,
                'settings': settings,
                'timestamp': self._get_timestamp()
            }

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            self.logger.info(f"Конфигурация сохранена в {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False

    def load_config(self, filename: str = 'ollama_config.json') -> Optional[Dict]:
        """Загрузка конфигурации из файла"""
        try:
            import json

            if not os.path.exists(filename):
                return None

            with open(filename, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.logger.info(f"Конфигурация загружена из {filename}")
            return config.get('settings')

        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации: {e}")
            return None

    def _get_timestamp(self) -> str:
        """Получение текущей временной метки"""
        from datetime import datetime
        return datetime.now().isoformat()

    def sync_with_user_settings(self, user_settings: Dict) -> Dict:
        """Синхронизация с пользовательскими настройками модели"""
        try:
            current_settings = self.get_optimal_settings()

            # Определяем критические параметры, требующие перезапуска сервера
            critical_params = {
                'num_thread', 'num_gpu', 'num_ctx', 'low_vram',
                'rope_frequency_base', 'rope_frequency_scale'
            }

            # Проверяем, изменились ли критические параметры
            runtime_settings = current_settings.get('runtime', {})
            needs_restart = any(
                user_settings.get(param) != runtime_settings.get(param)
                for param in critical_params
                if param in user_settings
            )

            # Обновляем runtime настройки пользовательскими
            for key, value in user_settings.items():
                if key in runtime_settings:
                    runtime_settings[key] = value
                elif key in current_settings.get('model', {}):
                    current_settings['model'][key] = value

            # Сохраняем обновленные настройки
            self.save_config(current_settings)

            self.logger.info(f"Настройки синхронизированы. Требуется перезапуск сервера: {needs_restart}")
            return {
                'settings': current_settings,
                'needs_restart': needs_restart,
                'critical_params_changed': list(critical_params.intersection(user_settings.keys()))
            }

        except Exception as e:
            self.logger.error(f"Ошибка синхронизации настроек: {e}")
            return {'settings': self.get_optimal_settings(), 'needs_restart': False, 'critical_params_changed': []}

    def apply_settings_to_server(self, settings: Dict) -> bool:
        """Принудительное применение настроек к запущенному серверу"""
        try:
            import requests
            import json

            # Применяем серверные настройки через переменные окружения
            server_settings = settings.get('server', {})
            for key, value in server_settings.items():
                os.environ[key] = str(value)
                self.logger.info(f"Применена переменная окружения: {key}={value}")

            # Проверяем, запущен ли сервер
            try:
                response = requests.get("http://localhost:11434/api/version", timeout=5)
                if response.status_code == 200:
                    self.logger.info("Сервер Ollama запущен, настройки применены")
                    return True
                else:
                    self.logger.warning("Сервер Ollama не отвечает")
                    return False
            except requests.exceptions.ConnectionError:
                self.logger.warning("Сервер Ollama не запущен")
                return False

        except Exception as e:
            self.logger.error(f"Ошибка применения настроек к серверу: {e}")
            return False

    def restart_server_if_needed(self, needs_restart: bool) -> bool:
        """Перезапуск сервера при необходимости"""
        if not needs_restart:
            return True

        try:
            import subprocess
            import time
            import requests

            self.logger.info("Перезапуск сервера Ollama...")

            # Останавливаем сервер
            try:
                subprocess.run(['pkill', '-f', 'ollama'], timeout=10)
                time.sleep(2)
            except:
                pass

            # Запускаем сервер с новыми настройками
            if sys.platform == "darwin":  # macOS
                subprocess.Popen(['ollama', 'serve'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(['ollama', 'serve'],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)

            # Ждем запуска сервера
            for i in range(30):
                try:
                    response = requests.get("http://localhost:11434/api/version", timeout=5)
                    if response.status_code == 200:
                        self.logger.info("Сервер Ollama успешно перезапущен")
                        return True
                except:
                    time.sleep(1)

            self.logger.error("Не удалось перезапустить сервер Ollama")
            return False

        except Exception as e:
            self.logger.error(f"Ошибка перезапуска сервера: {e}")
            return False


def get_optimal_ollama_config() -> Dict:
    """Функция для получения оптимальной конфигурации Ollama"""
    optimizer = OllamaOptimizer()
    settings = optimizer.get_optimal_settings()

    # Сохраняем конфигурацию
    optimizer.save_config(settings)

    return settings


if __name__ == "__main__":
    # Тестирование системы оптимизации
    logging.basicConfig(level=logging.INFO)

    optimizer = OllamaOptimizer()
    settings = optimizer.get_optimal_settings()

    print("=== АВТОМАТИЧЕСКАЯ ОПТИМИЗАЦИЯ OLLAMA ===")
    print(f"Система: {optimizer.detector.system_info}")
    print("\nСерверные настройки:")
    for key, value in settings['server'].items():
        print(f"  {key}={value}")

    print("\nRuntime настройки:")
    for key, value in settings['runtime'].items():
        print(f"  {key}={value}")

    print("\nНастройки модели:")
    for key, value in settings['model'].items():
        print(f"  {key}={value}")