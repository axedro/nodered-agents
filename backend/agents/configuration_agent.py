"""
Configuration Agent - Identifica y recopila configuraciones necesarias para cada nodo
Especializado en URLs, credenciales, dominios, puertos, y propiedades específicas
"""
from loguru import logger
from backend.core.state import AgentState, NodeConfiguration
from backend.core.llm_manager import LLMManager
from backend.rag.vector_store import VectorStoreManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType
import json
import re


CONFIGURATION_PROMPT = """Eres un experto en configuración de nodos de Node-RED.

REQUERIMIENTO DEL USUARIO: {clarified_request}

NODOS IDENTIFICADOS: {required_nodes}
SISTEMAS DETECTADOS: {detected_systems}

DOCUMENTACIÓN DE CONFIGURACIÓN:
{config_docs}

Tu tarea es identificar QUÉ CONFIGURACIONES necesita cada nodo para funcionar, basándote en la documentación proporcionada.

Para cada nodo, identifica:
1. URLs de APIs (si aplica)
2. Credenciales necesarias (usuario, password, API keys, tokens)
3. Dominios, puertos, hosts
4. Configuraciones específicas del tipo de nodo (topic MQTT, query SQL, headers HTTP, etc.)
5. Parámetros de conexión

EJEMPLOS:

Para un nodo "http request":
- URL del endpoint
- Método HTTP (GET, POST, etc.)
- Headers necesarios (Authorization, Content-Type)
- Authentication (API key, Bearer token)

Para un nodo "mqtt":
- Broker URL
- Puerto
- Topic
- QoS
- Usuario/password si requiere autenticación

Para un nodo "email":
- Servidor SMTP (host, puerto)
- Usuario y password
- De/Para
- Asunto

Para un nodo "mysql" o "postgres":
- Host y puerto
- Nombre de base de datos
- Usuario y password
- Query SQL

IMPORTANTE:
- Si el usuario NO especificó algún valor concreto (URL, credencial, etc.), márcalo como "NEEDS_USER_INPUT"
- Si hay valores por defecto razonables, úsalos
- Si el nodo no necesita configuración especial, indica "standard config"

REGLAS DE FORMATO JSON:
- NO incluyas comentarios (//) en el JSON
- NO incluyas texto explicativo dentro del JSON
- Usa SOLO sintaxis JSON válida estricta
- Todas las cadenas deben usar comillas dobles (")

Responde SOLO con este JSON:
{{
  "configurations": [
    {{
      "node_id": "http_request_1",
      "node_type": "http request",
      "properties": {{
        "url": "NEEDS_USER_INPUT",
        "method": "GET",
        "headers": {{}},
        "authentication": "NEEDS_USER_INPUT"
      }},
      "description": "HTTP request para obtener datos de API externa"
    }},
    {{
      "node_id": "email_1",
      "node_type": "email",
      "properties": {{
        "server": "NEEDS_USER_INPUT",
        "port": 587,
        "userid": "NEEDS_USER_INPUT",
        "password": "NEEDS_USER_INPUT"
      }},
      "description": "Envío de email con resultados"
    }}
  ],
  "missing_info": ["URL de la API", "Credenciales del servidor SMTP"]
}}

Si NO hay configuraciones especiales necesarias (solo nodos inject, function, debug):
{{
  "configurations": [],
  "missing_info": []
}}
"""


async def configuration_agent(state: AgentState) -> AgentState:
    """
    Identifica configuraciones necesarias para cada nodo del flujo.
    """
    logger.info("[ConfigurationAgent] Analyzing node configurations...")

    session_id = state.get('session_id')

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="ConfigurationAgent",
        message="Identificando configuraciones necesarias para cada nodo..."
    ))

    llm = LLMManager()
    vector_store = VectorStoreManager()

    # Buscar documentación relevante sobre configuración de nodos
    required_nodes = state.get('required_nodes', [])
    detected_systems = state.get('detected_systems', [])

    # Buscar docs para los tipos de nodos y sistemas identificados
    search_queries = required_nodes + detected_systems
    config_docs_text = ""

    for query in search_queries[:5]:  # Limitar a 5 búsquedas
        docs = vector_store.search_documentation(
            query=f"{query} configuration requirements",
            category="node_config",
            n_results=1
        )
        if docs:
            config_docs_text += f"\n\n{docs[0]['title']}:\n{docs[0]['content']}\n"

    if not config_docs_text:
        config_docs_text = "No se encontró documentación específica. Usar conocimiento general de Node-RED."

    prompt = CONFIGURATION_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        required_nodes=', '.join(required_nodes) if required_nodes else 'standard nodes',
        detected_systems=', '.join(detected_systems),
        config_docs=config_docs_text
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.3,
        max_tokens=2000
    )

    logger.info(f"[ConfigurationAgent] Response: {response[:300]}...")

    # Extraer JSON - usar approach robusto similar al Conversator
    try:
        # Función auxiliar para limpiar comentarios de estilo //
        def remove_json_comments(text):
            """Remove // style comments from JSON text"""
            lines = text.split('\n')
            cleaned_lines = []
            for line in lines:
                # Buscar // fuera de strings
                comment_pos = line.find('//')
                if comment_pos != -1:
                    # Verificar que no esté dentro de una string
                    before = line[:comment_pos]
                    quote_count = before.count('"') - before.count('\\"')
                    if quote_count % 2 == 0:  # Par de comillas = fuera de string
                        line = before.rstrip()
                cleaned_lines.append(line)
            return '\n'.join(cleaned_lines)

        # Buscar JSON en la respuesta usando depth tracking
        data = None
        start_pos = 0
        while True:
            json_start = response.find('{', start_pos)
            if json_start == -1:
                break

            json_candidate = response[json_start:]

            # Usar depth tracking para encontrar el JSON completo
            depth = 0
            for i, char in enumerate(json_candidate):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        # Tenemos un JSON completo
                        potential_json = json_candidate[:i+1]

                        # Limpiar comentarios
                        cleaned_json = remove_json_comments(potential_json)

                        try:
                            parsed = json.loads(cleaned_json)
                            if isinstance(parsed, dict) and 'configurations' in parsed:
                                data = parsed
                                logger.info(f"[ConfigurationAgent] Found valid JSON")
                                break
                        except json.JSONDecodeError:
                            pass

            if data:
                break

            start_pos = json_start + 1

        if data:

            configurations = data.get('configurations', [])
            missing_info = data.get('missing_info', [])

            # Convertir a formato NodeConfiguration
            state['node_configurations'] = [
                NodeConfiguration(
                    node_id=cfg['node_id'],
                    node_type=cfg['node_type'],
                    properties=cfg['properties'],
                    description=cfg['description']
                )
                for cfg in configurations
            ]

            # Agregar info faltante al estado
            if missing_info:
                if 'missing_information' not in state:
                    state['missing_information'] = []
                state['missing_information'].extend(missing_info)

            logger.info(f"[ConfigurationAgent] Identified {len(configurations)} node configurations")
            logger.info(f"[ConfigurationAgent] Missing info: {missing_info}")

            await progress_manager.send_event(session_id, ProgressEvent(
                type=ProgressEventType.AGENT_COMPLETE,
                agent="ConfigurationAgent",
                message=f"Configuraciones identificadas: {len(configurations)} nodos, {len(missing_info)} datos faltantes",
                details={'config_count': len(configurations), 'missing_count': len(missing_info)}
            ))

            if missing_info:
                await progress_manager.send_event(session_id, ProgressEvent(
                    type=ProgressEventType.INFO,
                    agent="ConfigurationAgent",
                    message=f"Información requerida: {', '.join(missing_info[:3])}{'...' if len(missing_info) > 3 else ''}"
                ))

        else:
            logger.warning("[ConfigurationAgent] Could not parse response")
            state['node_configurations'] = []

            await progress_manager.send_event(session_id, ProgressEvent(
                type=ProgressEventType.INFO,
                agent="ConfigurationAgent",
                message="No se pudieron identificar configuraciones específicas"
            ))

    except json.JSONDecodeError as e:
        logger.error(f"[ConfigurationAgent] JSON error: {e}")
        state['node_configurations'] = []

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.ERROR,
            agent="ConfigurationAgent",
            message=f"Error al parsear configuraciones: {str(e)}"
        ))

    return state
