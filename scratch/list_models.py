import httpx
import os

def list_models():
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    
    print(f"Listando modelos disponibles...")
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(url)
            print(f"Status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                for model in data.get('models', []):
                    print(f"- {model['name']} (supports: {model['supportedGenerationMethods']})")
            else:
                print(f"Error: {r.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_models()
