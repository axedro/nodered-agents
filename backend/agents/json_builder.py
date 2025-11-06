"""
JSON Builder Agent - Ensambla el flujo completo de Node-RED
El agente más importante: construye el JSON final del flujo
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType
import json
import re


JSON_BUILDER_PROMPT = """Eres un experto en crear flujos de Node-RED en formato JSON.

REQUERIMIENTO DEL USUARIO: {clarified_request}

INFORMACIÓN RECOPILADA POR EL MANAGER:
- Sistemas detectados: {detected_systems}
- Nodos instalados: {installed_nodes}
- Funciones generadas: {functions_summary}
- Configuraciones de nodos: {configurations_summary}
- Lógica condicional: {conditionals_summary}
- Plan de conexiones: {wiring_summary}

INSTRUCCIONES:
Genera un flujo válido de Node-RED en formato JSON que cumpla con el requerimiento.
Usa TODA la información proporcionada arriba para construir un flujo completo y funcional.

Estructura de un flujo de Node-RED:
[
  {{
    "id": "unique-id-1",
    "type": "inject",
    "name": "Start",
    "topic": "",
    "payload": "",
    "payloadType": "date",
    "repeat": "",
    "crontab": "",
    "once": false,
    "x": 100,
    "y": 100,
    "wires": [["unique-id-2"]]
  }},
  {{
    "id": "unique-id-2",
    "type": "function",
    "name": "Process Data",
    "func": "// código aquí\\nreturn msg;",
    "outputs": 1,
    "x": 300,
    "y": 100,
    "wires": [["unique-id-3"]]
  }},
  {{
    "id": "unique-id-3",
    "type": "debug",
    "name": "Output",
    "x": 500,
    "y": 100,
    "wires": []
  }}
]

REGLAS IMPORTANTES:
1. Cada nodo debe tener un 'id' único
2. El campo 'wires' conecta nodos (array de arrays de IDs)
3. Usa coordenadas x,y para posicionar nodos (incrementa x de 200 en 200)
4. Incluye nodos inject al inicio y debug al final
5. Usa los nodos instalados: {installed_nodes}
6. Si hay funciones generadas, úsalas en nodos function

RESPONDE SOLO CON EL JSON DEL FLUJO, nada más.
"""


async def json_builder_agent(state: AgentState) -> AgentState:
    """
    Construye el JSON completo del flujo de Node-RED.
    """
    logger.info("[JsonBuilder] Building complete Node-RED flow...")

    session_id = state.get('session_id')

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="JsonBuilder",
        message="Ensamblando flujo completo de Node-RED en formato JSON..."
    ))

    llm = LLMManager()

    # Preparar resumen de funciones
    functions_summary = ""
    if state.get('generated_functions'):
        functions_summary = "\n".join([
            f"- {f['id']}: {f['description']}\n  Código: {f['code'][:100]}..."
            for f in state['generated_functions']
        ])
    else:
        functions_summary = "No function nodes needed"

    # Preparar resumen de configuraciones
    configurations_summary = ""
    if state.get('node_configurations'):
        configurations_summary = "\n".join([
            f"- {cfg['node_type']} ({cfg['node_id']}): {cfg['description']}\n  Props: {cfg['properties']}"
            for cfg in state['node_configurations']
        ])
    else:
        configurations_summary = "No special configurations needed"

    # Preparar resumen de lógica condicional
    conditionals_summary = ""
    if state.get('conditional_logic'):
        conditionals_summary = "\n".join([
            f"- {cond['type']} ({cond['id']}): {cond['description']}"
            for cond in state['conditional_logic']
        ])
    else:
        conditionals_summary = "No conditional logic needed (linear flow)"

    # Preparar resumen del plan de wiring
    wiring_summary = ""
    if state.get('wiring_plan'):
        wiring_plan = state['wiring_plan']
        wiring_summary = wiring_plan.get('description', 'Flow connections planned')
        if wiring_plan.get('connections'):
            wiring_summary += "\n" + "\n".join([
                f"- {conn['from_node']} → {conn['to_node']}: {conn.get('description', '')}"
                for conn in wiring_plan['connections'][:5]  # Primeras 5
            ])
    else:
        wiring_summary = "Standard linear flow"

    prompt = JSON_BUILDER_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        detected_systems=', '.join(state.get('detected_systems', ['ninguno'])),
        installed_nodes=', '.join(state.get('installed_nodes', [])) if state.get('installed_nodes') else 'standard nodes',
        functions_summary=functions_summary,
        configurations_summary=configurations_summary,
        conditionals_summary=conditionals_summary,
        wiring_summary=wiring_summary
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.3,
        max_tokens=3000
    )

    logger.info(f"[JsonBuilder] Generated flow JSON: {len(response)} chars")

    # Extraer JSON (puede venir con backticks o texto adicional)
    json_text = response.strip()

    # Eliminar markdown code blocks si existen
    json_text = re.sub(r'^```json\s*', '', json_text)
    json_text = re.sub(r'^```\s*', '', json_text)
    json_text = re.sub(r'\s*```$', '', json_text)

    # Buscar el array JSON principal
    json_match = re.search(r'\[[\s\S]*\]', json_text)
    if json_match:
        json_text = json_match.group()

    state['final_json_flow'] = json_text

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_COMPLETE,
        agent="JsonBuilder",
        message=f"Flujo JSON generado exitosamente ({len(json_text)} caracteres)",
        details={'json_length': len(json_text)}
    ))

    # Siguiente agente: validator
    state['current_agent'] = 'validator'
    state['needs_user_input'] = False

    logger.info("[JsonBuilder] Flow JSON built successfully")

    return state
