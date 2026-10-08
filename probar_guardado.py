from Logica import db, config
from Logica.clasificador import clasificar_hibrido, PROMPT

correo = "El camion ABC-123 tiene sobrepeso segun la bascula"
r, crudo = clasificar_hibrido(correo)

# Guardar la evaluación del LLM
db.crear("evaluaciones_llm", {
    "prompt": PROMPT.format(correo=correo),
    "respuesta": crudo,
    "modelo": config.MODELO_DEFECTO,
    "latencia": r["latencia"],
    "coincidio_reglas": not r["requiere_revision_humana"],
})

# Guardar el incidente ya clasificado
db.crear("incidentes", {
    "correo": correo,
    "clasificacion": r,
    "estado": "nuevo",
    "historial": ["creado"],
})
print("Guardado. Revisa Compass: evaluaciones_llm e incidentes.")