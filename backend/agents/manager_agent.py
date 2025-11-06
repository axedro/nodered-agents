"""
Manager Agent - Coordinador principal del sistema multi-agente
Decide qué agentes usar y recopila información antes de volver al Conversator
"""
from loguru import logger
from backend.core.state import AgentState
from backend.core.llm_manager import LLMManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType

# Importar los agentes especializados
from backend.agents.local_searcher import local_searcher_agent
from backend.agents.web_searcher import web_searcher_agent
from backend.agents.installer import installer_agent
from backend.agents.configuration_agent import configuration_agent
from backend.agents.function_coder import function_coder_agent
from backend.agents.conditional_agent import conditional_agent
from backend.agents.wiring_agent import wiring_agent


MANAGER_ANALYSIS_PROMPT = """Eres el Manager del sistema. Tu tarea es ANALIZAR qué información necesitas recopilar.

REQUERIMIENTO CLARIFICADO DEL USUARIO:
{clarified_request}

NODOS REQUERIDOS: {required_nodes}
SISTEMAS DETECTADOS: {detected_systems}

Analiza qué agentes especializados debes ejecutar para recopilar TODA la información necesaria:

1. **LocalSearcher**: Verificar si tenemos los nodos instalados
2. **WebSearcher + Installer**: Si faltan nodos, buscar e instalar
3. **ConfigurationAgent**: Si hay nodos que necesitan configuración (URLs, credenciales, etc.)
4. **FunctionCoder**: Si hay transformaciones de datos, validaciones, o lógica personalizada
5. **ConditionalAgent**: Si hay lógica condicional (if/else, switch, filtros)
6. **WiringAgent**: Siempre necesario para planificar conexiones

Responde con un plan simple:
- Listar qué agentes ejecutar
- En qué orden
- Por qué cada uno

Ejemplo:
"Necesito ejecutar:
1. LocalSearcher - verificar nodos disponibles
2. ConfigurationAgent - el flujo requiere URL de API y credenciales SMTP
3. FunctionCoder - necesito procesar datos CSV
4. ConditionalAgent - NO necesario, flujo lineal
5. WiringAgent - planificar conexiones entre nodos"
"""


async def manager_agent(state: AgentState) -> AgentState:
    """
    Coordinador principal que ejecuta agentes especializados según necesidad.
    """
    logger.info("[Manager] Starting coordination of specialized agents...")

    session_id = state.get('session_id')

    # Enviar evento de inicio
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="Manager",
        message="Iniciando coordinación de agentes especializados..."
    ))

    llm = LLMManager()

    # Análisis inicial: ¿qué agentes necesito?
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.INFO,
        agent="Manager",
        message="Analizando requerimientos y planificando estrategia..."
    ))

    analysis_prompt = MANAGER_ANALYSIS_PROMPT.format(
        clarified_request=state.get('clarified_request', state['user_request']),
        required_nodes=', '.join(state['required_nodes']) if state['required_nodes'] else 'TBD',
        detected_systems=', '.join(state.get('detected_systems', []))
    )

    analysis = await llm.generate(
        prompt=analysis_prompt,
        temperature=0.3,
        max_tokens=1000
    )

    logger.info(f"[Manager] Analysis:\n{analysis}")

    state['manager_analysis'] = analysis

    # Inicializar listas si no existen
    if 'missing_information' not in state:
        state['missing_information'] = []

    # FASE 1: LocalSearcher - Verificar nodos disponibles
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_START,
        agent="Manager",
        message="FASE 1/6: Verificando nodos de Node-RED disponibles..."
    ))

    logger.info("[Manager] PHASE 1: Running LocalSearcher...")
    state = await local_searcher_agent(state)

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_COMPLETE,
        agent="Manager",
        message=f"Fase 1 completada: {len(state.get('installed_nodes', []))} nodos encontrados, {len(state.get('missing_nodes', []))} faltantes",
        details={
            'installed_count': len(state.get('installed_nodes', [])),
            'missing_count': len(state.get('missing_nodes', []))
        }
    ))

    # FASE 2: WebSearcher + Installer si hay nodos faltantes
    if state.get('missing_nodes') and len(state['missing_nodes']) > 0:
        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.PHASE_START,
            agent="Manager",
            message=f"FASE 2/6: Instalando {len(state['missing_nodes'])} paquetes faltantes..."
        ))

        logger.info("[Manager] PHASE 2: Running WebSearcher + Installer...")
        state = await web_searcher_agent(state)
        state = await installer_agent(state)

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.PHASE_COMPLETE,
            agent="Manager",
            message="Fase 2 completada: Paquetes instalados correctamente",
            details={'installed_packages': state.get('suggested_installations', [])}
        ))
    else:
        logger.info("[Manager] PHASE 2: Skipped (all nodes available)")
        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.INFO,
            agent="Manager",
            message="Fase 2 omitida: Todos los nodos ya están disponibles"
        ))

    # FASE 3: ConfigurationAgent - Configuraciones necesarias
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_START,
        agent="Manager",
        message="FASE 3/6: Analizando configuraciones de nodos (URLs, credenciales, etc.)..."
    ))

    logger.info("[Manager] PHASE 3: Running ConfigurationAgent...")
    state = await configuration_agent(state)

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_COMPLETE,
        agent="Manager",
        message=f"Fase 3 completada: {len(state.get('node_configurations', []))} configuraciones identificadas",
        details={'config_count': len(state.get('node_configurations', []))}
    ))

    # FASE 4: FunctionCoder - Generar código si es necesario
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_START,
        agent="Manager",
        message="FASE 4/6: Generando código JavaScript para nodos de función..."
    ))

    logger.info("[Manager] PHASE 4: Running FunctionCoder...")
    state = await function_coder_agent(state)

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_COMPLETE,
        agent="Manager",
        message=f"Fase 4 completada: {len(state.get('generated_functions', []))} funciones generadas",
        details={'function_count': len(state.get('generated_functions', []))}
    ))

    # FASE 5: ConditionalAgent - Lógica condicional
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_START,
        agent="Manager",
        message="FASE 5/6: Identificando lógica condicional (switch, filtros, if/else)..."
    ))

    logger.info("[Manager] PHASE 5: Running ConditionalAgent...")
    state = await conditional_agent(state)

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_COMPLETE,
        agent="Manager",
        message=f"Fase 5 completada: {len(state.get('conditional_logic', []))} bloques condicionales identificados",
        details={'conditional_count': len(state.get('conditional_logic', []))}
    ))

    # FASE 6: WiringAgent - Planificar conexiones
    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_START,
        agent="Manager",
        message="FASE 6/6: Planificando conexiones entre nodos..."
    ))

    logger.info("[Manager] PHASE 6: Running WiringAgent...")
    state = await wiring_agent(state)

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.PHASE_COMPLETE,
        agent="Manager",
        message=f"Fase 6 completada: {len(state.get('wiring_plan', {}).get('connections', []))} conexiones planificadas",
        details={'connection_count': len(state.get('wiring_plan', {}).get('connections', []))}
    ))

    # Resumen de lo recopilado
    summary = f"""
[Manager] ===== RECOPILACIÓN COMPLETADA =====

Nodos verificados: {len(state.get('installed_nodes', []))} disponibles
Nodos faltantes: {len(state.get('missing_nodes', []))}

Configuraciones identificadas: {len(state.get('node_configurations', []))}
Funciones generadas: {len(state.get('generated_functions', []))}
Lógica condicional: {len(state.get('conditional_logic', []))}
Conexiones planificadas: {len(state.get('wiring_plan', {}).get('connections', []))}

Información faltante del usuario: {state.get('missing_information', [])}
"""

    logger.info(summary)

    # Decidir siguiente paso
    if state.get('missing_information') and len(state['missing_information']) > 0:
        # Hay información faltante, volver al Conversator
        logger.info("[Manager] Missing information detected, returning to Conversator")

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.AGENT_COMPLETE,
            agent="Manager",
            message="Recopilación completada - Se necesita información adicional del usuario",
            details={'missing_info': state['missing_information']}
        ))

        state['current_agent'] = 'conversator'
        state['needs_user_input'] = True

        # Preparar mensaje para el usuario
        missing_info_msg = "He recopilado la información pero necesito algunos detalles adicionales:\n"
        for i, info in enumerate(state['missing_information'], 1):
            missing_info_msg += f"{i}. {info}\n"

        state['conversation_history'].append({
            'role': 'assistant',
            'content': missing_info_msg
        })

    else:
        # Tenemos toda la información, proceder a JsonBuilder
        logger.info("[Manager] All information collected, proceeding to JsonBuilder")

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.AGENT_COMPLETE,
            agent="Manager",
            message="Recopilación completada - Procediendo a generar el flujo de Node-RED",
            details={
                'installed_nodes': len(state.get('installed_nodes', [])),
                'functions': len(state.get('generated_functions', [])),
                'configurations': len(state.get('node_configurations', [])),
                'conditionals': len(state.get('conditional_logic', [])),
                'connections': len(state.get('wiring_plan', {}).get('connections', []))
            }
        ))

        state['current_agent'] = 'json_builder'
        state['needs_user_input'] = False

        state['conversation_history'].append({
            'role': 'assistant',
            'content': "He recopilado toda la información necesaria. Generando el flujo de Node-RED..."
        })

    return state
