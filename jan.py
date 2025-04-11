import requests
import json

url = "http://localhost:1337/v1/chat/completions"
headers = {"Content-Type": "application/json"}
payload = {
    "model": "gemini-2.0-flash",
    "messages": [{"role": "user", "content": "Проверка доступа к модели. Привет, как дела?"}],
    "max_tokens": 100
}
timeout = 10  # Установите таймаут запроса в секундах

try:
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

    response_json = response.json()
    print(json.dumps(response_json, indent=4, ensure_ascii=False)) # Более читаемый вывод

except requests.exceptions.RequestException as e:
    print(f"Ошибка запроса: {e}")
except json.JSONDecodeError as e:
    print(f"Ошибка при разборе JSON: {e}")
    print(f"Содержимое ответа: {response}")  # Полезно для отладки
except Exception as e:
    print(f"Непредвиденная ошибка: {e}")