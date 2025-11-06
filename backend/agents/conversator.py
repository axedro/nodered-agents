"""
Conversator Agent - Dialoga con el usuario para refinar los requerimientos
Hace preguntas para clarificar: ERP, CRM, destinos, formatos, etc.
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType
from backend.rag.vector_store import VectorStoreManager
import json
import re


CONVERSATION_SYSTEM_PROMPT = """Eres un experto en Node-RED. Tu tarea: recopilar información del usuario para crear un flujo completo y funcional.

REGLAS IMPORTANTES:
1. Si la solicitud inicial tiene DETALLES ESPECÍFICOS (origen, destino, credenciales, frecuencia), NO hagas más preguntas.
2. Si la solicitud es VAGA o INCOMPLETA, haz máximo 2-3 preguntas específicas y ESENCIALES.
3. Después de la SEGUNDA respuesta del usuario, SIEMPRE completa la conversación.

INFORMACIÓN ESENCIAL NECESARIA:
{requirements_checklist}

ENFÓCATE EN LO MÁS CRÍTICO:
- INPUT: ¿De dónde vienen los datos? ¿Credenciales/autenticación?
- OUTPUT: ¿A dónde van los datos? ¿Credenciales/configuración?
- TRIGGER: ¿Cuándo/cómo se ejecuta? (manual, cada X tiempo, evento)
- TRANSFORMACIÓN: ¿Qué procesamiento se necesita?

FORMATO DE RESPUESTA:

Si necesitas MÁS información (primera vez solamente):
Haz 1-2 preguntas directas y específicas.

Si ya tienes SUFICIENTE información:
Responde SOLO con este JSON (sin texto adicional):
{{
  "status": "complete",
  "clarified_request": "Descripción clara del flujo completo",
  "required_nodes": ["inject", "csv", "function", "email"],
  "detected_systems": ["FileSystem", "Email"]
}}

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

    session_id = state.get('session_id')

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="Conversator",
        message="Analizando y clarificando requerimientos del usuario..."
    ))

    llm = LLMManager()
    vector_store = VectorStoreManager()

    # Buscar checklist de requerimientos en documentación
    requirements_docs = vector_store.search_documentation(
        query="Essential Flow Information Checklist requirements",
        category="requirements",
        n_results=1
    )

    requirements_checklist = ""
    if requirements_docs:
        requirements_checklist = requirements_docs[0]['content']
    else:
        requirements_checklist = """
INPUT: origen de datos, autenticación, formato
OUTPUT: destino, credenciales, formato de salida
TRIGGER: frecuencia (manual, programado, evento)
PROCESAMIENTO: transformaciones, filtros, validaciones
"""

    # Contar cuántos intercambios ha habido (para forzar completion después de 2 rondas)
    user_messages = sum(1 for msg in state['conversation_history'] if msg['role'] == 'user')

    logger.info(f"[Conversator] User messages so far: {user_messages}")

    # Construir historial de mensajes con checklist
    system_prompt = CONVERSATION_SYSTEM_PROMPT.format(
        requirements_checklist=requirements_checklist
    )

    messages = [
        {"role": "system", "content": system_prompt}
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
        # Buscar JSON en la respuesta usando un approach más robusto
        # El LLM a veces pone texto antes del JSON, así que buscaremos todas las posibles posiciones
        completion_data = None

        # Estrategia 1: Buscar desde cada { encontrado
        start_pos = 0
        while True:
            json_start = response.find('{', start_pos)
            if json_start == -1:
                break

            # Intentar parsear desde esta posición
            json_candidate = response[json_start:]

            # Buscar el cierre del JSON
            try:
                # Intentar encontrar el JSON completo con status: complete
                # Buscar hasta el próximo } que cierre el JSON
                depth = 0
                for i, char in enumerate(json_candidate):
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            # Intentar parsear este fragmento
                            potential_json = json_candidate[:i+1]
                            try:
                                data = json.loads(potential_json)
                                if isinstance(data, dict) and data.get('status') == 'complete':
                                    completion_data = data
                                    logger.info(f"[Conversator] Found JSON: {potential_json[:100]}...")
                                    break
                            except json.JSONDecodeError:
                                # Este no era un JSON válido, continuar buscando
                                pass

                if completion_data:
                    break

            except Exception:
                pass

            start_pos = json_start + 1

        if completion_data:

            if completion_data.get('status') == 'complete':
                # ¡Conversación completa!
                logger.info("[Conversator] Conversation COMPLETE - sending to Manager")

                state['clarified_request'] = completion_data.get('clarified_request', state['user_request'])
                state['required_nodes'] = completion_data.get('required_nodes', [])
                state['detected_systems'] = completion_data.get('detected_systems', [])

                await progress_manager.send_event(session_id, ProgressEvent(
                    type=ProgressEventType.AGENT_COMPLETE,
                    agent="Conversator",
                    message=f"Requerimientos clarificados exitosamente: {len(state['required_nodes'])} nodos identificados",
                    details={
                        'required_nodes': state['required_nodes'],
                        'detected_systems': state['detected_systems']
                    }
                ))

                # Enviar al Manager para que coordine la recopilación de información
                state['current_agent'] = 'manager'
                state['needs_user_input'] = False

                state['conversation_history'].append({
                    'role': 'assistant',
                    'content': f"Perfecto, tengo la información inicial. Analizando los requerimientos para: {state['clarified_request']}"
                })

                return state

    except (json.JSONDecodeError, AttributeError) as e:
        logger.warning(f"[Conversator] Failed to parse JSON: {e}")

    # Si ya hubo 3+ intentos y aún no hay completion, forzar manualmente
    if user_messages >= 3:
        logger.warning("[Conversator] Forcing completion after 3 user messages - sending to Manager")

        # Crear descripción basada en el historial
        all_user_content = " ".join([msg['content'] for msg in state['conversation_history'] if msg['role'] == 'user'])

        state['clarified_request'] = f"{state['user_request']}. {all_user_content}"
        state['required_nodes'] = ["inject", "function", "debug"]  # Nodos básicos por defecto
        state['detected_systems'] = []

        # Enviar al Manager para que coordine
        state['current_agent'] = 'manager'
        state['needs_user_input'] = False

        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Entiendo. Analizando los requerimientos para crear el flujo."
        })

        return state

    # Continuar conversación
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.INFO,
        agent="Conversator",
        message="Esperando más información del usuario..."
    ))

    state['conversation_history'].append({
        'role': 'assistant',
        'content': response
    })

    state['current_agent'] = 'conversator'
    state['needs_user_input'] = True

    return state
