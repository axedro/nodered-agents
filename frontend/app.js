// Frontend JavaScript for Node-RED Multi-Agent Flow Builder

const API_BASE = 'http://localhost:8000/api';

let currentSessionId = null;
let isWaitingForResponse = false;

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
    } catch (error) {
        console.error('Error initializing nodes:', error);
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

        // Add assistant response
        addMessage('assistant', data.message);

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
