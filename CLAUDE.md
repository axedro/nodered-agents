# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent AI system for generating Node-RED flows through natural conversation. Uses LangGraph to orchestrate 8 specialized agents, RAG for continuous learning, and supports multiple LLM providers (Ollama local, OpenAI, Anthropic).

The system transforms user requirements like "I need to receive webhooks and send to Slack" into complete, validated Node-RED JSON flows through conversational interaction.

## Development Commands

### Backend Development

```bash
# Start backend server (recommended)
python -m uvicorn backend.main:app --reload

# Alternative start method
python -m backend.main

# Run integration tests (backend must be running)
python test_system.py
```

### Environment Setup

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your LLM configuration
```

### Ollama Setup (Local LLM)

```bash
# Start Ollama service (must be running)
ollama serve

# Download a model (if not already done)
ollama pull mistral
# ollama pull llama2
# ollama pull codellama
# ollama pull deepseek-coder

# Verify Ollama is accessible
curl http://localhost:11434/api/tags
```

### Frontend Development

```bash
# Serve frontend (choose one method)
cd frontend && python -m http.server 8080
# OR
npx http-server frontend -p 8080
```

### API Endpoints

- API Base: `http://localhost:8000/api`
- API Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

## Architecture

### Multi-Agent System (LangGraph Orchestration)

The system uses 8 specialized agents in a state machine workflow:

1. **CacheSearcher** (`backend/agents/cache_searcher.py`): Searches RAG for similar approved flows (>95% similarity)
2. **Conversator** (`backend/agents/conversator.py`): Engages user to clarify requirements, extracts systems/nodes needed
3. **LocalSearcher** (`backend/agents/local_searcher.py`): Queries ChromaDB for installed Node-RED nodes
4. **WebSearcher** (`backend/agents/web_searcher.py`): Searches npm for missing Node-RED packages
5. **Installer** (`backend/agents/installer.py`): Simulated package installation (MVP)
6. **FunctionCoder** (`backend/agents/function_coder.py`): Generates JavaScript for function nodes
7. **JsonBuilder** (`backend/agents/json_builder.py`): Assembles complete Node-RED flow JSON
8. **Validator** (`backend/agents/validator.py`): Validates flow structure and syntax

### Workflow Flow

```
User Request → CacheSearcher
                 ↓ (cache miss)
              Conversator (clarifies requirements)
                 ↓
              LocalSearcher (finds installed nodes)
                 ↓ (if missing nodes)
              WebSearcher → Installer
                 ↓
              FunctionCoder (generates JS code)
                 ↓
              JsonBuilder (assembles flow)
                 ↓
              Validator (validates JSON)
                 ↓
              Complete Flow
```

Cache hits skip directly to Validator. Validator may loop back to JsonBuilder on errors.

### Core Components

#### State Management (`backend/core/state.py`)
- **AgentState**: TypedDict defining shared state across all agents
- Key fields: `conversation_history`, `required_nodes`, `installed_nodes`, `generated_functions`, `final_json_flow`
- Uses annotated fields with `operator.add` for list concatenation across agent transitions

#### Graph Orchestration (`backend/core/graph.py`)
- **create_workflow_graph()**: Builds LangGraph StateGraph with conditional edges
- **route_next_agent()**: Routes between agents based on current state
- All agent transitions are defined via conditional edges, not linear chains

#### LLM Manager (`backend/core/llm_manager.py`)
- **LLMManager**: Singleton abstraction over multiple LLM providers
- **OllamaLLM**: Local inference via Ollama HTTP API
- **OpenAILLM**, **AnthropicLLM**: Stubs for cloud providers (not yet implemented)
- All agents call `await llm.generate_with_history(messages)` for LLM interactions

#### RAG System (`backend/rag/`)
- **VectorStoreManager** (`vector_store.py`): ChromaDB singleton managing 3 collections
  - `installed_nodes`: Catalog of available Node-RED nodes
  - `approved_flows`: User-approved solutions for reuse
  - `feedback_history`: Feedback for reinforcement learning
- **EmbeddingGenerator** (`embeddings.py`): Uses ChromaDB's default embeddings (sentence-transformers removed)
- Similarity threshold for cache hits: 0.95 (configurable via `SIMILARITY_THRESHOLD`)

### Configuration (`backend/config.py`)

Uses Pydantic Settings loading from `.env`:
- `LLM_PROVIDER`: ollama | openai | anthropic
- `OLLAMA_BASE_URL`, `OLLAMA_MODEL`: Ollama configuration
- `CHROMA_PERSIST_DIR`: ChromaDB storage location (default: `./data/chroma_db`)
- `MIN_FEEDBACK_SCORE`: Minimum score to consider flow "good" (default: 3)
- `SIMILARITY_THRESHOLD`: For cache matches (default: 0.95)

### API Layer (`backend/api/routes.py`)

FastAPI routes for:
- `POST /api/chat`: Send message, continues conversation
- `POST /api/feedback`: Submit feedback on generated flow
- `POST /api/init-nodes`: Initialize sample Node-RED nodes catalog
- `GET /api/stats`: Get system statistics
- Sessions tracked in memory (not persistent)

## Key Implementation Patterns

### Agent Implementation Pattern

All agents follow this structure:
```python
async def agent_name_agent(state: AgentState) -> AgentState:
    """Agent description"""
    logger.info("[AgentName] Starting...")

    llm = LLMManager()

    # Build prompt with context from state
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # ... add conversation history
    ]

    # Generate response
    response = await llm.generate_with_history(messages)

    # Update state based on response
    state['field'] = processed_response
    state['current_agent'] = 'next_agent_name'  # Controls routing
    state['needs_user_input'] = True/False
    state['is_complete'] = True/False

    return state
```

### State Transitions

Agents control workflow by setting `state['current_agent']`:
- Set to their own name to continue in same agent (e.g., Conversator waiting for user input)
- Set to next agent name to transition
- Set `is_complete=True` to end workflow

### Conversation History Management

Conversator builds LLM context from `state['conversation_history']`:
```python
messages = [{"role": "system", "content": SYSTEM_PROMPT}]
for msg in state['conversation_history']:
    messages.append({"role": msg['role'], "content": msg['content']})
```

Always append new messages to maintain context.

### JSON Extraction Pattern

Agents extract JSON from LLM responses using regex:
```python
json_match = re.search(r'\{[^{}]*"status"\s*:\s*"complete"[^{}]*\}', response, re.DOTALL)
if json_match:
    data = json.loads(json_match.group())
```

This handles LLMs that include text before/after JSON.

## Testing

### Integration Test Flow

`test_system.py` runs full end-to-end test:
1. Health check
2. Initialize sample nodes
3. Start chat session with simple flow request
4. Continue conversation if needed
5. Submit feedback on generated flow
6. Check statistics

Requires backend and Ollama running.

### Manual Testing

```bash
# Initialize sample nodes
curl -X POST http://localhost:8000/api/init-nodes

# Start conversation
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Quiero un flujo que lea una API REST y envíe a Slack", "user_id": "test"}'

# Get session_id from response, then continue
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id": "SESSION_ID", "message": "API de GitHub", "user_id": "test"}'
```

## Common Development Tasks

### Adding a New Agent

1. Create `backend/agents/new_agent.py` following the agent pattern
2. Import in `backend/agents/__init__.py`
3. Add node to workflow in `backend/core/graph.py`: `workflow.add_node("new_agent", new_agent_func)`
4. Add conditional edges for routing to/from new agent
5. Update `route_next_agent()` mapping if needed

### Modifying Agent Behavior

Edit the `SYSTEM_PROMPT` constant in the agent file. This defines the agent's instructions.

### Changing LLM Provider

Update `.env`:
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

Note: OpenAI and Anthropic providers are stubs (NotImplementedError). Only Ollama is fully implemented.

### Clearing RAG Data

```bash
# Delete ChromaDB storage
rm -rf data/chroma_db

# Re-initialize on next backend start
# Or call /api/init-nodes to add sample data
```

### Debugging Agent Transitions

Set `DEBUG=true` in `.env` and check logs for:
- `[Router] Current agent: X, Complete: Y`
- `[Router] Routing to: Z`
- Each agent logs `[AgentName] Starting...`

## Troubleshooting

### "Connection refused" errors
- Ensure Ollama is running: `ollama serve`
- Check Ollama is accessible: `curl http://localhost:11434/api/tags`

### "Model not found"
- Download model: `ollama pull mistral`

### Slow responses
- Use smaller model: `llama2` instead of `llama2:70b`
- Check Ollama resource usage
- Consider GPU acceleration for Ollama

### ChromaDB errors
- Clear database: `rm -rf data/chroma_db`
- Ensure write permissions on `data/` directory

### Agent stuck in loop
- Check `state['current_agent']` transitions in agent code
- Verify `is_complete` flag is set when done
- Review `route_next_agent()` conditional edges

## Dependencies

- **FastAPI**: Web framework for API
- **LangGraph**: Multi-agent orchestration
- **LangChain**: LLM framework (core, community packages)
- **ChromaDB**: Vector database for RAG
- **Ollama**: Local LLM inference
- **sentence-transformers**: Embeddings (via ChromaDB defaults)
- **Pydantic**: Settings and validation
- **httpx**: Async HTTP client
- **loguru**: Logging

See `requirements.txt` for version constraints.
