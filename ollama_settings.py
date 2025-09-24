import logging
import os
import subprocess
import sys
import time
import traceback
import webbrowser
from urllib.parse import quote

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QPushButton, QTextEdit, QVBoxLayout, QMessageBox, QComboBox, QFileDialog, QLabel, QDialog,
    QFormLayout, QLineEdit,
    QHBoxLayout, QProgressBar, QGroupBox, QSpinBox, QDoubleSpinBox, QCheckBox
)

# from lmstudio_settings import LmStudioSettings


def check_ollama_version():
    """Проверка версии ollama"""
    try:
        # В Windows нужно искать конкретно ollama.exe
        command = "ollama.exe" if sys.platform == "win32" else "ollama"

        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr
    except FileNotFoundError:
        if sys.platform == "win32":
            return False, ("Ollama не найден. Убедитесь, что:\n"
                           "1. Путь к папке с ollama.exe добавлен в PATH\n"
                           "2. Вы перезагрузили компьютер после добавления пути\n"
                           "3. Стандартный путь установки: C:\\Users\\<username>\\AppData\\Local\\Programs\\Ollama")
        return False, "Ollama не найден. Убедитесь, что путь к ollama добавлен в PATH"
    except Exception as e:
        return False, str(e)


class InstallWorker(QThread):
    log_signal = pyqtSignal(str)
    finish_signal = pyqtSignal(bool)

    def __init__(self, model_name, install_dir):
        super().__init__()
        self.model_name = model_name
        self.install_dir = install_dir.replace('\\', '/')
        self.command = "ollama.exe" if sys.platform == "win32" else "ollama"
        self.process = None
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True
        if self.process:
            self.process.terminate()
            self.log_signal.emit("Отмена установки...")

    def clean_model(self):
        """Очистка частично загруженной модели"""
        try:
            result = subprocess.run(
                [self.command, "rm", self.model_name],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=10
            )

            # Очищаем вывод от управляющих символов
            stderr = self.clean_line(result.stderr) if result.stderr else ""
            stdout = self.clean_line(result.stdout) if result.stdout else ""

            if result.returncode == 0:
                self.log_signal.emit(f"Модель {self.model_name} удалена")
                return True
            else:
                # Если модель не найдена, это нормально при первой установке
                if "model not found" in stderr.lower():
                    self.log_signal.emit("Модель еще не была полностью установлена")
                    # Попробуем очистить кэш
                    try:
                        cache_dir = os.path.join(self.install_dir)
                        model_files = [f for f in os.listdir(cache_dir) if
                                       f.startswith(self.model_name)]
                        for f in model_files:
                            os.remove(os.path.join(cache_dir, f))
                        if model_files:
                            self.log_signal.emit("Кэш модели очищен")
                    except Exception as e:
                        self.log_signal.emit(f"Не удалось очистить кэш: {str(e)}")
                    return True
                else:
                    error = stderr if stderr else stdout
                    self.log_signal.emit(f"Ошибка удаления: {error}")
                    return False
        except Exception as e:
            self.log_signal.emit(f"Ошибка при очистке модели: {str(e)}")
            return False

    def clean_line(self, line: str) -> str:
        """Очистка строки от управляющих символов терминала"""
        # Удаляем ANSI escape sequences
        import re
        # Удаляем все ANSI escape sequences
        line = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', line)
        # Удаляем специфичные управляющие последовательности
        line = line.replace('[K', '').replace('[A', '')
        line = line.replace('[?25l', '').replace('[?25h', '')
        line = line.replace('[?2026l', '').replace('[?2026h', '')
        line = line.replace('[1G', '').replace('[2K', '')
        # Удаляем возможные оставшиеся управляющие символы
        line = ''.join(char for char in line if ord(char) >= 32 or char in '\n\r\t')
        return line.strip()

    def check_model_files(self, directory: str, model_name: str) -> list:
        """Проверка файлов модели в указанной директории"""
        try:
            if not os.path.exists(directory):
                return []

            model_files = []
            model_prefix = model_name.replace(":", "_")

            for file in os.listdir(directory):
                if file.startswith(model_prefix):
                    file_path = os.path.join(directory, file)
                    size_bytes = os.path.getsize(file_path)
                    # Конвертируем размер в человекочитаемый формат
                    size = self.format_size(size_bytes)
                    model_files.append((file, size, file_path))

            return model_files
        except Exception as e:
            self.log_signal.emit(f"Ошибка при проверке файлов в {directory}: {str(e)}")
            return []

    def format_size(self, size_bytes: int) -> str:
        """Форматирование размера файла в человекочитаемый вид"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

    def set_system_env_variable(self, name: str, value: str) -> bool:
        """Установка системной переменной окружения"""
        try:
            if sys.platform == "win32":
                import winreg
                # Открываем ключ реестра для системных переменных
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                                     0, winreg.KEY_ALL_ACCESS)
                # Устанавливаем значение
                winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
                winreg.CloseKey(key)
                # Уведомляем систему об изменении переменных окружения
                import ctypes
                HWND_BROADCAST = 0xFFFF
                WM_SETTINGCHANGE = 0x1A
                SMTO_ABORTIFHUNG = 0x0002
                result = ctypes.windll.user32.SendMessageTimeoutW(
                    HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
                    SMTO_ABORTIFHUNG, 5000, ctypes.byref(ctypes.c_ulong()))
                return True
            else:
                # Для Linux/Mac добавляем в ~/.bashrc или ~/.zshrc
                shell_rc = os.path.expanduser("~/.bashrc")
                if os.path.exists(os.path.expanduser("~/.zshrc")):
                    shell_rc = os.path.expanduser("~/.zshrc")

                with open(shell_rc, "a") as f:
                    f.write(f'\nexport {name}="{value}"\n')
                return True
        except Exception as e:
            self.log_signal.emit(f"Ошибка установки переменной окружения: {str(e)}")
            return False

    def run(self):
        success, message = check_ollama_version()
        if not success:
            self.log_signal.emit(f"Ошибка: {message}")
            self.finish_signal.emit(False)
            return

        try:
            # Нормализуем пути, заменяя обратные слеши на прямые
            self.install_dir = self.install_dir.replace('\\', '/')
            models_dir = os.path.join(self.install_dir).replace('\\', '/')
            os.makedirs(models_dir, exist_ok=True)

            self.log_signal.emit(f"Выбранная директория установки: {models_dir}")

            # Устанавливаем OLLAMA_MODELS как системную переменную
            if self.set_system_env_variable("OLLAMA_MODELS", str(models_dir)):
                self.log_signal.emit("Установлена системная переменная OLLAMA_MODELS")
                self.log_signal.emit(
                    "ВАЖНО: Требуется перезагрузка компьютера для применения изменений")
            else:
                self.log_signal.emit(
                    "ВНИМАНИЕ: Не удалось установить системную переменную OLLAMA_MODELS")
                self.log_signal.emit(
                    "Установка продолжится, но может потребоваться ручная настройка")

            # Устанавливаем переменную для текущего процесса
            os.environ["OLLAMA_MODELS"] = models_dir

            self.log_signal.emit(f"Начинаю установку модели {self.model_name}...")

            # Запускаем установку с установленной OLLAMA_MODELS
            self.process = subprocess.Popen(
                [self.command, "pull", self.model_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                env=os.environ
            )

            for line in iter(self.process.stdout.readline, ""):
                if self.is_cancelled:
                    break

                clean_line = self.clean_line(line)
                if clean_line:
                    self.log_signal.emit(clean_line)

            exit_code = self.process.wait()
            if self.is_cancelled:
                self.log_signal.emit("Установка отменена")
                self.finish_signal.emit(False)
            elif exit_code == 0:
                # Проверяем файлы в новой директории
                custom_files = self.check_model_files(models_dir, self.model_name)

                if custom_files:
                    self.log_signal.emit(f"\nФайлы успешно установлены в {models_dir}:")
                    for file, size, _ in custom_files:
                        self.log_signal.emit(f"- {file} (размер: {size})")
                    self.log_signal.emit("\nУстановка завершена успешно")
                    self.log_signal.emit("ВАЖНО: Перезагрузите компьютер для применения изменений")
                else:
                    self.log_signal.emit("\nВНИМАНИЕ: Файлы не обнаружены в новой директории")
                    self.log_signal.emit(
                        "Проверьте, что Ollama имеет права на запись в указанную директорию")

                self.finish_signal.emit(True)
            else:
                error = self.process.stderr.read() if self.process.stderr else 'Неизвестная ошибка'
                error = self.clean_line(error)
                self.log_signal.emit(f"Ошибка установки: {error}")
                self.finish_signal.emit(False)

        except Exception as e:
            self.log_signal.emit(f"Ошибка: {str(e)}")
            self.finish_signal.emit(False)


class OllamaSettings(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки Ollama")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Группа установки модели
        install_group = QVBoxLayout()

        # Заголовок
        header = QLabel("Установка модели")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        install_group.addWidget(header)

        # Поле ввода и кнопки
        input_layout = QHBoxLayout()

        # Поле ввода модели
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Введите имя модели...")
        self.model_input.setMinimumWidth(200)  # Минимальная ширина поля ввода
        input_layout.addWidget(self.model_input, stretch=1)  # Растягиваем поле ввода

        # Кнопка перехода в библиотеку
        library_button = QPushButton("📚")
        library_button.setToolTip("Открыть библиотеку моделей Ollama")
        library_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #1565C0;
            }
        """)
        library_button.clicked.connect(self.open_ollama_library)
        input_layout.addWidget(library_button)

        # # Кнопка LmStudio
        # self.lmstudio_button = QPushButton("LMStudio")
        # self.lmstudio_button.setToolTip("Открыть LmStudio для управления моделями Ollama")
        # self.lmstudio_button.setStyleSheet("""
        #    QPushButton {
        #       background-color: #2196F3;
        #        color: white;
        #        border: none;
        #        border-radius: 4px;
        #        padding: 8px;
        #        font-size: 16px;
        #    }
        #    QPushButton:hover {
        #        background-color: #1976D2;
        #    }
        #    QPushButton:pressed {
        #        background-color: #1565C0;
        #    }
        # """)
        # self.lmstudio_button.clicked.connect(self.open_lmstudio)

        # Кнопка установки
        self.install_button = QPushButton("Установить")
        self.install_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.install_button.clicked.connect(self.install_model)
        input_layout.addWidget(self.install_button)
        # input_layout.addWidget(self.lmstudio_button)

        install_group.addLayout(input_layout)
        layout.addLayout(install_group)

        # Кнопка проверки Ollama
        self.check_btn = QPushButton("Проверить Ollama")
        layout.addWidget(self.check_btn)

        # Кнопка отмены установки
        self.cancel_btn = QPushButton("Отменить установку")
        self.cancel_btn.setEnabled(False)
        layout.addWidget(self.cancel_btn)

        # Выбор директории установки
        dir_layout = QHBoxLayout()
        self.select_dir_btn = QPushButton("Выбрать папку для установки")
        dir_layout.addWidget(self.select_dir_btn)
        self.selected_dir_label = QLabel()
        dir_layout.addWidget(self.selected_dir_label)
        layout.addLayout(dir_layout)

        # Список установленных моделей
        layout.addWidget(QLabel("Установленные модели:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.currentIndexChanged.connect(self.update_selected_model)
        layout.addWidget(self.model_combo)

        buttons_layout = QHBoxLayout()
        self.list_model_btn = QPushButton("Обновить список")
        self.delete_model_btn = QPushButton("Удалить")
        self.show_details_btn = QPushButton("Детали")
        self.run_model_btn = QPushButton("Запустить")
        self.run_model_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #EF6C00;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        buttons_layout.addWidget(self.list_model_btn)
        buttons_layout.addWidget(self.delete_model_btn)
        buttons_layout.addWidget(self.show_details_btn)
        buttons_layout.addWidget(self.run_model_btn)
        layout.addLayout(buttons_layout)

        # Добавляем раздел для запущенных моделей
        layout.addWidget(QLabel("Запущенные модели:"))
        self.running_combo = QComboBox()
        self.running_combo.setEditable(False)
        layout.addWidget(self.running_combo)

        running_buttons_layout = QHBoxLayout()
        self.refresh_running_btn = QPushButton("Обновить")
        self.stop_model_btn = QPushButton("Остановить")
        running_buttons_layout.addWidget(self.refresh_running_btn)
        running_buttons_layout.addWidget(self.stop_model_btn)
        layout.addLayout(running_buttons_layout)

        # Лог
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)

        # Добавляем прогресс-бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximum(0)  # Бесконечный прогресс
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Инициализация остальных переменных
        self.install_dir = os.path.expanduser("~/.ollama")
        self.models_dir = self.get_ollama_models_dir()
        self.selected_dir_label.setText(f"Папка: {self.models_dir}")
        self.selected_model_name = None
        self.models_info = []
        self.worker = None
        self.current_model = None

        # Подключение сигналов
        self.check_btn.clicked.connect(self.check_ollama)
        self.cancel_btn.clicked.connect(self.cancel_install)
        self.list_model_btn.clicked.connect(self.update_model_list)
        self.delete_model_btn.clicked.connect(self.delete_model)
        self.select_dir_btn.clicked.connect(self.select_install_dir)
        self.show_details_btn.clicked.connect(self.show_model_details)
        self.refresh_running_btn.clicked.connect(self.update_running_models)
        self.stop_model_btn.clicked.connect(self.stop_selected_model)
        self.run_model_btn.clicked.connect(self.run_selected_model)

        # Подключаем сигналы изменения выбора в комбобоксах
        self.model_combo.currentIndexChanged.connect(self.update_buttons_state)
        self.running_combo.currentIndexChanged.connect(self.update_buttons_state)

        # Инициализируем состояние кнопок
        self.update_buttons_state()

        # Проверяем ollama перед всем остальным
        self.log("Проверка ollama...")
        self.ollama_exe = self.check_ollama()
        if not self.ollama_exe:
            self.log("Ollama не найден. Инициализация прервана.")  # Добавил лог для ясности
            return  # Прекращаем инициализацию, если ollama не найден

        # Читаем системную переменную OLLAMA_MODELS
        self.install_dir = os.getenv("OLLAMA_MODELS")  # Можно убрать "" по умолчанию
        # os.getenv вернет None, если переменная не найдена

        if self.install_dir:  # None или пустая строка будут False
            self.log(f"Найдена системная переменная OLLAMA_MODELS: {self.install_dir}")
        else:
            self.install_dir = os.path.expanduser("~/.ollama")
            self.log(
                f"Системная переменная OLLAMA_MODELS не найдена. Используется путь по умолчанию: {self.install_dir}")

    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        self.status_text.repaint()

    def show_model_details(self):
        selected_text = self.model_combo.currentText()
        if not selected_text or not self.ollama_exe:
            self.log("Модель не выбрана или ollama недоступен")
            return

        model_name = selected_text.split(" (")[0]
        if not model_name:
            self.log("Ошибка: Не удалось определить имя модели")
            return

        model_info = next((item for item in self.models_info if item['name'] == model_name), None)
        if not model_info:
            self.log("Данные о модели не найдены. Обновите список моделей")
            return

        # Получаем дополнительную информацию о модели через ollama show
        try:
            result = subprocess.run(
                [self.ollama_exe, "show", model_name],
                capture_output=True,
                text=True,
                timeout=5
            )
            additional_info = result.stdout.strip() if result.returncode == 0 else "Информация недоступна"
        except Exception as e:
            additional_info = f"Ошибка получения информации: {str(e)}"

        dialog = QDialog(self)
        dialog.setWindowTitle("Детали модели")
        dialog.setMinimumWidth(500)
        layout = QFormLayout()

        # Основная информация
        layout.addRow("Имя модели:", QLabel(model_info['name']))
        layout.addRow("Размер:", QLabel(model_info['size']))
        layout.addRow("Полный путь:", QLabel(model_info['path']))

        # Дополнительная информация
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setPlainText(additional_info)
        info_text.setMinimumHeight(200)
        layout.addRow("Дополнительная информация:", info_text)

        dialog.setLayout(layout)
        dialog.exec()

    def update_model_list(self):
        if not self.ollama_exe:
            return

        previous_model = self.model_combo.currentText().split(" (")[
            0] if self.model_combo.currentText() else ""
        self.models_info = []
        self.model_combo.clear()
        try:
            result = subprocess.run(
                [self.ollama_exe, "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0 or "no models" in result.stderr.lower():
                self.log("Моделей не найдено")
                return

            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:  # Пропускаем заголовок
                for line in lines[1:]:
                    parts = line.strip().split()
                    if len(parts) < 3:
                        continue

                    name = parts[0]
                    size = parts[2]
                    ollama_home = os.getenv("OLLAMA_HOME", self.install_dir)
                    path = os.path.expanduser(f"{ollama_home}/models/{name}")
                    self.models_info.append({
                        "name": name,
                        "size": size,
                        "path": path
                    })
                    self.model_combo.addItem(f"{name} ({size})")

                # Восстанавливаем выбранную модель
                if previous_model:
                    for i in range(self.model_combo.count()):
                        if previous_model in self.model_combo.itemText(i):
                            self.model_combo.setCurrentIndex(i)
                            break

                self.log(f"Найдено моделей: {len(self.models_info)}")
            else:
                self.log("Моделей не найдено")
        except Exception as e:
            self.log(f"Ошибка получения списка: {str(e)}")

        self.update_buttons_state()

    def update_selected_model(self, index):
        selected_text = self.model_combo.itemText(index)
        self.selected_model_name = selected_text.split(" (")[0] if selected_text else None

    def delete_model(self):
        if not self.selected_model_name or not self.ollama_exe:
            self.log("Модель не выбрана или ollama недоступен")
            return

        confirm = QMessageBox.question(
            self,
            "Подтвердите удаление",
            f"Удалить модель {self.selected_model_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                result = subprocess.run(
                    [self.ollama_exe, "rm", self.selected_model_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.log(f"Модель {self.selected_model_name} удалена")
                    self.update_model_list()
                else:
                    self.log(f"Ошибка удаления: {result.stderr}")
            except Exception as e:
                self.log(f"Ошибка удаления: {str(e)}")

    def get_ollama_models_dir(self):
        # Проверяем переменную окружения (если установлена)
        custom_path = os.getenv("OLLAMA_MODELS")
        if custom_path:
            self.log(f"Найдена системная переменная OLLAMA_MODELS: {custom_path}")
            return custom_path

        # Иначе используем стандартный путь для macOS/Linux
        default_path = os.path.expanduser("~/.ollama/models")
        if os.path.exists(default_path):
            self.log(f"Cистемная переменная OLLAMA_MODELS не найдена, установлен путь: {default_path}")
            return default_path
        else:
            return "Модели Ollama не найдены. Убедитесь, что Ollama установлен и модели загружены."

    def select_install_dir(self):
        try:
            dir_name = QFileDialog.getExistingDirectory(
                self,
                "Выберите папку для установки",
                self.install_dir
            )
            if not dir_name:
                self.log("Директория не выбрана!")
                return
            if dir_name:
                dir_name = os.path.normpath(dir_name)
                confirm = QMessageBox.warning(
                    self,
                    "Важно!",
                    f"Модель будет установлена в {dir_name}/\nПродолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    self.install_dir = dir_name
                    # Устанавливаем системную переменную OLLAMA_MODELS
                    os.environ["OLLAMA_MODELS"] = f"{dir_name}"
                    self.selected_dir_label.setText(f"Папка: {self.install_dir}")
                    self.log(f"Папка установки изменена на: {self.install_dir}")
        except Exception as e:
            self.log(f"Ошибка при выборе папки: {str(e)}")

    def check_ollama(self):
        """Проверка наличия и доступности ollama"""
        try:
            if sys.platform == "win32":
                # Получаем все пути из PATH
                paths = []

                # Системный PATH
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                         "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                                         0, winreg.KEY_READ)
                    system_path = winreg.QueryValueEx(key, "Path")[0]
                    paths.extend(system_path.split(";"))
                    winreg.CloseKey(key)
                except Exception:
                    pass

                # Пользовательский PATH
                try:
                    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                         "Environment",
                                         0, winreg.KEY_READ)
                    user_path = winreg.QueryValueEx(key, "Path")[0]
                    paths.extend(user_path.split(";"))
                    winreg.CloseKey(key)
                except Exception:
                    pass

                # Текущий PATH из переменной окружения
                if "PATH" in os.environ:
                    paths.extend(os.environ["PATH"].split(os.pathsep))

                # Удаляем дубликаты и пустые строки
                paths = list(filter(None, set(paths)))

                # Проверяем наличие ollama.exe в каждом пути
                for path in paths:
                    try:
                        ollama_path = os.path.join(path.strip(), "ollama.exe")
                        if os.path.exists(ollama_path):
                            self.log(f"Найден ollama.exe в PATH: {ollama_path}")

                            # Проверяем версию
                            try:
                                version_result = subprocess.run(
                                    [ollama_path, "--version"],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if version_result.returncode == 0:
                                    version = version_result.stdout.strip()
                                    self.log(f"Версия Ollama: {version}")
                                    return ollama_path
                            except Exception:
                                continue
                    except Exception:
                        continue

                # Если не нашли в PATH, проверяем стандартный путь установки
                standard_path = os.path.expanduser(
                    "~\\AppData\\Local\\Programs\\Ollama\\ollama.exe")
                if os.path.exists(standard_path):
                    self.log(f"Найден ollama.exe: {standard_path}")
                    self.log("ВНИМАНИЕ: ollama.exe найден, но не добавлен в PATH")
                    self.log("Для работы приложения:")
                    self.log("1. Закройте это приложение")
                    self.log("2. Запустите его от имени администратора")
                    self.log("3. Путь к ollama.exe будет добавлен в PATH автоматически")

                    # Показываем диалог с предупреждением
                    QMessageBox.warning(
                        self,
                        "Требуются права администратора",
                        "Для корректной работы приложения необходимо:\n\n"
                        "1. Закрыть это приложение\n"
                        "2. Запустить его от имени администратора\n"
                        "3. Путь к ollama.exe будет добавлен в PATH автоматически",
                        QMessageBox.StandardButton.Ok
                    )
                    return None

                # Если нигде не нашли
                self.log("Ошибка: ollama.exe не найден. Убедитесь, что:")
                self.log("1. Ollama установлен в системе")
                self.log("2. Путь к папке с ollama.exe добавлен в PATH")
                self.log(
                    "3. Стандартный путь установки: C:\\Users\\<username>\\AppData\\Local\\Programs\\Ollama")
                return None

            else:
                # Для macOS просто проверяем наличие в PATH
                try:
                    result = subprocess.run(
                        ["which", "ollama"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        ollama_path = result.stdout.strip()
                        self.log(f"Найден ollama в PATH: {ollama_path}")

                        # Проверяем версию
                        version_result = subprocess.run(
                            [ollama_path, "--version"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if version_result.returncode == 0:
                            version = version_result.stdout.strip()
                            self.log(f"Версия Ollama: {version}")
                            return "ollama"
                    else:
                        self.log("Ошибка: ollama не найден в PATH")
                        self.log("Убедитесь, что Ollama установлен и путь добавлен в PATH")
                        return None
                except Exception as e:
                    self.log("Ошибка: ollama не найден в PATH")
                    self.log("Убедитесь, что Ollama установлен и путь добавлен в PATH")
                    return None

        except Exception as e:
            self.log(f"Ошибка при проверке ollama: {str(e)}")
            return None

    def cancel_install(self):
        if self.worker:
            self.worker.cancel()

            # Спрашиваем пользователя о необходимости очистки
            confirm = QMessageBox.question(
                self,
                "Очистка загрузки",
                "Очистить частично загруженную модель?\n\n"
                "Да - полностью удалить загруженные части\n"
                "Нет - сохранить для возможности продолжения загрузки",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # По умолчанию - не удалять
            )

            if confirm == QMessageBox.StandardButton.Yes:
                self.log("Очистка частично загруженной модели...")
                if self.worker.clean_model():
                    self.log("Модель успешно очищена")
                else:
                    self.log("Не удалось полностью очистить модель")
            else:
                self.log("Загруженные части сохранены для возможности продолжения")

            self.cancel_btn.setEnabled(False)
            self.install_button.setEnabled(True)

    def install_finished(self, success):
        # Восстанавливаем состояние кнопок
        self.cancel_btn.setEnabled(False)
        self.install_button.setEnabled(True)

        if success:
            self.update_model_list()
            self.log(
                f"Модель {self.model_input.text()} установлена в {self.install_dir}/{self.model_input.text()}!")
        else:
            self.log("Установка прервана или завершилась с ошибкой")

    # def open_lmstudio(self):
    #     """Открыть диалоговое окно LLMStudio"""
    #     lmstudio_settings = LmStudioSettings(self)
    #     lmstudio_settings.show()

    def open_ollama_library(self):
        """Открыть библиотеку моделей Ollama в браузере с поиском по введённому имени"""
        model_name = self.model_input.text().strip()  # Получаем имя модели из поля ввода

        try:
            # Формируем URL с параметром поиска
            base_url = "https://ollama.com/library"
            if model_name:
                search_url = f"{base_url}?q={quote(model_name)}"
            else:
                search_url = base_url  # Если имя пустое, открываем основную страницу

            webbrowser.open(search_url)
        except Exception as e:
            logging.error(f"Ошибка при открытии библиотеки моделей: {str(e)}")
            QMessageBox.warning(
                self,
                "Ошибка",
                "Не удалось открыть библиотеку моделей. Пожалуйста, проверьте введённое имя модели и попробуйте снова."
            )

    def install_model(self):
        """Обработчик нажатия кнопки установки модели"""
        try:
            model_name = self.model_input.text().strip()
            if not model_name:
                self.log("Ошибка: Не указано имя модели")
                return

            self.current_model = model_name
            self.worker = InstallWorker(model_name, self.install_dir)
            self.worker.log_signal.connect(self.log)
            self.worker.finish_signal.connect(self.install_finished)
            self.worker.start()

            # Блокируем кнопку установки и активируем кнопку отмены
            self.install_button.setEnabled(False)
            self.cancel_btn.setEnabled(True)
        except Exception as e:
            logging.error(f"Ошибка установки модели: {str(e,)}", exc_info=True, stack_info = True)
            self.log(f"Ошибка установки модели: {str(e)}")
            self.log(traceback.format_exc())  # Добавить стектрейс

    def update_buttons_state(self):
        """Обновление состояния кнопок интерфейса"""
        # Проверяем наличие выбранной модели в списке установленных
        has_selected_model = self.model_combo.currentText() != ""
        # Проверяем наличие запущенной модели
        has_running_model = self.running_combo.currentText() != ""

        # Обновляем состояние кнопок для установленных моделей
        self.delete_model_btn.setEnabled(has_selected_model)
        self.show_details_btn.setEnabled(has_selected_model)

        # Кнопка запуска активна только если:
        # 1. Есть выбранная модель
        # 2. Нет запущенных моделей
        self.run_model_btn.setEnabled(has_selected_model and not has_running_model)

        # Кнопка остановки активна только если есть запущенная модель
        self.stop_model_btn.setEnabled(has_running_model)

        # Кнопки обновления всегда активны
        self.refresh_running_btn.setEnabled(True)
        self.list_model_btn.setEnabled(True)

    def update_running_models(self):
        """Обновление списка запущенных моделей"""
        if not self.ollama_exe:
            return

        previous_model = self.running_combo.currentText()
        self.running_combo.clear()
        try:
            result = subprocess.run(
                [self.ollama_exe, "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:  # Пропускаем заголовок
                    for line in lines[1:]:
                        parts = line.strip().split()
                        if parts:
                            model_name = parts[0]
                            self.running_combo.addItem(model_name)
                    self.log(f"Найдено запущенных моделей: {len(lines) - 1}")
                else:
                    self.log("Нет запущенных моделей")
            else:
                self.log("Нет запущенных моделей")
        except Exception as e:
            self.log(f"Ошибка получения списка запущенных моделей: {str(e)}")

        # Восстанавливаем выбранную модель
        index = self.running_combo.findText(previous_model)
        if index >= 0:
            self.running_combo.setCurrentIndex(index)

        self.update_buttons_state()

    def stop_selected_model(self):
        """Остановка выбранной модели"""
        if not self.ollama_exe:
            return

        model_name = self.running_combo.currentText()
        if not model_name:
            self.log("Модель не выбрана")
            return

        try:
            self.stop_model_btn.setEnabled(False)
            self.run_model_btn.setEnabled(False)
            self.progress_bar.setMaximum(0)
            self.progress_bar.show()
            self.log(f"Останавливаем модель {model_name}...")

            result = subprocess.run(
                [self.ollama_exe, "stop", model_name],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                self.log(f"Модель {model_name} остановлена")
            else:
                self.log(f"Ошибка остановки модели: {result.stderr}")

        except Exception as e:
            self.log(f"Ошибка при остановке модели: {str(e)}")
        finally:
            self.progress_bar.hide()
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

            # Обновляем списки и состояние кнопок
            self.update_running_models()
            self.update_model_list()
            self.update_buttons_state()

    def run_selected_model(self):
        """Запуск выбранной модели"""
        if not self.ollama_exe:
            return

        model_name = self.model_combo.currentText()
        if not model_name:
            self.log("Модель не выбрана")
            return

        model_name = model_name.split(" (")[0]

        self.run_model_btn.setEnabled(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.show()

        self.run_worker = RunModelWorker(model_name, self.ollama_exe)
        self.run_worker.log_signal.connect(self.log)
        self.run_worker.progress_signal.connect(self.update_progress)
        self.run_worker.finish_signal.connect(self.run_finished)
        self.run_worker.start()

    def update_progress(self, value):
        """Обновление прогресс-бара"""
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}%")

    def run_finished(self, success):
        """Обработка завершения запуска модели"""
        # Скрываем прогресс
        self.progress_bar.hide()

        # Обновляем списки моделей и состояние кнопок
        self.update_running_models()
        self.update_model_list()

        if success:
            self.log("Модель успешно запущена и готова к использованию")
        else:
            self.log("Не удалось запустить модель")


class RunModelWorker(QThread):
    """Поток для запуска модели"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finish_signal = pyqtSignal(bool)

    def __init__(self, model_name, ollama_exe):
        super().__init__()
        self.model_name = model_name
        self.ollama_exe = ollama_exe
        self.server_process = None
        self.is_cancelled = False

    def check_server(self) -> bool:
        """Проверка работы сервера"""
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags")
            return response.status_code == 200
        except:
            return False

    def wait_for_server(self, timeout=30):
        """Ожидание запуска сервера"""
        import time
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.check_server():
                return True
            time.sleep(1)
        return False

    def check_model_loaded(self) -> bool:
        """Проверка загрузки модели"""
        try:
            import requests
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": "test",
                    "raw": True,
                    "stream": False
                },
                timeout=5
            )
            return response.status_code == 200
        except:
            return False

    def run(self):
        try:
            self.log_signal.emit(f"Запуск модели {self.model_name}...")

            # Проверяем сервер
            if not self.check_server():
                self.log_signal.emit("Запуск сервера Ollama...")
                if sys.platform == "win32":
                    self.server_process = subprocess.Popen(
                        [self.ollama_exe, "serve"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    self.server_process = subprocess.Popen(
                        [self.ollama_exe, "serve"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding='utf-8'
                    )

                if not self.wait_for_server():
                    self.log_signal.emit("Ошибка: Сервер не запустился")
                    self.finish_signal.emit(False)
                    return
                self.log_signal.emit("Сервер Ollama запущен")

            # Проверяем, загружена ли уже модель
            if self.check_model_loaded():
                self.log_signal.emit(f"Модель {self.model_name} уже загружена")
                self.progress_signal.emit(100)
                self.finish_signal.emit(True)
                return

            # Загружаем модель через API
            import requests
            import json

            self.log_signal.emit(f"Загрузка модели {self.model_name}...")
            self.progress_signal.emit(0)

            response = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": self.model_name},
                stream=True
            )

            for line in response.iter_lines():
                if self.is_cancelled:
                    break

                if line:
                    try:
                        data = json.loads(line)
                        if 'status' in data:
                            status = data['status'].lower()

                            if 'completed' in status:
                                self.progress_signal.emit(100)
                                break
                            elif 'downloading' in status:
                                try:
                                    percent_str = data['status'].split('%')[0].split(':')[
                                        -1].strip()
                                    percent = int(float(percent_str))
                                    self.progress_signal.emit(percent)
                                    self.log_signal.emit(f"Загрузка: {percent}%")
                                except:
                                    pass
                            else:
                                self.log_signal.emit(f"Статус: {data['status']}")

                        if 'error' in data:
                            self.log_signal.emit(f"Ошибка: {data['error']}")
                            self.finish_signal.emit(False)
                            return
                    except json.JSONDecodeError:
                        continue

            # Проверяем работоспособность модели
            retry_count = 0
            while retry_count < 3:
                if self.check_model_loaded():
                    self.log_signal.emit(
                        f"Модель {self.model_name} успешно загружена и готова к работе")
                    self.finish_signal.emit(True)
                    return
                retry_count += 1
                time.sleep(2)

            self.log_signal.emit("Ошибка: Не удалось проверить работоспособность модели")
            self.finish_signal.emit(False)

        except Exception as e:
            self.log_signal.emit(f"Ошибка при запуске модели: {str(e)}")
            self.finish_signal.emit(False)

    def cancel(self):
        """Отмена запуска"""
        self.is_cancelled = True
        if self.server_process:
            self.server_process.terminate()
