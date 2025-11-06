"""
Progress Event System - Sistema de eventos para comunicar progreso en tiempo real
Permite que los agentes envíen actualizaciones que se streamean al frontend
"""
import asyncio
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum


class ProgressEventType(str, Enum):
    """Tipos de eventos de progreso"""
    AGENT_START = "agent_start"
    AGENT_PROGRESS = "agent_progress"
    AGENT_COMPLETE = "agent_complete"
    PHASE_START = "phase_start"
    PHASE_COMPLETE = "phase_complete"
    ERROR = "error"
    INFO = "info"
    COMPLETE = "complete"


@dataclass
class ProgressEvent:
    """Evento de progreso"""
    type: ProgressEventType
    agent: str
    message: str
    details: Optional[Dict] = None


class ProgressManager:
    """
    Gestor de progreso que mantiene colas de eventos por sesión.
    Singleton para gestionar múltiples sesiones simultáneamente.
    """
    _instance = None
    _sessions: Dict[str, asyncio.Queue] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._sessions = {}
        return cls._instance

    def create_session(self, session_id: str) -> asyncio.Queue:
        """Crea una nueva sesión de progreso"""
        queue = asyncio.Queue()
        self._sessions[session_id] = queue
        return queue

    def get_queue(self, session_id: str) -> Optional[asyncio.Queue]:
        """Obtiene la cola de una sesión"""
        return self._sessions.get(session_id)

    async def send_event(self, session_id: str, event: ProgressEvent):
        """Envía un evento a la cola de una sesión"""
        queue = self.get_queue(session_id)
        if queue:
            await queue.put(event)

    def close_session(self, session_id: str):
        """Cierra una sesión y limpia la cola"""
        if session_id in self._sessions:
            del self._sessions[session_id]


# Singleton global
progress_manager = ProgressManager()
