from Logica.clasificador import clasificar_reglas

correos = [
    "Derrame de combustible en CAM-101, hay fuego en la zona de carga",
    "El camion ABC-123 tiene sobrepeso segun la bascula",
    "La certificacion del conductor de CAM-102 esta vencida",
    "ola la barrera no abre pa la entrada",
    "Solo quiero saludar al equipo",
]

for c in correos:
    r = clasificar_reglas(c)
    print(f"{r['prioridad']:8} {r['categoria']:14} {r['entidades']}")
    print("   ", c)