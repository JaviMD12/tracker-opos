import json
import time

from dotenv import load_dotenv

load_dotenv()

from google import genai

from app.services.ai_tutor import preguntar_al_tutor

client = genai.Client()

# 1. Casos de prueba: Preguntas directas, ambiguas y con "trampa"
BANCO_PRUEBAS = [
    {
        "id": "TEMA_01_HIDRAULICA",
        "pregunta": "¿Cuál es la pérdida de carga aproximada en una manguera de 45mm a 250 l/min?",
        "criterio_oficial": "Debe citar la fórmula de pérdida de carga o valores estándar de tablas oficiales sin inventar decimales."
    },
    {
        "id": "TEMA_02_NORMATIVA_CTE",
        "pregunta": "¿Qué altura de evacuación obliga a instalar una columna seca según el CTE DB-SI?",
        "criterio_oficial": "Debe indicar exactamente más de 24 metros (o 15 m en casos específicos regulados por ordenanza/norma si aplica)."
    },
    {
        "id": "TEMA_03_TRAMPA",
        "pregunta": "¿Cuál es el artículo de la Constitución Española que regula los parques de bomberos?",
        "criterio_oficial": "Debe rechazar la premisa: la CE no regula parques de bomberos directamente (art. 148/149 sobre competencias, pero no parques específicos)."
    }
]

def obtener_respuesta_tutor(pregunta: str) -> str:
    """Llama al tutor real (RAG + SYSTEM_PROMPT de app/services/ai_tutor.py),
    no a Gemini en bruto -- de lo contrario las brechas detectadas no
    dirian nada sobre el sistema que de verdad esta en produccion."""
    return preguntar_al_tutor(pregunta)

def evaluar_con_juez(pregunta: str, respuesta_tutor: str, criterio: str) -> dict:
    """Modelo juez que evalúa rigor y detecta alucinaciones."""
    prompt_juez = f"""
Actúa como un tribunal examinador implacable y auditor de calidad técnica.

Pregunta formulada: {pregunta}
Criterio oficial / Verdad técnica: {criterio}
Respuesta dada por el tutor:
\"\"\"{respuesta_tutor}\"\"\"

Evalúa si la respuesta contiene errores técnicos, imprecisiones o invenciones.
Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura:
{{
    "aprobado": true/false,
    "puntuacion_rigor_1_al_10": 1-10,
    "brecha_detectada": "Descripción clara del fallo o 'Ninguna'",
    "sugerencia_prompt": "Qué instrucción o dato en el contexto evitaría este error"
}}
"""
    evaluacion = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_juez,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(evaluacion.text)

def ejecutar_auditoria():
    informe_brechas = []
    print("Iniciando auditoría técnica del tutor...")

    for item in BANCO_PRUEBAS:
        print(f"Probando: {item['id']}...")
        resp_tutor = obtener_respuesta_tutor(item["pregunta"])
        analisis = evaluar_con_juez(item["pregunta"], resp_tutor, item["criterio_oficial"])
        
        if not analisis["aprobado"] or analisis["puntuacion_rigor_1_al_10"] < 9:
            informe_brechas.append({
                "id": item["id"],
                "pregunta": item["pregunta"],
                "respuesta_emitida": resp_tutor,
                "auditoria": analisis
            })
        time.sleep(1)

    with open("brechas_conocimiento.json", "w", encoding="utf-8") as f:
        json.dump(informe_brechas, f, ensure_ascii=False, indent=2)

    print(f"Auditoría finalizada. Se han detectado {len(informe_brechas)} brechas críticas.")
    print("Resultados guardados en 'brechas_conocimiento.json'.")

if __name__ == "__main__":
    ejecutar_auditoria()