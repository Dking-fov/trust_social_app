"""Manages live WebSocket client connections for real-time IM delivery and instant match notifications."""

import logging
from typing import Dict, List
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """In-memory active WebSocket connection registry."""

    def __init__(self):
        # Maps user_id -> list of active WebSocket connections (multi-device support)
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: int):
        """Accepts and registers incoming client connection."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        logger.info("WebSocket connected for user_id=%s, total connections=%s", user_id, len(self.active_connections[user_id]))

    def disconnect(self, websocket: WebSocket, user_id: int):
        """Deregisters client connection."""
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info("WebSocket disconnected for user_id=%s", user_id)

    async def send_personal_message(self, message: dict, user_id: int):
        """Dispatches JSON payload to all active client sockets of a user (<300ms)."""
        if user_id in self.active_connections:
            dead_sockets = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning("Failed to send message to user %s: %s", user_id, e)
                    dead_sockets.append(connection)
            for dead in dead_sockets:
                self.disconnect(dead, user_id)

    async def broadcast_to_match(self, user_a_id: int, user_b_id: int, event: str, data: dict):
        """Sends real-time event frame to both matched parties."""
        payload = {"event": event, "data": data}
        await self.send_personal_message(payload, user_a_id)
        await self.send_personal_message(payload, user_b_id)


ws_manager = ConnectionManager()
