# 🌱 Radar Agro GitHub

Aplicación web interactiva construida con **Python** y **Streamlit** para la vigilancia tecnológica, curaduría y seguimiento de proyectos de código abierto en **Ingeniería Agronómica, Agricultura de Precisión, Teledetección, Hidrometeorología y AgTech**.

El sistema parte de una base de datos maestra depurada (`radar_agronomia.csv`) con proyectos de Colombia, Latinoamérica y ecosistemas internacionales (inglés, chino, japonés, tailandés, ruso y francés), y permite descubrir nuevos repositorios desde la API oficial de GitHub sin duplicar registros ni perder el historial de seguimiento.

---

## ✨ Características principales

* **📋 Tablero interactivo de seguimiento (`Mi radar`):**
  * Filtros rápidos por favoritos (`⭐`), proyectos en ejecución (`🛠️ Lo estoy haciendo`), nuevos por revisar (`🆕`) y tareas completadas (`✔`).
  * Búsqueda por texto libre sobre nombres, descripciones, etiquetas, notas y extractos de `README.md`.
  * Edición directa en tabla de **Prioridad** (`P1 - Alta`, `P2 - Media`, `P3 - Explorar`), **Estado**, **Dominio Principal**, **Tipo de Solución** y **Notas de decisión**.
  * Vista de detalle individual con enlace directo al repositorio, sitio web oficial y resumen extraído del `README`.
* **🔎 Rastreo incremental multilingüe (`Buscar nuevos en GitHub`):**
  * Consulta la API REST de GitHub por grupos temáticos y regionales (incluyendo instituciones y cultivos clave de Colombia como AGROSAVIA, CIAT, IDEAM, Fedecafé, Cenipalma, café, cacao, palma y aguacate).
  * Filtra automáticamente repositorios archivados, *forks* y proyectos que ya existen en el CSV.
  * Descarga y limpia en paralelo los `README.md` (con soporte UTF-8 para alfabetos no latinos), calcula un **Score de potencial (1–10)** y clasifica automáticamente cada repositorio por dominio y tipo de solución.
* **📊 Analítica visual (`Resumen`):**
  * Gráficos de distribución por estado de avance, dominio agronómico, tipo de solución y enfoque geográfico.
* **💾 Persistencia automática en GitHub:**
  * Integración con la API de contenidos de GitHub (`st.secrets`) para hacer *commit* automático de `radar_agronomia.csv` cada vez que guardas cambios o agregas nuevos proyectos, evitando pérdida de datos por el almacenamiento efímero de Streamlit Community Cloud.

---

## 🗂️ Estructura del repositorio

```text
Radar_proyectos_agronomia/
├── app.py                  # Aplicación principal en Streamlit (interfaz, filtros, API GitHub y commits)
├── radar_agronomia.csv     # Base de datos maestra curada y lista de chequeo
├── requirements.txt        # Dependencias de Python necesarias para despliegue
└── README.md               # Documentación del proyecto
```

---

## 🧭 Taxonomía agronómica incluida

Los repositorios se organizan en **7 dominios principales**:
1. **Modelación de Cultivos y Simulación** (APSIM, DSSAT, AquaCrop, WOFOST, modelos de rendimiento).
2. **Teledetección, SIG y Geoespacial** (Sentinel-2, Landsat, Google Earth Engine, NDVI, QGIS).
3. **Fitopatología, Plagas y Visión Artificial** (detección de enfermedades foliares, malezas, fenotipado, YOLO).
4. **Robótica Agrícola, Drones y Maquinaria** (UAV, planificación de rutas, navegación autónoma, ROS2).
5. **IoT, Sensores de Suelo y Riego Inteligente** (ESP32, LoRaWAN, balance hídrico, NPK/humedad de suelo).
6. **Hidrometeorología, Clima y Datos Colombia/Regional** (IDEAM, DHIME, series climáticas, alertas agroclimáticas).
7. **Gestión Agrícola, Asistentes IA y Datos Abiertos** (cuadernos de campo, diseño experimental, ontologías, becas y empleo).

---

## 💻 Ejecución en local

1. **Clona este repositorio:**
   ```bash
   git clone https://github.com/sebas05k/Radar_proyectos_agronomia.git
   cd Radar_proyectos_agronomia
   ```

2. **Crea y activa un entorno virtual (opcional, recomendado):**
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   # En Linux / macOS:
   source .venv/bin/activate
   ```

3. **Instala las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Ejecuta la aplicación:**
   ```bash
   streamlit run app.py
   ```

---

## ☁️ Despliegue y configuración en Streamlit Community Cloud

Para que la aplicación guarde tus cambios de forma permanente directamente en este repositorio y amplíe el límite de consultas a GitHub (de 10 a 30 búsquedas/minuto):

1. Genera un **Fine-grained Personal Access Token** en GitHub con permiso **`Contents: Read and write`** sobre `sebas05k/Radar_proyectos_agronomia`.
2. Despliega `app.py` en [Streamlit Community Cloud](https://share.streamlit.io/) apuntando a la rama `main`.
3. En la configuración de la app (**Settings → Secrets**), agrega:

```toml
GITHUB_TOKEN = "github_pat_TU_TOKEN_AQUI"
GITHUB_REPO = "sebas05k/Radar_proyectos_agronomia"
GITHUB_BRANCH = "main"
GITHUB_CSV_PATH = "radar_agronomia.csv"
```

---

## 👨‍💻 Autor

Desarrollado por **Sebastián (`@sebas05k`)** — Ingeniería Agronómica aplicada a ciencia de datos, automatización y herramientas digitales para el sector agropecuario.