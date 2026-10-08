from Logica import logica, db

# 1. Tres casos para ver los tres semáforos
casos = {
    "verde":    dict(P=True, Q=False, R=False, S=True),
    "amarillo": dict(P=True, Q=True,  R=False, S=True),
    "rojo":     dict(P=True, Q=False, R=True,  S=True, H=True),
}
for nombre, c in casos.items():
    r = logica.evaluar_camion(**c)
    print(f"\n[{nombre}] {r['decision']}")
    for paso in r["explicacion"]:
        print("   ", paso)

# 2. Guardar una decisión en 'accesos'
r = logica.evaluar_camion(P=True, Q=True, R=False, S=True)
id_acc = db.crear("accesos", {
    "placa": "XYZ-987", "camion_id": "CAM-102",
    "P": True, "Q": True, "R": False, "S": True, "T": True, "H": False,
    "resultado": r["decision"],
    "explicacion": r["explicacion"],
    "operador": "operador1",
})
print("\nGuardado en accesos:", id_acc)

# 3. Conflictos
a_e, a_b = logica.detectar_conflictos()
print(f"\nFilas con A=1 y E=1: {len(a_e)}")
print(f"Filas con A=1 y B=1: {len(a_b)}")
print("Total de filas en la tabla:", len(logica.tabla_verdad()))