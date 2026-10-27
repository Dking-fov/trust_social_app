"""Full-chain REST API integration test suite for SoulRed social platform."""

import uuid
from fastapi.testclient import TestClient
from soulred.models.user import User


def test_auth_flow(client: TestClient):
    """Test user registration, authentication, token issuance, and profile retrieval."""
    unique_suffix = uuid.uuid4().hex[:6]
    username = f"charlie_{unique_suffix}"
    password = "SecurePassword123!"

    # 1. Register
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": password,
            "nickname": "Charlie Explorer",
            "phone": "13800138000",
            "mbti": "INFJ",
        },
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert reg_data["username"] == username
    assert reg_data["nickname"] == "Charlie Explorer"
    assert reg_data["mbti"] == "INFJ"

    # 2. Login
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Retrieve personal profile via /users/me
    me_resp = client.get("/api/v1/users/me", headers=headers)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["username"] == username
    assert me_data["mbti"] == "INFJ"

    # 4. Update profile persona
    update_resp = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={
            "bio": "在城市中探寻安静的小角落",
            "interest_tags": ["黑胶唱片", "独立书店"],
            "location": "上海·黄浦",
        },
    )
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["bio"] == "在城市中探寻安静的小角落"
    assert "黑胶唱片" in updated_data["interest_tags"]


def test_waterfall_feed_channels(client: TestClient, auth_headers_user_a: dict):
    """Test Xiaohongshu-style dual-column waterfall across recommend, nearby, and following channels."""
    # First, publish test note posts
    client.post(
        "/api/v1/posts",
        headers=auth_headers_user_a,
        json={
            "title": "徐汇滨江日落漫步 🌇",
            "content": "今天的晚霞像橘子味汽水，江边的风特别温柔。",
            "channel": "recommend",
            "images": [
                {
                    "image_url": "https://example.com/sunset.jpg",
                    "aspect_ratio": "3:4",
                }
            ],
            "latitude": 31.18,
            "longitude": 121.46,
        },
    )

    # 1. Recommend channel
    resp_rec = client.get("/api/v1/feed?channel=recommend&page=1&page_size=10")
    assert resp_rec.status_code == 200
    data_rec = resp_rec.json()
    assert "items" in data_rec
    assert data_rec["channel"] == "recommend"
    assert isinstance(data_rec["items"], list)

    # 2. Nearby channel with geo coordinates
    resp_near = client.get(
        "/api/v1/feed?channel=nearby&viewer_lat=31.19&viewer_lon=121.45&page=1&page_size=10"
    )
    assert resp_near.status_code == 200
    data_near = resp_near.json()
    assert data_near["channel"] == "nearby"

    # 3. Following channel
    resp_follow = client.get("/api/v1/feed?channel=following&page=1&page_size=10")
    assert resp_follow.status_code == 200
    data_follow = resp_follow.json()
    assert data_follow["channel"] == "following"


def test_post_creation_and_like(client: TestClient, auth_headers_user_a: dict, auth_headers_user_b: dict):
    """Test creating a post, saving draft, fetching post detail, and toggling likes."""
    # 1. Save and fetch draft
    draft_resp = client.post(
        "/api/v1/posts/draft",
        headers=auth_headers_user_a,
        json={
            "title": "草稿：秋日手冲咖啡笔记",
            "content": "水温 92度，粉水比 1:15...",
            "mood_tag": "治愈中",
        },
    )
    assert draft_resp.status_code == 200

    get_draft_resp = client.get("/api/v1/posts/draft", headers=auth_headers_user_a)
    assert get_draft_resp.status_code == 200
    assert get_draft_resp.json()["status"] == "found"

    # 2. Publish post note
    create_resp = client.post(
        "/api/v1/posts",
        headers=auth_headers_user_a,
        json={
            "title": "安福路街角的可露丽 🥐",
            "content": "外脆内软的蜂窝结构，朗姆酒香很浓郁，值得排队！",
            "mood_tag": "开心",
            "topics": ["美食探店", "法式甜品"],
            "images": [
                {
                    "image_url": "https://example.com/canele.jpg",
                    "aspect_ratio": "1:1",
                }
            ],
        },
    )
    assert create_resp.status_code == 201
    post_data = create_resp.json()
    post_id = post_data["id"]
    assert post_data["title"] == "安福路街角的可露丽 🥐"
    assert post_data["likes_count"] == 0

    # 3. User B likes the post
    like_resp = client.post(f"/api/v1/posts/{post_id}/like", headers=auth_headers_user_b)
    assert like_resp.status_code == 200
    like_data = like_resp.json()
    assert like_data["is_liked"] is True
    assert like_data["likes_count"] == 1

    # 4. User B unlikes the post
    unlike_resp = client.post(f"/api/v1/posts/{post_id}/like", headers=auth_headers_user_b)
    assert unlike_resp.status_code == 200
    unlike_data = unlike_resp.json()
    assert unlike_data["is_liked"] is False
    assert unlike_data["likes_count"] == 0


def test_matching_and_crush_flow(
    client: TestClient,
    test_user_a: User,
    test_user_b: User,
    auth_headers_user_a: dict,
    auth_headers_user_b: dict,
):
    """Test personality quiz, Soul radar search, daily cards, and reciprocal mutual crush."""
    # 1. User A submits personality quiz
    quiz_resp = client.post(
        "/api/v1/matching/quiz",
        headers=auth_headers_user_a,
        json={
            "mbti": "INFP",
            "answers": {"q1": "alone", "q2": "deep_talk", "q3": "intuition"},
        },
    )
    assert quiz_resp.status_code == 200
    quiz_data = quiz_resp.json()
    assert quiz_data["mbti"] == "INFP"
    assert len(quiz_data["traits_vector"]) > 0

    # 2. User B submits personality quiz (ENFJ golden match)
    client.post(
        "/api/v1/matching/quiz",
        headers=auth_headers_user_b,
        json={
            "mbti": "ENFJ",
            "answers": {"q1": "social", "q2": "empathy", "q3": "future"},
        },
    )

    # 3. User A searches Soul radar
    radar_resp = client.get("/api/v1/matching/radar", headers=auth_headers_user_a)
    assert radar_resp.status_code == 200
    radar_cards = radar_resp.json()
    assert isinstance(radar_cards, list)

    # 4. User A gets daily recommendation cards
    daily_resp = client.get("/api/v1/matching/daily?count=5", headers=auth_headers_user_a)
    assert daily_resp.status_code == 200
    daily_cards = daily_resp.json()
    assert isinstance(daily_cards, list)

    # 5. User A sends crush to User B (Single-sided pending)
    crush_a_resp = client.post(
        "/api/v1/matching/crush",
        headers=auth_headers_user_a,
        json={
            "target_user_id": test_user_b.id,
            "action": "crush",
        },
    )
    assert crush_a_resp.status_code == 200
    res_a = crush_a_resp.json()
    assert res_a["is_mutual"] is False
    assert res_a["status"] == "pending"

    # 6. User B sends reciprocal crush to User A (triggers MUTUAL match!)
    crush_b_resp = client.post(
        "/api/v1/matching/crush",
        headers=auth_headers_user_b,
        json={
            "target_user_id": test_user_a.id,
            "action": "crush",
        },
    )
    assert crush_b_resp.status_code == 200
    res_b = crush_b_resp.json()
    assert res_b["is_mutual"] is True
    assert res_b["status"] == "mutual"
    assert res_b["conversation_id"] is not None


def test_circle_comments(client: TestClient, auth_headers_user_a: dict, auth_headers_user_b: dict):
    """Test interest circles, membership join, and multi-tier nested comment tree."""
    # 1. Create a thematic circle
    circle_resp = client.post(
        "/api/v1/circles",
        headers=auth_headers_user_a,
        json={
            "name": f"胶片摄影社群_{uuid.uuid4().hex[:6]}",
            "category": "艺术展览",
            "description": "探讨 135/120 胶片机、暗房冲洗与光影美学",
        },
    )
    assert circle_resp.status_code == 201
    circle_data = circle_resp.json()
    circle_id = circle_data["id"]

    # 2. User B joins the circle
    join_resp = client.post(f"/api/v1/circles/{circle_id}/join", headers=auth_headers_user_b)
    assert join_resp.status_code == 200
    assert join_resp.json()["status"] == "success"

    # 3. User A posts top-level comment
    top_comment_resp = client.post(
        f"/api/v1/circles/{circle_id}/comments",
        headers=auth_headers_user_a,
        json={
            "content": "欢迎大家分享近期拍摄的胶片作品！",
        },
    )
    assert top_comment_resp.status_code == 201
    top_comment = top_comment_resp.json()
    parent_comment_id = top_comment["id"]

    # 4. User B replies to User A (Nested楼中楼)
    reply_resp = client.post(
        f"/api/v1/circles/{circle_id}/comments",
        headers=auth_headers_user_b,
        json={
            "parent_id": parent_comment_id,
            "content": "上周用 Kodak Portra 400 拍了一组秋叶，颗粒感太棒了！",
        },
    )
    assert reply_resp.status_code == 201
    reply_data = reply_resp.json()
    assert reply_data["parent_id"] == parent_comment_id

    # 5. Fetch nested comment tree
    tree_resp = client.get(f"/api/v1/circles/{circle_id}/comments/tree")
    assert tree_resp.status_code == 200
    tree_data = tree_resp.json()
    assert len(tree_data) >= 1
    root_node = next((n for n in tree_data if n["id"] == parent_comment_id), None)
    assert root_node is not None
    assert len(root_node["replies"]) >= 1
    assert root_node["replies"][0]["id"] == reply_data["id"]
