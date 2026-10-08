import io
import json
import re
import textwrap
from datetime import date, datetime, time, timedelta

import pandas as pd
import requests
import streamlit as st

from Logica import asistente, clasificador, config, db, demo, logica, riesgos

st.set_page_config(page_title="LogiSmart", page_icon="🚚", layout="wide")
st.title("🚚 LogiSmart")

PATRON_PLACA = re.compile(r"^[A-Z]{3}-?\d{3,4}$")
EMOJI = {"verde": "🟢", "amarillo": "🟡", "rojo": "🔴"}
ESTADOS = ["nuevo", "en_atencion", "cerrado"]
ICONO_PRIORIDAD = {"CRITICA": "🔴", "ALTA": "🟠", "MEDIA": "🟡", "BAJA": "🟢"}
NIVELES = ["Baja", "Media", "Alta"]


# ============================================================
# UTILIDADES
# ============================================================
def seguro(funcion, *args, **kwargs):
    """Ejecuta una función de BD; si falla, muestra un error amable."""
    try:
        return funcion(*args, **kwargs)
    except db.DBError:
        st.error("⚠️ Base de datos no disponible. "
                 "Revisa que MongoDB esté encendido e inténtalo de nuevo.")
    except Exception as e:
        st.error(f"⚠️ Ocurrió un error inesperado: {e}")
    return None


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def indice(opciones, valor, defecto=0):
    return opciones.index(valor) if valor in opciones else defecto


def generar_pdf(titulo, docs):
    """Genera un PDF sencillo con una entrada por documento."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    ancho, alto = A4
    y = alto - 50
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, titulo)
    y -= 25
    c.setFont("Helvetica", 8)
    for i, d in enumerate(docs, 1):
        texto = f"{i}. " + ", ".join(f"{k}: {v}" for k, v in d.items()
                                     if k != "_id")
        texto = texto.encode("latin-1", "replace").decode("latin-1")
        for linea in textwrap.wrap(texto, 120):
            if y < 40:
                c.showPage()
                c.setFont("Helvetica", 8)
                y = alto - 40
            c.drawString(40, y, linea)
            y -= 11
        y -= 4
    c.save()
    return buf.getvalue()


# ============================================================
# ESTADO INICIAL (solo la primera vez)
# ============================================================
for letra, defecto in dict(P=False, Q=False, R=False,
                           S=True, T=True, H=False).items():
    st.session_state.setdefault(letra, defecto)

for clave, valor in {"cfg_modelo": config.MODELO_DEFECTO,
                     "cfg_reintentos": 2,
                     "cfg_umbral": 6,
                     "cfg_sim_correo": True}.items():
    st.session_state.setdefault(clave, valor)

st.session_state.setdefault("chat", [])


# ============================================================
# CALLBACKS (se ejecutan antes de redibujar la página)
# ============================================================
def buscar_camion():
    placa = st.session_state.get("placa", "").strip().upper()
    if not PATRON_PLACA.match(placa):
        st.session_state["msg_busqueda"] = (
            "warning", "Placa no válida. Ejemplo de formato: ABC-123.")
        return
    cam = seguro(db.obtener, "camiones", {"placa": placa})
    if cam:
        st.session_state["P"] = bool(cam.get("autorizacion"))
        st.session_state["T"] = bool(cam.get("cert_conductor", True))
        st.session_state["msg_busqueda"] = (
            "success", f"Encontrado: {cam.get('camion_id')} · {cam.get('empresa')}")
    else:
        st.session_state["msg_busqueda"] = (
            "info", "Placa no registrada: captura las premisas a mano.")


def clasificar_correo():
    correo = st.session_state.get("correo_nuevo", "").strip()
    if len(correo) < 10:
        st.session_state["msg_inc"] = (
            "warning", "Pega un correo de al menos 10 caracteres.")
        return
    st.session_state.pop("msg_inc", None)
    modelo = st.session_state["cfg_modelo"]
    with st.spinner("Consultando al LLM… puede tardar unos segundos"):
        resultado, crudo = clasificador.clasificar_hibrido(
            correo, modelo, st.session_state["cfg_reintentos"])
    st.session_state["clasif"] = {"correo": correo, "resultado": resultado}
    seguro(db.crear, "evaluaciones_llm", {
        "prompt": clasificador.PROMPT.format(correo=correo),
        "respuesta": crudo,
        "modelo": modelo,
        "latencia": resultado["latencia"],
        "coincidio_reglas": not resultado["requiere_revision_humana"],
        "tipo": "clasificacion",
    })


def guardar_incidente():
    datos = st.session_state["clasif"]
    r = dict(datos["resultado"])
    r["categoria"] = st.session_state["edit_cat"]
    r["prioridad"] = st.session_state["edit_pri"]
    r["resumen"] = st.session_state["edit_res"]
    editado = (r["categoria"] != datos["resultado"]["categoria"]
               or r["prioridad"] != datos["resultado"]["prioridad"])
    historial = [f"{ahora()} · creado"]
    if editado:
        historial.append(f"{ahora()} · clasificación editada por el operador")
    _id = seguro(db.crear, "incidentes", {
        "correo": datos["correo"], "clasificacion": r,
        "estado": "nuevo", "historial": historial})
    if _id:
        texto = f"Incidente guardado ({_id})."
        if r["prioridad"] in ("CRITICA", "ALTA"):
            if st.session_state["cfg_sim_correo"]:
                texto += " 📧 (Simulado) Correo enviado a soporte@logismart.com."
            else:
                texto += (" ⚠️ El envío real de correo no está configurado "
                          "(falta SMTP); activa el modo simulación.")
        st.session_state["msg_inc"] = ("success", texto)
        st.session_state.pop("clasif", None)
        st.session_state["correo_nuevo"] = ""


def cambiar_estado(inc, nuevo):
    historial = inc.get("historial", []) + [
        f"{ahora()} · estado: {inc['estado']} → {nuevo}"]
    seguro(db.actualizar, "incidentes", inc["_id"],
           {"estado": nuevo, "historial": historial})


# ============================================================
# PESTAÑAS
# ============================================================
(tab_panel, tab_acceso, tab_sim, tab_inc,
 tab_asis, tab_riesgos, tab_rep, tab_cfg) = st.tabs(
    ["Panel", "Control de acceso", "Simulador", "Incidentes",
     "Asistente", "Riesgos éticos", "Reportes", "Configuración"])

# ============================================================
# PANEL
# ============================================================
with tab_panel:
    st.header("Panel de control")
    f1, f2 = st.columns(2)
    desde = f1.date_input("Desde", value=date.today() - timedelta(days=30),
                          key="panel_desde")
    hasta = f2.date_input("Hasta", value=date.today(), key="panel_hasta")

    if desde > hasta:
        st.error("La fecha inicial no puede ser posterior a la final.")
    else:
        dt_desde = datetime.combine(desde, time.min)
        dt_hasta = datetime.combine(hasta, time.max)
        filtro = {"creado": {"$gte": dt_desde, "$lte": dt_hasta}}

        accesos = seguro(db.listar, "accesos", filtro) or []
        incs = seguro(db.listar, "incidentes", filtro) or []
        rs = seguro(db.listar, "riesgos_eticos") or []

        abiertos = sum(1 for i in incs if i.get("estado") != "cerrado")
        umbral = st.session_state["cfg_umbral"]
        criticos = sum(1 for r in rs if riesgos.calcular(r)[1] >= umbral)

        m1, m2, m3 = st.columns(3)
        m1.metric("Camiones atendidos", len(accesos))
        m2.metric("Incidentes abiertos", abiertos)
        m3.metric(f"Riesgos críticos (residual ≥ {umbral})", criticos)

        g1, g2 = st.columns(2)
        with g1:
            st.subheader("Decisiones de acceso")
            if accesos:
                conteo = pd.Series(
                    [a.get("resultado", "?") for a in accesos]).value_counts()
                st.bar_chart(conteo)
            else:
                st.info("Sin accesos en este rango de fechas.")
        with g2:
            st.subheader("Incidentes por categoría y semana")
            agg = seguro(db.incidentes_por_categoria_semana,
                         dt_desde, dt_hasta) or []
            if agg:
                df = pd.DataFrame([
                    {"semana": f"{a['_id']['anio']}-S{a['_id']['semana']:02d}",
                     "categoria": a["_id"].get("categoria") or "sin categoría",
                     "total": a["total"]} for a in agg])
                st.bar_chart(df.pivot_table(index="semana",
                                            columns="categoria",
                                            values="total", fill_value=0))
            else:
                st.info("Sin incidentes en este rango de fechas.")

# ============================================================
# CONTROL DE ACCESO
# ============================================================
with tab_acceso:
    st.header("Control de acceso")

    c1, c2, c3 = st.columns([2, 1, 2])
    c1.text_input("Placa", key="placa", placeholder="ABC-123")
    c2.button("Buscar camión", on_click=buscar_camion)
    c3.text_input("Operador", value="operador1", key="operador")

    if "msg_busqueda" in st.session_state:
        tipo, texto = st.session_state["msg_busqueda"]
        getattr(st, tipo)(texto)

    st.subheader("Premisas")
    a, b = st.columns(2)
    a.checkbox("P · Autorización previa", key="P")
    a.checkbox("Q · Peso excedido", key="Q")
    a.checkbox("R · Materiales peligrosos", key="R")
    b.checkbox("S · Certificación del camión", key="S")
    b.checkbox("T · Conductor con certificación vigente", key="T")
    b.checkbox("H · Horario restringido", key="H")

    if st.button("Evaluar y registrar", type="primary"):
        placa = st.session_state["placa"].strip().upper()
        if not PATRON_PLACA.match(placa):
            st.error("Escribe una placa válida (tres letras y 3 o 4 números, "
                     "por ejemplo ABC-123).")
        else:
            premisas = {n: st.session_state[n] for n in "PQRSTH"}
            r = logica.evaluar_camion(**premisas)

            st.subheader(f"{EMOJI[r['semaforo']]} {r['decision']}")
            for paso in r["explicacion"]:
                st.write("•", paso)

            doc = {"placa": placa, **premisas,
                   "A": r["acceso_estandar"], "E": r["inspeccion_especial"],
                   "D": r["D"], "B": r["B"],
                   "resultado": r["decision"],
                   "explicacion": r["explicacion"],
                   "operador": st.session_state["operador"] or "sin_operador"}
            with st.spinner("Guardando en la bitácora…"):
                _id = seguro(db.crear, "accesos", doc)
            if _id:
                st.caption(f"Registrado ✔ ({_id})")

    # ---------- CRUD de camiones ----------
    with st.expander("Gestión de camiones (alta, edición y baja)"):
        with st.form("alta_camion", clear_on_submit=True):
            st.markdown("**Nuevo camión**")
            k1, k2, k3 = st.columns(3)
            n_placa = k1.text_input("Placa")
            n_id = k2.text_input("ID de camión (ej. CAM-101)")
            n_emp = k3.text_input("Empresa")
            k4, k5 = st.columns(2)
            n_aut = k4.checkbox("Autorizado")
            n_cert = k5.checkbox("Conductor con certificación vigente",
                                 value=True)
            if st.form_submit_button("Agregar camión"):
                p = n_placa.strip().upper()
                if not PATRON_PLACA.match(p):
                    st.error("Placa no válida. Ejemplo: ABC-123.")
                elif not n_id.strip() or not n_emp.strip():
                    st.error("El ID de camión y la empresa son obligatorios.")
                elif seguro(db.obtener, "camiones", {"placa": p}):
                    st.error("Ya existe un camión con esa placa.")
                else:
                    if seguro(db.crear, "camiones", {
                            "placa": p, "camion_id": n_id.strip().upper(),
                            "empresa": n_emp.strip(), "autorizacion": n_aut,
                            "cert_conductor": n_cert}):
                        st.success("Camión agregado.")

        camiones = seguro(db.listar, "camiones") or []
        if camiones:
            for cam in camiones:
                x1, x2, x3 = st.columns([4, 2, 1])
                x1.write(f"**{cam['placa']}** · {cam.get('camion_id')} · "
                         f"{cam.get('empresa')}")
                nueva_aut = x2.checkbox(
                    "Autorizado", value=bool(cam.get("autorizacion")),
                    key=f"aut_{cam['_id']}")
                if nueva_aut != bool(cam.get("autorizacion")):
                    seguro(db.actualizar, "camiones", cam["_id"],
                           {"autorizacion": nueva_aut})
                    st.rerun()
                if x3.button("🗑", key=f"del_cam_{cam['_id']}",
                             help="Eliminar camión"):
                    seguro(db.eliminar, "camiones", cam["_id"])
                    st.rerun()
        else:
            st.info("No hay camiones registrados.")

# ============================================================
# SIMULADOR
# ============================================================
with tab_sim:
    st.header("Simulador de tablas de verdad")
    st.caption("Mueve los interruptores y mira cómo cambian las reglas. "
               "Esta pestaña no guarda nada.")

    cols = st.columns(6)
    nombres = {"P": "P Autorización", "Q": "Q Peso excedido",
               "R": "R Peligrosos", "S": "S Cert. camión",
               "T": "T Cert. conductor", "H": "H Horario restr."}
    defecto_sim = {"P": True, "Q": False, "R": False,
                   "S": True, "T": True, "H": False}
    sim = {}
    for col, (letra, texto) in zip(cols, nombres.items()):
        sim[letra] = col.toggle(texto, value=defecto_sim[letra],
                                key=f"sim_{letra}")

    rs_sim = logica.evaluar_camion(**sim)

    m = st.columns(5)
    m[0].metric("A = P∧S∧¬Q", int(rs_sim["acceso_estandar"]))
    m[1].metric("E = P∧(R∨Q)", int(rs_sim["inspeccion_especial"]))
    m[2].metric("D = P∧¬T", int(rs_sim["D"]))
    m[3].metric("B = R∧H", int(rs_sim["B"]))
    m[4].metric("Decisión",
                f"{EMOJI[rs_sim['semaforo']]} {rs_sim['decision'].title()}")

    for paso in rs_sim["explicacion"]:
        st.write("•", paso)

    tabla = pd.DataFrame(logica.tabla_verdad())
    actual = {k: int(v) for k, v in sim.items()}

    def resaltar(fila):
        es_actual = all(fila[k] == v for k, v in actual.items())
        return ["background-color: #ffe08a" if es_actual else ""] * len(fila)

    with st.expander("Ver las 64 combinaciones (la fila actual está resaltada)"):
        st.dataframe(tabla.style.apply(resaltar, axis=1),
                     use_container_width=True, height=400)

    a_e, a_b = logica.detectar_conflictos()
    st.info(f"Análisis de conflictos: {len(a_e)} filas con A=1 y E=1, "
            f"{len(a_b)} filas con A=1 y B=1.")

# ============================================================
# INCIDENTES
# ============================================================
with tab_inc:
    st.header("Bandeja de incidentes")

    st.subheader("Nuevo incidente")
    st.text_area("Pega aquí el correo", key="correo_nuevo", height=130,
                 placeholder="Ej: El camión ABC-123 tiene sobrepeso según la báscula")
    st.button("Clasificar", type="primary", on_click=clasificar_correo)

    if "msg_inc" in st.session_state:
        tipo, texto = st.session_state["msg_inc"]
        getattr(st, tipo)(texto)

    if "clasif" in st.session_state:
        res = st.session_state["clasif"]["resultado"]
        st.markdown("**Resultado de la clasificación**")
        st.caption(f"Fuente: {res['fuente']} · Latencia: {res['latencia']:.1f} s")

        if res["fuente"].startswith("reglas"):
            st.warning("El LLM no respondió; se usó el clasificador por reglas.")
        if res["requiere_revision_humana"]:
            st.warning("⚠️ Requiere revisión humana: el LLM y las reglas "
                       "no coincidieron (o el LLM falló). Se aplicó la "
                       "prioridad más alta por seguridad.")

        e1, e2 = st.columns(2)
        e1.selectbox("Categoría", clasificador.CATEGORIAS,
                     index=clasificador.CATEGORIAS.index(res["categoria"]),
                     key="edit_cat")
        e2.selectbox("Prioridad", clasificador.PRIORIDADES,
                     index=clasificador.PRIORIDADES.index(res["prioridad"]),
                     key="edit_pri")
        st.text_input("Resumen", value=res["resumen"], key="edit_res")
        ent = {k: v for k, v in res["entidades"].items() if v}
        st.caption(f"Entidades detectadas: {ent if ent else 'ninguna'}")
        st.button("Guardar incidente", on_click=guardar_incidente)

    st.divider()
    st.subheader("Incidentes registrados")
    filtro_estado = st.selectbox("Filtrar por estado", ["todos"] + ESTADOS,
                                 key="filtro_estado")
    consulta = {} if filtro_estado == "todos" else {"estado": filtro_estado}
    incidentes = seguro(db.listar, "incidentes", consulta) or []

    if not incidentes:
        st.info("No hay incidentes para mostrar.")

    for inc in incidentes:
        cl = inc.get("clasificacion", {})
        icono = ICONO_PRIORIDAD.get(cl.get("prioridad"), "⚪")
        titulo = (f"{icono} {cl.get('prioridad', '?')} · "
                  f"{cl.get('categoria', '?')} · {inc['estado']} · "
                  f"{inc['correo'][:50]}")
        with st.expander(titulo):
            st.write(inc["correo"])
            if cl.get("requiere_revision_humana"):
                st.caption("⚠️ Marcado para revisión humana")
            st.caption(f"Resumen: {cl.get('resumen', '')}")

            n1, n2, n3 = st.columns([2, 1, 1])
            nuevo = n1.selectbox("Estado", ESTADOS,
                                 index=indice(ESTADOS, inc["estado"]),
                                 key=f"est_{inc['_id']}")
            if n2.button("Actualizar estado", key=f"btn_{inc['_id']}"):
                if nuevo != inc["estado"]:
                    cambiar_estado(inc, nuevo)
                    st.rerun()
                else:
                    st.info("El estado no cambió.")
            if n3.button("🗑 Eliminar", key=f"del_inc_{inc['_id']}"):
                seguro(db.eliminar, "incidentes", inc["_id"])
                st.rerun()

            st.markdown("**Historial**")
            for linea in inc.get("historial", []):
                st.write("•", linea)

# ============================================================
# ASISTENTE
# ============================================================
with tab_asis:
    st.header("Asistente")
    st.caption("Responde solo con datos de MongoDB y cita los registros. "
               "Pregunta por una placa o ID, por ejemplo: "
               "«¿Por qué CAM-102 fue enviado a inspección?»")

    if st.button("Limpiar conversación"):
        st.session_state["chat"] = []
        st.rerun()

    for rol, texto, fuentes in st.session_state["chat"]:
        with st.chat_message(rol):
            st.write(texto)
            if fuentes:
                with st.expander("Fuentes consultadas"):
                    for f in fuentes:
                        st.code(f)

    pregunta = st.chat_input("Escribe tu pregunta…")
    if pregunta:
        st.session_state["chat"].append(("user", pregunta, []))
        with st.chat_message("user"):
            st.write(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("Buscando en la base de datos y pensando…"):
                try:
                    texto, fuentes = asistente.responder(
                        pregunta, st.session_state["cfg_modelo"])
                except db.DBError:
                    texto, fuentes = ("⚠️ La base de datos no está disponible.",
                                      [])
                except requests.RequestException:
                    texto, fuentes = ("⚠️ No pude contactar a Ollama. "
                                      "Verifica que esté abierto.", [])
                except Exception as e:
                    texto, fuentes = (f"⚠️ Error inesperado: {e}", [])
            st.write(texto)
            if fuentes:
                with st.expander("Fuentes consultadas"):
                    for f in fuentes:
                        st.code(f)
        st.session_state["chat"].append(("assistant", texto, fuentes))

# ============================================================
# RIESGOS ÉTICOS
# ============================================================
with tab_riesgos:
    st.header("Matriz de riesgos éticos")
    lista = seguro(db.listar, "riesgos_eticos") or []
    umbral = st.session_state["cfg_umbral"]

    if lista:
        filas = []
        for r in lista:
            antes, despues = riesgos.calcular(r)
            filas.append({"Riesgo": r["descripcion"][:45],
                          "Antes": antes, "Después": despues,
                          "Nivel residual": riesgos.clasificar_puntaje(despues),
                          "Crítico": "Sí" if despues >= umbral else "No"})
        df_r = pd.DataFrame(filas)
        st.subheader("Puntaje antes y después de la mitigación")
        st.bar_chart(df_r.set_index("Riesgo")[["Antes", "Después"]])
        st.dataframe(df_r, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay riesgos. Agrega el primero abajo.")

    # ---------- Alta ----------
    with st.expander("➕ Agregar riesgo"):
        with st.form("alta_riesgo", clear_on_submit=True):
            a1, a2, a3 = st.columns(3)
            f_mod = a1.text_input("Módulo")
            f_des = a2.text_input("Descripción")
            f_cat = a3.text_input("Categoría")
            b1, b2, b3, b4 = st.columns(4)
            f_pro = b1.selectbox("Probabilidad", NIVELES, index=1)
            f_imp = b2.selectbox("Impacto", NIVELES, index=2)
            f_pr2 = b3.selectbox("Prob. residual", NIVELES, index=0)
            f_im2 = b4.selectbox("Impacto residual", NIVELES, index=2)
            f_mit = st.text_input("Mitigación")
            if st.form_submit_button("Guardar riesgo"):
                if not (f_mod.strip() and f_des.strip() and f_mit.strip()):
                    st.error("Módulo, descripción y mitigación son obligatorios.")
                else:
                    if seguro(riesgos.guardar_riesgo, {
                            "modulo": f_mod.strip(),
                            "descripcion": f_des.strip(),
                            "categoria": f_cat.strip() or "Sin categoría",
                            "probabilidad": f_pro, "impacto": f_imp,
                            "prob_residual": f_pr2, "imp_residual": f_im2,
                            "mitigacion": f_mit.strip()}):
                        st.success("Riesgo guardado.")
                        st.rerun()

    # ---------- Edición y baja ----------
    if lista:
        with st.expander("✏️ Editar o eliminar riesgo"):
            opciones = {r["_id"]: f"{r['modulo']} · {r['descripcion'][:40]}"
                        for r in lista}
            sel = st.selectbox("Riesgo", list(opciones),
                               format_func=lambda i: opciones[i],
                               key="riesgo_sel")
            r = next(x for x in lista if x["_id"] == sel)
            k = sel  # claves únicas por riesgo para que el formulario se actualice

            with st.form(f"editar_{k}"):
                a1, a2, a3 = st.columns(3)
                e_mod = a1.text_input("Módulo", r["modulo"], key=f"m_{k}")
                e_des = a2.text_input("Descripción", r["descripcion"],
                                      key=f"d_{k}")
                e_cat = a3.text_input("Categoría", r.get("categoria", ""),
                                      key=f"c_{k}")
                b1, b2, b3, b4 = st.columns(4)
                e_pro = b1.selectbox("Probabilidad", NIVELES,
                                     index=indice(NIVELES, r["probabilidad"]),
                                     key=f"p_{k}")
                e_imp = b2.selectbox("Impacto", NIVELES,
                                     index=indice(NIVELES, r["impacto"]),
                                     key=f"i_{k}")
                e_pr2 = b3.selectbox(
                    "Prob. residual", NIVELES,
                    index=indice(NIVELES, r.get("prob_residual",
                                                r["probabilidad"])),
                    key=f"pr_{k}")
                e_im2 = b4.selectbox(
                    "Impacto residual", NIVELES,
                    index=indice(NIVELES, r.get("imp_residual", r["impacto"])),
                    key=f"ir_{k}")
                e_mit = st.text_input("Mitigación", r.get("mitigacion", ""),
                                      key=f"mi_{k}")
                e_nota = st.text_input("Motivo del cambio (va al histórico)",
                                       key=f"n_{k}")
                if st.form_submit_button("Guardar cambios"):
                    if not (e_mod.strip() and e_des.strip()):
                        st.error("Módulo y descripción son obligatorios.")
                    else:
                        ok = seguro(riesgos.editar_riesgo, sel, {
                            "modulo": e_mod.strip(),
                            "descripcion": e_des.strip(),
                            "categoria": e_cat.strip(),
                            "probabilidad": e_pro, "impacto": e_imp,
                            "prob_residual": e_pr2, "imp_residual": e_im2,
                            "mitigacion": e_mit.strip()},
                            e_nota.strip() or "edición")
                        st.success("Riesgo actualizado.")
                        st.rerun()

            st.markdown("**Histórico**")
            hist = r.get("historico", [])
            if hist:
                st.dataframe(pd.DataFrame(hist), hide_index=True,
                             use_container_width=True)
            else:
                st.caption("Sin histórico.")

            confirmar = st.checkbox("Confirmo que quiero eliminar este riesgo",
                                    key=f"conf_{k}")
            if st.button("🗑 Eliminar riesgo", disabled=not confirmar,
                         key=f"delr_{k}"):
                seguro(db.eliminar, "riesgos_eticos", sel)
                st.rerun()

# ============================================================
# REPORTES
# ============================================================
with tab_rep:
    st.header("Reportes")
    col_sel = st.selectbox("Colección a exportar", db.COLECCIONES,
                           key="rep_col")
    docs = seguro(db.listar, col_sel) or []

    if not docs:
        st.info("No hay datos en esta colección.")
    else:
        st.caption(f"{len(docs)} registros")
        df_rep = pd.DataFrame(docs).astype(str)
        st.dataframe(df_rep, use_container_width=True, hide_index=True)

        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ CSV", df_rep.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{col_sel}.csv", mime="text/csv")
        d2.download_button(
            "⬇ JSON",
            json.dumps(docs, default=str, ensure_ascii=False, indent=2),
            file_name=f"{col_sel}.json", mime="application/json")
        d3.download_button("⬇ PDF", generar_pdf(f"Reporte: {col_sel}", docs),
                           file_name=f"{col_sel}.pdf",
                           mime="application/pdf")

    st.caption("El experimento de 30 correos se ejecuta con "
               "`python ejecutar_experimento.py` y genera "
               "`resultados_experimento.csv`.")

# ============================================================
# CONFIGURACIÓN
# ============================================================
with tab_cfg:
    st.header("Configuración")

    st.text_input("Modelo de Ollama", key="cfg_modelo",
                  help="Debe estar descargado, por ejemplo llama3.2")
    st.slider("Reintentos si el JSON del LLM es inválido", 0, 5,
              key="cfg_reintentos")
    st.slider("Umbral de riesgo crítico (puntaje residual)", 1, 9,
              key="cfg_umbral",
              help="Un riesgo es crítico si su puntaje residual es mayor o igual.")
    st.toggle("Modo simulación de correo", key="cfg_sim_correo",
              help="Si está activo, los correos de soporte solo se simulan.")

    st.divider()
    st.subheader("Datos de demostración")
    st.caption("Carga camiones, accesos, incidentes y riesgos de ejemplo. "
               "Puedes pulsarlo más de una vez: no duplica lo que ya existe.")
    if st.button("Cargar datos de demostración", type="primary"):
        with st.spinner("Cargando datos…"):
            nuevos = seguro(demo.cargar)
        if nuevos is not None:
            total = sum(nuevos.values())
            if total:
                st.success("Cargado: " + ", ".join(
                    f"{v} {k}" for k, v in nuevos.items() if v))
            else:
                st.info("Los datos de demostración ya estaban cargados.")
    st.divider()
    st.subheader("Diagnóstico de conexiones")
    t1, t2 = st.columns(2)
    if t1.button("Probar MongoDB"):
        try:
            db._bd()
            st.success(f"MongoDB conectado ({config.MONGO_URI}).")
        except db.DBError as e:
            st.error(f"No se pudo conectar a MongoDB: {e}")
    if t2.button("Probar Ollama"):
        try:
            resp = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=5)
            resp.raise_for_status()
            modelos = [m["name"] for m in resp.json().get("models", [])]
            st.success("Ollama responde. Modelos instalados: "
                       + (", ".join(modelos) if modelos else "ninguno"))
        except requests.RequestException as e:
            st.error(f"No se pudo contactar a Ollama: {e}")