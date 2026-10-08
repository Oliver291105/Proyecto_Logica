from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from . import config

COLECCIONES = ["camiones", "accesos", "incidentes",
               "riesgos_eticos", "evaluaciones_llm"]


class DBError(Exception):
    """Error propio: la GUI atrapa este y muestra un mensaje amigable."""


_cliente = None


def _bd():
    """Devuelve la base de datos; si no hay conexión lanza DBError."""
    global _cliente
    try:
        if _cliente is None:
            _cliente = MongoClient(config.MONGO_URI,
                                   serverSelectionTimeoutMS=2500)
        _cliente.admin.command("ping")
        return _cliente[config.DB_NAME]
    except PyMongoError as e:
        _cliente = None
        raise DBError(f"No se pudo conectar a MongoDB: {e}")


def crear(coleccion, documento):
    """Inserta un documento y devuelve su id (texto)."""
    documento = {**documento, "creado": datetime.now()}
    try:
        return str(_bd()[coleccion].insert_one(documento).inserted_id)
    except PyMongoError as e:
        raise DBError(str(e))


def listar(coleccion, filtro=None, limite=500):
    """Devuelve una lista de documentos, los más recientes primero."""
    try:
        docs = list(_bd()[coleccion].find(filtro or {})
                    .sort("_id", -1).limit(limite))
    except PyMongoError as e:
        raise DBError(str(e))
    for d in docs:
        d["_id"] = str(d["_id"])
    return docs


def obtener(coleccion, filtro):
    """Devuelve un solo documento o None."""
    try:
        d = _bd()[coleccion].find_one(filtro)
    except PyMongoError as e:
        raise DBError(str(e))
    if d:
        d["_id"] = str(d["_id"])
    return d


def actualizar(coleccion, _id, cambios):
    try:
        _bd()[coleccion].update_one({"_id": ObjectId(_id)},
                                    {"$set": cambios})
    except PyMongoError as e:
        raise DBError(str(e))


def eliminar(coleccion, _id):
    try:
        _bd()[coleccion].delete_one({"_id": ObjectId(_id)})
    except PyMongoError as e:
        raise DBError(str(e))

def incidentes_por_categoria_semana(desde=None, hasta=None):
    """Agregación: cuenta incidentes por categoría y semana ISO."""
    filtro = {}
    if desde or hasta:
        filtro["creado"] = {}
        if desde:
            filtro["creado"]["$gte"] = desde
        if hasta:
            filtro["creado"]["$lte"] = hasta
    pipeline = [
        {"$match": filtro},
        {"$group": {
            "_id": {"categoria": "$clasificacion.categoria",
                    "anio": {"$isoWeekYear": "$creado"},
                    "semana": {"$isoWeek": "$creado"}},
            "total": {"$sum": 1}}},
        {"$sort": {"_id.anio": 1, "_id.semana": 1}},
    ]
    try:
        return list(_bd().incidentes.aggregate(pipeline))
    except PyMongoError as e:
        raise DBError(str(e))