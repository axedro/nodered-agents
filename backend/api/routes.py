"""
FastAPI Routes - API endpoints for the multi-agent system
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from loguru import logger
from typing import Dict, Any
import uuid

from backend.models.schemas import (
    ConversationRequest,
    ConversationResponse,
    FlowFeedback
)
from backend.core.state import AgentState
from backend.core.graph import create_workflow_graph
from backend.rag.vector_store import VectorStoreManager

router = APIRouter()

# In-memory session storage (para MVP)
# En producción, usar Redis o base de datos
sessions: Dict[str, AgentState] = {}

# Workflow graph (singleton)
workflow_graph = None


def get_workflow():
    """Get or create workflow graph"""
    global workflow_graph
    if workflow_graph is None:
        workflow_graph = create_workflow_graph()
    return workflow_graph


@router.post("/chat", response_model=ConversationResponse)
async def chat(request: ConversationRequest):
    """
    Main chat endpoint - handles conversation with the multi-agent system
    """
    try:
        # Obtener o crear sesión
        session_id = request.session_id or str(uuid.uuid4())

        if session_id not in sessions:
            # Nueva sesión
            logger.info(f"Creating new session: {session_id}")
            sessions[session_id] = {
                'session_id': session_id,
                'user_id': request.user_id,
                'user_request': request.message,
                'conversation_history': [],
                'clarified_request': None,
                'required_nodes': [],
                'installed_nodes': [],
                'missing_nodes': [],
                'suggested_installations': [],
                'generated_functions': [],
                'final_json_flow': None,
                'error_message': None,
                'retry_count': 0,
                'current_agent': 'cache_searcher',
                'needs_user_input': False,
                'is_complete': False,
                'feedback_score': None,
                'cached_solution': None,
                'flow_description': '',
                'detected_systems': []
            }
        else:
            # Sesión existente - agregar mensaje del usuario
            logger.info(f"Continuing session: {session_id}")
            sessions[session_id]['conversation_history'].append({
                'role': 'user',
                'content': request.message
            })

        state = sessions[session_id]

        # Ejecutar el workflow
        workflow = get_workflow()
        result = await workflow.ainvoke(state)

        # Actualizar sesión
        sessions[session_id] = result

        # Obtener el último mensaje del asistente
        last_message = ""
        if result['conversation_history']:
            for msg in reversed(result['conversation_history']):
                if msg['role'] == 'assistant':
                    last_message = msg['content']
                    break

        # Preparar respuesta
        response = ConversationResponse(
            session_id=session_id,
            message=last_message,
            requires_input=result['needs_user_input'],
            flow_ready=result['is_complete'],
            flow_json=result['final_json_flow'] if result['is_complete'] else None,
            metadata={
                'current_agent': result['current_agent'],
                'error': result.get('error_message'),
                'detected_systems': result.get('detected_systems', []),
                'required_nodes': result.get('required_nodes', [])
            }
        )

        return response

    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(feedback: FlowFeedback):
    """
    Submit feedback on a generated flow for reinforcement learning
    """
    try:
        logger.info(f"Receiving feedback for session: {feedback.session_id}")

        if feedback.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")

        session = sessions[feedback.session_id]
        vector_store = VectorStoreManager()

        # Guardar feedback en RAG 3
        vector_store.add_feedback(
            session_id=feedback.session_id,
            user_request=session['user_request'],
            flow_json=feedback.flow_json,
            feedback_type=feedback.feedback_type,
            score=feedback.score,
            comments=feedback.comments,
            modifications=feedback.modifications_needed
        )

        # Si es aprobado y tiene buen score, agregarlo a soluciones aprobadas
        if feedback.feedback_type == 'approve' and feedback.score >= 4:
            vector_store.add_approved_flow(
                user_request=session['user_request'],
                flow_json=feedback.flow_json,
                score=feedback.score,
                metadata={
                    'clarified_request': session.get('clarified_request'),
                    'detected_systems': session.get('detected_systems', [])
                }
            )
            logger.info(f"Flow approved and added to solutions database")

        # Si necesita modificaciones, reiniciar el workflow
        if feedback.feedback_type == 'modify' and feedback.modifications_needed:
            session['conversation_history'].append({
                'role': 'user',
                'content': f"El flujo necesita estas modificaciones: {feedback.modifications_needed}"
            })
            session['is_complete'] = False
            session['current_agent'] = 'conversator'
            session['needs_user_input'] = False

        return {
            "status": "success",
            "message": "Feedback received and processed",
            "continue_conversation": feedback.feedback_type == 'modify'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """
    Get session information
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return {
        "session_id": session_id,
        "is_complete": session['is_complete'],
        "conversation_history": session['conversation_history'],
        "flow_ready": session['is_complete'],
        "current_agent": session['current_agent']
    }


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a session
    """
    if session_id in sessions:
        del sessions[session_id]
        return {"status": "success", "message": "Session deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/stats")
async def get_stats():
    """
    Get system statistics
    """
    vector_store = VectorStoreManager()

    return {
        "active_sessions": len(sessions),
        "installed_nodes_count": vector_store.get_collection_count("installed_nodes"),
        "approved_flows_count": vector_store.get_collection_count("approved_flows"),
        "feedback_stats": vector_store.get_feedback_stats()
    }


@router.post("/init-nodes")
async def initialize_sample_nodes():
    """
    Initialize some sample Node-RED nodes for testing
    """
    vector_store = VectorStoreManager()

    sample_nodes = [
        {
            "node_type": "inject",
            "package_name": "node-red",
            "description": "Inject node - triggers flows manually or on schedule"
        },
        {
            "node_type": "debug",
            "package_name": "node-red",
            "description": "Debug node - displays message in debug sidebar"
        },
        {
            "node_type": "function",
            "package_name": "node-red",
            "description": "Function node - write custom JavaScript code"
        },
        {
            "node_type": "http request",
            "package_name": "node-red",
            "description": "HTTP request node - make HTTP/HTTPS requests"
        },
        {
            "node_type": "http in",
            "package_name": "node-red",
            "description": "HTTP in node - create HTTP endpoints"
        },
        {
            "node_type": "http response",
            "package_name": "node-red",
            "description": "HTTP response node - send HTTP responses"
        },
        {
            "node_type": "template",
            "package_name": "node-red",
            "description": "Template node - create text based on Mustache template"
        },
        {
            "node_type": "change",
            "package_name": "node-red",
            "description": "Change node - modify message properties"
        },
        {
            "node_type": "switch",
            "package_name": "node-red",
            "description": "Switch node - route messages based on property values"
        }
    ]

    for node in sample_nodes:
        vector_store.add_installed_node(**node)

    return {
        "status": "success",
        "message": f"Initialized {len(sample_nodes)} sample nodes"
    }
