import asyncio
from typing import Any, Callable, Dict, List

class AgentBus:
    """
    A lightweight event bus for nanobot tools to emit side-car data 
    (like screenshots, logs, or status updates) to the UI.
    """
    _listeners: List[Callable[[Dict[str, Any]], Any]] = []

    @classmethod
    def subscribe(cls, callback: Callable[[Dict[str, Any]], Any]):
        cls._listeners.append(callback)

    @classmethod
    def unsubscribe(cls, callback: Callable[[Dict[str, Any]], Any]):
        if callback in cls._listeners:
            cls._listeners.remove(callback)

    @classmethod
    async def emit(cls, event_type: str, data: Any):
        event = {"type": "agent_trace", "sub_type": event_type, "data": data}
        for callback in cls._listeners:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)

# Global instance for easy access
bus = AgentBus()
