import pandas as pd
import re
import time
import random
from tqdm import tqdm
from urllib.parse import quote
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import os
import psutil
from fuzzywuzzy import fuzz

# ==== INICIAR CHROMEDRIVER ====
def iniciar_chromedriver():
    for proc in psutil.process_iter(['pid', 'name']):
        if 'chromedriver' in proc.info['name'].lower():
            return
    try:
        subprocess.Popen("chromedriver.exe", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("✅ ChromeDriver iniciado automáticamente.")
    except Exception as e:
        print("❌ No se pudo iniciar ChromeDriver:", e)

iniciar_chromedriver()

# ==== CARGA Y NORMALIZACIÓN ROBUSTA DE DATAFRAME ====
def cargar_df_robusto(nombre):
    def detectar_separador(path):
        with open(path, 'r', encoding='utf-8') as f:
            head = f.readline()
            return ';' if head.count(';') > head.count(',') else ','
    def normalizar_columna(col):
        return col.strip().lower().replace(" ", "_").replace("á", "a").replace("é", "e")                 .replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    df = pd.read_csv(nombre, sep=detectar_separador(nombre), engine='python', on_bad_lines='skip')
    df.columns = [normalizar_columna(c) for c in df.columns]
    return df.fillna('')

def normalizar_texto(txt):
    if not isinstance(txt, str): return ''
    return re.sub(r"[^a-z0-9áéíóúüñ ]", "", txt.lower())

# ==== EXTRACCIÓN ULTRAFLEXIBLE PARA LIBROS ====
def extraer_datos_apa(referencia):
    ref = referencia.replace('\n', ' ').replace('\r', ' ').replace('  ', ' ').strip()
    # Patrón flexible: título puede terminar en punto, ?, o !
    patron = re.compile(r'^(.+?)\s*\(([^\)]+)\)\.\s*(.+?[\.!?])\s+(.+)$', re.UNICODE)
    match = patron.match(ref)
    if match:
        autor, ano, titulo, resto = match.groups()
        ano_num = re.search(r'(\d{4})', ano)
        ano_final = int(ano_num.group(1)) if ano_num else None
        return (autor.strip(), ano_final, titulo.strip())
    patron2 = re.compile(r'^(.+?)\s*\(([^\)]+)\)\.\s*(.+?)\.\s*(.+)$', re.UNICODE)
    if patron2.match(ref):
        autor, ano, titulo, resto = patron2.match(ref).groups()
        ano_num = re.search(r'(\d{4})', ano)
        ano_final = int(ano_num.group(1)) if ano_num else None
        return (autor.strip(), ano_final, titulo.strip())
    return (None, None, None)

# ==== EXTRACCIÓN DE TÍTULO DE ARTÍCULO DE REVISTA APA7 ====
def extraer_titulo_articulo(ref):
    # Patrón: autor (año). título. revista...
    match = re.search(r'\)\.\s*(.+?)\.\s*[A-Za-z]', ref)
    if match:
        return match.group(1)
    # Si hay ? o ! como final de título
    match2 = re.search(r'\)\.\s*(.+?[!?])\s*[A-Za-z]', ref)
    if match2:
        return match2.group(1)
    # Si todo falla, intenta tras el año hasta el primer punto
    match3 = re.search(r'\)\.\s*(.+?)\.', ref)
    if match3:
        return match3.group(1)
    return ""

# ==== CLASIFICADOR DE TIPO ====
def clasificar_referencia(ref):
    ref = ref.lower()
    if re.search(r'\(\d{4}\).*?(\d{4})[–-](\d{4})', ref):
        return "Libro"
    if re.search(r'\(\d{4}\).*?\d+(\(\d+\))?.*\d+[–-]\d+', ref) and ("revista" in ref or "vol" in ref or re.search(r'\d+\s*\(\d+\)', ref)):
        return "Artículo de revista"
    if "en " in ref and ("ed." in ref or "editor" in ref or re.search(r'\b[ivxlcdm]{1,5}\b', ref)):
        return "Capítulo de libro"
    if "tesis" in ref or "memoria" in ref:
        return "Tesis"
    if "congreso" in ref or "coloquio" in ref or "ponencia" in ref:
        return "Congreso"
    if "recuperado de" in ref or re.search(r'https?://', ref):
        return "Recurso web"
    return "Libro"

# ==== COTEJO FLEXIBLE CON FUZZY ====
def cotejar_libro(ref, df_catalogo):
    autor_ref, ano_ref, titulo_ref = extraer_datos_apa(ref)
    if not all([autor_ref, ano_ref, titulo_ref]):
        return {"Encontrado": False, "Observaciones": "APA incompleta"}
    aut_ref_norm = normalizar_texto(autor_ref.split()[0])
    tit_ref_norm = normalizar_texto(titulo_ref)
    df_cat = df_catalogo.copy()
    df_cat["autor_norm"] = df_cat["autor"].apply(normalizar_texto)
    df_cat["titulo_norm"] = df_cat["titulo"].apply(normalizar_texto)
    df_cat["sim_titulo"] = df_cat["titulo_norm"].apply(lambda x: fuzz.token_set_ratio(x, tit_ref_norm))
    df_match = df_cat[(df_cat["ano"] >= ano_ref) &
                      (df_cat["autor_norm"].str.contains(aut_ref_norm)) &
                      (df_cat["sim_titulo"] >= 80)]
    if not df_match.empty:
        fila = df_match.iloc[0]
        return {"Encontrado": True, "Ejemplares": int(fila["numero_ejemplares"]), "Año": fila["ano"],
                "Observaciones": f"{fila['numero_ejemplares']} ejemplares ({fila['ano']})"}
    return {"Encontrado": False, "Observaciones": "No encontrado"}

# ==== MÓDULOS DE BUSQUEDA EXTERNA ====
def buscar_en_buscalibre(titulo, driver):
    url = f"https://www.buscalibre.cl/libros/search?q={quote(titulo)}"
    driver.get(url)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href^='https://www.buscalibre.cl/libro-']")))
        enlace = driver.find_elements(By.CSS_SELECTOR, "a[href^='https://www.buscalibre.cl/libro-']")
        if enlace:
            href = enlace[0].get_attribute("href")
            precio_tag = driver.find_elements(By.CSS_SELECTOR, "p.precio-ahora strong")
            precio = int(''.join(filter(str.isdigit, precio_tag[0].text))) if precio_tag else 0
            return href, precio
    except:
        return "No encontrado", 0
    return "No encontrado", 0

def buscar_en_google_articulo(titulo, driver):
    # Solo busca título + pdf
    busqueda = quote(f'"{titulo}" pdf')
    url_busqueda = f"https://www.google.com/search?q={busqueda}"
    driver.get(url_busqueda)
    time.sleep(random.uniform(4, 6))
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a")))
        enlaces = driver.find_elements(By.CSS_SELECTOR, "a")
        resultados = []
        for enlace in enlaces:
            href = enlace.get_attribute("href")
            if href and href.startswith("http") and not any(x in href for x in ["google.com", "youtube.com", "support.google.com"]):
                if "pdf" in href or "openaccess" in href or "oa" in href:
                    return href, "Acceso abierto"
                resultados.append(href)
            if len(resultados) >= 3:
                break
        # Si no encontró PDFs, devuelve el primer enlace externo o el de búsqueda
        if resultados:
            return resultados[0], "Acceso restringido"
        return url_busqueda, "No disponible"
    except:
        return url_busqueda, "Error"

def buscar_en_google_old(ref, driver):
    # Versión anterior: toda la referencia
    busqueda = quote(ref)
    url_busqueda = f"https://www.google.com/search?q={busqueda}"
    driver.get(url_busqueda)
    time.sleep(random.uniform(4, 6))
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a")))
        enlaces = driver.find_elements(By.CSS_SELECTOR, "a")
        for enlace in enlaces:
            href = enlace.get_attribute("href")
            if href and href.startswith("http") and not any(x in href for x in ["google.com", "youtube.com", "support.google.com"]):
                if "pdf" in href or "openaccess" in href or "oa" in href:
                    return href, "Acceso abierto"
                return href, "Acceso restringido"
        return url_busqueda, "No disponible"
    except:
        return url_busqueda, "Error"

# ==== PROCESO PRINCIPAL ====
def main():
    df_refs = cargar_df_robusto("referencias.csv")
    df_cat = cargar_df_robusto("catalogo.csv")
    df_refs["tipo"] = df_refs["referencia"].apply(clasificar_referencia)
    df_refs["btca_ua"] = 0
    df_refs["observaciones"] = ""
    df_refs["disponible_on_line_url"] = ""
    df_refs["valor_pesos"] = 0
    df_refs["proveedor"] = ""
    df_refs["articulo_cientifico"] = ""
    df_cat["ano"] = pd.to_numeric(df_cat["ano"], errors="coerce").fillna(0).astype(int)
    opciones = webdriver.ChromeOptions()
    opciones.add_argument("--headless=new")
    opciones.add_argument("user-agent=Mozilla/5.0")
    driver = webdriver.Chrome(service=Service("chromedriver.exe"), options=opciones)

    for i, fila in tqdm(df_refs.iterrows(), total=len(df_refs), desc="Procesando referencias"):
        ref = fila["referencia"]
        tipo = fila["tipo"]
        if tipo in ["Libro", "Capítulo de libro"]:
            resultado = cotejar_libro(ref, df_cat)
            df_refs.at[i, "observaciones"] = resultado["Observaciones"]
            if resultado["Encontrado"]:
                df_refs.at[i, "btca_ua"] = resultado["Ejemplares"]
            else:
                try:
                    url, precio = buscar_en_buscalibre(ref, driver)
                except Exception as e:
                    if "invalid session id" in str(e).lower():
                        driver.quit()
                        driver = webdriver.Chrome(service=Service("chromedriver.exe"), options=opciones)
                        url, precio = buscar_en_buscalibre(ref, driver)
                    else:
                        url, precio = "Error", 0
                df_refs.at[i, "disponible_on_line_url"] = url
                df_refs.at[i, "valor_pesos"] = precio
                df_refs.at[i, "proveedor"] = "Buscalibre"
        elif tipo == "Artículo de revista":
            titulo = extraer_titulo_articulo(ref)
            if titulo:
                url, acceso = buscar_en_google_articulo(titulo, driver)
            else:
                url, acceso = buscar_en_google_old(ref, driver)
            df_refs.at[i, "disponible_on_line_url"] = url
            df_refs.at[i, "articulo_cientifico"] = acceso
            df_refs.at[i, "observaciones"] = "Artículo verificado por Google"

    driver.quit()
    df_refs.to_csv("resultado_final.csv", index=False, encoding="utf-8")
    print("✅ Proceso finalizado. Archivo generado: resultado_final.csv")

if __name__ == "__main__":
    main()
