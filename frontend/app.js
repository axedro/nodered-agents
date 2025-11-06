// Frontend JavaScript for Node-RED Multi-Agent Flow Builder

const API_BASE = 'http://localhost:8000/api';

let currentSessionId = null;
let isWaitingForResponse = false;
let eventSource = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('Node-RED Multi-Agent Flow Builder initialized');
    initializeSampleNodes();
});

// Initialize sample nodes in the backend
async function initializeSampleNodes() {
    try {
        const response = await fetch(`${API_BASE}/init-nodes`, {
            method: 'POST'
        });
        const data = await response.json();
        console.log('Sample nodes initialized:', data);

        // Also initialize documentation
        const docResponse = await fetch(`${API_BASE}/init-documentation`, {
            method: 'POST'
        });
        const docData = await docResponse.json();
        console.log('Documentation initialized:', docData);
    } catch (error) {
        console.error('Error initializing:', error);
    }
}

// Connect to SSE stream for progress updates
function connectToProgressStream(sessionId) {
    // If we already have a connection for this session, just show progress and return
    if (eventSource && currentSessionId === sessionId) {
        console.log('Reusing existing SSE connection for session:', sessionId);
        const progressSection = document.getElementById('progressSection');
        progressSection.classList.add('active');
        return;
    }

    // Close existing connection if it's for a different session
    if (eventSource) {
        console.log('Closing previous SSE connection');
        eventSource.close();
    }

    // Clear previous progress only when starting a new session
    const progressSection = document.getElementById('progressSection');
    progressSection.innerHTML = '';
    progressSection.classList.add('active');

    // Create new EventSource connection
    eventSource = new EventSource(`${API_BASE}/chat/${sessionId}/stream`);

    eventSource.onopen = () => {
        console.log('SSE connection opened');
    };

    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            console.log('Progress event:', data);

            if (data.type === 'connected') {
                addProgressEvent('info', 'Conectado al sistema de progreso', '🔗');
            } else {
                addProgressEvent(data.type, data.message, getIconForEventType(data.type));

                // If it's a message from the assistant (starts with 💬), add to chat
                if (data.type === 'info' && data.message.startsWith('💬 ')) {
                    const chatMessage = data.message.substring(3); // Remove "💬 " prefix
                    addMessage('assistant', chatMessage);

                    // Re-enable input for user response
                    isWaitingForResponse = false;
                    updateUIState(false);

                    // Don't close the stream - we'll need it for the next response
                    // Just collapse the progress section after a short delay
                    setTimeout(() => {
                        progressSection.classList.remove('active');
                    }, 2000);
                }

                // If complete, fetch the final result and close
                if (data.type === 'complete') {
                    // Fetch session to get final flow
                    fetchSessionResult(currentSessionId);

                    // Re-enable input
                    isWaitingForResponse = false;
                    updateUIState(false);

                    setTimeout(() => {
                        if (eventSource) {
                            eventSource.close();
                            eventSource = null;
                        }
                        // Hide progress section after a delay
                        setTimeout(() => {
                            progressSection.classList.remove('active');
                        }, 3000);
                    }, 1000);
                }
            }
        } catch (error) {
            console.error('Error parsing SSE event:', error);
        }
    };

    eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    };
}

// Add progress event to UI
function addProgressEvent(type, message, icon = '•') {
    const progressSection = document.getElementById('progressSection');
    const eventDiv = document.createElement('div');
    eventDiv.className = `progress-event ${type}`;

    const iconSpan = document.createElement('span');
    iconSpan.className = 'progress-icon';
    iconSpan.textContent = icon;

    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;

    eventDiv.appendChild(iconSpan);
    eventDiv.appendChild(messageSpan);
    progressSection.appendChild(eventDiv);

    // Scroll to bottom
    progressSection.scrollTop = progressSection.scrollHeight;
}

// Get icon for event type
function getIconForEventType(type) {
    const icons = {
        'agent_start': '🤖',
        'agent_complete': '✅',
        'phase_start': '⚙️',
        'phase_complete': '✓',
        'info': 'ℹ️',
        'error': '❌',
        'complete': '🎉'
    };
    return icons[type] || '•';
}

// Fetch session result after workflow completes
async function fetchSessionResult(sessionId) {
    try {
        const response = await fetch(`${API_BASE}/session/${sessionId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const sessionData = await response.json();
        console.log('Session result:', sessionData);

        // Display flow if ready
        if (sessionData.flow_ready && sessionData.flow_json) {
            displayFlow(sessionData.flow_json);
            updateStatus('ready', '✓ Flujo Generado');
            addMessage('assistant', '✓ Flujo generado y validado exitosamente! El JSON está listo en el panel derecho.');
        }
    } catch (error) {
        console.error('Error fetching session result:', error);
    }
}

// Send message to the multi-agent system
async function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();

    if (!message || isWaitingForResponse) return;

    // Add user message to chat
    addMessage('user', message);
    input.value = '';

    // Disable input while waiting
    isWaitingForResponse = true;
    updateUIState(true);

    try {
        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: message,
                user_id: 'demo_user'
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Update session ID
        currentSessionId = data.session_id;

        // Connect to progress stream with a delay to ensure backend workflow has started
        setTimeout(() => {
            connectToProgressStream(currentSessionId);
        }, 300);

        // Add assistant response (will be initial message)
        if (data.message && data.message !== "Procesando tu solicitud... Conéctate al stream para ver el progreso en tiempo real.") {
            addMessage('assistant', data.message);
        }

        // Update flow if ready
        if (data.flow_ready && data.flow_json) {
            displayFlow(data.flow_json);
            updateStatus('ready', '✓ Flujo Generado');
        } else {
            updateStatus('waiting', 'En proceso...');
        }

        // Log metadata
        console.log('Metadata:', data.metadata);

    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('system', `❌ Error: ${error.message}. Asegúrate de que el backend esté corriendo.`);
        updateStatus('error', 'Error');
    } finally {
        isWaitingForResponse = false;
        updateUIState(false);
    }
}

// Add message to chat
function addMessage(role, content) {
    const messagesDiv = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);

    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Display flow JSON
function displayFlow(flowJson) {
    const flowTextarea = document.getElementById('flowJson');

    try {
        // Try to format JSON
        const parsed = JSON.parse(flowJson);
        flowTextarea.value = JSON.stringify(parsed, null, 2);
    } catch (e) {
        // If not valid JSON, display as is
        flowTextarea.value = flowJson;
    }

    // Enable action buttons
    document.getElementById('copyBtn').disabled = false;
    document.getElementById('approveBtn').disabled = false;
    document.getElementById('rejectBtn').disabled = false;
}

// Update status indicator
function updateStatus(type, text) {
    const indicator = document.getElementById('statusIndicator');
    indicator.className = `status-indicator ${type}`;
    indicator.textContent = text;
}

// Update UI state (loading/ready)
function updateUIState(isLoading) {
    const sendBtn = document.getElementById('sendBtn');
    const input = document.getElementById('userInput');

    if (isLoading) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<span class="loading"></span>';
        input.disabled = true;
    } else {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Enviar';
        input.disabled = false;
        input.focus();
    }
}

// Copy flow to clipboard
function copyFlow() {
    const flowTextarea = document.getElementById('flowJson');
    flowTextarea.select();
    document.execCommand('copy');

    // Visual feedback
    const btn = document.getElementById('copyBtn');
    const originalText = btn.textContent;
    btn.textContent = '✓ Copiado!';
    setTimeout(() => {
        btn.textContent = originalText;
    }, 2000);
}

// Submit feedback
async function submitFeedback(type, score) {
    if (!currentSessionId) {
        alert('No hay sesión activa');
        return;
    }

    const flowJson = document.getElementById('flowJson').value;

    if (!flowJson) {
        alert('No hay flujo para evaluar');
        return;
    }

    if (type === 'modify') {
        // Show feedback section for modifications
        document.getElementById('feedbackSection').style.display = 'block';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                flow_json: flowJson,
                feedback_type: type,
                score: score,
                comments: null,
                modifications_needed: null
            })
        });

        const data = await response.json();

        if (type === 'approve') {
            addMessage('system', '✓ ¡Gracias! El flujo ha sido aprobado y guardado para futuras referencias.');
            updateStatus('ready', '✓ Aprobado');
        } else if (type === 'reject') {
            addMessage('system', '✗ Feedback registrado. ¿Quieres intentar de nuevo? Cuéntame qué necesitas cambiar.');
            updateStatus('waiting', 'Rechazado');
        }

        console.log('Feedback response:', data);

    } catch (error) {
        console.error('Error submitting feedback:', error);
        addMessage('system', `❌ Error al enviar feedback: ${error.message}`);
    }
}

// Submit detailed feedback
async function submitDetailedFeedback() {
    const score = parseInt(document.getElementById('scoreRange').value);
    const comments = document.getElementById('feedbackComments').value;

    if (!currentSessionId) {
        alert('No hay sesión activa');
        return;
    }

    const flowJson = document.getElementById('flowJson').value;

    try {
        const response = await fetch(`${API_BASE}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                flow_json: flowJson,
                feedback_type: score >= 4 ? 'approve' : 'modify',
                score: score,
                comments: comments || null,
                modifications_needed: score < 4 ? comments : null
            })
        });

        const data = await response.json();

        addMessage('system', '✓ Feedback detallado enviado. Gracias!');
        document.getElementById('feedbackSection').style.display = 'none';

        console.log('Detailed feedback response:', data);

    } catch (error) {
        console.error('Error submitting detailed feedback:', error);
        addMessage('system', `❌ Error al enviar feedback: ${error.message}`);
    }
}

// Get session info
async function getSessionInfo() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`${API_BASE}/session/${currentSessionId}`);
        const data = await response.json();
        console.log('Session info:', data);
        return data;
    } catch (error) {
        console.error('Error getting session info:', error);
    }
}

// Get system stats
async function getStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        const data = await response.json();
        console.log('System stats:', data);
        return data;
    } catch (error) {
        console.error('Error getting stats:', error);
    }
}
