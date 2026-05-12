import httpx
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Dime 'HOLA' si puedes leer esto."}
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 100,
        }
    }
    
    print(f"Probando Gemini con URL: {url.split('=')[0]}=***")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Respuesta: {data['candidates'][0]['content']['parts'][0]['text']}")
            else:
                print(f"Error: {response.text}")
    except Exception as e:
        print(f"Excepción: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
