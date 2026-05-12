import httpx
import os
import sys

# Intentar cargar .env si existe
try:
    from dotenv import load_dotenv
    load_dotenv('backend/.env')
except ImportError:
    pass

def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY no encontrada en el entorno.")
        return

    model = "gemini-1.5-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": "Dime 'HOLA' si puedes leer esto y funcionar correctamente."}
                ]
            }
        ]
    }
    
    print(f"Probando Gemini 1.5 Flash...")
    print(f"URL: {url.split('=')[0]}=***")
    print(f"Key Prefix: {api_key[:10]}...")
    
    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, json=payload)
            print(f"Status Code: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                text = data['candidates'][0]['content']['parts'][0]['text']
                print(f"Respuesta de Gemini: {text}")
            else:
                print(f"Error de la API: {response.text}")
    except Exception as e:
        print(f"Error de conexión: {e}")

if __name__ == "__main__":
    test_gemini()
