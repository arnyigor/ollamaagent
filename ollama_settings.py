import json
import os
import subprocess
import sys
from shutil import which

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QTextEdit, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QFileDialog, QLabel, QDialog, QFormLayout, QLineEdit
)


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
                        cache_dir = os.path.join(self.install_dir, "models")
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
            models_dir = os.path.join(self.install_dir, "models").replace('\\', '/')
            os.makedirs(models_dir, exist_ok=True)

            self.log_signal.emit(f"Выбранная директория установки: {models_dir}")

            # Устанавливаем OLLAMA_MODELS как системную переменную
            if self.set_system_env_variable("OLLAMA_MODELS", models_dir):
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


class OllamaSettings(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OllamaAgent")
        self.setGeometry(100, 100, 600, 400)

        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)

        self.check_btn = QPushButton("Проверить Ollama")
        self.install_model_btn = QPushButton("Установить модель")
        self.cancel_btn = QPushButton("Отменить установку")
        self.cancel_btn.setEnabled(False)
        self.list_model_btn = QPushButton("Обновить список моделей")
        self.delete_model_btn = QPushButton("Удалить модель")
        self.show_details_btn = QPushButton("Детали выбранной модели")

        self.model_combo = QComboBox()
        self.model_combo.setEditable(False)
        self.model_combo.currentIndexChanged.connect(self.update_selected_model)

        self.recommended_combo = QComboBox()
        self.recommended_combo.addItems([
            "phi3:3.8b (Intel CPU-оптимизированная)",
            "codegemma:2b (Код-генерация)",
            "qwen2.5-coder:3b (Код-ревью)"
        ])
        self.recommended_combo.currentTextChanged.connect(self.update_model_input)

        self.model_name_input = QLineEdit()
        self.model_name_input.setPlaceholderText("Имя модели (например: phi3:3.8b)")

        self.select_dir_btn = QPushButton("Выбрать папку для установки")
        self.selected_dir_label = QLabel()

        layout = QVBoxLayout()
        layout.addWidget(self.check_btn)

        install_group = QVBoxLayout()
        install_group.addWidget(QLabel("Рекомендуемые модели:"))
        install_group.addWidget(self.recommended_combo)
        install_group.addWidget(self.model_name_input)
        install_group.addWidget(self.select_dir_btn)
        install_group.addWidget(self.install_model_btn)
        install_group.addWidget(self.cancel_btn)
        layout.addLayout(install_group)

        layout.addWidget(QLabel("Установленные модели:"))
        layout.addWidget(self.model_combo)
        layout.addWidget(self.list_model_btn)
        layout.addWidget(self.delete_model_btn)
        layout.addWidget(self.show_details_btn)
        layout.addWidget(self.selected_dir_label)
        layout.addWidget(self.status_text)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Читаем системную переменную OLLAMA_MODELS
        models_dir = self.get_system_env_variable("OLLAMA_MODELS")
        if models_dir:
            self.install_dir = models_dir
            self.log(f"Найдена системная переменная OLLAMA_MODELS: {self.install_dir}")
        else:
            self.install_dir = os.path.expanduser("~/.ollama")
            self.log(
                f"Системная переменная OLLAMA_MODELS не найдена, используется путь по умолчанию: {self.install_dir}")

        self.selected_dir_label.setText(f"Папка: {self.install_dir}")
        self.selected_model_name = None
        self.models_info = []
        self.worker = None
        self.current_model = None

        self.check_btn.clicked.connect(self.check_ollama)
        self.install_model_btn.clicked.connect(self.start_install)
        self.cancel_btn.clicked.connect(self.cancel_install)
        self.list_model_btn.clicked.connect(self.update_model_list)
        self.delete_model_btn.clicked.connect(self.delete_model)
        self.select_dir_btn.clicked.connect(self.select_install_dir)
        self.show_details_btn.clicked.connect(self.show_model_details)

    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        self.status_text.repaint()

    def show_model_details(self):
        selected_text = self.model_combo.currentText()
        if not selected_text:
            self.log("Модель не выбрана")
            return

        model_name = selected_text.split(" (")[0]
        if not model_name:
            self.log("Ошибка: Не удалось определить имя модели")
            return

        model_info = next((item for item in self.models_info if item['name'] == model_name), None)
        if not model_info:
            self.log("Данные о модели не найдены. Обновите список моделей")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Детали модели")
        layout = QFormLayout()
        layout.addRow("Имя модели:", QLabel(model_info['name']))
        layout.addRow("Размер:", QLabel(model_info['size']))
        layout.addRow("Полный путь:", QLabel(model_info['path']))
        dialog.setLayout(layout)
        dialog.exec()

    def update_model_list(self):
        self.models_info = []
        self.model_combo.clear()
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if "No models installed" in result.stderr:
                self.log("Моделей не найдено")
                return

            lines = result.stdout.strip().split('\n')[1:]
            for line in lines:
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

            self.log(f"Найдено моделей: {len(self.models_info)}")
        except Exception as e:
            self.log(f"Ошибка получения списка: {str(e)}")

    def update_selected_model(self, index):
        selected_text = self.model_combo.itemText(index)
        self.selected_model_name = selected_text.split(" (")[0] if selected_text else None

    def delete_model(self):
        if not self.selected_model_name:
            self.log("Модель не выбрана")
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
                    ["ollama", "rm", self.selected_model_name],
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

    def select_install_dir(self):
        try:
            dir_name = QFileDialog.getExistingDirectory(
                self,
                "Выберите папку для установки",
                self.install_dir
            )
            if dir_name:
                dir_name = os.path.normpath(dir_name)
                confirm = QMessageBox.warning(
                    self,
                    "Важно!",
                    f"Модель будет установлена в {dir_name}/models/\nПродолжить?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if confirm == QMessageBox.StandardButton.Yes:
                    self.install_dir = dir_name
                    self.selected_dir_label.setText(f"Папка: {self.install_dir}")
                    self.log(f"Папка установки изменена на: {self.install_dir}")
        except Exception as e:
            self.log(f"Ошибка при выборе папки: {str(e)}")

    def check_ollama(self):
        try:
            self.log("Проверка ollama...")
            success, message = check_ollama_version()

            if success:
                self.log(f"Ollama установлен! Версия: {message}")
            else:
                self.log(f"Ошибка: {message}")
                if sys.platform == "win32":
                    self.log("\nДля Windows:")
                    self.log("1. Найдите путь к папке, где установлен ollama.exe")
                    self.log("2. Добавьте этот путь в переменную PATH:")
                    self.log("   - Нажмите Win + R, введите sysdm.cpl и нажмите Enter")
                    self.log("   - Перейдите на вкладку 'Дополнительно'")
                    self.log("   - Нажмите 'Переменные среды'")
                    self.log("   - В разделе 'Переменные среды пользователя' найдите Path")
                    self.log("   - Добавьте путь к папке с ollama.exe")
                    self.log("   - Нажмите OK")
                    self.log(
                        "\nВажно: После добавления пути в PATH необходимо перезагрузить компьютер!")

        except Exception as e:
            self.log(f"Неожиданная ошибка: {str(e)}")
            import traceback
            self.log(traceback.format_exc())

    def update_model_input(self, combo_text):
        model_name = combo_text.split(" (")[0]
        self.model_name_input.setText(model_name)

    def start_install(self):
        model_name = self.model_name_input.text().strip() or \
                     self.recommended_combo.currentText().split(" (")[0]
        if not model_name:
            self.log("Ошибка: Не указано имя модели")
            return

        self.current_model = model_name  # Сохраняем имя текущей модели
        self.worker = InstallWorker(model_name, self.install_dir)
        self.worker.log_signal.connect(self.log)
        self.worker.finish_signal.connect(self.install_finished)
        self.worker.start()

        # Активируем кнопку отмены и блокируем кнопку установки
        self.cancel_btn.setEnabled(True)
        self.install_model_btn.setEnabled(False)

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
            self.install_model_btn.setEnabled(True)

    def install_finished(self, success):
        # Восстанавливаем состояние кнопок
        self.cancel_btn.setEnabled(False)
        self.install_model_btn.setEnabled(True)

        if success:
            self.update_model_list()
            self.log(
                f"Модель {self.model_name_input.text()} установлена в {self.install_dir}/models/{self.model_name_input.text()}!")
        else:
            self.log("Установка прервана или завершилась с ошибкой")

    def get_system_env_variable(self, name: str) -> str:
        """Получение системной переменной окружения"""
        try:
            if sys.platform == "win32":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     "SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment",
                                     0, winreg.KEY_READ)
                value, _ = winreg.QueryValueEx(key, name)
                winreg.CloseKey(key)
                return value
            else:
                # Для Linux/Mac проверяем различные файлы конфигурации
                possible_files = [
                    os.path.expanduser("~/.bashrc"),
                    os.path.expanduser("~/.bash_profile"),
                    os.path.expanduser("~/.zshrc"),
                    "/etc/environment"
                ]

                for file_path in possible_files:
                    if os.path.exists(file_path):
                        with open(file_path, "r") as f:
                            content = f.read()
                            # Ищем строку вида: export NAME=value или NAME=value
                            import re
                            match = re.search(f"(?:export\s+)?{name}=[\"']?([^\"'\n]+)[\"']?",
                                              content)
                            if match:
                                return match.group(1)

                return ""
        except Exception as e:
            self.log(f"Ошибка чтения переменной {name}: {str(e)}")
            return ""
