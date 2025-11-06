"""
Cache Searcher Agent - Busca soluciones previas en el RAG
Primer agente del workflow: Si encuentra una solución >95% similar, termina el trabajo
"""
from loguru import logger
from backend.core.state import AgentState
from backend.rag.vector_store import VectorStoreManager
from backend.config import settings
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType


async def cache_searcher_agent(state: AgentState) -> AgentState:
    """
    Busca en el RAG de soluciones aprobadas si existe una solicitud similar.
    Si encuentra una con >95% similitud, la usa directamente.
    """
    logger.info(f"[CacheSearcher] Searching for similar flows: {state['user_request'][:50]}...")

    session_id = state.get('session_id')

    await progress_manager.send_event(session_id, ProgressEvent(
        type=ProgressEventType.AGENT_START,
        agent="CacheSearcher",
        message="Buscando soluciones similares en la base de conocimiento..."
    ))

    vector_store = VectorStoreManager()

    # Buscar flujos similares con score mínimo
    similar_flows = vector_store.search_similar_flows(
        user_request=state['user_request'],
        n_results=1,
        min_score=settings.min_feedback_score
    )

    if similar_flows and similar_flows[0]['similarity'] >= settings.similarity_threshold:
        # ¡Cache hit! Usamos la solución existente
        best_match = similar_flows[0]
        logger.info(f"[CacheSearcher] Cache HIT! Similarity: {best_match['similarity']:.2%}")

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.AGENT_COMPLETE,
            agent="CacheSearcher",
            message=f"✓ Solución encontrada en caché (similitud: {best_match['similarity']:.2%})",
            details={'similarity': best_match['similarity']}
        ))

        # Incrementar contador de uso
        vector_store.increment_flow_usage(best_match['id'])

        state['cached_solution'] = best_match['flow_json']
        state['final_json_flow'] = best_match['flow_json']
        state['current_agent'] = 'validator'
        state['is_complete'] = False
        state['needs_user_input'] = False

        state['conversation_history'].append({
            'role': 'assistant',
            'content': f"Encontré una solución similar previamente aprobada (similitud: {best_match['similarity']:.2%}). Validando..."
        })

    else:
        # Cache miss, continuar con el flujo normal
        logger.info("[CacheSearcher] Cache MISS. Proceeding with conversation.")

        await progress_manager.send_event(session_id, ProgressEvent(
            type=ProgressEventType.AGENT_COMPLETE,
            agent="CacheSearcher",
            message="No se encontró una solución similar en caché - iniciando generación personalizada"
        ))

        state['cached_solution'] = None
        state['current_agent'] = 'conversator'
        state['needs_user_input'] = False  # Dejar que conversator decida

    return state
