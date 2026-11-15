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
REPO_DEFECTO = "sebas05k/Radar_proyectos_agronomia"

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
    "Tipo de Solución", "Enfoque Geográfico", "Enlace GitHub", "Notas_Decision",
]
COLUMNAS_VISTA = [
    "Check", "Favorito", "Prioridad", "Estado", "Proyecto", "Autor / Institución",
    "Dominio Principal", "Tipo de Solución", "Enfoque Geográfico", "Lenguaje",
    "Estrellas", "Score", "Enlace GitHub", "Notas_Decision", "Descripción",
    "Etiquetas", "Idea / Extracto README", "Actualizado", "Agregado",
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
    token, repo = secreto("GITHUB_TOKEN"), secreto("GITHUB_REPO", REPO_DEFECTO)
    if not (token and repo):
        return False, ("Guardado solo en el servidor (se pierde si la app se reinicia). "
                       "Descarga el CSV o configura GITHUB_TOKEN en los secrets.")
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



# ───────────────────────── Temas agronómicos (filtro por palabras clave) ─────────────────────────
TEMAS = {
    "Fitomejoramiento y genética": ["plant breeding", "breeding", "genomic", "genotyp", "phenotyp", "qtl",
                                    "gwas", "germplasm", "fitomejoramiento", "genética"],
    "Fitopatología y plagas": ["disease", "pest", "pathology", "plaga", "blight", "fungal", "enfermedad", "weed", "病虫害"],
    "Suelos y nutrición": ["soil", "suelo", "fertiliz", "nutrient", "carbon", "fertilidad"],
    "Agua y riego": ["irrigation", "riego", "water", "evapotranspiration", "drought", "sequía"],
    "Clima y agrometeorología": ["weather", "climate", "clima", "rainfall", "phenolog", "meteorolog"],
    "Agroecología y sostenibilidad": ["agroecolog", "regenerative", "organic", "sustainab", "agroforest",
                                      "biodiversity", "permacultur"],
    "Cultivos específicos": ["coffee", "café", "cacao", "cocoa", "palm", "avocado", "aguacate", "banana",
                             "rice", "maize", "wheat", "soybean", "potato", "tomato", "vegetable"],
    "Teledetección y agricultura de precisión": ["remote sensing", "satellite", "ndvi", "uav", "drone",
                                                 "precision agriculture", "gis"],
    "Modelación y simulación": ["crop model", "simulat", "apsim", "dssat", "aquacrop", "growth model"],
    "Bioinformática y R": ["bioinformatic", "r package", "cran", "bioconductor", "genome", "sequencing"],
}


def parse_busqueda(q, implicito="AND"):
    """Sintaxis: ndvi AND cacao | ndvi OR sentinel | "plant breeding" | -maiz | NOT maiz.
    AND liga más fuerte que OR. Palabras sueltas se unen con `implicito`. Los excluidos son globales."""
    grupos, excluidos = [[]], []
    neg = and_expl = prev = False
    for t in re.findall(r'"[^"]+"|\S+', q):
        if t in ("OR", "|"):
            grupos.append([]); prev = and_expl = False
            continue
        if t in ("AND", "&"):
            and_expl = True
            continue
        if t == "NOT":
            neg = True
            continue
        negativo = neg or (t.startswith("-") and len(t) > 1)
        termino = (t.lstrip("-") if t.startswith("-") else t).strip("()").strip('"').lower()
        neg = False
        if not termino:
            continue
        if negativo:
            excluidos.append(termino)
            continue
        if prev and not and_expl and implicito == "OR":
            grupos.append([])
        grupos[-1].append(termino)
        prev, and_expl = True, False
    return [g for g in grupos if g], excluidos


def mascara_texto(blob, q, implicito="AND"):
    grupos, excluidos = parse_busqueda(q, implicito)
    if not grupos and not excluidos:
        return pd.Series(True, index=blob.index)
    m = pd.Series(not grupos, index=blob.index)
    for g in grupos:
        mg = pd.Series(True, index=blob.index)
        for term in g:
            mg &= blob.str.contains(term, regex=False)
        m |= mg
    for term in excluidos:
        m &= ~blob.str.contains(term, regex=False)
    return m


def mascara_temas(blob, temas, modo):
    if not temas:
        return pd.Series(True, index=blob.index)
    ms = [blob.apply(lambda t, k=k: any(_coincide(p, t) for p in TEMAS[k])) for k in temas]
    return pd.concat(ms, axis=1).all(axis=1) if modo == "todos" else pd.concat(ms, axis=1).any(axis=1)


# ───────────────────────── Completar filas existentes desde GitHub ─────────────────────────
RE_ENLACE = re.compile(r"github\.com/([^/\s]+)/([^/\s#?]+)")


def repo_de_enlace(url):
    m = RE_ENLACE.search(url or "")
    return (m.group(1), re.sub(r"\.git$", "", m.group(2))) if m else None


def elegir_candidato(fila, exactos, permisivo=False):
    """Devuelve (repo|None, candidatos). Solo acepta si nombre exacto + lenguaje + (estrellas parecidas o autor)."""
    est = int(fila["Estrellas"] or 0)
    lang = fila["Lenguaje"].strip().lower()
    autor = fila["Autor / Institución"].lower()
    ok_lang = lambda x: not lang or (x.get("language") or "").lower() == lang
    ok_est = lambda x: abs(x["stargazers_count"] - est) <= max(3, 0.2 * est)
    ok_autor = lambda x: len(x["owner"]["login"]) >= 3 and x["owner"]["login"].lower() in autor
    buenos = [x for x in exactos if ok_lang(x) and (ok_est(x) or ok_autor(x))]
    if len(buenos) > 1:  # desempata por autor y luego por estrellas idénticas; si no, es ambigua
        for criterio in (ok_autor, lambda x: x["stargazers_count"] == est):
            sub = [x for x in buenos if criterio(x)]
            if len(sub) == 1:
                buenos = sub
                break
    if len(buenos) == 1:
        return buenos[0], exactos, "ok"
    if permisivo and len(exactos) == 1 and ok_lang(exactos[0]):  # único con ese nombre exacto
        return exactos[0], exactos, "ok_unico"
    return None, exactos, "ambigua"


def buscar_por_nombre(fila, headers, permisivo=False):
    nombre = fila["Proyecto"].strip()
    r = requests.get(f"{API}/search/repositories", headers=headers, timeout=20,
                     params={"q": f'"{nombre}" in:name', "per_page": 30})
    if r.status_code in (403, 429):
        return "limite", None, []
    if r.status_code != 200:
        return f"error {r.status_code}", None, []
    exactos = [x for x in r.json().get("items", []) if x["name"].lower() == nombre.lower()]
    repo, cands, estado = elegir_candidato(fila, exactos, permisivo)
    return (estado if cands else "no_existe"), repo, cands


def aplicar_repo(df, idx, repo, readme):
    df.at[idx, "Enlace GitHub"] = repo["html_url"]
    nuevos = {"Descripción": repo.get("description") or "",
              "Etiquetas": ", ".join(repo.get("topics", [])),
              "Idea / Extracto README": readme,
              "Web / Contacto": repo.get("homepage") or "",
              "Lenguaje": repo.get("language") or ""}
    for col, val in nuevos.items():
        if val and not str(df.at[idx, col]).strip():  # nunca pisa lo que ya tenías
            df.at[idx, col] = val
    df.at[idx, "Estrellas"] = repo["stargazers_count"]
    df.at[idx, "Actualizado"] = repo["updated_at"][:10]


def completar_radar(df, forzar, max_filas, progreso, permisivo=True):
    """Completa metadatos de filas viejas. Filas con enlace usuario/repo -> API directa (en paralelo).
    Filas con enlace sin usuario -> busca por nombre y solo acepta coincidencias seguras."""
    h = gh_headers()
    core, search = None, None
    try:
        rl = requests.get(f"{API}/rate_limit", headers=h, timeout=10).json()["resources"]
        core, search = rl["core"]["remaining"], rl["search"]["remaining"]
    except Exception:
        pass
    sin_usuario = df["Enlace GitHub"].map(lambda u: repo_de_enlace(u) is None)
    pendiente = df.index[sin_usuario | df["Actualizado"].eq("")] if not forzar else df.index
    directas = [i for i in pendiente if not sin_usuario[i]]
    por_nombre = [i for i in pendiente if sin_usuario[i]]
    res = dict(total_pendientes=len(pendiente), completadas=0, corregidos=0, ambiguas=0,
               no_existe=0, errores=0, limite=False, restantes=0, por_verificar=0)
    if core is not None and core < len(directas[:max_filas]):
        directas = directas[:max(core - 2, 0)]
        res["limite"] = True
    directas = directas[:max_filas]
    por_nombre = por_nombre[:max(max_filas - len(directas), 0)]
    total = max(len(directas) + len(por_nombre), 1)
    hecho, resueltos = 0, []  # resueltos: (idx, repo)

    def una(i):
        o, n = repo_de_enlace(df.at[i, "Enlace GitHub"])
        return i, requests.get(f"{API}/repos/{o}/{n}", headers=h, timeout=20)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, r in ex.map(una, directas):
            hecho += 1
            progreso.progress(hecho / total, text=f"Consultando repos… {hecho}/{total}")
            if r.status_code == 200:
                resueltos.append((i, r.json()))
            elif r.status_code in (403, 429):
                res["limite"] = True
            elif r.status_code == 404:
                res["no_existe"] += 1
                if not df.at[i, "Notas_Decision"]:
                    df.at[i, "Notas_Decision"] = "[auto] El enlace ya no existe en GitHub (¿renombrado o borrado?)"
            else:
                res["errores"] += 1

    pausa = 2.2 if secreto("GITHUB_TOKEN") else 6.5
    for i in por_nombre:
        hecho += 1
        progreso.progress(hecho / total, text=f"Buscando por nombre: {df.at[i, 'Proyecto']} ({hecho}/{total})")
        try:
            estado, repo, cands = buscar_por_nombre(df.loc[i], h, permisivo)
        except requests.RequestException:
            res["errores"] += 1
            continue
        if estado == "limite":
            res["limite"] = True
            break
        if estado in ("ok", "ok_unico"):
            resueltos.append((i, repo))
            res["corregidos"] += 1
            if estado == "ok_unico":
                res["por_verificar"] += 1
                if not df.at[i, "Notas_Decision"]:
                    df.at[i, "Notas_Decision"] = "[auto] Enlace asignado por ser el único repo con ese nombre; verifícalo"
        elif estado in ("ambigua", "no_existe") and not df.at[i, "Notas_Decision"]:
            if estado == "ambigua":
                res["ambiguas"] += 1
                top = sorted(cands, key=lambda x: -x["stargazers_count"])[:3]
                df.at[i, "Notas_Decision"] = "[auto] Enlace sin verificar. Candidatos: " + " | ".join(
                    f"{x['html_url']} (★{x['stargazers_count']})" for x in top)
            else:
                res["no_existe"] += 1
                df.at[i, "Notas_Decision"] = "[auto] No encontré este repo en GitHub por nombre"
        elif estado in ("ambigua", "no_existe"):
            res["ambiguas" if estado == "ambigua" else "no_existe"] += 1
        else:
            res["errores"] += 1
        time.sleep(pausa)

    def leer(par):
        i, repo = par
        if str(df.at[i, "Idea / Extracto README"]).strip():
            return i, repo, ""
        return i, repo, resumen_readme(repo["owner"]["login"], repo["name"], repo.get("default_branch", "main"))

    progreso.progress(1.0, text="Leyendo README…")
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, repo, readme in ex.map(leer, resueltos):
            aplicar_repo(df, i, repo, readme)
            res["completadas"] += 1
    sin_usuario = df["Enlace GitHub"].map(lambda u: repo_de_enlace(u) is None)
    res["restantes"] = int((sin_usuario | df["Actualizado"].eq("")).sum())
    return res


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
texto = sb.text_input("🔎 Buscar texto", placeholder='ej: ndvi AND cacao · yolo OR sentinel · -maiz',
                      help='AND / OR / NOT, "frase exacta" y -excluir. AND liga más fuerte que OR. '
                           'Ej: ndvi AND colombia OR "plant breeding" -maiz')
implicito = "OR" if sb.radio("Palabras sin operador", ["todas (AND)", "alguna (OR)"], horizontal=True).startswith("alguna") else "AND"
f_temas = sb.multiselect("Tema agronómico", list(TEMAS))
modo_temas = "todos" if sb.radio("Coincidir temas", ["cualquiera", "todos"], horizontal=True) == "todos" else "cualquiera"
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
           + " · commit al repo: " + ("activo ✅" if secreto("GITHUB_TOKEN") else "no configurado"))

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
if texto.strip() or f_temas:
    blob = df[CAMPOS_BUSQUEDA].astype(str).agg(" ".join, axis=1).str.lower()
    if texto.strip():
        mask &= mascara_texto(blob, texto, implicito)
    mask &= mascara_temas(blob, f_temas, modo_temas)
vista = df[mask].sort_values(orden, ascending=asc, key=(lambda s: s.str.lower()) if orden == "Proyecto" else None)

# ───────────────────────── Pestañas ─────────────────────────
tab_radar, tab_buscar, tab_completar, tab_resumen = st.tabs(
    ["📋 Mi radar", "🔎 Buscar nuevos en GitHub", "✨ Completar datos", "📊 Resumen"])

with tab_radar:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("En el radar", len(df))
    c2.metric("Mostrando", len(vista))
    c3.metric("⭐ Favoritos", int(df["Favorito"].sum()))
    c4.metric("🆕 Nuevos", int(df["Estado"].eq("Nuevo").sum()))
    st.caption("Edita ✔, ⭐, prioridad, estado, clasificación y notas; luego pulsa **Guardar cambios**. "
               "Guarda antes de cambiar filtros: los cambios sin guardar se descartan.")

    firma = hashlib.md5(repr((vista_rapida, texto, implicito, f_temas, modo_temas, f_estado, f_prio, f_dom, f_tipo, f_geo, f_len,
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
        "Etiquetas": st.column_config.TextColumn(width="medium"),
        "Idea / Extracto README": st.column_config.TextColumn("README (extracto)", width="large"),
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

with tab_completar:
    sin_usuario = df["Enlace GitHub"].map(lambda u: repo_de_enlace(u) is None)
    pend = int((sin_usuario | df["Actualizado"].eq("")).sum())
    c1, c2, c3 = st.columns(3)
    c1.metric("Filas por completar", pend)
    c2.metric("Enlaces sin usuario/", int(sin_usuario.sum()))
    c3.metric("Sin descripción", int(df["Descripción"].eq("").sum()))
    st.write("Rellena **Descripción, Etiquetas, Extracto README, Actualizado, Web/Contacto, Estrellas y el enlace "
             "usuario/repo** de las filas viejas. Solo llena campos vacíos: no pisa tus notas, estado, favoritos "
             "ni clasificación. Al terminar hace commit del CSV a GitHub.")
    st.caption("Los enlaces sin usuario se resuelven buscando por nombre y solo se aceptan si coinciden nombre, "
               "lenguaje y (estrellas o autor). Los dudosos no se tocan: quedan con una nota `[auto]` en Notas "
               "con los candidatos, y puedes pegar el enlace correcto en la tabla (la columna GitHub es editable) "
               "y volver a pulsar el botón.")
    max_filas = st.slider("Máximo de filas por pasada", 10, 250, 200, step=10)
    permisivo = st.checkbox("Aceptar también si es el único repo con ese nombre exacto (aunque las estrellas no coincidan)",
                            value=True, help="Esas filas quedan con una nota [auto] para que las verifiques.")
    forzar = st.checkbox("Reprocesar también filas ya completas (refresca estrellas y fechas)")
    t_est = int(min(pend, max_filas) * (2.2 if secreto("GITHUB_TOKEN") else 6.5))
    st.caption(f"Tiempo estimado: hasta ~{t_est // 60} min {t_est % 60} s "
               f"(las búsquedas por nombre son lo más lento). "
               + ("" if secreto("GITHUB_TOKEN") else "⚠️ Sin GITHUB_TOKEN solo hay 60 consultas por hora."))
    if st.button("✨ Completar descripciones y enlaces desde GitHub", type="primary", disabled=(pend == 0 and not forzar)):
        barra = st.progress(0.0, text="Iniciando…")
        res = completar_radar(df, forzar, max_filas, barra, permisivo)
        ok, msg = persistir(df, f"Radar Agro: completa {res['completadas']} filas desde GitHub")
        st.session_state.ver += 1
        st.success(f"Completadas: {res['completadas']} · enlaces corregidos: {res['corregidos']} · "
                   f"por verificar: {res['por_verificar']} · dudosos: {res['ambiguas']} · no encontrados: {res['no_existe']} · errores: {res['errores']}. {msg}")
        if res["limite"]:
            st.warning("Se alcanzó el límite de la API de GitHub; espera y pulsa de nuevo para continuar donde quedó.")
        if res["restantes"]:
            st.info(f"Quedan {res['restantes']} filas por completar (dudosas, no encontradas o fuera de esta pasada).")

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
