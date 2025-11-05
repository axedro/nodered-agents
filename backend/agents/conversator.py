"""
Conversator Agent - Dialoga con el usuario para refinar los requerimientos
Hace preguntas para clarificar: ERP, CRM, destinos, formatos, etc.
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
import json
import re


CONVERSATION_SYSTEM_PROMPT = """Eres un asistente experto en Node-RED que ayuda a usuarios a crear flujos de automatización.

Tu trabajo es hacer preguntas clarificadoras para entender EXACTAMENTE qué flujo necesita el usuario.

Debes preguntar sobre:
1. Sistemas involucrados (ERP, CRM, bases de datos, APIs, etc.)
2. Tipo de integración (HTTP, MQTT, base de datos, email, Slack, etc.)
3. Datos a procesar (formatos, transformaciones necesarias)
4. Destinos finales (dónde va la información)
5. Lógica de negocio (condiciones, filtros, validaciones)

Haz UNA o DOS preguntas a la vez. Sé conciso pero amigable.

Cuando tengas TODA la información necesaria, responde con un JSON en este formato:
{
  "status": "complete",
  "clarified_request": "Descripción completa y clara del flujo",
  "required_nodes": ["http request", "function", "slack"],
  "detected_systems": ["Salesforce", "Slack"]
}

Mientras tanto, haz preguntas específicas para clarificar.
"""


async def conversator_agent(state: AgentState) -> AgentState:
    """
    Dialoga con el usuario para entender completamente sus necesidades.
    """
    logger.info("[Conversator] Starting conversation...")

    llm = LLMManager()

    # Construir historial de mensajes
    messages = [
        {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT}
    ]

    # Agregar historial de conversación
    for msg in state['conversation_history']:
        messages.append({
            "role": msg['role'],
            "content": msg['content']
        })

    # Si es la primera vez, agregar el request inicial
    if not state.get('clarified_request'):
        messages.append({
            "role": "user",
            "content": f"Necesito ayuda con esto: {state['user_request']}"
        })

    # Generar respuesta
    response = await llm.generate_with_history(
        messages=messages,
        temperature=0.7,
        max_tokens=500
    )

    logger.info(f"[Conversator] Response: {response[:100]}...")

    # Verificar si la conversación está completa
    try:
        # Intentar extraer JSON de la respuesta
        json_match = re.search(r'\{[^{}]*"status"\s*:\s*"complete"[^{}]*\}', response, re.DOTALL)
        if json_match:
            completion_data = json.loads(json_match.group())

            if completion_data.get('status') == 'complete':
                # ¡Conversación completa!
                logger.info("[Conversator] Conversation COMPLETE")

                state['clarified_request'] = completion_data.get('clarified_request', state['user_request'])
                state['required_nodes'] = completion_data.get('required_nodes', [])
                state['detected_systems'] = completion_data.get('detected_systems', [])
                state['current_agent'] = 'local_searcher'
                state['needs_user_input'] = False

                state['conversation_history'].append({
                    'role': 'assistant',
                    'content': f"Perfecto, tengo toda la información. Voy a buscar los nodos necesarios para: {state['clarified_request']}"
                })

                return state

    except json.JSONDecodeError:
        pass

    # Continuar conversación
    state['conversation_history'].append({
        'role': 'assistant',
        'content': response
    })

    state['current_agent'] = 'conversator'
    state['needs_user_input'] = True

    return state
