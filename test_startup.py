#!/usr/bin/env python3
import sys
import traceback
import logging

# Настройка логирования для перехвата всех ошибок
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

try:
    print("=== Тестирование импортов ===")

    print("1. Импорт основных модулей...")
    import os
    import time
    import json
    print("   ✓ Базовые модули импортированы")

    print("2. Импорт PyQt6...")
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
    from PyQt6.QtCore import Qt, QTimer
    print("   ✓ PyQt6 импортирован")

    print("3. Импорт локальных модулей...")
    from chat_window import ChatWindow
    print("   ✓ chat_window импортирован")

    from ollama_api import OllamaAPI
    print("   ✓ ollama_api импортирован")

    from system_optimizer import OllamaOptimizer
    print("   ✓ system_optimizer импортирован")

    print("4. Создание QApplication...")
    app = QApplication(sys.argv)
    print("   ✓ QApplication создан")

    print("5. Создание ChatWindow...")
    window = ChatWindow()
    print("   ✓ ChatWindow создан")

    print("6. Показ окна...")
    window.show()
    print("   ✓ Окно показано")

    print("=== Все тесты пройдены успешно! ===")
    print("Приложение должно запускаться без проблем.")

except Exception as e:
    print(f"\n❌ ОШИБКА: {e}")
    print("\nПолный стектрейс:")
    traceback.print_exc()
    sys.exit(1)