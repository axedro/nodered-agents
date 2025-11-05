"""
JSON Builder Agent - Ensambla el flujo completo de Node-RED
El agente más importante: construye el JSON final del flujo
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
import json
import re


JSON_BUILDER_PROMPT = """Eres un experto en crear flujos de Node-RED en formato JSON.

REQUERIMIENTO DEL USUARIO: {clarified_request}

INFORMACIÓN DISPONIBLE:
- Sistemas detectados: {detected_systems}
- Nodos instalados: {installed_nodes}
- Funciones generadas: {functions_summary}

INSTRUCCIONES:
Genera un flujo válido de Node-RED en formato JSON que cumpla con el requerimiento.

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

    llm = LLMManager()

    # Preparar resumen de funciones
    functions_summary = ""
    if state['generated_functions']:
        functions_summary = "\n".join([
            f"- {f['id']}: {f['description']}"
            for f in state['generated_functions']
        ])
    else:
        functions_summary = "No function nodes needed"

    prompt = JSON_BUILDER_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        detected_systems=', '.join(state.get('detected_systems', ['ninguno'])),
        installed_nodes=', '.join(state['installed_nodes']) if state['installed_nodes'] else 'standard nodes',
        functions_summary=functions_summary
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

    # Siguiente agente: validator
    state['current_agent'] = 'validator'
    state['needs_user_input'] = False

    logger.info("[JsonBuilder] Flow JSON built successfully")

    return state
