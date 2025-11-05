"""
Pydantic models for API requests/responses and internal data structures
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime


class ChatMessage(BaseModel):
    """Single chat message"""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationRequest(BaseModel):
    """Request to start or continue a conversation"""
    session_id: Optional[str] = None
    message: str
    user_id: Optional[str] = "default_user"


class ConversationResponse(BaseModel):
    """Response from the agent system"""
    session_id: str
    message: str
    requires_input: bool = True
    flow_ready: bool = False
    flow_json: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FlowFeedback(BaseModel):
    """Feedback on a generated flow"""
    session_id: str
    flow_json: str
    feedback_type: Literal["approve", "reject", "modify"]
    score: int = Field(ge=1, le=5, description="Score from 1 (bad) to 5 (excellent)")
    comments: Optional[str] = None
    modifications_needed: Optional[str] = None


class NodeInfo(BaseModel):
    """Information about a Node-RED node"""
    node_type: str
    package_name: Optional[str] = None
    is_installed: bool = False
    description: Optional[str] = None


class FlowMetadata(BaseModel):
    """Metadata about a generated flow"""
    flow_id: str
    user_request: str
    created_at: datetime
    approved: bool = False
    score: Optional[int] = None
    usage_count: int = 0
