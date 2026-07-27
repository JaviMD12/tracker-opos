"""Script offline para generar un temario a partir de un PDF usando el SDK
oficial de Gemini (google-genai) y Context Caching: el PDF se sube y se cachea
UNA sola vez, y cada apartado del temario se genera con una llamada aparte
que referencia ese cache -- el modelo no vuelve a analizar el PDF entero en
cada peticion, lo que abarata mucho el consumo de tokens de entrada frente a
reenviar el PDF completo en cada llamada.

No depende de FastAPI: se ejecuta directamente.

    cd backend
    python generar_temario_cache.py

Requiere GOOGLE_API_KEY en el .env de backend/.
"""

import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import os  # noqa: E402

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from google.genai.errors import APIError  # noqa: E402

# --- Configuracion editable -------------------------------------------------

MODELO = "gemini-2.5-flash"

# Ruta relativa al PDF de origen. Cambia solo esta variable para procesar
# otro documento.
RUTA_PDF = "documentos_origen/rescate_altura.pdf"

# TTL del cache: 60 minutos. Pasado este tiempo la API lo borra sola aunque
# el script no llegue al finally (por ejemplo si se corta la conexion).
TTL_CACHE_SEGUNDOS = 60 * 60

ARCHIVO_SALIDA = Path(__file__).resolve().parent / "temario_generado.txt"

# Apartados del temario a generar, en orden. Ajusta esta lista al indice real
# del PDF que estes procesando -- estos son solo de ejemplo para
# "rescate_altura.pdf".
EPIGRAFES = [
    "Fundamentos fisicos aplicados al rescate en altura (fuerzas, cargas dinamicas y factor de caida)",
    "Equipos de proteccion individual: arneses, conectores y dispositivos anticaidas",
    "Anclajes: tipos, resistencia y criterios de instalacion segura",
    "Tecnicas de progresion y aseguramiento en vertical",
    "Sistemas de rescate y evacuacion de victimas en altura",
    "Nudos y configuraciones de cuerda aplicados al rescate",
    "Normativa y protocolos de seguridad en trabajos verticales",
]

# --- System prompt de redactor academico (sala limpia) ----------------------

SYSTEM_PROMPT = (
    "Eres un redactor tecnico academico que prepara temario de oposiciones "
    "de bomberos y emergencias a partir de un PDF de origen adjunto como "
    "material de consulta. Para cada apartado que se te pida, tu tarea es "
    "explicar ese apartado con rigor tecnico total, manteniendo todos los "
    "datos exactos del PDF (cifras, normativa, formulas, parametros "
    "tecnicos, plazos) sin resumir ni omitir ninguno.\n\n"
    "Reglas estrictas de formato y estilo:\n"
    "1. PROHIBIDO EL FORMATO ESQUEMA: no uses listas ni viñetas para "
    "definir conceptos o explicar teoria, ni siquiera para clasificaciones "
    "tecnicas (tipos de anclaje, tipos de nudo, ventajas/desventajas...). "
    "Redacta en prosa densa y continua, con parrafos bien desarrollados y "
    "conectores logicos entre ideas ('ademas', 'por otro lado', 'en este "
    "sentido', 'como consecuencia de lo anterior'...). Ejemplo del patron "
    "obligatorio: en lugar de listar tipos de anclaje, escribe 'los "
    "anclajes se clasifican segun su naturaleza en tres grandes grupos. En "
    "primer lugar, los anclajes naturales... En segundo lugar...'. La unica "
    "excepcion es la transcripcion literal de un articulo normativo que la "
    "propia ley enumere en apartados (a, b, c...), y aun asi introducelo "
    "con una frase en prosa antes.\n"
    "2. NO RESUMAS: mantén el mismo nivel de profundidad y densidad tecnica "
    "que el PDF de origen para el apartado solicitado -- el objetivo es que "
    "el opositor no pierda ni un detalle.\n"
    "3. No copies frases textuales del PDF: reescribe el contenido con "
    "vocabulario propio y una estructura pedagogica tuya, no la del "
    "documento original.\n"
    "4. Elimina cualquier resto de portada, indice, autoria, academia, "
    "editorial o licencia que aparezca en el PDF -- no la menciones, "
    "simplemente no debe aparecer en tu respuesta.\n"
    "5. Formato de salida en Markdown limpio: un titulo con '##' para el "
    "apartado y negrita para terminos clave: el cuerpo es siempre prosa "
    "desarrollada.\n"
    "6. Responde UNICAMENTE con el contenido del apartado, sin "
    "explicaciones tuyas ni frases tipo 'aqui tienes el resultado'."
)


def _esperar_archivo_activo(cliente: genai.Client, archivo: types.File) -> types.File:
    """Tras subir el PDF, la API lo procesa en segundo plano (extrae texto,
    genera embeddings internos, etc.) -- hay que esperar a que pase a ACTIVE
    antes de poder usarlo en un cache o en una generacion."""
    while archivo.state == types.FileState.PROCESSING:
        print("  procesando el PDF en la API todavia, esperando 2s...")
        time.sleep(2)
        archivo = cliente.files.get(name=archivo.name)

    if archivo.state == types.FileState.FAILED:
        raise RuntimeError(f"La API no pudo procesar el archivo: {archivo.error}")

    return archivo


def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return

    path_pdf = Path(RUTA_PDF)
    if not path_pdf.is_file():
        print(f"No se encontro el archivo: {path_pdf.resolve()}")
        return

    if not EPIGRAFES:
        print("La lista EPIGRAFES esta vacia, no hay nada que generar.")
        return

    cliente = genai.Client(api_key=api_key)
    cache = None

    try:
        print(f"Subiendo '{path_pdf.name}' a la API de Gemini...")
        archivo_subido = cliente.files.upload(file=path_pdf)
        archivo_subido = _esperar_archivo_activo(cliente, archivo_subido)
        print(f"  archivo activo: {archivo_subido.name} ({archivo_subido.size_bytes} bytes)")

        print(
            f"Creando cache de contexto (TTL {TTL_CACHE_SEGUNDOS // 60} min) "
            "con el PDF adjunto..."
        )
        # Nota: la API exige un minimo de tokens en el contenido cacheado
        # (1024 tokens totales, verificado en pruebas contra la API real) --
        # un PDF corto puede hacer que esta llamada falle con un error 400
        # "Cached content is too small".
        cache = cliente.caches.create(
            model=MODELO,
            config=types.CreateCachedContentConfig(
                display_name=f"cache_{path_pdf.stem}",
                system_instruction=SYSTEM_PROMPT,
                contents=[archivo_subido],
                ttl=f"{TTL_CACHE_SEGUNDOS}s",
            ),
        )
        print(f"  cache creado: {cache.name}")

        secciones_generadas = 0
        with ARCHIVO_SALIDA.open("w", encoding="utf-8") as f_salida:
            for i, epigrafe in enumerate(EPIGRAFES, start=1):
                print(f"\nApartado {i}/{len(EPIGRAFES)}: {epigrafe}")

                try:
                    respuesta = cliente.models.generate_content(
                        model=MODELO,
                        contents=(
                            f"Redacta el apartado '{epigrafe}' del temario, "
                            "usando el PDF adjunto en el cache como fuente "
                            "de datos tecnicos."
                        ),
                        config=types.GenerateContentConfig(
                            cached_content=cache.name,
                        ),
                    )
                except APIError as exc:
                    print(f"  ERROR llamando a Gemini en este apartado: {exc}")
                    continue

                texto = (respuesta.text or "").strip()
                if not texto:
                    print("  la IA no devolvio texto para este apartado, se omite.")
                    continue

                # Se escribe (y se vuelca a disco) apartado a apartado, para
                # no perder lo ya generado si un apartado posterior falla.
                f_salida.write(texto + "\n\n")
                f_salida.flush()
                secciones_generadas += 1
                print(f"  guardado ({len(texto)} caracteres).")

        print(
            f"\nListo: {secciones_generadas}/{len(EPIGRAFES)} apartados "
            f"guardados en {ARCHIVO_SALIDA}."
        )

    finally:
        # Se borra el cache tanto si todo fue bien como si hubo un error,
        # para no pagar almacenamiento de un cache que ya no se va a usar
        # (aunque el TTL lo borraria solo pasada 1 hora).
        if cache is not None:
            try:
                cliente.caches.delete(name=cache.name)
                print(f"Cache {cache.name} eliminado.")
            except APIError as exc:
                print(f"Aviso: no se pudo borrar el cache {cache.name}: {exc}")


if __name__ == "__main__":
    main()
