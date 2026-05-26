----------------------------------------------------------
FUNCIONAMIENTO GENERAL DEL SCRIPT
----------------------------------------------------------
1. Carga y validación de archivos (CSV)
2. Inicio automático de ChromeDriver (Selenium)
- Si no está instalado, solicita su instalación
3. Normalización de datos y nombres de columnas
4. Extracción de campos bibliográficos desde cada referencia
5. Cotejo flexible contra el catálogo local usando fuzzy matching
6. Búsqueda y verificación externa (Buscalibre para libros; Google para artículos de revista)
- En el caso de artículos de revista, si no se encuentra acceso directo, se entrega el enlace a la búsqueda
en Google.
7. Registro de resultados para cada referencia
8. Generación de informe final resultado_final.csv
----------------------------------------------------------
CREAR UNA APLICACIÓN WEB CON STREAMLIT
----------------------------------------------------------
1. Instalar Streamlit:
> pip install streamlit
2. Crear un archivo app.py (puedes partir desde tu script actual adaptando la entrada/salida por archivos
subidos y descarga).
Ejemplo básico de inicio:
--------------------------
import streamlit as st
st.title("Automatización de revisión bibliográfica APA7")
uploaded_refs = st.file_uploader("Sube tu archivo de referencias (CSV)", type="csv")
uploaded_cat = st.file_uploader("Sube tu catálogo (CSV)", type="csv")
if st.button("Procesar"):
# Aquí puedes cargar y llamar a las funciones del script principal
st.success("Procesamiento completado. Descarga tu archivo de resultados.")
--------------------------
3. Ejecutar localmente:
> streamlit run app.py
4. Publicar en GitHub:
- Subir el proyecto a un repositorio propio.
- Sube tu archivo requirements.txt con todas las dependencias.
- Puedes usar servicios como Streamlit Cloud o Heroku para desplegar la app (opcional).
----------------------------------------------------------
CONTACTO Y SOPORTE
----------------------------------------------------------
Para dudas o soporte técnico, contactar a:

----------------------------------------------------------
