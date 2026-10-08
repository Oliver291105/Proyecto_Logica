import requests

r = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "llama3.2", "prompt": "Responde solo: hola", "stream": False},
    timeout=60,
)
print(r.json()["response"])