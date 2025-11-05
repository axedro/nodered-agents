"""
Web Searcher Agent - Busca nodos faltantes en la web
Encuentra paquetes npm de Node-RED para los nodos que faltan
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
import json
import re


WEB_SEARCH_PROMPT = """Eres un experto en Node-RED que conoce todos los paquetes disponibles.

Necesito encontrar paquetes npm para estos nodos faltantes: {missing_nodes}

Para el contexto: el usuario quiere crear este flujo: {clarified_request}

Dame una lista de paquetes npm que debería instalar. Responde SOLO con un JSON en este formato:

{{
  "suggestions": [
    {{
      "node_type": "nombre del nodo",
      "package": "node-red-contrib-nombre",
      "source": "npm",
      "description": "breve descripción"
    }}
  ]
}}

Usa paquetes reales y populares de Node-RED. Si no estás seguro, sugiere el más común.
"""


async def web_searcher_agent(state: AgentState) -> AgentState:
    """
    Busca paquetes npm para los nodos faltantes.
    """
    logger.info(f"[WebSearcher] Searching for {len(state['missing_nodes'])} missing nodes...")

    llm = LLMManager()

    prompt = WEB_SEARCH_PROMPT.format(
        missing_nodes=', '.join(state['missing_nodes']),
        clarified_request=state.get('clarified_request', state['user_request'])
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.3,
        max_tokens=1000
    )

    logger.info(f"[WebSearcher] Response: {response[:200]}...")

    # Extraer JSON de la respuesta
    try:
        json_match = re.search(r'\{.*"suggestions".*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            suggestions = data.get('suggestions', [])

            state['suggested_installations'] = suggestions
            logger.info(f"[WebSearcher] Found {len(suggestions)} package suggestions")

            # Ir al instalador
            state['current_agent'] = 'installer'
            state['conversation_history'].append({
                'role': 'assistant',
                'content': f"Encontré {len(suggestions)} paquetes para instalar. Procediendo con la instalación..."
            })

        else:
            # No se pudo parsear, continuar sin instalaciones
            logger.warning("[WebSearcher] Could not parse suggestions, proceeding without")
            state['suggested_installations'] = []
            state['current_agent'] = 'function_coder'

    except json.JSONDecodeError as e:
        logger.error(f"[WebSearcher] JSON parsing error: {e}")
        state['suggested_installations'] = []
        state['current_agent'] = 'function_coder'

    state['needs_user_input'] = False
    return state
