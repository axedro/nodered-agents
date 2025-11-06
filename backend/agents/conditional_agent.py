"""
Conditional Agent - Crea lógica condicional para el flujo
Especializado en switch nodes, if/else, filtrado, y routing condicional
"""
from loguru import logger
from backend.core.state import AgentState, ConditionalLogic
from backend.core.llm_manager import LLMManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType
import json
import re


CONDITIONAL_PROMPT = """Eres un experto en lógica condicional de Node-RED.

REQUERIMIENTO DEL USUARIO: {clarified_request}

NODOS IDENTIFICADOS: {required_nodes}

Tu tarea es identificar si el flujo necesita LÓGICA CONDICIONAL:
- Switch nodes (enrutar mensajes según condiciones)
- Function nodes con if/else
- Filtrado de datos
- Routing basado en propiedades del mensaje

EJEMPLOS DE CUÁNDO SE NECESITA LÓGICA CONDICIONAL:

1. "Enviar a email SI el valor es mayor que 100, sino a Slack"
   → Switch node con reglas: >100 = output 1, else = output 2

2. "Filtrar solo los registros con status = 'active'"
   → Function node con: if (msg.payload.status === 'active') return msg;

3. "Si es fin de semana, no enviar notificación"
   → Function con: if (new Date().getDay() === 0 || new Date().getDay() === 6) return null;

4. "Enrutar según el tipo de error: timeout → retry, otros → log"
   → Switch node con rules por msg.error.type

TIPOS DE NODOS CONDICIONALES:

**Switch Node:**
{{
  "type": "switch",
  "rules": [
    {{"t": "gt", "v": "100", "vt": "num", "output": 0}},
    {{"t": "else", "output": 1}}
  ]
}}

**Function Node con if/else:**
{{
  "type": "function_conditional",
  "code": "if (msg.payload.value > 100) {{\\n  return [msg, null];\\n}} else {{\\n  return [null, msg];\\n}}"
}}

Responde SOLO con este JSON:

Si HAY lógica condicional:
{{
  "conditionals": [
    {{
      "id": "switch_1",
      "type": "switch",
      "rules": [
        {{"property": "payload.value", "operator": "gt", "value": 100, "output": 0}},
        {{"type": "else", "output": 1}}
      ],
      "description": "Enruta según valor: >100 a email, resto a Slack"
    }},
    {{
      "id": "filter_function",
      "type": "function_conditional",
      "rules": [
        {{"condition": "msg.payload.status === 'active'", "action": "return msg"}},
        {{"condition": "else", "action": "return null"}}
      ],
      "description": "Filtra solo registros activos"
    }}
  ]
}}

Si NO hay lógica condicional (flujo lineal simple):
{{
  "conditionals": []
}}
"""


async def conditional_agent(state: AgentState) -> AgentState:
    """
    Identifica y genera lógica condicional necesaria para el flujo.
    """
    logger.info("[ConditionalAgent] Analyzing conditional logic needs...")

    session_id = state.get('session_id')

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="ConditionalAgent",
        message="Analizando lógica condicional (switch, filtros, if/else)..."
    ))

    llm = LLMManager()

    prompt = CONDITIONAL_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        required_nodes=', '.join(state['required_nodes']) if state['required_nodes'] else 'standard nodes'
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.4,
        max_tokens=1500
    )

    logger.info(f"[ConditionalAgent] Response: {response[:300]}...")

    # Extraer JSON
    try:
        json_match = re.search(r'\{[\s\S]*"conditionals"[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())

            conditionals = data.get('conditionals', [])

            # Convertir a formato ConditionalLogic con validación de campos
            valid_conditionals = []
            for cond in conditionals:
                # Validar que existan todos los campos requeridos
                if all(key in cond for key in ['id', 'type', 'rules', 'description']):
                    valid_conditionals.append(
                        ConditionalLogic(
                            id=cond['id'],
                            type=cond['type'],
                            rules=cond['rules'],
                            description=cond['description']
                        )
                    )
                else:
                    logger.warning(f"[ConditionalAgent] Skipping invalid conditional: {cond.get('id', 'unknown')} - missing required fields")

            state['conditional_logic'] = valid_conditionals

            logger.info(f"[ConditionalAgent] Identified {len(valid_conditionals)} conditional logic blocks")

            await progress_manager.send_event(session_id, ProgressEvent(
                type=ProgressEventType.AGENT_COMPLETE,
                agent="ConditionalAgent",
                message=f"Lógica condicional identificada: {len(valid_conditionals)} bloques",
                details={'conditional_count': len(valid_conditionals)}
            ))

            if valid_conditionals:
                for cond in valid_conditionals:
                    logger.info(f"  - {cond['type']}: {cond['description']}")

        else:
            logger.warning("[ConditionalAgent] Could not parse response")
            state['conditional_logic'] = []

            await progress_manager.send_event(session_id, ProgressEvent(
                type=ProgressEventType.INFO,
                agent="ConditionalAgent",
                message="No se encontró lógica condicional en la respuesta"
            ))

    except json.JSONDecodeError as e:
        logger.error(f"[ConditionalAgent] JSON error: {e}")
        state['conditional_logic'] = []

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.ERROR,
            agent="ConditionalAgent",
            message=f"Error al parsear JSON: {str(e)}"
        ))
    except KeyError as e:
        logger.error(f"[ConditionalAgent] KeyError: {e}")
        state['conditional_logic'] = []

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.ERROR,
            agent="ConditionalAgent",
            message=f"Error: falta campo requerido {str(e)}"
        ))

    return state
