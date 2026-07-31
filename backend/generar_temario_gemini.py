"""Script offline para ensamblar los Temarios Premium a partir de los bloques
ya reescritos en conocimiento_ia/. Adaptado para Gemini 2.5 Flash.
"""

import asyncio
import os
import re
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

# Importaciones de Google GenAI
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parent / ".env")

MODELO_CHAT = "gemini-2.5-flash"
DIR_ORIGEN = Path(__file__).resolve().parent / "conocimiento_ia"
DIR_SALIDA = Path(__file__).resolve().parent / "Temarios_Premium"

# Gemini 2.5 Flash tiene un límite de SALIDA de 8192 tokens. 
# Reducimos un poco el tamaño del bloque de entrada para asegurarnos de que
# la reescritura expansiva no supere ese límite al generar la respuesta.
TOKENS_MAX_POR_FRAGMENTO = 6000
TOKENS_CONTEXTO_PREVIO = 1500
MAX_TEMAS_EN_PARALELO = 1
MAX_TOKENS_SALIDA = 8192

_PATRON_BLOQUE = re.compile(r"^(?P<tema>.+)_bloque_(?P<numero>\d+)\.txt$")


def _contar_tokens(texto: str) -> int:
    """Heurística estándar y rápida sin usar librerías externas (1 token ~= 4 caracteres)."""
    return len(texto) // 4


def escanear_bloques(directorio: Path) -> dict[str, list[Path]]:
    temas: dict[str, list[tuple[int, Path]]] = defaultdict(list)
    for ruta in directorio.glob("*_bloque_*.txt"):
        match = _PATRON_BLOQUE.match(ruta.name)
        if not match:
            continue
        temas[match.group("tema")].append((int(match.group("numero")), ruta))

    return {
        tema: [ruta for _, ruta in sorted(bloques)] for tema, bloques in temas.items()
    }


def agrupar_en_fragmentos(rutas: list[Path]) -> list[str]:
    fragmentos: list[str] = []
    actual: list[str] = []
    tokens_actual = 0

    for ruta in rutas:
        contenido = ruta.read_text(encoding="utf-8").strip()
        tokens_bloque = _contar_tokens(contenido)

        if actual and tokens_actual + tokens_bloque > TOKENS_MAX_POR_FRAGMENTO:
            fragmentos.append("\n\n".join(actual))
            actual = []
            tokens_actual = 0

        actual.append(contenido)
        tokens_actual += tokens_bloque

    if actual:
        fragmentos.append("\n\n".join(actual))

    return fragmentos


def _cola_en_tokens(texto: str, max_tokens: int) -> str:
    max_chars = max_tokens * 4
    if len(texto) <= max_chars:
        return texto
    return texto[-max_chars:]


SYSTEM_PROMPT = (
    "Eres un reescritor experto en temario de oposiciones de bomberos y "
    "emergencias, especializado en convertir apuntes tecnicos comprimidos en "
    "un manual de estudio profesional. Recibes bloques de texto que ya son "
    "resumenes o extractos de manuales externos, en el orden correcto. Tu "
    "trabajo NO es editar ni sintetizar: es REESCRIBIR Y EXPANDIR cada "
    "bloque con tus propias palabras, produciendo un unico documento "
    "continuo, coherente y con estilo propio, publicable como manual de "
    "estudio oficial.\n\n"
    "=== REGLA MAXIMA E INNEGOCIABLE: PROHIBIDO RESUMIR (REESCRITURA "
    "EXPANSIVA 1:1) ===\n"
    "Esta terminantemente prohibido comprimir, sintetizar o convertir el "
    "texto de entrada en un indice de conceptos -- aunque el bloque "
    "original ya venga en forma de resumen o apunte telegrafico, tu tarea "
    "es justo la contraria: desarrollarlo. Reescribe con tus propias "
    "palabras manteniendo exactamente el mismo nivel de detalle, la misma "
    "longitud y TODOS los datos tecnicos del original (cifras, articulos de "
    "ley, formulas, procedimientos, excepciones, matices). Por cada parrafo "
    "que recibas, genera un parrafo de igual o MAYOR longitud, mejorando la "
    "redaccion academica sin eliminar ni un solo dato. Esta prohibido "
    "omitir frases, fusionar varias ideas en una sola, o dejar fuera "
    "cualquier informacion presente en el original por parecer "
    "secundaria.\n\n"
    "=== REGLA MAXIMA E INNEGOCIABLE: DESTRUCCION DE METADATOS ===\n"
    "Los bloques de origen pueden contener restos de portadas, creditos, "
    "licencias o pies de pagina de los materiales de los que proceden. Esta "
    "PROHIBIDO de forma ABSOLUTA incluir, citar, parafrasear o dejar rastro "
    "de: licencias de cualquier tipo (por ejemplo 'Creative Commons', 'CC "
    "BY-SA', dominio publico, 'todos los derechos reservados'...); nombres "
    "de autores, coordinadores o prologuistas; academias, centros de "
    "formacion, editoriales o entidades (por ejemplo 'CEIS Guadalajara' o "
    "cualquier otra); manuales o temarios de origen; copyright, ISBN, "
    "ediciones, revisiones de version, dedicatorias, agradecimientos, o "
    "frases como 'manual elaborado por...' / 'curso impartido por...' / "
    "'material extraido de...'. Si detectas cualquier fragmento de este "
    "tipo en el texto de origen, ELIMINALO POR COMPLETO Y EN SILENCIO -- no "
    "lo menciones, no expliques que lo has quitado, simplemente no debe "
    "aparecer en tu respuesta. El documento tiene que leerse como un manual "
    "anonimo, propio y original de esta editorial: empieza SIEMPRE "
    "directamente con el titulo del tema y el contenido tecnico, nunca con "
    "portadas, creditos, licencias ni menciones de procedencia.\n\n"
    "=== FORMATO ===\n"
    "Redacta en prosa fluida, profesional y academica, propia de un manual "
    "de estudio para oposiciones -- parrafos bien desarrollados, con "
    "oraciones completas y transiciones hiladas entre ideas (conectores "
    "como 'ademas', 'por otro lado', 'en este sentido', 'como consecuencia "
    "de lo anterior'...). Reserva las listas y viñetas UNICAMENTE para lo "
    "que es intrinsecamente enumerable -- una secuencia cerrada de pasos de "
    "un procedimiento, una formula con sus variables, o un listado de "
    "articulos/apartados normativos citados textualmente -- y aun asi "
    "introducelo con una frase en prosa antes de la lista. Usa Markdown "
    "SOLO para titulo principal (#), subtitulos (##, ###) y negrita en "
    "terminos clave; el cuerpo del texto es siempre prosa desarrollada, "
    "jamas viñetas sueltas.\n\n"
    "Resto de reglas:\n"
    "- Hila los bloques entre si: suaviza las transiciones para que no se "
    "note que el texto viene de fragmentos separados.\n"
    "- Elimina unicamente repeticiones literales entre bloques consecutivos "
    "que reintroduzcan el mismo concepto o definicion, pero nunca a costa "
    "de perder contenido tecnico unico ni de acortar el desarrollo.\n"
    "- Mantén un tono tecnico y riguroso. NUNCA inventes ni añadas datos, "
    "cifras, articulos de ley o procedimientos que no esten ya en el texto "
    "original.\n"
    "- Cuando se te pase el final de lo que ya llevas editado del "
    "documento como contexto, NO lo repitas en tu respuesta: continua el "
    "documento justo donde lo dejaste, manteniendo el mismo estilo, tono y "
    "numeracion de titulos.\n"
    "- Cuando se te avise de que aun quedan mas bloques por llegar, no "
    "cierres el documento ni añadas conclusiones o resumenes finales "
    "todavia -- eso solo corresponde al ultimo fragmento del tema.\n"
    "- Devuelve UNICAMENTE el Markdown del documento (o de su "
    "continuacion). Sin explicaciones tuyas, sin bloques de codigo "
    "envolviendo la respuesta, sin frases tipo 'aqui tienes el resultado'."
)


def _construir_mensaje_usuario(
    tema: str, fragmento: str, contexto_previo: str | None, es_ultimo: bool
) -> str:
    partes = [f"Tema: {tema}"]

    if contexto_previo:
        partes.append(
            "Esto es el final de lo que ya llevas editado del documento "
            f"(no lo repitas, continua justo despues):\n\n{contexto_previo}"
        )
        partes.append("Continua el documento con los siguientes bloques nuevos:")
    else:
        partes.append(
            "Estos son los primeros bloques del tema: empieza el documento "
            "con un titulo principal (#) adecuado."
        )

    partes.append(fragmento)

    if not es_ultimo:
        partes.append(
            "Aviso: estos NO son todos los bloques del tema, vendran mas a "
            "continuacion en la siguiente llamada. No cierres el documento "
            "ni añadas conclusiones finales todavia."
        )

    return "\n\n---\n\n".join(partes)


async def ensamblar_tema(
    cliente: genai.Client, tema: str, rutas: list[Path], semaforo: asyncio.Semaphore
) -> str:
    fragmentos = agrupar_en_fragmentos(rutas)
    documento = ""

    async with semaforo:
        for i, fragmento in enumerate(fragmentos):
            es_ultimo = i == len(fragmentos) - 1
            contexto_previo = (
                _cola_en_tokens(documento, TOKENS_CONTEXTO_PREVIO)
                if documento
                else None
            )
            mensaje = _construir_mensaje_usuario(
                tema, fragmento, contexto_previo, es_ultimo
            )

            print(f"  [{tema}] fragmento {i + 1}/{len(fragmentos)}...")

            # --- NUEVO: BUCLE DE REINTENTOS ANTI-SATURACIÓN ---
            max_reintentos = 5
            for intento in range(max_reintentos):
                try:
                    respuesta = await cliente.aio.models.generate_content(
                        model=MODELO_CHAT,
                        contents=mensaje,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            temperature=0.3,
                            max_output_tokens=MAX_TOKENS_SALIDA,
                        ),
                    )
                    break  # Si funciona a la primera, rompe el bucle de reintentos y sigue
                except Exception as exc:
                    if intento == max_reintentos - 1:
                        # Si ya ha fallado 5 veces seguidas, entonces sí, que tire la toalla
                        raise exc
                    
                    # Tiempo de espera progresivo: 15s, 30s, 45s...
                    tiempo_espera = 15 * (intento + 1)
                    print(f"  [{tema}] Servidor saturado (intento {intento+1}/{max_reintentos}). Esperando {tiempo_espera}s para reintentar...")
                    await asyncio.sleep(tiempo_espera)
            # ----------------------------------------------------
            
            texto_generado = (respuesta.text or "").strip()
            
            # Limpieza básica por si Gemini envuelve la respuesta en bloque de código
            if texto_generado.startswith("```markdown"):
                texto_generado = texto_generado[11:]
            if texto_generado.startswith("```"):
                texto_generado = texto_generado[3:]
            if texto_generado.endswith("```"):
                texto_generado = texto_generado[:-3]
                
            documento = f"{documento}\n\n{texto_generado.strip()}" if documento else texto_generado.strip()

    return documento


async def procesar_tema(
    cliente: genai.Client, tema: str, rutas: list[Path], semaforo: asyncio.Semaphore
) -> None:
    ruta_salida = DIR_SALIDA / f"{tema}.md"
    if ruta_salida.exists():
        print(f"[{tema}] Tema ya generado, omitiendo... ({ruta_salida.name} ya existe)")
        return

    try:
        documento = await ensamblar_tema(cliente, tema, rutas, semaforo)
    except Exception as exc:
        print(f"[{tema}] error llamando a Gemini, se descarta este tema: {exc}")
        return

    ruta_salida.write_text(documento, encoding="utf-8")
    print(f"[{tema}] guardado en {ruta_salida}")


async def main() -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("Falta GOOGLE_API_KEY en el .env, no se puede llamar a Gemini.")
        return

    temas = escanear_bloques(DIR_ORIGEN)
    if not temas:
        print(
            f"No se encontraron bloques en {DIR_ORIGEN} "
            "(patron esperado: '<tema>_bloque_<n>.txt')."
        )
        return

    resumen = ", ".join(f"{tema} ({len(rutas)} bloques)" for tema, rutas in temas.items())
    print(f"Temas encontrados: {resumen}")

    DIR_SALIDA.mkdir(exist_ok=True)
    
    # Inicialización del cliente de GenAI
    cliente = genai.Client(api_key=api_key)
    semaforo = asyncio.Semaphore(MAX_TEMAS_EN_PARALELO)

    await asyncio.gather(
        *(
            procesar_tema(cliente, tema, rutas, semaforo)
            for tema, rutas in temas.items()
        )
    )

    print("\nListo.")


if __name__ == "__main__":
    asyncio.run(main())