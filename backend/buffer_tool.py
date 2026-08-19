import os
import sys
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BUFFER_ACCESS_TOKEN")
GRAPHQL_URL = "https://api.buffer.com"

QUERY_ORGANIZACIONES = """
query GetOrganizations {
  account {
    organizations {
      id
    }
  }
}
"""

QUERY_CANALES = """
query GetChannels($organizationId: OrganizationId!) {
  channels(input: { organizationId: $organizationId }) {
    id
    displayName
    service
  }
}
"""

MUTATION_CREAR_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    ... on PostActionSuccess {
      post {
        id
        text
      }
    }
    ... on MutationError {
      message
    }
  }
}
"""


def _graphql(query: str, variables: dict | None = None) -> dict:
    """Ejecuta una query/mutation contra la API GraphQL de Buffer.
    La API REST legacy (api.bufferapp.com/1) que usaba este script antes
    rechaza los tokens de tipo "Public API token" (401) y ademas se retira
    el 1 de febrero de 2027 -- Buffer exige migrar a esta API GraphQL
    (api.buffer.com, autenticacion Bearer)."""
    r = requests.post(
        GRAPHQL_URL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    r.raise_for_status()
    cuerpo = r.json()
    if "errors" in cuerpo:
        raise RuntimeError(json.dumps(cuerpo["errors"], indent=2, ensure_ascii=False))
    return cuerpo["data"]


def listar_perfiles():
    """Obtiene los canales vinculados (id, nombre, red social) de todas las
    organizaciones de la cuenta."""
    organizaciones = _graphql(QUERY_ORGANIZACIONES)["account"]["organizations"]
    resultado = []
    for org in organizaciones:
        canales = _graphql(QUERY_CANALES, {"organizationId": org["id"]})["channels"]
        resultado.extend(canales)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))


def crear_post(channel_id: str, texto: str, due_at: str | None = None):
    """Programa una publicacion en Buffer. Sin due_at, se añade al proximo
    hueco libre de la cola de publicacion (mode: addToQueue) -- no se
    publica de inmediato. Con due_at (ISO 8601, UTC), se programa a esa
    hora exacta (mode: customScheduled)."""
    entrada = {
        "text": texto,
        "channelId": channel_id,
        "schedulingType": "automatic",
        "mode": "customScheduled" if due_at else "addToQueue",
    }
    if due_at:
        entrada["dueAt"] = due_at

    datos = _graphql(MUTATION_CREAR_POST, {"input": entrada})["createPost"]
    if "message" in datos:
        print(f"Error al publicar: {datos['message']}")
    else:
        print("Post programado con exito:")
        print(json.dumps(datos["post"], indent=2, ensure_ascii=False))


def _fecha_local_a_iso_utc(fecha_hora_str: str) -> str:
    """Convierte 'YYYY-MM-DD HH:MM' (hora local del sistema) a ISO 8601 UTC,
    el formato que exige dueAt en la mutation createPost."""
    dt_local = datetime.strptime(fecha_hora_str, "%Y-%m-%d %H:%M").astimezone()
    return dt_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "listar":
        listar_perfiles()
    elif len(sys.argv) > 3 and sys.argv[1] == "publicar":
        # Uso: python buffer_tool.py publicar <channel_id> "<texto>" [due_at_iso8601]
        due_at = sys.argv[4] if len(sys.argv) > 4 else None
        crear_post(sys.argv[2], sys.argv[3], due_at)
    elif len(sys.argv) > 4 and sys.argv[1] == "programar":
        # Uso: python buffer_tool.py programar <channel_id> "<texto>" 'YYYY-MM-DD HH:MM'
        try:
            due_at = _fecha_local_a_iso_utc(sys.argv[4])
        except ValueError:
            print("Formato de fecha invalido. Usa: 'YYYY-MM-DD HH:MM' (hora local)")
            sys.exit(1)
        crear_post(sys.argv[2], sys.argv[3], due_at)
    else:
        print(
            "Uso:\n"
            "  python buffer_tool.py listar\n"
            "  python buffer_tool.py publicar <channel_id> '<texto>' [due_at_iso8601]\n"
            "  python buffer_tool.py programar <channel_id> '<texto>' 'YYYY-MM-DD HH:MM'"
        )
