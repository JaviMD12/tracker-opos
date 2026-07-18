"""Script offline para preparar temario en PDF antes de subirlo a
app/conocimiento/. No depende de FastAPI: solo lee un PDF, llama a OpenAI por
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

import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402
from openai import OpenAIError  # noqa: E402
from pypdf import PdfReader  # noqa: E402

MODELO_CHAT = "gpt-4o-mini"
PAGINAS_POR_BLOQUE = 4
SEGUNDOS_ENTRE_LLAMADAS = 1.5

CARPETA_SALIDA = Path(__file__).resolve().parent / "conocimiento_ia"

SYSTEM_PROMPT = (
    "Eres un editor tecnico experto en preparar temario de oposiciones. "
    "Recibes texto extraido automaticamente de un PDF -- puede traer saltos "
    "de pagina, cabeceras/pies de pagina repetidos o formato roto. Tu tarea:\n"
    "1. Limpia el texto: elimina cabeceras, pies de pagina, numeracion y marcas de agua.\n"
    "2. Elimina relleno y paja, pero nunca pierdas datos técnicos ni definiciones.\n"
    "3. Extrae y destaca datos tecnicos clave (cifras, parametros, formulas), plazos y fechas.\n"
    "4. Estructura la salida en Markdown, con titulos (#, ##) y listas.\n"
    "5. REGLA DE EXCLUSIÓN ESTRICTA: Si el bloque de texto contiene ÚNICAMENTE índices, "
    "nombres de autores, prólogos institucionales, presentaciones, bibliografías o portadas, "
    "y no contiene absolutamente nada de teoría técnica o legislación útil para un examen "
    "tipo test, debes responder ÚNICA Y EXCLUSIVAMENTE con el texto exacto: "
    "(sin contenido relevante en este bloque)"
)


def extraer_texto_bloque(reader: PdfReader, indice_inicio: int, num_paginas: int) -> str:
    textos = []
    for pagina in reader.pages[indice_inicio : indice_inicio + PAGINAS_POR_BLOQUE]:
        textos.append(pagina.extract_text() or "")
    return "\n\n".join(textos).strip()


def limpiar_bloque_con_ia(texto_bloque: str, rango_paginas: str) -> str:
    llm = ChatOpenAI(model=MODELO_CHAT, temperature=0.2)
    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=f"Paginas {rango_paginas} del documento original:\n\n{texto_bloque}"
        ),
    ]
    respuesta = llm.invoke(mensajes)
    return respuesta.content


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

    reader = PdfReader(str(path_pdf))
    total_paginas = len(reader.pages)
    total_bloques = (total_paginas + PAGINAS_POR_BLOQUE - 1) // PAGINAS_POR_BLOQUE

    CARPETA_SALIDA.mkdir(parents=True, exist_ok=True)
    print(
        f"\n'{path_pdf.name}': {total_paginas} paginas, "
        f"{total_bloques} bloques de hasta {PAGINAS_POR_BLOQUE} paginas cada uno.\n"
        f"Guardando en: {CARPETA_SALIDA}\n"
    )

    numero_bloque = 0
    bloques_guardados = 0
    bloques_vacios = 0
    bloques_fallidos = 0

    for indice_inicio in range(arranque, total_paginas, PAGINAS_POR_BLOQUE):
        numero_bloque += 1
        pagina_desde = indice_inicio + 1
        pagina_hasta = min(indice_inicio + PAGINAS_POR_BLOQUE, total_paginas)
        rango_paginas = f"{pagina_desde}-{pagina_hasta}"

        print(f"Bloque {numero_bloque}/{total_bloques} (paginas {rango_paginas})...", end=" ")

        texto_bloque = extraer_texto_bloque(reader, indice_inicio, PAGINAS_POR_BLOQUE)
        if not texto_bloque:
            print("sin texto extraible, omitido (no se llama a OpenAI).")
            bloques_vacios += 1
            continue

        try:
            texto_limpio = limpiar_bloque_con_ia(texto_bloque, rango_paginas)
        except OpenAIError as exc:
            print(f"ERROR llamando a OpenAI: {exc}")
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


if __name__ == "__main__":
    main()
