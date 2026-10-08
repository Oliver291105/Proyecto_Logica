from pymongo import MongoClient
from pymongo.errors import PyMongoError

try:
    cliente = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2500)
    cliente.admin.command("ping")
    print("Conexión correcta")

    bd = cliente["logismart_prueba"]
    bd.camiones.insert_one({"placa": "ABC-123", "empresa": "Prueba"})
    print("Guardado:", bd.camiones.find_one({"placa": "ABC-123"}))
    cliente.drop_database("logismart_prueba")
    print("Base de prueba borrada")
except PyMongoError as e:
    print("No se pudo conectar:", e)