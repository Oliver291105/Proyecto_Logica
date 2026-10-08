from Logica import db

# CREATE
id1 = db.crear("camiones", {
    "placa": "ABC-123", "camion_id": "CAM-101",
    "empresa": "Transcarga",
    "autorizacion": True, "cert_conductor": True,
})
print("1. Creado:", id1)

# READ
print("2. Buscado:", db.obtener("camiones", {"placa": "ABC-123"}))
print("3. Lista:", len(db.listar("camiones")), "camión(es)")

# UPDATE
db.actualizar("camiones", id1, {"empresa": "Transcarga SA"})
print("4. Actualizado:", db.obtener("camiones", {"placa": "ABC-123"})["empresa"])

# DELETE
db.eliminar("camiones", id1)
print("5. Quedan:", len(db.listar("camiones")), "camión(es)")