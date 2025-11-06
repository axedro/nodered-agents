"""
LangGraph Workflow - Orquesta todos los agentes
Define el flujo de control entre agentes
"""
from langgraph.graph import StateGraph, END
from loguru import logger

from backend.core.state import AgentState
from backend.agents import (
    cache_searcher_agent,
    conversator_agent,
    manager_agent,
    configuration_agent,
    conditional_agent,
    wiring_agent,
    local_searcher_agent,
    web_searcher_agent,
    installer_agent,
    function_coder_agent,
    json_builder_agent,
    validator_agent
)


def route_next_agent(state: AgentState) -> str:
    """
    Función de routing que decide qué agente ejecutar a continuación
    basándose en el estado actual.
    """
    current = state.get('current_agent', 'cache_searcher')

    logger.info(f"[Router] Current agent: {current}, Complete: {state.get('is_complete')}, Needs input: {state.get('needs_user_input')}")

    # Si el workflow está completo, terminar
    if state.get('is_complete'):
        return END

    # Si necesita input del usuario, terminar para esperar respuesta
    if state.get('needs_user_input'):
        logger.info("[Router] Waiting for user input - ending workflow")
        return END

    # Routing basado en current_agent
    agent_map = {
        'cache_searcher': 'cache_searcher',
        'conversator': 'conversator',
        'manager': 'manager',
        'configuration': 'configuration',
        'conditional': 'conditional',
        'wiring': 'wiring',
        'local_searcher': 'local_searcher',
        'web_searcher': 'web_searcher',
        'installer': 'installer',
        'function_coder': 'function_coder',
        'json_builder': 'json_builder',
        'validator': 'validator'
    }

    next_agent = agent_map.get(current, END)

    logger.info(f"[Router] Routing to: {next_agent}")

    return next_agent


def create_workflow_graph() -> StateGraph:
    """
    Crea y configura el grafo de workflow con todos los agentes.

    NUEVA ARQUITECTURA CON MANAGER:
    1. cache_searcher -> (si hit) validator -> END
                      -> (si miss) conversator
    2. conversator -> (cuando complete) manager
    3. manager -> coordina:
                  - local_searcher (verifica nodos)
                  - web_searcher + installer (si faltan nodos)
                  - configuration_agent (recopila configs)
                  - function_coder (genera código)
                  - conditional_agent (genera lógica condicional)
                  - wiring_agent (planifica conexiones)
    4. manager -> (si falta info) conversator -> usuario
               -> (si completo) json_builder
    5. json_builder -> validator
    6. validator -> (si valid) END
                 -> (si error) json_builder (retry)

    El Manager ejecuta los agentes internamente y decide si necesita más input del usuario.
    """
    logger.info("Creating LangGraph workflow with Manager architecture...")

    # Crear el grafo con el estado tipado
    workflow = StateGraph(AgentState)

    # Agregar solo agentes principales del flujo
    # El Manager ejecuta internamente: local_searcher, web_searcher, installer,
    # function_coder, configuration_agent, conditional_agent, wiring_agent
    workflow.add_node("cache_searcher", cache_searcher_agent)
    workflow.add_node("conversator", conversator_agent)
    workflow.add_node("manager", manager_agent)
    workflow.add_node("json_builder", json_builder_agent)
    workflow.add_node("validator", validator_agent)

    # Definir el punto de entrada
    workflow.set_entry_point("cache_searcher")

    # Agregar edges condicionales desde cada agente
    workflow.add_conditional_edges(
        "cache_searcher",
        route_next_agent,
        {
            "cache_searcher": "cache_searcher",
            "conversator": "conversator",
            "validator": "validator",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "conversator",
        route_next_agent,
        {
            "conversator": "conversator",
            "manager": "manager",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "manager",
        route_next_agent,
        {
            "conversator": "conversator",
            "json_builder": "json_builder",
            END: END
        }
    )


    workflow.add_conditional_edges(
        "json_builder",
        route_next_agent,
        {
            "validator": "validator",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "validator",
        route_next_agent,
        {
            "json_builder": "json_builder",
            "validator": "validator",
            END: END
        }
    )

    logger.info("Workflow graph created successfully")

    return workflow.compile()
