"""
Local Searcher Agent - Busca nodos instalados localmente en el RAG
Determina qué nodos están disponibles y cuáles faltan
"""
from loguru import logger
from backend.core.state import AgentState
from backend.rag.vector_store import VectorStoreManager


async def local_searcher_agent(state: AgentState) -> AgentState:
    """
    Busca los nodos requeridos en el catálogo local de nodos instalados.
    Separa entre installed_nodes y missing_nodes.
    """
    logger.info(f"[LocalSearcher] Searching for {len(state['required_nodes'])} nodes...")

    vector_store = VectorStoreManager()

    installed = []
    missing = []

    for node_type in state['required_nodes']:
        # Buscar el nodo en el RAG de nodos instalados
        results = vector_store.search_installed_nodes(
            query=node_type,
            n_results=1
        )

        if results and results[0]['node_type'].lower() in node_type.lower():
            # Nodo encontrado
            installed.append(results[0]['node_type'])
            logger.info(f"[LocalSearcher] Found: {results[0]['node_type']}")
        else:
            # Nodo no encontrado
            missing.append(node_type)
            logger.warning(f"[LocalSearcher] Missing: {node_type}")

    state['installed_nodes'] = installed
    state['missing_nodes'] = missing

    if missing:
        # Hay nodos faltantes, ir al web searcher
        logger.info(f"[LocalSearcher] Found {len(missing)} missing nodes. Going to WebSearcher.")
        state['current_agent'] = 'web_searcher'
        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Encontré que faltan estos nodos: {', '.join(missing)}. Buscando en la web..."
        })
    else:
        # Todos los nodos están instalados
        logger.info("[LocalSearcher] All nodes are installed. Proceeding to code generation.")
        state['current_agent'] = 'function_coder'
        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Todos los nodos necesarios están instalados. Generando el flujo..."
        })

    state['needs_user_input'] = False
    return state
