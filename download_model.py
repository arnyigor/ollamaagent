# download_model.py

import os
import sys
import argparse
from pathlib import Path
from typing import Optional
from huggingface_hub import hf_hub_download


def download_model(repo_id: str, filename: str, output_dir: str = ".") -> str:
    """
    Скачивает модель с Hugging Face и возвращает путь к файлу.

    Args:
        repo_id (str): ID репозитория на Hugging Face.
        filename (str): Имя файла модели.
        output_dir (str): Локальная директория для сохранения модели.

    Returns:
        str: Путь к скачанному файлу.
    """
    try:
        print(f"📥 Скачиваем {filename} из {repo_id}...")

        # Создаем директорию если её нет
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Скачиваем файл
        file_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=output_dir
        )

        # Преобразуем в абсолютный путь для надежности
        absolute_path = os.path.abspath(file_path)
        print(f"✅ Модель успешно скачана: {absolute_path}")
        return absolute_path

    except Exception as e:
        print(f"❌ Ошибка при скачивании модели: {e}")
        sys.exit(1)


def create_modelfile(model_path: str, modelfile_path: str = "Modelfile"):
    """
    Создаёт Modelfile для ollama с расширенными настройками.
    """
    # Преобразуем пути к абсолютным для избежания ошибок
    abs_model_path = os.path.abspath(model_path)
    abs_modelfile_path = os.path.abspath(modelfile_path)

    # Получаем директорию Modelfile
    modelfile_dir = os.path.dirname(abs_modelfile_path)

    try:
        # Определяем, как ссылаться на модель в Modelfile
        if modelfile_dir and os.path.commonpath([abs_model_path, modelfile_dir]) == modelfile_dir:
            # Модель и Modelfile в одной директории - используем относительный путь
            relative_path = os.path.relpath(abs_model_path, modelfile_dir)
            model_reference = f"./{relative_path}"
        else:
            # Используем абсолютный путь
            model_reference = abs_model_path

        modelfile_content = f"""# 1. Указываем базовую модель (скачанную в формате GGUF)
FROM {model_reference}

# 2. Задаем шаблон промпта (TEMPLATE)
# Шаблон Llama 3, подходит для многих современных моделей
# TEMPLATE \"\"\"<|start_header_id|>system<|end_header_id|>
# 
# {{{{ .System }}}}<|eot_id|><|start_header_id|>user<|end_header_id|>
# 
# {{{{ .Prompt }}}}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
# 
# {{{{ .Response }}}}<|eot_id|>\"\"\"

# 3. Устанавливаем системное сообщение по умолчанию
# SYSTEM \"\"\"Ты — полезный и дружелюбный ИИ-ассистент. Отвечай на русском языке.\"\"\"

# 4. Настраиваем параметры генерации текста (PARAMETER)
# Температура: 0.7 — хороший баланс между креативностью и предсказуемостью
# PARAMETER temperature 0.7

# top_k: 40 — стандартное значение для ограничения выборки
# PARAMETER top_k 40

# top_p: 0.9 — стандартное значение для nucleus sampling
# PARAMETER top_p 0.9

# num_ctx: 4096 — безопасное значение для большинства систем
PARAMETER num_ctx 4096

# stop: Стоп-токены для шаблона Llama 3/Phi-3
# PARAMETER stop "<|start_header_id|>"
# PARAMETER stop "<|end_header_id|>"
# PARAMETER stop "<|eot_id|>"
# PARAMETER stop "<|reserved_special_token"

# 5. Дополнительные параметры для оптимизации (раскомментируйте нужное)
# num_gpu_layers: -1 = попытаться выгрузить все слои в VRAM
# PARAMETER num_gpu_layers -1

# seed: Закомментирован для случайной генерации. Раскомментируйте для воспроизводимости
# PARAMETER seed 42
"""

        # Создаем директорию для Modelfile если нужно
        if modelfile_dir:
            Path(modelfile_dir).mkdir(parents=True, exist_ok=True)

        with open(abs_modelfile_path, "w", encoding="utf-8") as f:
            f.write(modelfile_content)
        print(f"✅ Modelfile создан: {abs_modelfile_path}")

    except Exception as e:
        print(f"❌ Ошибка при создании Modelfile: {e}")
        sys.exit(1)


def run_download(
        repo_id: str = "janhq/Jan-v1-4B-GGUF",
        filename: str = "Jan-v1-4B-Q8_0.gguf",
        output_dir: str = "./models",
        modelfile_path: str = "./models/Modelfile"
) -> str:
    """
    Основная функция для скачивания модели и создания Modelfile.
    Может использоваться программно из кода.

    Args:
        repo_id (str): ID репозитория на Hugging Face
        filename (str): Имя файла модели
        output_dir (str): Директория для сохранения модели
        modelfile_path (str): Путь к Modelfile

    Returns:
        str: Путь к скачанной модели
    """
    # Скачиваем модель
    model_file = download_model(repo_id, filename, output_dir)

    # Создаём Modelfile
    create_modelfile(model_file, modelfile_path)

    # Формируем имя модели из repo_id (часть после последнего слэша)
    model_name = repo_id.split('/')[-1].lower()

    # Получаем абсолютный путь к Modelfile для вывода
    abs_modelfile_path = os.path.abspath(modelfile_path)

    print(f"✅ Готово! Теперь можно использовать:")
    print(f" ollama create {model_name} -f {os.path.dirname(abs_modelfile_path)}/{os.path.basename(modelfile_path)}")

    return model_file


def main(cli_args: Optional[list] = None):
    """
    Точка входа для командной строки.

    Args:
        cli_args (list, optional): Аргументы командной строки.
                                  Если None, используются sys.argv.
    """
    parser = argparse.ArgumentParser(description="Скачать модель с Hugging Face и создать Modelfile для ollama.")
    parser.add_argument("--repo-id", default="janhq/Jan-v1-4B-GGUF", help="ID репозитория на Hugging Face")
    parser.add_argument("--filename", default="Jan-v1-4B-Q8_0.gguf", help="Имя файла модели")
    parser.add_argument("--output-dir", default="./models", help="Директория для сохранения")
    parser.add_argument("--modelfile-path", default="./models/Modelfile", help="Путь к Modelfile")

    # Если переданы аргументы - парсим их, иначе используем sys.argv[1:]
    args = parser.parse_args(cli_args if cli_args is not None else sys.argv[1:])

    # Запускаем основную логику
    run_download(args.repo_id, args.filename, args.output_dir, args.modelfile_path)


if __name__ == "__main__":
    """ 
    python3.10 download_model.py \
    --repo-id janhq/Jan-v1-4B-GGUF \
    --filename Jan-v1-4B-Q4_K_M.gguf \
    --output-dir ./models
    --modelfile-path ./models/Modelfile
    """
    main()