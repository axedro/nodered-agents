"""
Function Coder Agent - Genera código JavaScript para nodos function
Crea el código necesario para transformaciones, lógica de negocio, etc.
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
import json
import re
import uuid


FUNCTION_CODER_PROMPT = """Eres un experto en JavaScript y Node-RED.

El usuario necesita este flujo: {clarified_request}

Los nodos requeridos incluyen nodos 'function'. Necesito que generes el código JavaScript para estos nodos.

Información del contexto:
- Sistemas detectados: {detected_systems}
- Nodos disponibles: {installed_nodes}

Genera el código JavaScript necesario. Responde con un JSON en este formato:

{{
  "functions": [
    {{
      "id": "function_1",
      "description": "Descripción de qué hace",
      "code": "// Código JavaScript aquí\\nvar data = msg.payload;\\nreturn msg;"
    }}
  ]
}}

Asegúrate de que el código:
1. Maneje msg.payload correctamente
2. Retorne msg al final
3. Tenga manejo de errores básico
4. Sea conciso pero completo
"""


async def function_coder_agent(state: AgentState) -> AgentState:
    """
    Genera código JavaScript para nodos function si es necesario.
    """
    logger.info("[FunctionCoder] Generating function code...")

    # Verificar si se necesitan nodos function
    needs_function = any('function' in node.lower() for node in state['required_nodes'])

    if not needs_function:
        logger.info("[FunctionCoder] No function nodes needed, skipping...")
        state['current_agent'] = 'json_builder'
        state['needs_user_input'] = False
        return state

    llm = LLMManager()

    prompt = FUNCTION_CODER_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        detected_systems=', '.join(state.get('detected_systems', [])),
        installed_nodes=', '.join(state['installed_nodes'])
    )

    response = await llm.generate(
        prompt=prompt,
        temperature=0.5,
        max_tokens=1500
    )

    logger.info(f"[FunctionCoder] Response: {response[:200]}...")

    # Extraer JSON de la respuesta
    try:
        json_match = re.search(r'\{.*"functions".*\}', response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            functions = data.get('functions', [])

            # Convertir a formato del estado
            state['generated_functions'] = [
                {
                    'id': f.get('id', f'function_{uuid.uuid4().hex[:8]}'),
                    'code': f.get('code', ''),
                    'description': f.get('description', '')
                }
                for f in functions
            ]

            logger.info(f"[FunctionCoder] Generated {len(state['generated_functions'])} functions")

        else:
            logger.warning("[FunctionCoder] Could not parse function code")
            state['generated_functions'] = []

    except json.JSONDecodeError as e:
        logger.error(f"[FunctionCoder] JSON parsing error: {e}")
        state['generated_functions'] = []

    # Siguiente agente: json_builder
    state['current_agent'] = 'json_builder'
    state['needs_user_input'] = False
    state['conversation_history'].append({
        'role': 'assistant',
        'content': f"Generé el código para {len(state['generated_functions'])} nodos function. Construyendo el flujo completo..."
    })

    return state
