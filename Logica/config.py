import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "logismart")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELO_DEFECTO = os.getenv("OLLAMA_MODEL", "llama3.2")