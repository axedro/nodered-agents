"""
FastAPI Routes - API endpoints for the multi-agent system
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from typing import Dict, Any
import uuid
import json
import asyncio

from backend.models.schemas import (
    ConversationRequest,
    ConversationResponse,
    FlowFeedback
)
from backend.core.state import AgentState
from backend.core.graph import create_workflow_graph
from backend.rag.vector_store import VectorStoreManager
from backend.core.progress import progress_manager, ProgressEvent, ProgressEventType

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


async def run_workflow_background(session_id: str, state: AgentState):
    """Execute workflow in background and update session"""
    try:
        workflow = get_workflow()
        result = await workflow.ainvoke(state)
        sessions[session_id] = result
        logger.info(f"[Background] Workflow completed for session: {session_id}")

        # Si el workflow necesita input del usuario, enviar el último mensaje del asistente
        if result.get('needs_user_input') and result.get('conversation_history'):
            last_assistant_message = ""
            for msg in reversed(result['conversation_history']):
                if msg['role'] == 'assistant':
                    last_assistant_message = msg['content']
                    break

            if last_assistant_message:
                await progress_manager.send_event(session_id, ProgressEvent(
                    type=ProgressEventType.INFO,
                    agent="System",
                    message=f"💬 {last_assistant_message}"
                ))

    except Exception as e:
        logger.error(f"[Background] Workflow error for session {session_id}: {e}")
        if session_id in sessions:
            sessions[session_id]['error_message'] = str(e)
            sessions[session_id]['is_complete'] = True

            await progress_manager.send_event(session_id, ProgressEvent(
                type=ProgressEventType.ERROR,
                agent="System",
                message=f"Error: {str(e)}"
            ))


@router.post("/chat", response_model=ConversationResponse)
async def chat(request: ConversationRequest, background_tasks: BackgroundTasks):
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
                'node_configurations': [],
                'conditional_logic': [],
                'wiring_plan': None,
                'manager_analysis': None,
                'missing_information': [],
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

        # Ejecutar el workflow en background usando asyncio.create_task
        asyncio.create_task(run_workflow_background(session_id, state))

        # Retornar inmediatamente para que el frontend pueda conectarse al stream
        # El workflow continuará ejecutándose en background

        # Preparar respuesta inicial
        response = ConversationResponse(
            session_id=session_id,
            message="Procesando tu solicitud... Conéctate al stream para ver el progreso en tiempo real.",
            requires_input=False,
            flow_ready=False,
            flow_json=None,
            metadata={
                'current_agent': 'cache_searcher',
                'error': None,
                'detected_systems': [],
                'required_nodes': []
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
        "flow_json": session.get('final_json_flow'),
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


@router.post("/init-documentation")
async def initialize_documentation():
    """
    Initialize Node-RED best practices and configuration requirements documentation
    """
    vector_store = VectorStoreManager()

    documentation_entries = [
        # Flow Design Best Practices
        {
            "title": "Flow Organization and Structure",
            "category": "best_practices",
            "content": """Best practices for organizing Node-RED flows:
- Separate flows across multiple tabs by logical components
- Use groups to visually organize related nodes
- Keep groups compact for readability
- Flows should start at top and work down to bottom
- Avoid crossing wires - it reduces readability
- Use Link nodes and Subflows for reusable components
- Position Catch nodes close to the parts they correspond to
- Use flow-scoped context instead of global when possible"""
        },
        {
            "title": "Message Design Patterns",
            "category": "best_practices",
            "content": """Common Node-RED design patterns:
- Sequence Pattern: Add properties to msg object for use in later stages
- Aggregator Pattern: Combine multiple async operations (e.g., multiple API responses)
- Separator Pattern: Split output into multiple messages
- Store & Search Pattern: Storage and retrieval of data from data sources
- Send results to MQTT/Kafka quickly - avoid long multi-step flows
- Keep flows short and decoupled from each other"""
        },

        # Node Configuration Requirements
        {
            "title": "Email Node Configuration Requirements",
            "category": "node_config",
            "content": """Required configuration for email nodes:
SENDING EMAIL (SMTP):
- SMTP server address (e.g., smtp.gmail.com)
- SMTP port: 465 (SSL) or 587 (TLS)
- Use secure connection: Enable for port 465, disable for 587
- Email credentials (username/password or OAuth2 for Gmail/Outlook)
- From address
- To address(es)

RECEIVING EMAIL (IMAP/POP3):
- IMAP/POP3 server address (e.g., imap.gmail.com)
- Port: 993 (IMAP SSL) or 995 (POP3 SSL)
- Email credentials
- Folder to monitor (default: INBOX)
- Poll frequency

SPECIAL NOTES:
- Gmail requires app password if 2FA enabled
- Outlook 365 requires OAuth2.0
- Dependencies: uses nodemailer npm module"""
        },
        {
            "title": "HTTP Request Node Configuration",
            "category": "node_config",
            "content": """Required configuration for HTTP request nodes:
- URL: Full endpoint URL (can use mustache template from msg properties)
- Method: GET, POST, PUT, DELETE, PATCH
- Authentication (if required):
  * Basic auth: username/password
  * Bearer token
  * OAuth2
  * API key (header or query param)
- Headers: Content-Type, Accept, custom headers
- Payload: Request body for POST/PUT (JSON, form data, raw)
- Timeout: Request timeout in milliseconds
- TLS/SSL: Certificate validation settings
- Follow redirects: Enable/disable
- Response encoding: UTF-8, binary, etc.

COMMON PATTERNS:
- Set msg.url for dynamic endpoints
- Set msg.headers for dynamic headers
- Set msg.payload for request body
- Response available in msg.payload"""
        },
        {
            "title": "Function Node Best Practices",
            "category": "node_config",
            "content": """Function node coding requirements and best practices:
- Must return msg object or null
- Use return [msg1, msg2] for multiple outputs
- Use node.warn() for warnings, node.error() for errors
- Access context: context.get/set for flow scope, context.global for global
- Common patterns:
  * Filtering: return msg.payload.value > 100 ? msg : null;
  * Transformation: msg.payload = transform(msg.payload); return msg;
  * Routing: return [msg, null]; // send to first output only
- Avoid blocking operations - use async/await or promises
- Keep functions focused - one responsibility per function
- Document complex logic with comments"""
        },
        {
            "title": "Inject Node Configuration",
            "category": "node_config",
            "content": """Required configuration for inject (trigger) nodes:
- Trigger type:
  * Manual: Button click only
  * Interval: Repeat at specified interval
  * Specific time: Time of day (cron-like)
  * Interval between times: Only during specific hours
- Payload: What to inject (timestamp, string, number, JSON, buffer, flow/global context)
- Topic: Optional message topic
- Repeat: For scheduled triggers
  * Every X seconds/minutes/hours/days
  * At specific time (HH:MM)
  * On specific days of week
- Inject once at start: Trigger when flow deployed

COMMON PATTERNS:
- Hourly: Interval 1 hour
- Daily at specific time: Specific time 09:00
- Business hours: Between 09:00 and 17:00"""
        },
        {
            "title": "GitHub Integration Requirements",
            "category": "node_config",
            "content": """Configuration for GitHub API integration:
- Authentication:
  * Personal Access Token (classic or fine-grained)
  * GitHub App authentication
  * OAuth2 app
- Repository information:
  * Owner/organization name
  * Repository name(s)
  * Branch name (if needed)
- API endpoints commonly used:
  * GET /repos/{owner}/{repo} - Repository info
  * GET /repos/{owner}/{repo}/issues - List issues
  * GET /repos/{owner}/{repo}/pulls - List pull requests
  * GET /users/{username}/repos - User repositories
- Rate limiting considerations:
  * Authenticated: 5,000 requests/hour
  * Unauthenticated: 60 requests/hour
- Headers required:
  * Authorization: token GITHUB_TOKEN
  * Accept: application/vnd.github.v3+json
  * User-Agent: Your-App-Name"""
        },
        {
            "title": "Essential Flow Information Checklist",
            "category": "requirements",
            "content": """Information needed to create a complete Node-RED flow:
INPUT/SOURCE:
- Where does data come from? (API, file, database, webhook, manual trigger)
- Authentication/credentials for source
- Data format (JSON, CSV, XML, etc.)
- Trigger frequency (manual, scheduled, event-driven)

PROCESSING:
- What transformations are needed?
- What conditions/filters to apply?
- What validation is required?
- Error handling requirements

OUTPUT/DESTINATION:
- Where should results go? (email, database, API, file, dashboard)
- Authentication/credentials for destination
- Output format required
- Success/failure notifications needed

SCHEDULING:
- How often should flow run?
- Specific times or intervals?
- Time zone considerations

CONFIGURATION:
- Environment-specific settings (dev/prod URLs)
- Credentials storage (environment variables, file)
- Logging and debugging requirements"""
        }
    ]

    for doc in documentation_entries:
        vector_store.add_documentation(**doc)

    return {
        "status": "success",
        "message": f"Initialized {len(documentation_entries)} documentation entries"
    }


@router.get("/chat/{session_id}/stream")
async def stream_progress(session_id: str):
    """
    SSE endpoint - Stream progress events in real-time
    Tipo Claude Code: muestra qué agente está ejecutando y su progreso
    """

    async def event_generator():
        # Crear cola de progreso para esta sesión
        queue = progress_manager.create_session(session_id)

        try:
            # Enviar evento inicial
            yield f"data: {json.dumps({'type': 'connected', 'session_id': session_id})}\n\n"

            # Loop infinito esperando eventos
            while True:
                try:
                    # Esperar evento con timeout
                    event: ProgressEvent = await asyncio.wait_for(queue.get(), timeout=0.5)

                    # Serializar evento
                    event_data = {
                        'type': event.type,
                        'agent': event.agent,
                        'message': event.message,
                        'details': event.details or {}
                    }

                    # Enviar evento SSE
                    yield f"data: {json.dumps(event_data)}\n\n"

                    # Si es evento COMPLETE, terminar stream
                    if event.type == ProgressEventType.COMPLETE:
                        break

                except asyncio.TimeoutError:
                    # Enviar keep-alive
                    yield f": keep-alive\n\n"

        except asyncio.CancelledError:
            logger.info(f"Stream cancelled for session {session_id}")
        finally:
            # Limpiar sesión
            progress_manager.close_session(session_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
