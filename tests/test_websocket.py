"""WebSocket real-time direct messaging end-to-end integration test suite."""

import json
from fastapi.testclient import TestClient
from soulred.models.user import User
from soulred.models.chat import ChatConversation, ChatMessage
from soulred.models.match import CrushMatch, CrushStatusEnum


def test_websocket_direct_message_exchange(
    client: TestClient,
    test_user_a: User,
    test_user_b: User,
    db_session,
):
    """Test real-time bidirectional message delivery, keepalive ping/pong, and delivery ACK."""
    user_a_id = str(test_user_a.id)
    user_b_id = str(test_user_b.id)

    # Pre-establish mutual friend / crush connection so they are not constrained by stranger limits
    crush = (
        db_session.query(CrushMatch)
        .filter(CrushMatch.user_id == user_a_id, CrushMatch.target_user_id == user_b_id)
        .first()
    )
    if not crush:
        crush = CrushMatch(
            user_id=user_a_id,
            target_user_id=user_b_id,
            status=CrushStatusEnum.MUTUAL.value,
        )
        db_session.add(crush)
    else:
        crush.status = CrushStatusEnum.MUTUAL.value
    db_session.commit()

    # 1. Connect User A and User B concurrently
    with client.websocket_connect(f"/ws/chat/{user_a_id}") as ws_a:
        ack_a = json.loads(ws_a.receive_text())
        assert ack_a["type"] == "connection_ack"
        assert ack_a["user_id"] == user_a_id

        # Test keepalive ping/pong
        ws_a.send_text(json.dumps({"type": "ping"}))
        pong_resp = json.loads(ws_a.receive_text())
        assert pong_resp["type"] == "pong"

        with client.websocket_connect(f"/ws/chat/{user_b_id}") as ws_b:
            ack_b = json.loads(ws_b.receive_text())
            assert ack_b["type"] == "connection_ack"

            # 2. User A sends chat message to User B
            ws_a.send_text(
                json.dumps({
                    "type": "message",
                    "receiver_id": user_b_id,
                    "content": "Hi Bob! 听了你分享的吉他弹唱，指弹技巧太赞了 🎸",
                    "message_type": "text",
                })
            )

            # User A receives ACK receipt
            ack_msg = json.loads(ws_a.receive_text())
            assert ack_msg["type"] == "message_ack"
            assert ack_msg["is_delivered"] is True

            # User B receives live real-time message (<200ms latency)
            received_by_b = json.loads(ws_b.receive_text())
            assert received_by_b["type"] == "new_message"
            assert received_by_b["sender_id"] == user_a_id
            assert "指弹技巧太赞了" in received_by_b["content"]

            # 3. User B replies to User A
            ws_b.send_text(
                json.dumps({
                    "type": "message",
                    "receiver_id": user_a_id,
                    "content": "谢谢 Alice！下次一起去现场听 livehouse 呀～",
                    "message_type": "text",
                })
            )

            ack_b_msg = json.loads(ws_b.receive_text())
            assert ack_b_msg["type"] == "message_ack"
            assert ack_b_msg["is_delivered"] is True

            received_by_a = json.loads(ws_a.receive_text())
            assert received_by_a["type"] == "new_message"
            assert received_by_a["sender_id"] == user_b_id
            assert "livehouse" in received_by_a["content"]


def test_websocket_stranger_daily_limit(
    client: TestClient,
    test_user_a: User,
    test_user_b: User,
    db_session,
):
    """Test stranger anti-harassment limits: strictly 1 text message per day, no images/voice."""
    user_a_id = str(test_user_a.id)
    user_b_id = str(test_user_b.id)

    # Ensure they are strangers (no mutual crush, no conversation session, no previous messages)
    db_session.query(CrushMatch).filter(
        (CrushMatch.user_id == user_a_id) | (CrushMatch.target_user_id == user_a_id)
    ).delete()
    db_session.query(ChatMessage).filter(
        (ChatMessage.sender_id == user_a_id) | (ChatMessage.receiver_id == user_a_id)
    ).delete()
    db_session.query(ChatConversation).filter(
        (ChatConversation.user_a_id == user_a_id) | (ChatConversation.user_b_id == user_a_id)
    ).delete()
    db_session.commit()

    with client.websocket_connect(f"/ws/chat/{user_a_id}") as ws_a:
        ack = json.loads(ws_a.receive_text())
        assert ack["type"] == "connection_ack"

        # 1. Attempt sending an image to a stranger (Should be BLOCKED)
        ws_a.send_text(
            json.dumps({
                "type": "message",
                "receiver_id": user_b_id,
                "content": "Check this picture",
                "message_type": "image",
                "media_url": "https://example.com/unsolicited.jpg",
            })
        )
        err_img = json.loads(ws_a.receive_text())
        assert err_img["type"] == "error"
        assert err_img["code"] == "STRANGER_LIMIT_EXCEEDED"

        # 2. First greeting text message (Should SUCCEED)
        ws_a.send_text(
            json.dumps({
                "type": "message",
                "receiver_id": user_b_id,
                "content": "Hi Bob, 看到你的主页很喜欢你的风格，打个招呼！",
                "message_type": "text",
            })
        )
        ack1 = json.loads(ws_a.receive_text())
        assert ack1["type"] == "message_ack"

        # 3. Second message on the same day to stranger (Should be BLOCKED by 1-msg/day quota)
        ws_a.send_text(
            json.dumps({
                "type": "message",
                "receiver_id": user_b_id,
                "content": "还有一句话想和你说...",
                "message_type": "text",
            })
        )
        err_limit = json.loads(ws_a.receive_text())
        assert err_limit["type"] == "error"
        assert err_limit["code"] == "STRANGER_LIMIT_EXCEEDED"
