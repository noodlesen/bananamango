# nutrition_tracker/utils.py
import os
import json
import requests

PROXYAPI_KEY = os.getenv("PROXYAPI_KEY")
PROXYAPI_BASE = "https://openai.api.proxyapi.ru/v1"


def analyze_meal_text(text: str) -> dict:
    """
    Возвращает КБЖУ для переданного текста через GPT на ProxyAPI.
    """
    result: dict = {"calories": 0, "protein": 0, "fat": 0, "carbs": 0}

    prompt = f"Определи калории, белки, жиры и углеводы для следующего блюда: {text}"

    url = f"{PROXYAPI_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {PROXYAPI_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()

        content = data["choices"][0]["message"]["content"]

        # ожидаем JSON-подобный словарь
        parsed = json.loads(content.replace("'", '"'))

        result["calories"] = parsed.get("calories", 0)
        result["protein"] = parsed.get("protein", 0)
        result["fat"] = parsed.get("fat", 0)
        result["carbs"] = parsed.get("carbs", 0)

    except Exception:
        # при любой ошибке возвращаем нули
        pass

    return result
