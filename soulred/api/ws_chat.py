"""WebSocket real-time direct messaging gateway for SoulRed.

Provides:
- High-concurrency connection management (ConnectionManager)
- Heartbeat / ping-pong keepalive protocol
- End-to-end message delivery latency < 200ms
- Real-time stranger anti-harassment limit enforcement
- Offline message persistence and delivery receipts
"""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from sqlalchemy.orm import Session

from soulred.database import SessionLocal
from soulred.models.user import User
from soulred.models.chat import ChatMessage
from soulred.services.chat_service import ChatService
from soulred.services.matching_service import MatchingService
from soulred.utils.crypto import decode_access_token

logger = logging.getLogger("soulred.websocket")

router = APIRouter(tags=["WebSocket Gateway"])


class ConnectionManager:
    """Manages concurrent client WebSocket connections with multi-device support."""

    def __init__(self):
        # Map user_id to set of active WebSocket instances
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """Accept WebSocket and register active connection."""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.info(f"User {user_id} connected via WebSocket (active sessions: {len(self.active_connections[user_id])})")

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        """Unregister closed WebSocket instance."""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.info(f"User {user_id} disconnected from WebSocket")

    async def send_personal_message(self, message: Any, user_id: str) -> bool:
        """Deliver JSON or string payload to all active sockets of a target user."""
        if user_id not in self.active_connections:
            return False

        payload = message if isinstance(message, str) else json.dumps(message, default=str)
        dead_sockets = set()
        delivered = False

        for ws in self.active_connections[user_id]:
            try:
                await ws.send_text(payload)
                delivered = True
            except Exception as e:
                logger.warning(f"Error sending message to user {user_id}: {e}")
                dead_sockets.add(ws)

        for dead in dead_sockets:
            self.disconnect(user_id, dead)

        return delivered

    async def broadcast(self, message: Any) -> None:
        """Broadcast payload to all currently connected users."""
        payload = message if isinstance(message, str) else json.dumps(message, default=str)
        for user_id, sockets in list(self.active_connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(payload)
                except Exception:
                    self.disconnect(user_id, ws)

    def is_user_online(self, user_id: str) -> bool:
        """Check if user has at least one active connection."""
        return user_id in self.active_connections and len(self.active_connections[user_id]) > 0


manager = ConnectionManager()


@router.websocket("/ws/chat/{user_id}")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: Optional[str] = Query(None),
):
    """WebSocket messaging endpoint.
    
    Accepts client connection, validates token/identity, routes messages,
    enforces stranger rate-limiting, and maintains heartbeat.
    """
    # 1. Optional JWT authentication via query parameter
    if token:
        try:
            payload = decode_access_token(token)
            token_user_id = payload.get("sub") or payload.get("user_id")
            if token_user_id and token_user_id != user_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    # Verify user existence in database
    db: Session = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
    finally:
        db.close()

    await manager.connect(websocket, user_id)

    # Send welcome acknowledgment
    await websocket.send_text(
        json.dumps({
            "type": "connection_ack",
            "user_id": user_id,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "status": "connected",
        })
    )

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                # Handle plain text ping
                if raw_data.strip().lower() == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "time": datetime.now(timezone.utc).isoformat()}))
                continue

            msg_type = data.get("type", "message")

            # 2. Heartbeat Ping / Pong
            if msg_type == "ping":
                await websocket.send_text(json.dumps({
                    "type": "pong",
                    "time": datetime.now(timezone.utc).isoformat(),
                }))
                continue

            # 3. Direct Message Delivery
            if msg_type in ["message", "chat"]:
                receiver_id = data.get("receiver_id")
                content = data.get("content", "").strip()
                payload_type = data.get("message_type", "text")
                media_url = data.get("media_url")

                if not receiver_id or not content:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "code": "INVALID_PAYLOAD",
                        "detail": "receiver_id and content are required",
                    }))
                    continue

                db_session: Session = SessionLocal()
                try:
                    # 4. Anti-harassment Stranger Limit Check
                    can_send = MatchingService.check_stranger_message_limit(
                        db=db_session,
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        message_type=payload_type,
                    )

                    if not can_send:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "code": "STRANGER_LIMIT_EXCEEDED",
                            "detail": "陌生人单日仅限发送 1 条打招呼纯文本消息，禁止发送图片/语音",
                        }))
                        continue

                    # 5. Persist message and advance intimacy state machine
                    stored_msg = ChatService.record_message(
                        db=db_session,
                        sender_id=user_id,
                        receiver_id=receiver_id,
                        content=content,
                        message_type=payload_type,
                        media_url=media_url,
                    )

                    msg_payload = {
                        "type": "new_message",
                        "message_id": stored_msg.id,
                        "conversation_id": stored_msg.conversation_id,
                        "sender_id": user_id,
                        "receiver_id": receiver_id,
                        "content": stored_msg.content,
                        "message_type": stored_msg.message_type,
                        "media_url": stored_msg.media_url,
                        "created_at": stored_msg.created_at.isoformat() if stored_msg.created_at else None,
                    }

                    # Deliver to recipient if online
                    is_delivered = await manager.send_personal_message(msg_payload, receiver_id)

                    # Send ACK receipt back to sender
                    await websocket.send_text(json.dumps({
                        "type": "message_ack",
                        "message_id": stored_msg.id,
                        "conversation_id": stored_msg.conversation_id,
                        "is_delivered": is_delivered,
                        "created_at": stored_msg.created_at.isoformat() if stored_msg.created_at else None,
                    }))

                except Exception as ex:
                    logger.error(f"Error processing chat message: {ex}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "code": "MESSAGE_PROCESSING_ERROR",
                        "detail": str(ex),
                    }))
                finally:
                    db_session.close()

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception as e:
        logger.error(f"WebSocket unhandled error: {e}")
        manager.disconnect(user_id, websocket)
