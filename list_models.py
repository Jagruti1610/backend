import requests
from app.core.config import settings

API_KEY = settings.GEMINI_API_KEY

response = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}")

if response.status_code == 200:
    data = response.json()
    print("=== Models that support embedContent ===\n")
    for model in data.get("models", []):
        if "embedContent" in model.get("supportedGenerationMethods", []):
            name = model['name'].replace('models/', '')
            print(f"✅ {name}")
else:
    print(f"Error: {response.status_code}")
    print(response.text)