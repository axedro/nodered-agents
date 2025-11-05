"""
Conversator Agent - Dialoga con el usuario para refinar los requerimientos
Hace preguntas para clarificar: ERP, CRM, destinos, formatos, etc.
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
import json
import re


CONVERSATION_SYSTEM_PROMPT = """Eres un experto en Node-RED. Tu tarea: recopilar información del usuario para crear un flujo.

REGLAS IMPORTANTES:
1. Si la solicitud inicial tiene DETALLES ESPECÍFICOS (origen de datos, destino, frecuencia), NO hagas más preguntas.
2. Si la solicitud es VAGA o INCOMPLETA, haz máximo 2 preguntas específicas.
3. Después de la SEGUNDA respuesta del usuario, SIEMPRE completa la conversación.

INFORMACIÓN NECESARIA:
- Origen de datos (archivo, API, base de datos, etc.)
- Destino (email, base de datos, API, etc.)
- Frecuencia/trigger (tiempo, evento, manual)
- Transformaciones necesarias (si/no)

FORMATO DE RESPUESTA:

Si necesitas MÁS información (primera vez solamente):
Haz 1-2 preguntas directas y específicas.

Si ya tienes SUFICIENTE información:
Responde SOLO con este JSON (sin texto adicional):
{
  "status": "complete",
  "clarified_request": "Descripción clara del flujo completo",
  "required_nodes": ["inject", "csv", "function", "email"],
  "detected_systems": ["FileSystem", "Email"]
}

EJEMPLOS:

Usuario: "Leer CSV y enviar email"
Respuesta: "¿De dónde proviene el CSV y a qué dirección enviar el email?"

Usuario: "CSV de /data, enviar a admin@test.com diariamente a las 9am"
Respuesta JSON completo con status: "complete"

IMPORTANTE: Después de 2 intercambios, SIEMPRE genera el JSON con "status": "complete"."""


async def conversator_agent(state: AgentState) -> AgentState:
    """
    Dialoga con el usuario para entender completamente sus necesidades.
    """
    logger.info("[Conversator] Starting conversation...")

    llm = LLMManager()

    # Contar cuántos intercambios ha habido (para forzar completion después de 2 rondas)
    user_messages = sum(1 for msg in state['conversation_history'] if msg['role'] == 'user')

    logger.info(f"[Conversator] User messages so far: {user_messages}")

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

    # Si ya hubo 2+ respuestas del usuario, forzar completion
    if user_messages >= 2:
        messages.append({
            "role": "system",
            "content": "Ya tienes suficiente información. Genera el JSON con 'status': 'complete' AHORA."
        })

    # Generar respuesta con temperatura más baja para ser más determinista
    response = await llm.generate_with_history(
        messages=messages,
        temperature=0.3 if user_messages >= 1 else 0.7,
        max_tokens=500
    )

    logger.info(f"[Conversator] Response: {response[:200]}...")

    # Verificar si la conversación está completa
    try:
        # Buscar JSON en la respuesta (más flexible)
        json_match = re.search(r'\{[^{}]*"status"\s*:\s*"complete"[^{}]*\}', response, re.DOTALL | re.IGNORECASE)

        if not json_match:
            # Intentar buscar con estructura más anidada
            json_match = re.search(r'\{(?:[^{}]|{[^{}]*})*"status"\s*:\s*"complete"(?:[^{}]|{[^{}]*})*\}', response, re.DOTALL | re.IGNORECASE)

        if json_match:
            json_str = json_match.group()
            logger.info(f"[Conversator] Found JSON: {json_str[:100]}...")
            completion_data = json.loads(json_str)

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

    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"[Conversator] Failed to parse JSON: {e}")

    # Si ya hubo 3+ intentos y aún no hay completion, forzar manualmente
    if user_messages >= 3:
        logger.warning("[Conversator] Forcing completion after 3 user messages")

        # Crear descripción basada en el historial
        all_user_content = " ".join([msg['content'] for msg in state['conversation_history'] if msg['role'] == 'user'])

        state['clarified_request'] = f"{state['user_request']}. {all_user_content}"
        state['required_nodes'] = ["inject", "function", "debug"]  # Nodos básicos por defecto
        state['detected_systems'] = []
        state['current_agent'] = 'local_searcher'
        state['needs_user_input'] = False

        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Entiendo. Voy a crear el flujo basado en la información proporcionada."
        })

        return state

    # Continuar conversación
    state['conversation_history'].append({
        'role': 'assistant',
        'content': response
    })

    state['current_agent'] = 'conversator'
    state['needs_user_input'] = True

    return state
