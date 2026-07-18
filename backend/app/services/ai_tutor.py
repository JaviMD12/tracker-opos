"""Tutor IA del Plan Pro: RAG sobre las rutinas fisicas, las tecnicas de estudio
y cualquier documento (PDF o TXT) que el usuario deposite en
`backend/app/conocimiento/`.

La base vectorial combina:
- el texto plano generado a partir de los diccionarios `RUTINAS_PRO` y
  `TECNICAS_ESTUDIO_PRO`;
- todos los PDF y TXT encontrados en `conocimiento/`.
Todo se trocea con `RecursiveCharacterTextSplitter` (chunks de 1000 caracteres,
solapamiento de 200) antes de indexarse en Chroma.

El indice se persiste en disco en `backend/chroma_db_data/` (ver
CARPETA_PERSISTENCIA_VECTORSTORE): la primera vez que se usa el Tutor IA tras
un `git clone` (o si se borra esa carpeta) se reconstruye leyendo los PDFs y
llamando a OpenAI para los embeddings, lo cual tarda 1-2 minutos con el
volumen actual de documentos; en cualquier arranque posterior, se carga
directamente desde disco en menos de 2 segundos, sin volver a leer los PDFs
ni gastar llamadas a OpenAI (_vectorstore, con inicializacion perezosa: no se
llama a OpenAI ni se toca el disco hasta la primera pregunta, para que el
resto de la aplicacion siga funcionando aunque la clave de API no este
configurada todavia).

Nota: los Simulacros IA ya NO usan este vectorstore -- se sirven desde un
banco de preguntas precargado (ver app/models/pregunta_test.py y
backend/generar_banco.py), para que la respuesta al frontend sea una consulta
SQL en vez de una llamada a OpenAI en cada peticion.
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

# Indice de Chroma persistido en disco (backend/chroma_db_data/). No se crea
# aqui al importar el modulo a proposito: si no existe todavia, es la señal
# que usa _obtener_vectorstore() para decidir si tiene que reconstruir el
# indice desde los PDFs (CASO B) o si puede cargarlo tal cual (CASO A).
CARPETA_PERSISTENCIA_VECTORSTORE = Path(__file__).resolve().parent.parent.parent / "chroma_db_data"

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


def _sanear_texto_unicode(texto: str) -> str:
    """Elimina surrogates UTF-16 sueltos que pypdf a veces deja al extraer
    texto de PDFs con fuentes/codificaciones no estandar (frecuente en PDFs
    escaneados/exportados desde Word). Sin esto, Chroma (chromadb, bindings
    en Rust) revienta con UnicodeEncodeError al indexar ese fragmento,
    tumbando el vectorstore entero (afecta al Tutor IA y a los Simulacros
    por igual, ya que comparten el mismo vectorstore)."""
    return texto.encode("utf-8", errors="ignore").decode("utf-8")


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

    for documento in documentos:
        documento.page_content = _sanear_texto_unicode(documento.page_content)

    return documentos


def _indice_persistido_existe() -> bool:
    """True si CARPETA_PERSISTENCIA_VECTORSTORE ya tiene un indice de Chroma
    creado en una ejecucion anterior (carpeta presente y con contenido)."""
    return CARPETA_PERSISTENCIA_VECTORSTORE.exists() and any(
        CARPETA_PERSISTENCIA_VECTORSTORE.iterdir()
    )


def _obtener_vectorstore() -> Chroma:
    """Devuelve el vectorstore compartido por el Tutor IA y los Simulacros,
    cargandolo una sola vez por proceso (_vectorstore como singleton lazy).

    CASO A (ya indexado): si CARPETA_PERSISTENCIA_VECTORSTORE tiene datos de
    una ejecucion anterior, se abre directamente desde disco (rapido, sin
    leer PDFs ni llamar a OpenAI para generar embeddings).
    CASO B (primera vez / carpeta vacia o borrada): se reconstruye el indice
    completo desde los PDFs/TXT de conocimiento/ y se persiste en disco para
    que la proxima carga sea instantanea.
    """
    global _vectorstore
    if _vectorstore is not None:
        return _vectorstore

    embeddings = OpenAIEmbeddings(model=MODELO_EMBEDDINGS)

    if _indice_persistido_existe():
        _vectorstore = Chroma(
            persist_directory=str(CARPETA_PERSISTENCIA_VECTORSTORE),
            embedding_function=embeddings,
        )
        return _vectorstore

    documentos = _construir_documentos_diccionarios() + _cargar_documentos_conocimiento()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
    )
    fragmentos = splitter.split_documents(documentos)
    _vectorstore = Chroma.from_documents(
        fragmentos,
        embeddings,
        persist_directory=str(CARPETA_PERSISTENCIA_VECTORSTORE),
    )
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


SYSTEM_PROMPT_PLAN_ESTUDIO = (
    "Eres un analista experto en oposiciones públicas. Tu objetivo es leer "
    "convocatorias oficiales y extraer un plan de estudio milimétrico."
)


def generar_plan_estudio_convocatoria(titulo_plaza: str, requisitos_minimos: str) -> str:
    """Genera un plan de ataque en Markdown para una convocatoria concreta del
    Tablon de Plazas Premium, adaptado exclusivamente al cuerpo real de la
    plaza (el prompt ya no fuerza temario de bomberos/hidraulica de forma
    fija: el propio texto le exige identificar el cuerpo antes de redactar,
    para que una plaza administrativa no reciba temario de bomberos)."""
    user_prompt = (
        "Analiza la siguiente convocatoria oficial. "
        f"Plaza: '{titulo_plaza}'. Extracto: '{requisitos_minimos}'. "
        "INSTRUCCIONES ESTRICTAS: "
        "1. Identifica el cuerpo exacto basándote en el título. "
        "2. Resume los requisitos reales o plazos. "
        "3. Construye un plan de ataque en Markdown adaptado EXCLUSIVAMENTE a "
        "la naturaleza de esta plaza (ej. si es puramente administrativa, "
        "enfócate en legislación; si es de bomberos, en fuego e hidráulica). "
        "NO mezcles temarios. "
        "4. Si el extracto está muy vacío, avisa al usuario de consultar las "
        "bases, pero ofrécele las materias troncales habituales del cuerpo."
    )
    llm = ChatOpenAI(model=MODELO_CHAT, temperature=0.3)
    mensajes = [
        SystemMessage(content=SYSTEM_PROMPT_PLAN_ESTUDIO),
        HumanMessage(content=user_prompt),
    ]
    respuesta = llm.invoke(mensajes)
    return respuesta.content


