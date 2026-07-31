"""Script offline para preparar temario en PDF antes de subirlo a
app/conocimiento/. No depende de FastAPI: solo lee un PDF, llama a Gemini por
bloques de paginas y escribe archivos .txt limpios y estructurados.

Uso:
    cd backend
    python procesar_temario.py
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from google import genai
from google.genai import types

MODELO_CHAT = "gemini-2.5-flash"
PAGINAS_POR_BLOQUE = 4
SEGUNDOS_ENTRE_LLAMADAS = 1.5
TTL_CACHE_SEGUNDOS = 180 * 60
CARPETA_SALIDA = Path(__file__).resolve().parent / "conocimiento_ia"

SYSTEM_PROMPT = (
    "Eres un redactor técnico experto que prepara un temario ORIGINAL y EXHAUSTIVO de "
    "oposiciones de bomberos y emergencias a partir de texto extraído "
    "automáticamente de PDFs de terceros. \n\n"
    "¡ATENCIÓN A LA ESTRUCTURA DEL PDF! El documento original está maquetado a DOBLE COLUMNA. "
    "Debes leer la columna izquierda de arriba a abajo completamente y luego pasar a la columna "
    "derecha de arriba a abajo. EXCEPCIÓN CRÍTICA: Si te encuentras con una tabla, gráfico o esquema "
    "que ocupa todo el ancho de la página (cruzando ambas columnas), suspende temporalmente la regla de "
    "las columnas, procesa esa tabla de forma horizontal y lógica de principio a fin, y cuando termines "
    "con ella, retoma la lectura a doble columna con el texto que haya debajo.\n\n"
    "Tu objetivo es crear una obra completamente nueva (cero plagio) pero conservando el 100% de la información.\n\n"
    "FASE 1: EXTRACCIÓN. Aísla cada dato, cifra, decimal, fórmula, fecha, ley, artículo y métrica "
    "(ej. 'más de 2 metros'). Omite opiniones, estilo personal, editoriales o academias.\n\n"
    "FASE 2: REDACCIÓN. Escribe un texto NUEVO, riguroso y puramente técnico.\n\n"
    "REGLAS INQUEBRANTABLES:\n"
    "1. CERO PLAGIO: El texto debe ser irreconocible en su redacción frente al original.\n"
    "2. EXHAUSTIVIDAD TOTAL (PROHIBIDO RESUMIR): No omitas ni un solo dato, decreto o característica. "
    "Los 'datos duros' (leyes, fechas, cifras) transcríbelos idénticos.\n"
    "3. FORMATO: Genera tablas en Markdown si el original tiene tablas. Usa listas para enumerar legislación o pasos.\n"
    "4. LIMPIEZA ABSOLUTA: No incluyas introducciones ni avisos de IA.\n\n"
    "REGLA DE CIERRE OBLIGATORIA: Cuando hayas procesado hasta la última palabra del bloque indicado, "
    "debes escribir obligatoriamente en una línea nueva al final del todo la etiqueta exacta: [FIN DEL BLOQUE]."
)

def _esperar_archivo_activo(cliente: genai.Client, archivo: types.File) -> types.File:
    while archivo.state == types.FileState.PROCESSING:
        print("  procesando el PDF, esperando 2s...")
        time.sleep(2)
        archivo = cliente.files.get(name=archivo.name)
    if archivo.state == types.FileState.FAILED:
        raise RuntimeError(f"La API falló al procesar: {archivo.error}")
    return archivo

def limpiar_bloque_con_ia(
    cliente: genai.Client, cache: types.CachedContent, pagina_desde: int, pagina_hasta: int
) -> str:
    prompt_llamada = (
        f"Reescribe de forma EXHAUSTIVA el contenido de las páginas {pagina_desde} a {pagina_hasta}.\n"
        f"RECUERDA: Lee respetando las columnas. No te dejes NI UN SOLO Real Decreto ni cifra por el camino. "
        f"Si una idea acaba a medias en la página {pagina_hasta}, lee el inicio de la {pagina_hasta + 1} para terminarla. "
        f"Al terminar absolutamente todo, escribe: [FIN DEL BLOQUE]"
    )
    
    intentos = 0
    max_intentos = 3
    
    while intentos < max_intentos:
        try:
            respuesta = cliente.models.generate_content(
                model=MODELO_CHAT,
                contents=prompt_llamada,
                config=types.GenerateContentConfig(
                    cached_content=cache.name,
                    max_output_tokens=8192,
                ),
            )
            texto = respuesta.text or ""
            
            # Verificación del candado de cierre
            if "[FIN DEL BLOQUE]" in texto:
                # Todo correcto, devolvemos el texto limpio sin la etiqueta
                return texto.replace("[FIN DEL BLOQUE]", "").strip()
            
            # Si llega aquí, la IA se cortó a medias
            print(f"\n  [!] Advertencia: La IA cortó el texto a medias (intento {intentos + 1}/{max_intentos}). Reintentando...")
            intentos += 1
            time.sleep(3)
            
        except Exception as e:
            print(f"\n  [!] Error de API: {e}. Reintentando...")
            intentos += 1
            time.sleep(3)
            
    # Si tras 3 intentos no logra completarlo, devuelve lo que tenga para no bloquear el programa entero
    print("  [!] Imposible obtener el bloque completo tras 3 intentos. Guardando texto parcial.")
    return texto.replace("[FIN DEL BLOQUE]", "").strip()

def main() -> None:
    ruta_pdf = input("Ruta del PDF a procesar: ").strip().strip('"')
    input_pagina = input("¿Página de inicio? (Enter para la 1): ").strip()
    arranque = (int(input_pagina) - 1) if input_pagina.isdigit() and int(input_pagina) > 0 else 0
    if not ruta_pdf: return
    path_pdf = Path(ruta_pdf)
    if not path_pdf.is_file(): return
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key: return

    input_total = input("¿Cuántas páginas tiene el PDF en total?: ").strip()
    if not input_total.isdigit() or int(input_total) <= 0: return
    total_paginas = int(input_total)
    total_bloques = (total_paginas + PAGINAS_POR_BLOQUE - 1) // PAGINAS_POR_BLOQUE

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    cliente = genai.Client(api_key=api_key)

    archivo_subido = cliente.files.upload(file=path_pdf)
    archivo_subido = _esperar_archivo_activo(cliente, archivo_subido)
    
    cache = cliente.caches.create(
        model=MODELO_CHAT,
        config=types.CreateCachedContentConfig(
            display_name=f"cache_{path_pdf.stem}",
            system_instruction=SYSTEM_PROMPT,
            contents=[archivo_subido],
            ttl=f"{TTL_CACHE_SEGUNDOS}s",
        ),
    )

    numero_bloque = 0
    try:
        for indice_inicio in range(arranque, total_paginas, PAGINAS_POR_BLOQUE):
            numero_bloque += 1
            pagina_desde = indice_inicio + 1
            pagina_hasta = min(indice_inicio + PAGINAS_POR_BLOQUE, total_paginas)
            
            print(f"Bloque {numero_bloque}/{total_bloques} (págs {pagina_desde}-{pagina_hasta})...", end=" ", flush=True)
            
            texto_limpio = limpiar_bloque_con_ia(cliente, cache, pagina_desde, pagina_hasta)
            
            ruta_salida = CARPETA_SALIDA / f"{path_pdf.stem}_bloque_{numero_bloque}.txt"
            ruta_salida.write_text(texto_limpio, encoding="utf-8")
            print(f"-> Guardado ({len(texto_limpio.split())} palabras)")
            
            time.sleep(SEGUNDOS_ENTRE_LLAMADAS)
    finally:
        try: cliente.caches.delete(name=cache.name)
        except: pass
        try: cliente.files.delete(name=archivo_subido.name)
        except: pass

if __name__ == "__main__":
    main()