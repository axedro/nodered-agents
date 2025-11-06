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


class NodeConfiguration(TypedDict):
    """Configuration for a specific node"""
    node_id: str
    node_type: str
    properties: Dict[str, any]  # URLs, credentials, etc.
    description: str


class ConditionalLogic(TypedDict):
    """Conditional logic for switch/function nodes"""
    id: str
    type: str  # 'switch' or 'function_conditional'
    rules: List[Dict[str, any]]
    description: str


class WiringPlan(TypedDict):
    """Plan for connecting nodes"""
    connections: List[Dict[str, any]]  # [{from: id, to: id, output_port: 0}]
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

    # Manager coordination data
    node_configurations: List[NodeConfiguration]  # Configs from ConfigurationAgent
    conditional_logic: List[ConditionalLogic]  # Logic from ConditionalAgent
    wiring_plan: Optional[WiringPlan]  # Connections from WiringAgent
    manager_analysis: Optional[str]  # Summary from Manager
    missing_information: List[str]  # What Manager needs from user

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
