"""
Validator Agent - Valida el JSON del flujo generado
Último agente: verifica que el JSON sea válido y completo
"""
from loguru import logger
from backend.core.state import AgentState
import json


async def validator_agent(state: AgentState) -> AgentState:
    """
    Valida el JSON del flujo:
    1. Sintaxis JSON correcta
    2. Estructura de Node-RED válida
    3. Referencias de wires correctas
    """
    logger.info("[Validator] Validating flow JSON...")

    flow_json = state.get('final_json_flow')

    if not flow_json:
        state['error_message'] = "No flow JSON to validate"
        state['is_complete'] = False
        state['current_agent'] = 'json_builder'
        return state

    try:
        # 1. Validar sintaxis JSON
        flow_data = json.loads(flow_json)

        if not isinstance(flow_data, list):
            raise ValueError("Flow must be a JSON array")

        # 2. Validar estructura básica
        node_ids = set()
        errors = []

        for i, node in enumerate(flow_data):
            # Verificar campos requeridos
            if 'id' not in node:
                errors.append(f"Node {i} missing 'id' field")
            else:
                if node['id'] in node_ids:
                    errors.append(f"Duplicate node ID: {node['id']}")
                node_ids.add(node['id'])

            if 'type' not in node:
                errors.append(f"Node {i} missing 'type' field")

            # wires es opcional pero si existe debe ser array
            if 'wires' in node and not isinstance(node['wires'], list):
                errors.append(f"Node {node.get('id', i)} has invalid 'wires' field")

        # 3. Validar referencias de wires
        for node in flow_data:
            if 'wires' in node:
                for wire_group in node['wires']:
                    if isinstance(wire_group, list):
                        for target_id in wire_group:
                            if target_id not in node_ids:
                                errors.append(f"Node {node['id']} wires to non-existent node: {target_id}")

        if errors:
            logger.error(f"[Validator] Validation failed: {len(errors)} errors")
            logger.error(f"[Validator] Errors: {errors}")

            state['error_message'] = f"Validation errors: {'; '.join(errors[:3])}"
            state['is_complete'] = False
            state['retry_count'] = state.get('retry_count', 0) + 1

            if state['retry_count'] < 3:
                # Reintentar con json_builder
                state['current_agent'] = 'json_builder'
                state['conversation_history'].append({
                    'role': 'assistant',
                    'content': f"El flujo tiene errores de validación. Reintentando... (intento {state['retry_count']})"
                })
            else:
                # Demasiados intentos, marcar como completo pero con error
                state['is_complete'] = True
                state['needs_user_input'] = True
                state['conversation_history'].append({
                    'role': 'assistant',
                    'content': f"No pude generar un flujo válido después de {state['retry_count']} intentos. Por favor revisa y corrige manualmente."
                })

        else:
            # ¡Validación exitosa!
            logger.info("[Validator] ✓ Flow JSON is VALID!")

            state['error_message'] = None
            state['is_complete'] = True
            state['needs_user_input'] = True  # Esperar feedback del usuario

            # Formatear JSON bonito
            state['final_json_flow'] = json.dumps(flow_data, indent=2)

            state['conversation_history'].append({
                'role': 'assistant',
                'content': "✓ Flujo generado y validado exitosamente! Aquí está tu JSON de Node-RED. Por favor pruébalo y dame feedback."
            })

    except json.JSONDecodeError as e:
        logger.error(f"[Validator] Invalid JSON: {e}")
        state['error_message'] = f"Invalid JSON syntax: {str(e)}"
        state['is_complete'] = False
        state['retry_count'] = state.get('retry_count', 0) + 1

        if state['retry_count'] < 3:
            state['current_agent'] = 'json_builder'
            state['conversation_history'].append({
                'role': 'assistant',
                'content': f"El JSON generado tiene errores de sintaxis. Reintentando..."
            })
        else:
            state['is_complete'] = True
            state['needs_user_input'] = True

    except Exception as e:
        logger.error(f"[Validator] Unexpected error: {e}")
        state['error_message'] = str(e)
        state['is_complete'] = True
        state['needs_user_input'] = True

    return state
