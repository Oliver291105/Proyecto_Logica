from itertools import product


def evaluar_camion(P, Q, R, S, T=True, H=False):
    """
    P autorización, Q peso excedido, R materiales peligrosos,
    S certificación del camión, T certificación del conductor,
    H horario restringido.
    """

    # Reglas originales (no se tocan)
    A = P and S and not Q          # acceso estándar
    E = P and (R or Q)             # inspección especial

    # Reglas nuevas
    D = P and not T                # conductor sin certificación vigente
    B = R and H                    # peligrosos en horario restringido

    # Explicación: cada línea dice qué pasó y por qué
    pasos = []

    faltan = [n for n, ok in [("autorización P", P),
                              ("certificación S", S),
                              ("sin exceso de peso ¬Q", not Q)] if not ok]
    pasos.append(f"R1 A = P∧S∧¬Q → {int(A)}"
                 + (f" (falta: {', '.join(faltan)})" if faltan else ""))

    causas = [n for n, v in [("materiales peligrosos R", R),
                             ("peso excedido Q", Q)] if v]
    pasos.append(f"R2 E = P∧(R∨Q) → {int(E)}"
                 + (f" (causa: {', '.join(causas)})" if E else ""))

    pasos.append(f"R3 D = P∧¬T → {int(D)}"
                 + (" (conductor sin certificación vigente)" if D else ""))
    pasos.append(f"R4 B = R∧H → {int(B)}"
                 + (" (peligrosos en horario restringido)" if B else ""))

    # Decisión final, en orden de severidad
    if not P:
        decision, semaforo = "ACCESO DENEGADO", "rojo"
        pasos.append("Sin autorización (¬P): se deniega.")
    elif B:
        decision, semaforo = "ACCESO DENEGADO", "rojo"
        pasos.append("B activa: se bloquea aunque tenga autorización.")
    elif E or D:
        decision, semaforo = "ENVIAR A INSPECCIÓN", "amarillo"
        pasos.append("E o D activa: requiere inspección.")
    elif A and T:
        decision, semaforo = "ACCESO PERMITIDO", "verde"
        pasos.append("A cumplida y sin alertas: se permite.")
    else:
        decision, semaforo = "ACCESO DENEGADO", "rojo"
        pasos.append("No cumple A: se deniega.")

    return {
        # claves originales, para que main.py siga funcionando
        "autorizacion": P, "peso_excedido": Q,
        "carga_peligrosa": R, "certificacion": S,
        "acceso_estandar": A, "inspeccion_especial": E,
        # claves nuevas
        "conductor_vigente": T, "horario_restringido": H,
        "D": D, "B": B,
        "decision": decision, "semaforo": semaforo,
        "explicacion": pasos,
    }


def tabla_verdad():
    """Las 64 combinaciones de P,Q,R,S,T,H."""
    filas = []
    for c in product([False, True], repeat=6):
        r = evaluar_camion(*c)
        filas.append({**dict(zip("PQRSTH", map(int, c))),
                      "A": int(r["acceso_estandar"]),
                      "E": int(r["inspeccion_especial"]),
                      "D": int(r["D"]), "B": int(r["B"]),
                      "decision": r["decision"]})
    return filas


def detectar_conflictos():
    """Reto opcional: filas donde dos reglas dicen cosas opuestas."""
    t = tabla_verdad()
    a_y_e = [f for f in t if f["A"] and f["E"]]
    a_y_b = [f for f in t if f["A"] and f["B"]]
    return a_y_e, a_y_b