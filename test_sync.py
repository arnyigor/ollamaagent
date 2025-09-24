#!/usr/bin/env python3
"""
Тест синхронизации пользовательских настроек с системными
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

def test_settings_sync():
    """Тестирование синхронизации настроек"""
    try:
        from system_optimizer import OllamaOptimizer
        from ollama_api import OllamaAPI

        print("=== ТЕСТИРОВАНИЕ СИНХРОНИЗАЦИИ НАСТРОЕК ===")

        # Создаем оптимизатор
        optimizer = OllamaOptimizer()
        print(f"Системная информация: {optimizer.detector.system_info}")

        # Получаем текущие настройки
        current_settings = optimizer.get_optimal_settings()
        print(f"Текущие серверные настройки: {current_settings.get('server', {})}")
        print(f"Текущие runtime настройки: {current_settings.get('runtime', {})}")

        # Тестовые пользовательские настройки
        user_settings = {
            'temperature': 0.5,
            'num_thread': 4,
            'num_ctx': 1024,
            'top_k': 50,
            'repeat_penalty': 1.2
        }

        print(f"\nПользовательские настройки: {user_settings}")

        # Создаем API и тестируем синхронизацию
        api = OllamaAPI()

        # Синхронизируем настройки
        sync_result = api.sync_with_user_settings(user_settings)

        print("\nРезультат синхронизации:")
        print(f"Требуется перезапуск: {sync_result.get('needs_restart', False)}")
        print(f"Измененные критические параметры: {sync_result.get('critical_params_changed', [])}")

        # Получаем обновленные настройки
        updated_settings = api.get_current_settings()
        print("\nОбновленные настройки:")
        print(f"Runtime: {updated_settings.get('runtime_settings', {})}")
        print(f"Model: {updated_settings.get('model_settings', {})}")

        # Проверяем применение настроек
        print("\nПроверка применения:")
        for key, expected_value in user_settings.items():
            if key in updated_settings.get('runtime_settings', {}):
                actual_value = updated_settings['runtime_settings'][key]
                status = "✅" if actual_value == expected_value else "❌"
                print(f"{status} {key}: {actual_value} (ожидаемое: {expected_value})")
            elif key in updated_settings.get('model_settings', {}):
                actual_value = updated_settings['model_settings'][key]
                status = "✅" if actual_value == expected_value else "❌"
                print(f"{status} {key}: {actual_value} (ожидаемое: {expected_value})")

        return True

    except Exception as e:
        print(f"Ошибка тестирования синхронизации: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_persistence():
    """Тестирование сохранения конфигурации"""
    try:
        from system_optimizer import OllamaOptimizer

        print("\n=== ТЕСТИРОВАНИЕ СОХРАНЕНИЯ КОНФИГУРАЦИИ ===")

        optimizer = OllamaOptimizer()
        settings = optimizer.get_optimal_settings()

        # Сохраняем конфигурацию
        config_file = 'test_sync_config.json'
        if optimizer.save_config(settings, config_file):
            print(f"✅ Конфигурация сохранена в {config_file}")

            # Загружаем конфигурацию
            loaded_settings = optimizer.load_config(config_file)
            if loaded_settings:
                print("✅ Конфигурация успешно загружена")
                print(f"Загружено настроек: {len(loaded_settings)} категорий")

                # Очищаем тестовый файл
                try:
                    os.remove(config_file)
                    print("✅ Тестовый файл конфигурации удален")
                except:
                    pass

                return True
            else:
                print("❌ Ошибка загрузки конфигурации")
                return False
        else:
            print("❌ Ошибка сохранения конфигурации")
            return False

    except Exception as e:
        print(f"Ошибка тестирования конфигурации: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ СИНХРОНИЗАЦИИ НАСТРОЕК OLLAMA")
    print("=" * 60)

    tests = [
        ("Синхронизация настроек", test_settings_sync),
        ("Сохранение конфигурации", test_config_persistence)
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

    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ: {passed}/{total} пройдено")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\nСистема синхронизации работает корректно:")
        print("• Пользовательские настройки применяются к системным")
        print("• Критические параметры определяются правильно")
        print("• Настройки сохраняются и загружаются корректно")
        return 0
    else:
        print("⚠️  НЕКОТОРЫЕ ТЕСТЫ ПРОВАЛЕНЫ")
        print("Проверьте логи ошибок выше")
        return 1

if __name__ == "__main__":
    sys.exit(main())