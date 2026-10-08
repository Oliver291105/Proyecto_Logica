import json
import pandas as pd
from Logica import config
from Logica.clasificador import (clasificar_reglas, clasificar_llm,
                                    fusionar, PRIORIDADES)

with open("data/correos_etiquetados.json", encoding="utf-8") as f:
    correos = json.load(f)

filas = []
for i, c in enumerate(correos, 1):
    print(f"[{i}/{len(correos)}] {c['texto'][:60]}")
    reglas = clasificar_reglas(c["texto"])
    llm, _, lat = clasificar_llm(c["texto"], reintentos=1)   # UNA sola llamada
    hibrido = fusionar(reglas, llm, lat)

    resultados = {
        "reglas": (reglas, reglas["latencia"]),
        "llm": (llm, lat),
        "hibrido": (hibrido, hibrido["latencia"]),
    }
    for metodo, (r, latencia) in resultados.items():
        filas.append({
            "texto": c["texto"],
            "metodo": metodo,
            "real": c["prioridad"],
            "pred": r["prioridad"] if r else "FALLO",
            "cat_real": c["categoria"],
            "cat_pred": r["categoria"] if r else "FALLO",
            "latencia": latencia,
        })

df = pd.DataFrame(filas)
df.to_csv("resultados_experimento.csv", index=False, encoding="utf-8-sig")

print("\n" + "=" * 60)
for metodo in ["reglas", "llm", "hibrido"]:
    g = df[df.metodo == metodo]
    print(f"\n### {metodo.upper()}")
    print(f"Exactitud (prioridad): {(g.real == g.pred).mean():.0%}")
    print(f"Exactitud (categoría): {(g.cat_real == g.cat_pred).mean():.0%}")
    print(f"Latencia media: {g.latencia.mean():.2f} s")
    print(f"Fallos de JSON: {(g.pred == 'FALLO').sum()}")
    print(pd.crosstab(g.real, g.pred, rownames=["real"], colnames=["predicho"]))