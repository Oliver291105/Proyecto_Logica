# ============================================================
# EVALUACIÓN ÉTICA Y MATRIZ DE RIESGOS
# ============================================================

# Ahora vamos a crear una clase:

# EvaluadorRiesgosIA La clase permitirá registrar:

# módulo, riesgo, categoría, impacto, probabilidad, mitigación

# Por ejemplo:
# Módulo:Cámara de detección de somnolencia
# Riesgo: Sesgo en visión nocturna
# Categoría: Sesgo
# Impacto: Alto
# Probabilidad: Media
# Mitigación: Pruebas con diferentes condiciones de iluminación

# python -m py_compile logismart/riesgos.py para verificar que no exista ningun error 
# e indica que se pudo compilar

import json
import os
from datetime import datetime

from . import db

class EvaluadorRiesgosIA:
    """
    Clase encargada de registrar y exportar
    los riesgos éticos de un sistema de IA.
    """

    def __init__(self):
        """
        Constructor de la clase.

        self.riesgos almacenará todos los
        riesgos registrados.
        """

        self.riesgos = []

    # ========================================================
    # REGISTRAR RIESGO
    # ========================================================

    def registrar_riesgo(
        self,
        modulo,
        riesgo,
        categoria,
        impacto,
        probabilidad,
        mitigacion
    ):
        """
        Registra un nuevo riesgo dentro del sistema.
        """

        riesgo_nuevo = {
            "modulo": modulo,
            "riesgo": riesgo,
            "categoria": categoria,
            "impacto": impacto,
            "probabilidad": probabilidad,
            "mitigacion": mitigacion
        }

        self.riesgos.append(riesgo_nuevo)

    # ========================================================
    # MOSTRAR RIESGOS
    # ========================================================

    def mostrar_riesgos(self):
        """
        Muestra en pantalla todos los riesgos registrados.
        """

        print("\n========================================")
        print("       MATRIZ DE RIESGOS DE IA")
        print("========================================")

        for numero, riesgo in enumerate(
            self.riesgos,
            start=1
        ):

            print(f"\nRiesgo #{numero}")

            print(
                "Módulo:",
                riesgo["modulo"]
            )

            print(
                "Riesgo:",
                riesgo["riesgo"]
            )

            print(
                "Categoría:",
                riesgo["categoria"]
            )

            print(
                "Impacto:",
                riesgo["impacto"]
            )

            print(
                "Probabilidad:",
                riesgo["probabilidad"]
            )

            print(
                "Mitigación:",
                riesgo["mitigacion"]
            )

    # ========================================================
    # EXPORTAR REPORTE
    # ========================================================

    def exportar_reporte(self, archivo):
        """
        Exporta los riesgos registrados a un archivo JSON.

        Si la carpeta no existe, se crea automáticamente.
        """

        # ----------------------------------------------------
        # Obtener la carpeta donde se guardará el archivo
        # ----------------------------------------------------

        carpeta = os.path.dirname(archivo)

        # ----------------------------------------------------
        # Crear la carpeta si no existe
        # ----------------------------------------------------

        if carpeta:
            os.makedirs(
                carpeta,
                exist_ok=True
            )

        # ----------------------------------------------------
        # Crear estructura del reporte
        # ----------------------------------------------------

        reporte = {
            "total_riesgos": len(self.riesgos),
            "riesgos": self.riesgos
        }

        # ----------------------------------------------------
        # Abrir archivo
        # ----------------------------------------------------

        with open(
            archivo,
            "w",
            encoding="utf-8"
        ) as f:

            # ------------------------------------------------
            # Convertir Python a JSON
            # ------------------------------------------------

            json.dump(
                reporte,
                f,
                indent=4,
                ensure_ascii=False
            )

        # ----------------------------------------------------
        # Confirmación
        # ----------------------------------------------------

        print(
            f"\nReporte exportado correctamente en: {archivo}"
        )

# ============================================================
# PUNTAJE Y RIESGO RESIDUAL
# ============================================================

NIVELES = {"Baja": 1, "Bajo": 1,
           "Media": 2, "Medio": 2,
           "Alta": 3, "Alto": 3}


def puntaje(probabilidad, impacto):
    """probabilidad × impacto (resultado entre 1 y 9)."""
    return NIVELES[probabilidad] * NIVELES[impacto]


def clasificar_puntaje(p):
    if p >= 6:
        return "Crítico"
    if p >= 3:
        return "Medio"
    return "Bajo"


def calcular(riesgo):
    """Devuelve (puntaje_inicial, puntaje_residual) de un riesgo."""
    antes = puntaje(riesgo["probabilidad"], riesgo["impacto"])
    despues = puntaje(
        riesgo.get("prob_residual", riesgo["probabilidad"]),
        riesgo.get("imp_residual", riesgo["impacto"]),
    )
    return antes, despues


def es_critico(riesgo):
    """Un riesgo es crítico si su puntaje RESIDUAL es 6 o más."""
    return calcular(riesgo)[1] >= 6


# ============================================================
# PERSISTENCIA CON HISTÓRICO
# ============================================================

def guardar_riesgo(riesgo):
    """Inserta un riesgo en MongoDB con histórico inicial."""
    antes, despues = calcular(riesgo)
    riesgo = {**riesgo, "historico": [{
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "antes": antes, "despues": despues,
        "nota": "alta del riesgo",
    }]}
    return db.crear("riesgos_eticos", riesgo)


def editar_riesgo(_id, cambios, nota="edición"):
    """Actualiza un riesgo y AGREGA una entrada al histórico."""
    actual = db.obtener("riesgos_eticos", {"_id": _id}) \
        if False else next(
            (r for r in db.listar("riesgos_eticos") if r["_id"] == _id), None)
    if actual is None:
        raise ValueError("El riesgo no existe")

    nuevo = {**actual, **cambios}
    antes, despues = calcular(nuevo)
    historico = actual.get("historico", []) + [{
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "antes": antes, "despues": despues, "nota": nota,
    }]
    db.actualizar("riesgos_eticos", _id, {**cambios, "historico": historico})

# ============================================================
# PRUEBA DIRECTA DEL MÓDULO
# ============================================================

if __name__ == "__main__":

    evaluador = EvaluadorRiesgosIA()

    # --------------------------------------------------------
    # RIESGO 1
    # --------------------------------------------------------

    evaluador.registrar_riesgo(
        modulo="Cámara de detección",
        riesgo="Sesgo en condiciones nocturnas",
        categoria="Sesgo",
        impacto="Alto",
        probabilidad="Media",
        mitigacion=(
            "Realizar pruebas con diferentes "
            "condiciones de iluminación"
        )
    )

    # --------------------------------------------------------
    # RIESGO 2
    # --------------------------------------------------------

    evaluador.registrar_riesgo(
        modulo="Sistema de vigilancia",
        riesgo="Uso inadecuado de información personal",
        categoria="Privacidad",
        impacto="Alto",
        probabilidad="Media",
        mitigacion=(
            "Aplicar controles de acceso "
            "y políticas de retención"
        )
    )

    # --------------------------------------------------------
    # MOSTRAR
    # --------------------------------------------------------

    evaluador.mostrar_riesgos()

    # --------------------------------------------------------
    # EXPORTAR
    # --------------------------------------------------------

    evaluador.exportar_reporte(
        "reportes/reporte_riesgos.json"
    )