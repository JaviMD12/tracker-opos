"""Tutor IA del Plan Pro: RAG sobre las rutinas fisicas, las tecnicas de estudio
y cualquier documento (PDF o TXT) que el usuario deposite en
`backend/app/conocimiento/`.

La base vectorial se construye en memoria (sin persistir a disco) combinando:
- el texto plano generado a partir de los diccionarios `RUTINAS_PRO` y
  `TECNICAS_ESTUDIO_PRO`;
- todos los PDF y TXT encontrados en `conocimiento/`.
Todo se trocea con `RecursiveCharacterTextSplitter` (chunks de 1000 caracteres,
solapamiento de 200) antes de indexarse en Chroma.

La inicializacion es perezosa (lazy): no se llama a OpenAI ni se leen los
documentos hasta la primera pregunta, para que el resto de la aplicacion siga
funcionando aunque la clave de API no este configurada todavia.
"""

from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import (
    DirectoryLoader,
    PyPDFDirectoryLoader,
    TextLoader,
)
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.services.rutinas import RUTINAS_PRO, TECNICAS_ESTUDIO_PRO

# OPENAI_API_KEY se carga desde backend/.env (ver app/main.py, load_dotenv()).
# Si no esta configurada, OpenAIEmbeddings/ChatOpenAI fallan al primer uso real
# (inicializacion perezosa, ver _obtener_vectorstore), no al importar este modulo.

MODELO_CHAT = "gpt-4o-mini"
MODELO_EMBEDDINGS = "text-embedding-3-small"
FRAGMENTOS_A_RECUPERAR = 4
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Carpeta donde el usuario deposita sus propios PDFs/TXT de estudio y
# entrenamiento para ampliar el conocimiento del tutor. Se crea sola si no
# existe todavia (no requiere red ni clave de API, es seguro hacerlo al
# importar este modulo).
CARPETA_CONOCIMIENTO = Path(__file__).resolve().parent.parent / "conocimiento"
CARPETA_CONOCIMIENTO.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (
    "Eres un preparador fisico de elite, fisiologo deportivo, tutor academico "
    "y orientador experto en las bases legales de la oposicion de bomberos. "
    "Ademas de entrenamiento y estudio, TIENES PERMITIDO y DEBES responder "
    "detalladamente a cualquier pregunta administrativa (plazos, requisitos, "
    "exclusiones medicas, baremos) basandote en los documentos oficiales "
    "proporcionados en el contexto. Tu autoridad es absoluta. "
    "Tu fuente de conocimiento es el contexto proporcionado en cada pregunta, "
    "extraido de las rutinas de entrenamiento, las tecnicas de estudio y los "
    "documentos (incluida la convocatoria oficial y sus bases legales) del "
    "Plan Pro del usuario. No uses conocimiento general ni inventes datos que "
    "no esten en ese contexto.\n\n"
    "REGLA DE LONGITUD (estricta, aplicala siempre antes de responder):\n"
    "- Si la pregunta pide un dato concreto y cerrado (un plazo, una fecha, "
    "un requisito puntual de una ley, una cifra, un limite...), responde "
    "UNICAMENTE con ese dato en una sola frase directa. Nada de "
    "introducciones, contexto previo ni justificaciones añadidas.\n"
    "- Da una respuesta larga y desarrollada SOLO si el usuario la pide de "
    "forma explicita (por ejemplo: 'explicame', 'resume', 'cuentame mas', "
    "'desarrolla', 'por que', 'en detalle').\n"
    "- Cuando la respuesta sea desarrollada, usa Markdown obligatoriamente: "
    "parrafos muy cortos, listas con viñetas para enumerar puntos, y las "
    "palabras clave en **negrita**.\n\n"
    "Si el usuario pregunta algo fuera de las rutinas fisicas, las tecnicas "
    "de estudio, las bases administrativas/legales de la oposicion o el "
    "temario proporcionado (por ejemplo, recetas de cocina u otras preguntas "
    "genericas sin relacion), dile cortesmente que solo puedes asesorarle "
    "sobre el contenido de su Plan Pro y sugierele reformular la pregunta en "
    "torno a sus rutinas, sus tecnicas de estudio, la convocatoria oficial o "
    "sus documentos cargados. Responde siempre en español, con un tono "
    "motivador y profesional."
)

_vectorstore: Chroma | None = None


def _construir_documentos_diccionarios() -> list[Document]:
    """Convierte RUTINAS_PRO y TECNICAS_ESTUDIO_PRO en Document de LangChain."""
    documentos = []

    for clave, rutina in RUTINAS_PRO.items():
        fases_texto = "\n".join(
            f"- {fase['fase']} (Intensidad: {fase['intensidad']}, Volumen: {fase['volumen']}). "
            f"{fase['detalle']} Por que funciona: {fase['fundamento']}"
            for fase in rutina["entrenamiento_semanal"]
        )
        texto = (
            f"RUTINA DE ENTRENAMIENTO FISICO: {rutina['titulo']} (prueba: {clave})\n"
            f"Base cientifica: {rutina['descripcion_cientifica']}\n"
            f"Programa semanal:\n{fases_texto}\n"
            f"Bibliografia: {rutina['bibliografia']}"
        )
        documentos.append(
            Document(page_content=texto, metadata={"tipo": "rutina_fisica", "prueba": clave})
        )

    for clave, tecnica in TECNICAS_ESTUDIO_PRO.items():
        pasos_texto = "\n".join(f"- {paso}" for paso in tecnica["paso_a_paso"])
        texto = (
            f"TECNICA DE ESTUDIO: {tecnica['nombre']}\n"
            f"Concepto cientifico: {tecnica['concepto_cientifico']}\n"
            f"Pasos:\n{pasos_texto}\n"
            f"Ejemplo aplicado al temario: {tecnica['ejemplo_aplicado']}"
        )
        documentos.append(
            Document(page_content=texto, metadata={"tipo": "tecnica_estudio", "clave": clave})
        )

    return documentos


def _cargar_documentos_conocimiento() -> list[Document]:
    """Escanea backend/app/conocimiento/ y carga todos los PDF y TXT que encuentre."""
    documentos: list[Document] = []

    documentos.extend(PyPDFDirectoryLoader(str(CARPETA_CONOCIMIENTO)).load())

    cargador_txt = DirectoryLoader(
        str(CARPETA_CONOCIMIENTO),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        silent_errors=True,
    )
    documentos.extend(cargador_txt.load())

    return documentos


def _obtener_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        documentos = _construir_documentos_diccionarios() + _cargar_documentos_conocimiento()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        fragmentos = splitter.split_documents(documentos)
        embeddings = OpenAIEmbeddings(model=MODELO_EMBEDDINGS)
        _vectorstore = Chroma.from_documents(fragmentos, embeddings)
    return _vectorstore


def preguntar_al_tutor(query: str) -> str:
    """Busca los fragmentos mas relevantes del Plan Pro y genera la respuesta
    del tutor IA restringida a ese contexto."""
    vectorstore = _obtener_vectorstore()
    fragmentos = vectorstore.similarity_search(query, k=FRAGMENTOS_A_RECUPERAR)
    contexto = "\n\n---\n\n".join(doc.page_content for doc in fragmentos)

    llm = ChatOpenAI(model=MODELO_CHAT, temperature=0.3)
    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"Contexto disponible de tu Plan Pro:\n{contexto}\n\n"
                f"Pregunta del usuario: {query}"
            )
        ),
    ]
    respuesta = llm.invoke(mensajes)
    return respuesta.content
