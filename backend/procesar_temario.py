"""Script offline para preparar temario en PDF antes de subirlo a
app/conocimiento/. No depende de FastAPI: solo lee un PDF, llama a Gemini por
bloques de paginas y escribe archivos .txt limpios y estructurados.

Uso:

    cd backend
    python procesar_temario.py

Pide por consola la ruta del PDF. Los resultados se guardan en
backend/conocimiento_ia/bloque_1.txt, bloque_2.txt, etc. -- una vez revisados,
puedes copiar los que te sirvan a app/conocimiento/ para que el Tutor IA los
indexe (lee .txt y .pdf de esa carpeta automaticamente, ver
services/ai_tutor.py).
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

MODELO_CHAT = "gemini-2.5-flash"
PAGINAS_POR_BLOQUE = 4
SEGUNDOS_ENTRE_LLAMADAS = 1.5

# TTL del cache de contexto: 60 minutos. El PDF entero y el SYSTEM_PROMPT
# son identicos en todas las llamadas del bucle (solo cambia el rango de
# paginas pedido), asi que se suben y se cachean una unica vez y se
# referencian en cada llamada -- ya no se reenvia el bloque de texto
# extraido como input fresco en cada iteracion.
TTL_CACHE_SEGUNDOS = 180 * 60

CARPETA_SALIDA = Path(__file__).resolve().parent / "conocimiento_ia"

SYSTEM_PROMPT = (
    "Eres un redactor tecnico que prepara temario ORIGINAL de oposiciones de "
    "bomberos y emergencias, a partir de texto extraido automaticamente de "
    "PDFs de terceros -- puede traer saltos de pagina, cabeceras/pies "
    "repetidos o formato roto. Tu proceso tiene dos fases obligatorias:\n\n"
    "FASE 1 (mental, no la muestres en tu respuesta) -- EXTRACCION DE DATOS "
    "PUROS: lee el bloque y separa mentalmente solo los hechos, conceptos "
    "cientificos, datos tecnicos, normativa, formulas, cifras, plazos y "
    "definiciones que contiene (por ejemplo: fisica del fuego, tacticas de "
    "ventilacion, hidraulica). Descarta explicitamente todo lo demas: la "
    "estructura del autor original, el orden en que presenta las ideas, sus "
    "metaforas, sus ejemplos propios, su estilo de redaccion y cualquier "
    "rastro de su identidad.\n\n"
    "FASE 2 (esta es tu respuesta real) -- REDACCION ORIGINAL: usando "
    "EXCLUSIVAMENTE los datos puros extraidos en la fase 1, redacta una "
    "explicacion academica completamente nueva. No sigas el orden ni la "
    "estructura del texto original: organiza la explicacion con tu propia "
    "logica pedagogica, la que consideres mas clara para un opositor. Si "
    "hacen falta ejemplos o analogias para ilustrar un concepto, "
    "invéntalos tu mismo con tu propio conocimiento -- nunca reutilices los "
    "ejemplos, metaforas o frases del texto original.\n\n"
    "Reglas estrictas para la fase 2:\n"
    "1. Tono de manual premium de alto rigor tecnico para oposiciones: "
    "preciso, riguroso, sin coloquialismos.\n"
    "2. Se exhaustivo: no dejes ningun dato tecnico, cifra, plazo o norma "
    "extraido en la fase 1 sin desarrollar -- el objetivo es que el "
    "opositor no pierda ni un detalle, aunque el texto final no tenga por "
    "que tener la misma longitud ni estructura que el original.\n"
    "3. PROHIBIDO ABSOLUTO: no copies ni parafrasees frases del texto "
    "original, ni conserves su orden de parrafos -- la narrativa debe estar "
    "totalmente desvinculada de como el autor original lo conto.\n"
    "4. Elimina cabeceras, pies de pagina, numeracion, marcas de agua y "
    "cualquier resto de portada, indice, autoria, academia, editorial o "
    "licencia que aparezca en el texto de origen -- no los menciones, "
    "simplemente no deben existir en tu respuesta.\n"
    "5. NARRATIVA CONTINUA (restriccion positiva obligatoria): estas "
    "obligado a FUSIONAR los conceptos independientes extraidos en la fase "
    "1 dentro de parrafos fluidos, hilando cada idea con la siguiente "
    "mediante conectores logicos (por ejemplo 'ademas', 'por otro lado', "
    "'en este sentido', 'como consecuencia de lo anterior'...). Piensa como "
    "un redactor de libros de texto universitarios, nunca como quien hace "
    "un resumen de apuntes.\n"
    "   EJEMPLO DE EJECUCION OBLIGATORIO: si extraes definiciones "
    "independientes de 'Proton', 'Neutron' y 'Electron', NO puedes "
    "devolver una lista con las tres. DEBES fusionarlas asi: 'El nucleo "
    "del atomo concentra casi toda su masa y esta compuesto por protones, "
    "que determinan el numero atomico con su carga positiva, y neutrones, "
    "que carecen de carga electrica. Orbitando en el exterior de este "
    "nucleo compacto se encuentran los electrones, particulas subatomicas "
    "de carga negativa...'. Aplica este mismo patron de fusion a CUALQUIER "
    "grupo de conceptos o definiciones relacionados que extraigas, sea cual "
    "sea la materia (hidraulica, legislacion, tactica operativa, etc.).\n"
    "   Las listas o guiones quedan BLOQUEADOS A NIVEL DE SISTEMA. Solo "
    "estan permitidos como excepcion cerrada cuando el propio contenido es "
    "una clasificacion legal o normativa estricta que exija separacion "
    "visual por ley (por ejemplo, un articulo que enumera apartados a), b), "
    "c) tal cual los fija la norma) -- nunca como recurso de conveniencia "
    "para definiciones, conceptos o teoria.\n"
    "   ATENCION, ESTO CIERRA UNA LAGUNA HABITUAL: las clasificaciones "
    "teoricas, cientificas o tacticas (por ejemplo, tipos de reacciones, "
    "fases del fuego, metodos de extincion, ventajas/desventajas) NO "
    "ENTRAN EN LA EXCEPCION DE LISTAS. DEBEN redactarse en prosa continua "
    "obligatoriamente, igual que cualquier otro grupo de conceptos. Por "
    "ejemplo, en lugar de hacer una lista, redacta: 'Existen tres tipos de "
    "reacciones. En primer lugar, las reacciones fisicas, que... En segundo "
    "lugar, las reacciones quimicas, caracterizadas por... Y por ultimo, "
    "las reacciones nucleares...'. La unica excepcion para usar listas "
    "sigue siendo, de forma exclusiva, la transcripcion literal de la "
    "estructura de un articulo de una ley (ej. Art. 2 apartados a, b, c). "
    "Incluso en ese caso excepcional, introduce la lista con una frase en "
    "prosa antes de ella. Usa Markdown SOLO para titulo principal (#), "
    "subtitulos (##, ###) y negrita en terminos clave; el cuerpo del texto "
    "es siempre prosa desarrollada.\n"
    "6. REGLA DE EXCLUSIÓN ESTRICTA: si el bloque de texto contiene "
    "ÚNICAMENTE índices, nombres de autores, prólogos institucionales, "
    "presentaciones, bibliografías o portadas, y no contiene absolutamente "
    "ningún dato técnico o normativo aprovechable, responde ÚNICA Y "
    "EXCLUSIVAMENTE con el texto exacto: (sin contenido relevante en este "
    "bloque)"
)


def _esperar_archivo_activo(cliente: genai.Client, archivo: types.File) -> types.File:
    """Tras subir el PDF, la API lo procesa en segundo plano antes de poder
    usarlo en un cache -- hay que esperar a que pase a ACTIVE."""
    while archivo.state == types.FileState.PROCESSING:
        print("  procesando el PDF en la API todavia, esperando 2s...")
        time.sleep(2)
        archivo = cliente.files.get(name=archivo.name)

    if archivo.state == types.FileState.FAILED:
        raise RuntimeError(f"La API no pudo procesar el archivo: {archivo.error}")

    return archivo


def limpiar_bloque_con_ia(
    cliente: genai.Client, cache: types.CachedContent, pagina_desde: int, pagina_hasta: int
) -> str:
    # max_output_tokens explicito y generoso: al ser un modelo de
    # razonamiento, parte del presupuesto de salida se lo come el "thinking"
    # interno (ver usage_metadata.thoughts_token_count) antes de llegar al
    # texto final -- sin margen de sobra, un bloque que exija una expansion
    # larga se puede quedar corto de texto visible.
    respuesta = cliente.models.generate_content(
        model=MODELO_CHAT,
        contents=(
            "Aplica las instrucciones del sistema y reescribe de forma "
            f"exhaustiva exclusivamente el contenido de las páginas "
            f"{pagina_desde} a {pagina_hasta} del documento adjunto."
        ),
        config=types.GenerateContentConfig(
            cached_content=cache.name,
            max_output_tokens=8192,
        ),
    )
    return respuesta.text or ""


def main() -> None:
    ruta_pdf = input("Ruta del PDF a procesar: ").strip().strip('"')
    input_pagina = input("¿Página de inicio? (Pulsa Enter para empezar desde la 1): ").strip()
    arranque = (int(input_pagina) - 1) if input_pagina.isdigit() and int(input_pagina) > 0 else 0
    if not ruta_pdf:
        print("La ruta no puede estar vacia.")
        return

    path_pdf = Path(ruta_pdf)
    if not path_pdf.is_file():
        print(f"No se encontro el archivo: {path_pdf}")
        return

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return

    # Ya no se usa pypdf para leer el PDF localmente (Gemini lo lee de forma
    # nativa desde el cache), asi que el numero de paginas ya no se puede
    # obtener leyendo el archivo: se pide por consola.
    input_total_paginas = input("¿Cuántas páginas tiene el PDF en total?: ").strip()
    if not input_total_paginas.isdigit() or int(input_total_paginas) <= 0:
        print("El numero de paginas tiene que ser un entero positivo.")
        return
    total_paginas = int(input_total_paginas)
    total_bloques = (total_paginas + PAGINAS_POR_BLOQUE - 1) // PAGINAS_POR_BLOQUE

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    print(
        f"\n'{path_pdf.name}': {total_paginas} paginas, "
        f"{total_bloques} bloques de hasta {PAGINAS_POR_BLOQUE} paginas cada uno.\n"
        f"Guardando en: {CARPETA_SALIDA}\n"
    )

    cliente = genai.Client(api_key=api_key)

    print(f"Subiendo '{path_pdf.name}' a la API de Gemini...")
    archivo_subido = cliente.files.upload(file=path_pdf)
    archivo_subido = _esperar_archivo_activo(cliente, archivo_subido)
    print(f"  archivo activo: {archivo_subido.name} ({archivo_subido.size_bytes} bytes)\n")

    print(
        "Creando cache de contexto con el PDF adjunto y el SYSTEM_PROMPT "
        f"(TTL {TTL_CACHE_SEGUNDOS // 60} min)..."
    )
    cache = cliente.caches.create(
        model=MODELO_CHAT,
        config=types.CreateCachedContentConfig(
            display_name=f"cache_{path_pdf.stem}",
            system_instruction=SYSTEM_PROMPT,
            contents=[archivo_subido],
            ttl=f"{TTL_CACHE_SEGUNDOS}s",
        ),
    )
    print(f"  cache creado: {cache.name}\n")

    numero_bloque = 0
    bloques_guardados = 0
    bloques_vacios = 0
    bloques_fallidos = 0

    try:
        for indice_inicio in range(arranque, total_paginas, PAGINAS_POR_BLOQUE):
            numero_bloque += 1
            pagina_desde = indice_inicio + 1
            pagina_hasta = min(indice_inicio + PAGINAS_POR_BLOQUE, total_paginas)
            rango_paginas = f"{pagina_desde}-{pagina_hasta}"

            print(f"Bloque {numero_bloque}/{total_bloques} (paginas {rango_paginas})...", end=" ")

            try:
                texto_limpio = limpiar_bloque_con_ia(cliente, cache, pagina_desde, pagina_hasta)
            except Exception as exc:
                print(f"ERROR llamando a la API: {exc}")
                bloques_fallidos += 1
                time.sleep(SEGUNDOS_ENTRE_LLAMADAS)
                continue

            if texto_limpio.strip() == "(sin contenido relevante en este bloque)":
                print("sin contenido relevante segun la IA, omitido.")
                bloques_vacios += 1
                time.sleep(SEGUNDOS_ENTRE_LLAMADAS)
                continue

            nombre_base = path_pdf.stem  # Extrae el nombre original del PDF
            ruta_salida = CARPETA_SALIDA / f"{nombre_base}_bloque_{numero_bloque}.txt"
            ruta_salida.write_text(texto_limpio, encoding="utf-8")
            bloques_guardados += 1
            print(f"guardado en {ruta_salida.name}")

            # Evita saturar los limites de la API entre llamadas.
            time.sleep(SEGUNDOS_ENTRE_LLAMADAS)

        print(
            f"\nListo: {bloques_guardados} bloques guardados, "
            f"{bloques_vacios} sin contenido relevante, "
            f"{bloques_fallidos} fallidos, de {total_bloques} totales."
        )
    finally:
        # Doble borrado: el cache Y el archivo subido, tanto si el bucle
        # termino bien como si hubo un error, para no pagar almacenamiento
        # de recursos que ya no se van a usar (aunque el TTL del cache lo
        # borraria solo pasada 1 hora).
        try:
            cliente.caches.delete(name=cache.name)
            print(f"Cache {cache.name} eliminado.")
        except Exception as exc:
            print(f"Aviso: no se pudo borrar el cache {cache.name}: {exc}")

        try:
            cliente.files.delete(name=archivo_subido.name)
            print(f"Archivo {archivo_subido.name} eliminado.")
        except Exception as exc:
            print(f"Aviso: no se pudo borrar el archivo {archivo_subido.name}: {exc}")


if __name__ == "__main__":
    main()
