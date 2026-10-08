from . import db, logica, riesgos

CAMIONES = [
    ("ABC-123", "CAM-101", "Transcarga", True, True),
    ("XYZ-987", "CAM-102", "Fletes MX", True, False),
    ("DEF-456", "CAM-103", "Logistica Norte", False, True),
    ("GHI-789", "CAM-104", "Transcarga", True, True),
]

#            placa      P      Q      R      S     T      H
ACCESOS = [
    ("ABC-123", True,  False, False, True, True,  False),
    ("XYZ-987", True,  True,  False, True, True,  False),
    ("DEF-456", False, False, False, True, True,  False),
    ("GHI-789", True,  False, True,  True, True,  True),
    ("XYZ-987", True,  False, False, True, False, False),
]

INCIDENTES = [
    ("Derrame de combustible en CAM-101, hay fuego en la zona de carga",
     "seguridad", "CRITICA", "nuevo"),
    ("El camion ABC-123 tiene sobrepeso segun la bascula",
     "peso", "ALTA", "en_atencion"),
    ("La certificacion del conductor de CAM-102 esta vencida",
     "documentacion", "MEDIA", "cerrado"),
    ("ola la barrera no abre pa la entrada",
     "acceso", "MEDIA", "nuevo"),
]

RIESGOS = [
    ("Asistente LLM", "Alucinaciones: respuestas inventadas sobre un camión",
     "Fiabilidad", "Alta", "Alta",
     "RAG con citas; 'no tengo información' sin registros", "Media", "Alta"),
    ("Clasificador de incidentes",
     "Sesgo con correos de ortografía informal o jerga",
     "Sesgo", "Media", "Alta",
     "Pruebas con correos informales y revisión humana", "Baja", "Alta"),
    ("Camiones", "Privacidad de datos personales del conductor",
     "Privacidad", "Media", "Alta",
     "Minimizar datos, control de acceso, retención limitada", "Baja", "Alta"),
    ("Motor de reglas", "Dependencia excesiva de la automatización",
     "Autonomía", "Media", "Media",
     "Marca de revisión humana y bitácora auditable", "Baja", "Media"),
]


def cargar():
    """Carga datos de demostración. No duplica lo que ya existe.
    Devuelve cuántos registros nuevos agregó por colección."""
    nuevos = {"camiones": 0, "accesos": 0, "incidentes": 0, "riesgos_eticos": 0}

    for placa, cid, empresa, aut, cert in CAMIONES:
        if not db.obtener("camiones", {"placa": placa}):
            db.crear("camiones", {"placa": placa, "camion_id": cid,
                                  "empresa": empresa, "autorizacion": aut,
                                  "cert_conductor": cert})
            nuevos["camiones"] += 1

    if not db.listar("accesos", {"operador": "demo"}, limite=1):
        for placa, P, Q, R, S, T, H in ACCESOS:
            r = logica.evaluar_camion(P, Q, R, S, T, H)
            cam = db.obtener("camiones", {"placa": placa}) or {}
            db.crear("accesos", {
                "placa": placa, "camion_id": cam.get("camion_id"),
                "P": P, "Q": Q, "R": R, "S": S, "T": T, "H": H,
                "A": r["acceso_estandar"], "E": r["inspeccion_especial"],
                "D": r["D"], "B": r["B"], "resultado": r["decision"],
                "explicacion": r["explicacion"], "operador": "demo"})
            nuevos["accesos"] += 1

    for texto, cat, pri, estado in INCIDENTES:
        if not db.obtener("incidentes", {"correo": texto}):
            db.crear("incidentes", {
                "correo": texto, "estado": estado,
                "clasificacion": {"categoria": cat, "prioridad": pri,
                                  "entidades": {}, "resumen": texto[:80],
                                  "fuente": "demo",
                                  "requiere_revision_humana": False},
                "historial": ["demo · creado"]})
            nuevos["incidentes"] += 1

    existentes = {r["descripcion"] for r in db.listar("riesgos_eticos")}
    for mod, desc, cat, pro, imp, mit, pr2, im2 in RIESGOS:
        if desc not in existentes:
            riesgos.guardar_riesgo({
                "modulo": mod, "descripcion": desc, "categoria": cat,
                "probabilidad": pro, "impacto": imp, "mitigacion": mit,
                "prob_residual": pr2, "imp_residual": im2})
            nuevos["riesgos_eticos"] += 1

    return nuevos