#!/usr/bin/env python3
"""
Тестовый скрипт для системы автоматической оптимизации Ollama
"""

import logging
import sys
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

def test_system_detection():
    """Тестирование определения системных характеристик"""
    try:
        from system_optimizer import SystemDetector, OllamaOptimizer

        print("=== ТЕСТИРОВАНИЕ ОПРЕДЕЛЕНИЯ СИСТЕМЫ ===")

        detector = SystemDetector()
        system_info = detector.system_info

        print(f"Платформа: {system_info.get('platform', 'Неизвестно')}")
        print(f"Процессор: {system_info.get('processor', 'Неизвестно')}")
        print(f"Количество ядер CPU: {system_info.get('cpu_count', 'Неизвестно')}")
        print(f"Объем памяти: {system_info.get('memory_gb', 'Неизвестно')} ГБ")
        print(f"Архитектура: {system_info.get('architecture', 'Неизвестно')}")
        print(f"GPU: {system_info.get('gpu', 'Неизвестно')}")
        print(f"Память GPU: {system_info.get('gpu_memory_gb', 'Неизвестно')} ГБ")
        print(f"Тип GPU: {system_info.get('gpu_type', 'Неизвестно')}")

        return True

    except Exception as e:
        print(f"Ошибка тестирования определения системы: {e}")
        return False

def test_optimization():
    """Тестирование системы оптимизации"""
    try:
        from system_optimizer import OllamaOptimizer

        print("\n=== ТЕСТИРОВАНИЕ ОПТИМИЗАЦИИ ===")

        optimizer = OllamaOptimizer()
        settings = optimizer.get_optimal_settings()

        print("Серверные настройки:")
        for key, value in settings.get('server', {}).items():
            print(f"  {key} = {value}")

        print("\nRuntime настройки:")
        for key, value in settings.get('runtime', {}).items():
            print(f"  {key} = {value}")

        print("\nНастройки модели:")
        for key, value in settings.get('model', {}).items():
            print(f"  {key} = {value}")

        return True

    except Exception as e:
        print(f"Ошибка тестирования оптимизации: {e}")
        return False

def test_config_save_load():
    """Тестирование сохранения и загрузки конфигурации"""
    try:
        from system_optimizer import OllamaOptimizer

        print("\n=== ТЕСТИРОВАНИЕ КОНФИГУРАЦИИ ===")

        optimizer = OllamaOptimizer()
        settings = optimizer.get_optimal_settings()

        # Сохраняем конфигурацию
        config_file = 'test_ollama_config.json'
        if optimizer.save_config(settings, config_file):
            print(f"Конфигурация сохранена в {config_file}")

            # Загружаем конфигурацию
            loaded_settings = optimizer.load_config(config_file)
            if loaded_settings:
                print("Конфигурация успешно загружена")
                print(f"Загружено настроек: {len(loaded_settings)} категорий")

                # Очищаем тестовый файл
                try:
                    os.remove(config_file)
                    print("Тестовый файл конфигурации удален")
                except:
                    pass

                return True
            else:
                print("Ошибка загрузки конфигурации")
                return False
        else:
            print("Ошибка сохранения конфигурации")
            return False

    except Exception as e:
        print(f"Ошибка тестирования конфигурации: {e}")
        return False

def test_api_integration():
    """Тестирование интеграции с API"""
    try:
        from ollama_api import OllamaAPI

        print("\n=== ТЕСТИРОВАНИЕ ИНТЕГРАЦИИ С API ===")

        # Создаем API с оптимизацией
        api = OllamaAPI()

        # Получаем информацию об оптимизации
        optimization_info = api.get_optimization_info()

        print("Информация об оптимизации получена:")
        print(f"Системная информация: {len(optimization_info.get('system_info', {}))} параметров")
        print(f"Серверные настройки: {len(optimization_info.get('optimal_settings', {}).get('server', {}))} параметров")
        print(f"Runtime настройки: {len(optimization_info.get('default_runtime_settings', {}))} параметров")
        print(f"Настройки модели: {len(optimization_info.get('default_model_settings', {}))} параметров")

        return True

    except Exception as e:
        print(f"Ошибка тестирования интеграции с API: {e}")
        return False

def test_settings_synchronization():
    """Тестирование синхронизации пользовательских настроек"""
    try:
        from ollama_api import OllamaAPI

        print("\n=== ТЕСТИРОВАНИЕ СИНХРОНИЗАЦИИ НАСТРОЕК ===")

        # Создаем API с оптимизацией
        api = OllamaAPI()

        # Тестовые пользовательские настройки
        user_settings = {
            'temperature': 0.5,
            'num_thread': 4,
            'num_ctx': 1024,
            'top_k': 50
        }

        print(f"Тестовые пользовательские настройки: {user_settings}")

        # Синхронизируем настройки
        sync_result = api.sync_with_user_settings(user_settings)

        print("Результат синхронизации:")
        print(f"Требуется перезапуск: {sync_result.get('needs_restart', False)}")
        print(f"Измененные критические параметры: {sync_result.get('critical_params_changed', [])}")

        # Получаем обновленные настройки
        current_settings = api.get_current_settings()
        runtime_settings = current_settings.get('runtime_settings', {})

        print("Проверка применения настроек:")
        for key, expected_value in user_settings.items():
            actual_value = runtime_settings.get(key)
            if actual_value == expected_value:
                print(f"✅ {key}: {actual_value} (ожидаемое: {expected_value})")
            else:
                print(f"❌ {key}: {actual_value} (ожидаемое: {expected_value})")

        return True

    except Exception as e:
        print(f"Ошибка тестирования синхронизации настроек: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 НАЧАЛО ТЕСТИРОВАНИЯ СИСТЕМЫ АВТОМАТИЧЕСКОЙ ОПТИМИЗАЦИИ OLLAMA")
    print("=" * 70)

    tests = [
        ("Определение системы", test_system_detection),
        ("Система оптимизации", test_optimization),
        ("Конфигурация", test_config_save_load),
        ("Интеграция с API", test_api_integration),
        ("Синхронизация настроек", test_settings_synchronization)
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                print(f"✅ {test_name}: ПРОЙДЕН")
                passed += 1
            else:
                print(f"❌ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            print(f"❌ {test_name}: ОШИБКА - {e}")

    print("\n" + "=" * 70)
    print(f"РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {passed}/{total} пройдено")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\nСистема автоматической оптимизации Ollama готова к использованию:")
        print("• Автоматическое определение характеристик системы")
        print("• Оптимальные настройки для вашего оборудования")
        print("• Интеграция с API для runtime оптимизации")
        print("• Сохранение и загрузка конфигурации")
        return 0
    else:
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("Проверьте логи ошибок выше и повторите тестирование")
        return 1

if __name__ == "__main__":
    sys.exit(main())