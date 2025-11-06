"""
Wiring Agent - Planifica las conexiones entre nodos del flujo
Especializado en determinar cómo conectar nodos de forma lógica y eficiente
"""
from loguru import logger
from backend.core.state import AgentState, WiringPlan
from backend.core.llm_manager import LLMManager
import json
import re


WIRING_PROMPT = """Eres un experto en diseño de flujos de Node-RED.

REQUERIMIENTO DEL USUARIO: {clarified_request}

INFORMACIÓN DISPONIBLE:
- Nodos necesarios: {required_nodes}
- Funciones generadas: {functions_count}
- Configuraciones: {configs_count}
- Lógica condicional: {conditionals_count}

Tu tarea es PLANIFICAR LAS CONEXIONES entre nodos.

PRINCIPIOS DE CONEXIÓN EN NODE-RED:
1. Todo flujo empieza con un nodo trigger (inject, http in, mqtt in, etc.)
2. Los datos fluyen de izquierda a derecha
3. Los nodos function procesan/transforman datos
4. Los nodos switch dividen el flujo en múltiples ramas
5. Los nodos de salida (debug, email, http request, etc.) terminan ramas
6. Un nodo puede conectarse a múltiples nodos (outputs)

ESTRUCTURA DE CONEXIÓN:
{{
  "from_node": "inject_1",
  "to_node": "function_1",
  "output_port": 0,
  "description": "Trigger inicial → procesamiento"
}}

EJEMPLOS:

Flujo simple (A → B → C):
inject → function → debug

Flujo con condicional (A → B → C1/C2):
inject → function → switch → [email, slack]

Flujo con múltiples salidas:
inject → http_request → function → [debug, database]

IMPORTANTE:
- output_port empieza en 0
- Si un nodo tiene múltiples outputs (switch, function con return array), especifica el puerto
- Asegura que todos los nodos estén conectados (no nodos huérfanos)

REGLAS DE FORMATO JSON:
- NO incluyas comentarios (//) en el JSON
- NO incluyas texto explicativo dentro del JSON
- Usa SOLO sintaxis JSON válida estricta
- Todas las cadenas deben usar comillas dobles (")
- Asegura que todas las comas estén correctamente colocadas

Responde SOLO con este JSON:
{{
  "connections": [
    {{
      "from_node": "inject_1",
      "from_type": "inject",
      "to_node": "csv_reader",
      "to_type": "csv",
      "output_port": 0,
      "description": "Trigger inicia lectura de CSV"
    }},
    {{
      "from_node": "csv_reader",
      "from_type": "csv",
      "to_node": "function_process",
      "to_type": "function",
      "output_port": 0,
      "description": "CSV → procesamiento de datos"
    }},
    {{
      "from_node": "function_process",
      "from_type": "function",
      "to_node": "email_sender",
      "to_type": "email",
      "output_port": 0,
      "description": "Datos procesados → envío por email"
    }},
    {{
      "from_node": "email_sender",
      "from_type": "email",
      "to_node": "debug_1",
      "to_type": "debug",
      "output_port": 0,
      "description": "Confirmación → debug"
    }}
  ],
  "flow_diagram": "inject → csv → function → email → debug"
}}
"""


async def wiring_agent(state: AgentState) -> AgentState:
    """
    Planifica las conexiones entre nodos del flujo.
    """
    logger.info("[WiringAgent] Planning node connections...")

    llm = LLMManager()

    # Contar elementos disponibles
    functions_count = len(state.get('generated_functions', []))
    configs_count = len(state.get('node_configurations', []))
    conditionals_count = len(state.get('conditional_logic', []))

    prompt = WIRING_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        required_nodes=', '.join(state['required_nodes']) if state['required_nodes'] else 'standard nodes',
        functions_count=functions_count,
        configs_count=configs_count,
        conditionals_count=conditionals_count
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.3,
        max_tokens=2000
    )

    logger.info(f"[WiringAgent] Response: {response[:300]}...")

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
                            if isinstance(parsed, dict) and 'connections' in parsed:
                                data = parsed
                                logger.info(f"[WiringAgent] Found valid JSON")
                                break
                        except json.JSONDecodeError:
                            pass

            if data:
                break

            start_pos = json_start + 1

        if data:

            connections = data.get('connections', [])
            flow_diagram = data.get('flow_diagram', '')

            state['wiring_plan'] = WiringPlan(
                connections=connections,
                description=flow_diagram
            )

            logger.info(f"[WiringAgent] Planned {len(connections)} connections")
            logger.info(f"[WiringAgent] Flow diagram: {flow_diagram}")

        else:
            logger.warning("[WiringAgent] Could not parse response")
            state['wiring_plan'] = WiringPlan(connections=[], description='')

    except json.JSONDecodeError as e:
        logger.error(f"[WiringAgent] JSON error: {e}")
        state['wiring_plan'] = WiringPlan(connections=[], description='')

    return state
