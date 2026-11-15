"""
Radar Agro GitHub
-----------------
Unifica los rastreos internacional + Colombia/español + inglés en una sola app.
- Parte SIEMPRE del CSV curado (radar_agronomia.csv): no rehace nada desde cero.
- "Buscar nuevos" consulta GitHub y agrega SOLO los repos que no están en el CSV.
- Buscador de texto, filtros, favoritos, check, prioridad, estado y notas editables.
- Guarda en el servidor y (opcional) hace commit del CSV al mismo repo de GitHub.
"""

import base64
import hashlib
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Radar Agro GitHub", page_icon="🌱", layout="wide")

CSV_PATH = Path(__file__).parent / "radar_agronomia.csv"
API = "https://api.github.com"

# ───────────────────────── Esquema del CSV ─────────────────────────
COLUMNAS = [
    "Check", "Favorito", "Prioridad", "Estado", "Proyecto",
    "Autor / Institución", "Dominio Principal", "Tipo de Solución",
    "Enfoque Geográfico", "Lenguaje", "Estrellas", "Score", "Enlace GitHub",
    "Notas_Decision",
    # columnas nuevas (los repos del CSV viejo quedan en blanco)
    "Descripción", "Etiquetas", "Actualizado", "Agregado", "Origen",
    "Idea / Extracto README", "Web / Contacto",
]
EDITABLES = [
    "Check", "Favorito", "Prioridad", "Estado", "Dominio Principal",
    "Tipo de Solución", "Enfoque Geográfico", "Notas_Decision",
]
COLUMNAS_VISTA = [
    "Check", "Favorito", "Prioridad", "Estado", "Proyecto", "Autor / Institución",
    "Dominio Principal", "Tipo de Solución", "Enfoque Geográfico", "Lenguaje",
    "Estrellas", "Score", "Enlace GitHub", "Notas_Decision", "Descripción",
    "Actualizado", "Agregado",
]
CAMPOS_BUSQUEDA = [
    "Proyecto", "Autor / Institución", "Dominio Principal", "Tipo de Solución",
    "Enfoque Geográfico", "Lenguaje", "Descripción", "Etiquetas",
    "Idea / Extracto README", "Notas_Decision",
]
PRIORIDADES = ["P1 - Alta", "P2 - Media", "P3 - Explorar"]
ESTADOS = ["Nuevo", "Pendiente", "Me interesa", "Lo estoy haciendo",
           "Probado / Hecho", "Descartado"]
DOMINIO_DEFECTO = "Gestión Agrícola, Asistentes IA y Datos Abiertos"
TIPO_DEFECTO = "Plataforma / App Web-Móvil"

# ───────────────────────── Búsquedas en GitHub ─────────────────────────
# {p} se reemplaza por la fecha "pushed desde". GitHub solo admite ~5 operadores
# AND/OR/NOT por consulta, por eso las consultas largas se partieron.
BUSQUEDAS = [
    # Internacional (por idioma)
    dict(grupo="Internacional", nombre="China (IA y plagas)", enfoque="Asia (China / Japón / India)",
         q="(智慧农业 OR 精准农业 OR 病虫害 OR 作物产量) stars:>=3 pushed:>{p}"),
    dict(grupo="Internacional", nombre="Japón (Smart Agri y robótica)", enfoque="Asia (China / Japón / India)",
         q="(スマート農業 OR 精密農業 OR 農業AI OR 農学 OR 作況) size:>80 pushed:>{p}"),
    dict(grupo="Internacional", nombre="Tailandia (IoT tropical)", enfoque="Asia (China / Japón / India)",
         q="(เกษตรอัจฉริยะ OR เกษตรแม่นยำ OR โรคพืช OR การเกษตร) size:>50 pushed:>{p}"),
    dict(grupo="Internacional", nombre="Rusia (satélites y suelos)", enfoque="Europa / Norteamérica",
         q='("сельское хозяйство" OR агрономия OR урожайность OR "точное земледелие") size:>80 pushed:>{p}'),
    dict(grupo="Internacional", nombre="Francia (agroecología y modelos)", enfoque="Europa / Norteamérica",
         q="(agronomie OR agriculture) (teledetection OR irrigation OR rendement OR capteur) size:>100 pushed:>{p}"),
    dict(grupo="Internacional", nombre="Global (IoT, drones y sensores)", enfoque="Global / Multi-región",
         q="(smart-farming OR agricultural-robotics OR soil-sensor OR crop-disease) stars:>=5 pushed:>{p}"),
    # Colombia y español
    dict(grupo="Colombia y español", nombre="Colombia agro", enfoque="Colombia / Latinoamérica",
         q="colombia (agricultura OR agronomia OR cultivos) size:>50 pushed:>{p}"),
    dict(grupo="Colombia y español", nombre="Instituciones Colombia", enfoque="Colombia / Latinoamérica",
         q="(agrosavia OR ciat OR ideam OR fedecafe OR cenipalma) size:>30"),
    dict(grupo="Colombia y español", nombre="Cultivos clave", enfoque="Colombia / Latinoamérica",
         q="(cafe OR cacao OR palma OR aguacate) (agronomia OR cultivo OR colombia) size:>50"),
    dict(grupo="Colombia y español", nombre="Agronomía en español", enfoque="Colombia / Latinoamérica",
         q="(agronomia OR agricultura) (teledeteccion OR precision OR suelos OR clima) size:>80 pushed:>{p}"),
    # Becas y empleo
    dict(grupo="Becas y empleo", nombre="Becas y empleo (español)", enfoque="Global / Multi-región",
         q="(becas OR convocatoria OR empleo) (agricultura OR agronomia)"),
    dict(grupo="Becas y empleo", nombre="Becas y empleo (inglés)", enfoque="Global / Multi-región",
         q="(scholarship OR fellowship OR jobs) (agriculture OR agronomy)"),
    # Inglés
    dict(grupo="Inglés", nombre="EN · Agronomía", enfoque="Global / Multi-región",
         q='(agronomy OR agronomic OR "crop management") stars:>=3 pushed:>{p}'),
    dict(grupo="Inglés", nombre="EN · Agricultura y herramientas", enfoque="Global / Multi-región",
         q="(agriculture OR farming) (toolkit OR library OR dashboard OR api) stars:>=5 pushed:>{p}"),
    dict(grupo="Inglés", nombre="EN · Fitomejoramiento y fenotipado", enfoque="Global / Multi-región",
         q='("plant breeding" OR phenotyping OR "genomic selection") (crop OR plant) stars:>=2 pushed:>{p}'),
    dict(grupo="Inglés", nombre="EN · Fitopatología", enfoque="Global / Multi-región",
         q='("plant disease" OR "plant pathology" OR "crop disease") (detection OR model OR dataset) stars:>=2 pushed:>{p}'),
    dict(grupo="Inglés", nombre="EN · Teledetección y drones", enfoque="Global / Multi-región",
         q='("precision agriculture" OR "crop monitoring") (satellite OR UAV OR NDVI OR sentinel) stars:>=3 pushed:>{p}'),
    dict(grupo="Inglés", nombre="EN · Modelos de cultivo y datos abiertos", enfoque="Global / Multi-región",
         q='("crop model" OR "crop simulation" OR "open data") (agriculture OR crop) stars:>=3 pushed:>{p}'),
    dict(grupo="Inglés", nombre="EN · Agroecología y suelos", enfoque="Global / Multi-región",
         q='(agroecology OR "soil health" OR "soil carbon" OR "regenerative agriculture") stars:>=2 pushed:>{p}'),
]
GRUPOS = list(dict.fromkeys(b["grupo"] for b in BUSQUEDAS))

# ───────────────────────── Clasificación automática (aproximada) ─────────────────────────
DOMINIOS = {
    "Modelación de Cultivos y Simulación": [
        "crop model", "crop simulation", "simulat", "apsim", "dssat", "aquacrop",
        "growth model", "yield model", "simulador", "modelo de cultivo"],
    "Teledetección, SIG y Geoespacial": [
        "remote sensing", "satellite", "sentinel", "landsat", "ndvi", "gis", "qgis",
        "geospatial", "earth engine", "raster", "teledeteccion", "teledetección", "遥感", "спутник"],
    "Robótica Agrícola, Drones y Maquinaria": [
        "robot", "drone", "dron", "uav", "ros2", "tractor", "harvest", "machinery", "autonomous"],
    "Fitopatología, Plagas y Visión Artificial": [
        "disease", "pest", "pathology", "plaga", "weed", "病虫害", "blight", "leaf",
        "yolo", "phenotyp", "fitopat", "enfermedad"],
    "IoT, Sensores de Suelo y Riego Inteligente": [
        "iot", "sensor", "irrigation", "esp32", "esp8266", "arduino", "mqtt",
        "soil moisture", "riego", "greenhouse", "invernadero"],
    "Hidrometeorología, Clima y Datos Colombia/Regional": [
        "weather", "climate", "hydromet", "ideam", "rainfall", "precipitation", "clima",
        "colombia", "agrosavia", "fedecafe", "cenipalma", "ciat", "sipsa", "datos abiertos"],
}
TIPOS = {
    "Firmware / Hardware IoT": ["firmware", "esp32", "esp8266", "arduino", "stm32", "pcb", "hardware", "raspberry"],
    "Dataset / Ontología / Recurso": [
        "dataset", "data set", "ontology", "benchmark", "corpus", "awesome", "curated",
        "recursos", "becas", "scholarship", "fellowship", "jobs"],
    "Librería / Plugin SIG-SDK": [
        "library", "package", "sdk", "plugin", "pip install", "cran", "toolkit", "wrapper", "api"],
    "Modelo / Simulador Científico": ["model", "simulat", "apsim", "dssat"],
    "IA / Visión Artificial": [
        "yolo", "cnn", "deep learning", "neural", "machine learning", "classification",
        "detection", "transformer", "llm", "pytorch", "tensorflow", "segmentation", "ai"],
    "Plataforma / App Web-Móvil": [
        "app", "web", "platform", "dashboard", "mobile", "streamlit", "flutter",
        "react", "django", "plataforma", "aplicación"],
}


def _coincide(palabra, texto):
    # palabras cortas (<=3) exactas; las largas por prefijo ("simulat" -> "simulation")
    patron = rf"\b{re.escape(palabra)}\b" if len(palabra) <= 3 else rf"\b{re.escape(palabra)}"
    return re.search(patron, texto) is not None


def clasificar(texto, catalogo, defecto):
    texto = re.sub(r"[-_/]", " ", texto.lower())
    puntos = {k: sum(_coincide(p, texto) for p in palabras) for k, palabras in catalogo.items()}
    mejor = max(puntos, key=puntos.get)
    return mejor if puntos[mejor] > 0 else defecto


# ───────────────────────── CSV: cargar / guardar ─────────────────────────
def cargar_csv():
    if CSV_PATH.exists():
        df = pd.read_csv(CSV_PATH, dtype=str, encoding="utf-8-sig").fillna("")
    else:
        df = pd.DataFrame(columns=COLUMNAS)
    for c in COLUMNAS:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNAS + [c for c in df.columns if c not in COLUMNAS]]
    afirmativo = ["[x]", "x", "true", "sí", "si", "yes", "1"]
    df["Check"] = df["Check"].str.strip().str.lower().isin(afirmativo)
    df["Favorito"] = df["Favorito"].str.strip().str.lower().isin(afirmativo)
    df["Estrellas"] = pd.to_numeric(df["Estrellas"], errors="coerce").fillna(0).astype(int)
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0.0)
    df["Prioridad"] = df["Prioridad"].replace("", "P3 - Explorar")
    df["Estado"] = df["Estado"].replace("", "Pendiente")
    return df.reset_index(drop=True)


def a_csv_bytes(df):
    out = df.copy()
    out["Check"] = out["Check"].map({True: "[x]", False: "[ ]"})
    out["Favorito"] = out["Favorito"].map({True: "Sí", False: "No"})
    return out.to_csv(index=False).encode("utf-8-sig")


def secreto(nombre, defecto=""):
    try:
        return st.secrets.get(nombre, defecto)
    except Exception:
        return defecto


def gh_headers():
    h = {"Accept": "application/vnd.github+json"}
    if secreto("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {secreto('GITHUB_TOKEN')}"
    return h


def persistir(df, mensaje):
    """Guarda en disco y, si hay secrets configurados, hace commit del CSV en GitHub."""
    datos = a_csv_bytes(df)
    CSV_PATH.write_bytes(datos)
    token, repo = secreto("GITHUB_TOKEN"), secreto("GITHUB_REPO")
    if not (token and repo):
        return False, ("Guardado solo en el servidor (se pierde si la app se reinicia). "
                       "Descarga el CSV o configura GITHUB_TOKEN y GITHUB_REPO.")
    ruta = secreto("GITHUB_CSV_PATH", "radar_agronomia.csv")
    rama = secreto("GITHUB_BRANCH", "main")
    url = f"{API}/repos/{repo}/contents/{ruta}"
    try:
        r = requests.get(url, headers=gh_headers(), params={"ref": rama}, timeout=15)
        cuerpo = {"message": mensaje, "branch": rama,
                  "content": base64.b64encode(datos).decode()}
        if r.status_code == 200:
            cuerpo["sha"] = r.json()["sha"]
        r = requests.put(url, headers=gh_headers(), json=cuerpo, timeout=30)
        if r.status_code in (200, 201):
            return True, "Guardado en GitHub ✅"
        return False, f"GitHub respondió {r.status_code}: {r.json().get('message', '')}"
    except requests.RequestException as e:
        return False, f"No se pudo guardar en GitHub: {e}"


# ───────────────────────── Rastreo de GitHub ─────────────────────────
def resumen_readme(owner, repo, rama):
    for nombre in ["README.md", "readme.md", "README.rst"]:
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{owner}/{repo}/{rama}/{nombre}", timeout=6)
            if r.status_code == 200:
                r.encoding = "utf-8"  # chino, japonés, ruso, tailandés
                t = r.text
                t = re.sub(r"!\[.*?\]\(.*?\)", "", t)
                t = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", t)
                t = re.sub(r"<[^>]+>", "", t)
                t = re.sub(r"[#*`>_-]{2,}", " ", t)
                t = re.sub(r"\s+", " ", t).strip()
                return t[:450] + ("..." if len(t) > 450 else "")
        except requests.RequestException:
            pass
    return ""


def calcular_potencial(repo, resumen):
    p = 0
    p += 2 if repo["stargazers_count"] >= 2 else 0
    p += 2 if repo["stargazers_count"] >= 15 else 0
    p += 2 if repo["forks_count"] >= 1 else 0
    p += 2 if repo["owner"]["type"] == "Organization" else 0
    p += 1 if repo.get("homepage") else 0
    p += 1 if len(resumen) > 150 else 0
    p += 1 if repo["updated_at"][:4] == str(date.today().year) else 0
    return min(p, 10)


def buscar_github(consultas, dias, progreso):
    fecha = (date.today() - timedelta(days=dias)).isoformat()
    pausa = 2.2 if secreto("GITHUB_TOKEN") else 6.5  # límites: 30 vs 10 búsquedas/min
    candidatos, avisos = {}, []
    for i, b in enumerate(consultas):
        progreso.progress(i / len(consultas), text=f"Buscando: {b['nombre']}…")
        try:
            r = requests.get(
                f"{API}/search/repositories", headers=gh_headers(), timeout=20,
                params={"q": b["q"].replace("{p}", fecha), "sort": "updated",
                        "order": "desc", "per_page": 30})
        except requests.RequestException as e:
            avisos.append(f"'{b['nombre']}': error de conexión ({e})")
            continue
        if r.status_code == 200:
            for repo in r.json().get("items", []):
                if repo.get("archived") or repo.get("fork"):
                    continue
                candidatos.setdefault(repo["html_url"].lower().rstrip("/"), (repo, b))
        elif r.status_code in (403, 429):
            avisos.append(f"Límite de GitHub alcanzado en '{b['nombre']}'. Se detuvo la búsqueda; "
                          "espera 1 minuto o configura GITHUB_TOKEN.")
            break
        else:
            avisos.append(f"'{b['nombre']}': GitHub respondió {r.status_code}")
        time.sleep(pausa)
    progreso.progress(1.0, text="Búsqueda terminada")
    return candidatos, avisos


def construir_filas(candidatos):
    """Descarga README (en paralelo) solo de los repos nuevos y arma las filas."""
    def una(item):
        repo, b = item
        resumen = resumen_readme(repo["owner"]["login"], repo["name"],
                                 repo.get("default_branch", "main"))
        etiquetas = ", ".join(repo.get("topics", []))
        texto = " ".join([repo["name"], repo.get("description") or "", etiquetas, resumen])
        fila = {c: "" for c in COLUMNAS}
        fila.update({
            "Check": False, "Favorito": False, "Prioridad": "P3 - Explorar", "Estado": "Nuevo",
            "Proyecto": repo["name"], "Autor / Institución": repo["owner"]["login"],
            "Dominio Principal": clasificar(texto, DOMINIOS, DOMINIO_DEFECTO),
            "Tipo de Solución": clasificar(texto, TIPOS, TIPO_DEFECTO),
            "Enfoque Geográfico": b["enfoque"], "Lenguaje": repo.get("language") or "",
            "Estrellas": repo["stargazers_count"], "Score": float(calcular_potencial(repo, resumen)),
            "Enlace GitHub": repo["html_url"], "Descripción": repo.get("description") or "",
            "Etiquetas": etiquetas, "Actualizado": repo["updated_at"][:10],
            "Agregado": date.today().isoformat(), "Origen": b["nombre"],
            "Idea / Extracto README": resumen, "Web / Contacto": repo.get("homepage") or "",
        })
        return fila
    with ThreadPoolExecutor(max_workers=8) as ex:
        filas = list(ex.map(una, candidatos))
    return pd.DataFrame(filas, columns=COLUMNAS)


def opciones(df, col, base):
    return sorted(set(base) | {v for v in df[col].unique() if v})


# ───────────────────────── Estado de la sesión ─────────────────────────
if "df" not in st.session_state:
    st.session_state.df = cargar_csv()
    st.session_state.ver = 0
    st.session_state.msg = None
df = st.session_state.df

st.title("🌱 Radar Agro GitHub")
if st.session_state.msg:
    st.info(st.session_state.msg)
    st.session_state.msg = None

# ───────────────────────── Sidebar: buscador y filtros ─────────────────────────
sb = st.sidebar
sb.header("Buscar y filtrar")
vista_rapida = sb.radio("Vista rápida", [
    "Todos", "⭐ Favoritos", "🛠️ Lo estoy haciendo", "🆕 Nuevos por revisar", "✔ Marcados"])
texto = sb.text_input("🔎 Buscar texto", placeholder="ej: NDVI, cacao, YOLO, Colombia…")
f_estado = sb.multiselect("Estado", opciones(df, "Estado", ESTADOS))
f_prio = sb.multiselect("Prioridad", opciones(df, "Prioridad", PRIORIDADES))
f_dom = sb.multiselect("Dominio", opciones(df, "Dominio Principal", list(DOMINIOS) + [DOMINIO_DEFECTO]))
f_tipo = sb.multiselect("Tipo de solución", opciones(df, "Tipo de Solución", list(TIPOS)))
f_geo = sb.multiselect("Enfoque geográfico", opciones(df, "Enfoque Geográfico", []))
f_len = sb.multiselect("Lenguaje", opciones(df, "Lenguaje", []))
min_est = sb.number_input("Estrellas mínimas", min_value=0, value=0, step=5)
min_score = sb.slider("Score mínimo", 0.0, 10.0, 0.0, 0.5)
orden = sb.selectbox("Ordenar por", ["Score", "Estrellas", "Actualizado", "Agregado", "Proyecto"])
asc = sb.checkbox("Orden ascendente", value=False)
sb.divider()
sb.download_button("⬇️ Descargar CSV", a_csv_bytes(df), "radar_agronomia.csv", "text/csv")
if sb.button("🔄 Recargar CSV desde disco"):
    st.session_state.df = cargar_csv()
    st.session_state.ver += 1
    st.rerun()
sb.caption("GitHub: " + ("con token ✅" if secreto("GITHUB_TOKEN") else "sin token (búsquedas más lentas)")
           + " · commit al repo: " + ("activo ✅" if secreto("GITHUB_REPO") and secreto("GITHUB_TOKEN") else "no configurado"))

mask = pd.Series(True, index=df.index)
if vista_rapida == "⭐ Favoritos":
    mask &= df["Favorito"]
elif vista_rapida == "🛠️ Lo estoy haciendo":
    mask &= df["Estado"].eq("Lo estoy haciendo")
elif vista_rapida == "🆕 Nuevos por revisar":
    mask &= df["Estado"].isin(["Nuevo", "Pendiente"])
elif vista_rapida == "✔ Marcados":
    mask &= df["Check"]
for col, sel in [("Estado", f_estado), ("Prioridad", f_prio), ("Dominio Principal", f_dom),
                 ("Tipo de Solución", f_tipo), ("Enfoque Geográfico", f_geo), ("Lenguaje", f_len)]:
    if sel:
        mask &= df[col].isin(sel)
mask &= (df["Estrellas"] >= min_est) & (df["Score"] >= min_score)
if texto.strip():
    blob = df[CAMPOS_BUSQUEDA].astype(str).agg(" ".join, axis=1).str.lower()
    for palabra in texto.lower().split():
        mask &= blob.str.contains(palabra, regex=False)
vista = df[mask].sort_values(orden, ascending=asc, key=(lambda s: s.str.lower()) if orden == "Proyecto" else None)

# ───────────────────────── Pestañas ─────────────────────────
tab_radar, tab_buscar, tab_resumen = st.tabs(["📋 Mi radar", "🔎 Buscar nuevos en GitHub", "📊 Resumen"])

with tab_radar:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("En el radar", len(df))
    c2.metric("Mostrando", len(vista))
    c3.metric("⭐ Favoritos", int(df["Favorito"].sum()))
    c4.metric("🆕 Nuevos", int(df["Estado"].eq("Nuevo").sum()))
    st.caption("Edita ✔, ⭐, prioridad, estado, clasificación y notas; luego pulsa **Guardar cambios**. "
               "Guarda antes de cambiar filtros: los cambios sin guardar se descartan.")

    firma = hashlib.md5(repr((vista_rapida, texto, f_estado, f_prio, f_dom, f_tipo, f_geo, f_len,
                              min_est, min_score, orden, asc)).encode()).hexdigest()[:8]
    cfg = {
        "Check": st.column_config.CheckboxColumn("✔", width="small"),
        "Favorito": st.column_config.CheckboxColumn("⭐", width="small"),
        "Prioridad": st.column_config.SelectboxColumn(options=opciones(df, "Prioridad", PRIORIDADES)),
        "Estado": st.column_config.SelectboxColumn(options=opciones(df, "Estado", ESTADOS)),
        "Dominio Principal": st.column_config.SelectboxColumn(
            options=opciones(df, "Dominio Principal", list(DOMINIOS) + [DOMINIO_DEFECTO])),
        "Tipo de Solución": st.column_config.SelectboxColumn(options=opciones(df, "Tipo de Solución", list(TIPOS))),
        "Enfoque Geográfico": st.column_config.SelectboxColumn(
            options=opciones(df, "Enfoque Geográfico", [b["enfoque"] for b in BUSQUEDAS])),
        "Estrellas": st.column_config.NumberColumn(format="%d"),
        "Score": st.column_config.NumberColumn(format="%.1f"),
        "Enlace GitHub": st.column_config.LinkColumn("GitHub", display_text=r"https://github\.com/(.*)"),
        "Notas_Decision": st.column_config.TextColumn("Notas", width="medium"),
        "Descripción": st.column_config.TextColumn(width="large"),
    }
    with st.form("form_radar"):
        editado = st.data_editor(
            vista[COLUMNAS_VISTA], key=f"editor_{st.session_state.ver}_{firma}",
            hide_index=True, width="stretch", height=560, column_config=cfg,
            disabled=[c for c in COLUMNAS_VISTA if c not in EDITABLES])
        guardar = st.form_submit_button("💾 Guardar cambios", type="primary")
    if guardar:
        df.loc[editado.index, EDITABLES] = editado[EDITABLES]
        ok, msg = persistir(df, "Radar Agro: actualiza seguimiento")
        st.session_state.msg = msg
        st.session_state.ver += 1
        st.rerun()

    if len(vista):
        elegido = st.selectbox("Ver detalle de un proyecto", vista["Proyecto"] + "  ·  " + vista["Autor / Institución"])
        fila = vista[(vista["Proyecto"] + "  ·  " + vista["Autor / Institución"]) == elegido].iloc[0]
        st.markdown(f"**[{fila['Enlace GitHub']}]({fila['Enlace GitHub']})**")
        if fila["Descripción"]:
            st.write(fila["Descripción"])
        if fila["Idea / Extracto README"]:
            st.caption(fila["Idea / Extracto README"])
        if fila["Etiquetas"]:
            st.caption("Etiquetas: " + fila["Etiquetas"])
        if fila["Web / Contacto"]:
            st.caption("Web: " + fila["Web / Contacto"])
        if fila["Origen"]:
            st.caption("Encontrado con: " + fila["Origen"])

with tab_buscar:
    st.write("Consulta GitHub y agrega **solo los repos que aún no están en tu CSV**, "
             "con estado *Nuevo*. No toca lo que ya tienes marcado.")
    grupos_sel = st.multiselect("Grupos de búsqueda", GRUPOS,
                                 default=[g for g in GRUPOS if g != "Becas y empleo"])
    dias = st.slider("Repos con actividad en los últimos (días)", 30, 730, 365, step=30)
    propia = st.text_input("Búsqueda propia (opcional, sintaxis de GitHub)",
                           placeholder='ej: (cacao OR cocoa) (genomics OR breeding) stars:>=2')
    consultas = [b for b in BUSQUEDAS if b["grupo"] in grupos_sel]
    if propia.strip():
        consultas.append(dict(grupo="Propia", nombre="Búsqueda propia",
                              enfoque="Global / Multi-región", q=propia.strip()))
    pausa_est = 2.2 if secreto("GITHUB_TOKEN") else 6.5
    st.caption(f"{len(consultas)} consultas · ~{int(len(consultas) * (pausa_est + 1))} s")
    with st.expander("Ver las consultas"):
        st.dataframe(pd.DataFrame(consultas)[["grupo", "nombre", "q"]], hide_index=True, width="stretch")

    if st.button("🚀 Buscar repos nuevos", type="primary", disabled=not consultas):
        barra = st.progress(0.0, text="Iniciando…")
        candidatos, avisos = buscar_github(consultas, dias, barra)
        conocidos = set(df["Enlace GitHub"].str.lower().str.rstrip("/"))
        nuevos_items = [v for k, v in candidatos.items() if k not in conocidos]
        for a in avisos:
            st.warning(a)
        if not nuevos_items:
            st.success(f"Sin repos nuevos: los {len(candidatos)} encontrados ya estaban en tu radar.")
        else:
            with st.spinner(f"Leyendo README de {len(nuevos_items)} repos nuevos…"):
                nuevos = construir_filas(nuevos_items)
            st.session_state.df = pd.concat([df, nuevos], ignore_index=True)
            ok, msg = persistir(st.session_state.df, f"Radar Agro: +{len(nuevos)} repos nuevos")
            st.session_state.ver += 1
            st.success(f"{len(nuevos)} repos nuevos agregados (de {len(candidatos)} encontrados). {msg}")
            st.dataframe(
                nuevos[["Proyecto", "Autor / Institución", "Dominio Principal", "Estrellas",
                        "Score", "Enlace GitHub", "Descripción"]],
                hide_index=True, width="stretch",
                column_config={"Enlace GitHub": st.column_config.LinkColumn(
                    "GitHub", display_text=r"https://github\.com/(.*)")})
            st.caption("Ya están en *Mi radar* con estado **Nuevo**. "
                       "Dominio y tipo se asignan por palabras clave: corrígelos si hace falta.")

with tab_resumen:
    a, b = st.columns(2)
    a.subheader("Por estado")
    a.bar_chart(df["Estado"].value_counts())
    b.subheader("Por dominio")
    b.bar_chart(df["Dominio Principal"].value_counts(), horizontal=True)
    a.subheader("Por tipo de solución")
    a.bar_chart(df["Tipo de Solución"].value_counts(), horizontal=True)
    b.subheader("Por enfoque geográfico")
    b.bar_chart(df["Enfoque Geográfico"].value_counts(), horizontal=True)
