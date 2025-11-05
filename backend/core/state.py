"""
LangGraph State Management
This defines the shared state that all agents will read from and write to.
"""
from typing import TypedDict, List, Dict, Optional, Annotated
from operator import add


class FunctionCode(TypedDict):
    """Code for a function node"""
    id: str
    code: str
    description: str


class AgentState(TypedDict):
    """
    The shared state object that gets passed between all agents.
    Each agent can read from and write to this state.
    """
    # Session management
    session_id: str
    user_id: str

    # User request and conversation
    user_request: str
    conversation_history: Annotated[List[Dict[str, str]], add]  # Will append messages
    clarified_request: Optional[str]

    # Node requirements and availability
    required_nodes: List[str]
    installed_nodes: List[str]
    missing_nodes: List[str]
    suggested_installations: List[Dict[str, str]]  # [{name, package, source}]

    # Generated code
    generated_functions: List[FunctionCode]

    # Final output
    final_json_flow: Optional[str]

    # Error handling
    error_message: Optional[str]
    retry_count: int

    # Workflow control
    current_agent: str
    needs_user_input: bool
    is_complete: bool

    # Feedback and learning
    feedback_score: Optional[int]
    cached_solution: Optional[str]  # If found in RAG

    # Metadata
    flow_description: str
    detected_systems: List[str]  # ERP, CRM, etc.
