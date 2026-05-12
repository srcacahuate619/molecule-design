"""
Verificación rápida: Gemini 2.5-flash desde el worker.
"""
import httpx
import os

# Cargar settings
from core.config import get_settings
settings = get_settings()

print(f"Modelo configurado: {settings.gemini_model}")
print(f"API Key: {'SET (' + settings.gemini_api_key[:10] + '...)' if settings.gemini_api_key else 'NONE'}")

url = f"https://generativelanguage.googleapis.com/v1/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
payload = {"contents": [{"parts": [{"text": "Responde solo: FUNCIONA"}]}]}

with httpx.Client(timeout=20.0) as client:
    r = client.post(url, json=payload)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        print(f"✅ Gemini respondió: {text.strip()}")
    else:
        print(f"❌ Error: {r.text[:300]}")
