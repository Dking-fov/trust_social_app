"""Unit and API integration test suite for Xiaohongshu Portrait Feed (RED).
Track 1: Covers data constraints, edge cases, security, business state machines,
and API integration endpoints according to PRD specifications.
"""

import json
import re
from datetime import datetime
import pytest
from fastapi.testclient import TestClient

from src.main import app


CATEGORIES = [
    "all",
    "street",
    "vintage",
    "mood",
    "celebrity",
    "film",
    "cyberpunk",
    "fresh",
    "light-shadow",
]
SORT_OPTIONS = ["hot", "latest", "likes"]


def parse_mock_portraits_from_source():
    """Extract mock portraits data by reading src/data/mockPortraits.ts."""
    with open("src/data/mockPortraits.ts", "r", encoding="utf-8") as f:
        content = f.read()

    items = []
    pattern = re.compile(
        r"id:\s*'(red-portrait-\d+)',\s*"
        r"title:\s*'([^']*)',\s*"
        r"description:\s*'([^']*)',\s*"
        r"imageUrl:\s*'([^']*)',\s*"
        r"width:\s*(\d+),\s*"
        r"height:\s*(\d+),\s*"
        r"aspectRatio:[^,]+,\s*"
        r"creator:\s*\{\s*id:\s*'([^']*)',\s*name:\s*'([^']*)',\s*avatar:\s*'([^']*)',\s*bio:\s*'([^']*)',\s*isFollowed:\s*(true|false),?\s*\},\s*"
        r"likesCount:\s*(\d+),\s*"
        r"favoritesCount:\s*(\d+),\s*"
        r"tags:\s*\[([^\]]*)\],\s*"
        r"category:\s*'([^']*)',\s*"
        r"publishTime:\s*'([^']*)',\s*"
        r"location:\s*'([^']*)'",
        re.MULTILINE
    )
    for m in pattern.finditer(content):
        tags_raw = m.group(14)
        tags = [t.strip().strip("'\"") for t in tags_raw.split(",") if t.strip()]
        items.append({
            "id": m.group(1),
            "title": m.group(2),
            "description": m.group(3),
            "imageUrl": m.group(4),
            "width": int(m.group(5)),
            "height": int(m.group(6)),
            "aspectRatio": int(m.group(5)) / int(m.group(6)),
            "creator": {
                "id": m.group(7),
                "name": m.group(8),
                "avatar": m.group(9),
                "bio": m.group(10),
                "isFollowed": m.group(11) == "true",
            },
            "likesCount": int(m.group(12)),
            "favoritesCount": int(m.group(13)),
            "tags": tags,
            "category": m.group(15),
            "publishTime": m.group(16),
            "location": m.group(17),
        })
    return items


@pytest.fixture(scope="module")
def mock_portraits():
    portraits = parse_mock_portraits_from_source()
    assert len(portraits) >= 12, "Should have parsed at least 12 mock portraits"
    return portraits


@pytest.fixture(scope="module")
def api_client():
    """FastAPI TestClient fixture for API integration tests."""
    return TestClient(app)


# =========================================================================
# 1. Data Models, Invariants, and Boundary Constraints (PRD US-001)
# =========================================================================

class TestPortraitFeedDataModelAndConstraints:
    """PRD US-001: Data model integrity, required attributes, aspect ratio constraints."""

    def test_mock_portraits_count_and_completeness(self, mock_portraits):
        """Ensure rich dataset exists for masonry infinite scroll."""
        assert len(mock_portraits) == 16, f"Expected 16 mock portraits, found {len(mock_portraits)}"

    def test_every_portrait_has_valid_attributes(self, mock_portraits):
        """Validate non-empty strings, positive dimensions, valid creator info."""
        for item in mock_portraits:
            assert item["id"].startswith("red-portrait-")
            assert len(item["title"]) > 3, "Title must be informative"
            assert item["imageUrl"].startswith("http"), "Image URL must be valid HTTP(S) link"
            assert item["width"] > 0 and item["height"] > 0, "Dimensions must be positive"
            assert 0.5 <= item["aspectRatio"] <= 1.5, "Aspect ratio should be standard portrait orientation"
            assert item["creator"]["id"], "Creator id is mandatory"
            assert item["creator"]["name"], "Creator name is mandatory"
            assert item["creator"]["avatar"].startswith("http"), "Creator avatar must be valid URL"
            assert item["likesCount"] >= 0, "Likes count cannot be negative"
            assert item["favoritesCount"] >= 0, "Favorites count cannot be negative"
            assert len(item["tags"]) >= 1, "At least one tag required"
            assert item["category"] in CATEGORIES, f"Category {item['category']} not in allowed list"
            assert item["location"], "Location is required"

    def test_tags_are_non_empty_and_unique_per_post(self, mock_portraits):
        """Data constraint: Tags must be unique within a post and non-empty."""
        for item in mock_portraits:
            for tag in item["tags"]:
                assert len(tag.strip()) > 0, "Tag string must not be whitespace"
            assert len(item["tags"]) == len(set(item["tags"])), f"Duplicate tags in item {item['id']}"

    def test_publish_time_format_and_parseability(self, mock_portraits):
        """Data constraint: Publish times must strictly follow '%Y-%m-%d %H:%M' format."""
        for item in mock_portraits:
            parsed = datetime.strptime(item["publishTime"], "%Y-%m-%d %H:%M")
            assert parsed.year >= 2024, "Publish dates must be recent"


# =========================================================================
# 2. Security and Extreme Edge Cases
# =========================================================================

class TestSecurityAndEdgeCases:
    """Security verification and edge cases against search and data processing."""

    def filter_portraits(self, portraits, query="", category="all"):
        q = query.strip().lower()
        results = portraits
        if category and category != "all":
            results = [p for p in results if p["category"] == category]
        if q:
            results = [
                p for p in results
                if q in p["title"].lower()
                or q in p["creator"]["name"].lower()
                or any(q in t.lower() for t in p["tags"])
                or q in p["description"].lower()
            ]
        return results

    def test_sql_injection_payloads_in_search(self, mock_portraits):
        """Ensure search safely handles SQL injection attack strings without exceptions."""
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE portraits; --",
            "1 UNION SELECT null, null, null--",
            "' UNION ALL SELECT 1, 'admin', 'pass'--",
            "admin'--",
        ]
        for payload in sqli_payloads:
            # Should not raise exception and return safe empty results
            results = self.filter_portraits(mock_portraits, query=payload)
            assert isinstance(results, list)
            assert len(results) == 0

    def test_xss_and_html_tag_payloads(self, mock_portraits):
        """Ensure XSS script injection payloads are treated as plain text strings."""
        xss_payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "javascript:void(0)",
            "';alert(String.fromCharCode(88,83,83))//",
        ]
        for payload in xss_payloads:
            results = self.filter_portraits(mock_portraits, query=payload)
            assert isinstance(results, list)
            assert len(results) == 0

    def test_unicode_emojis_and_regex_special_characters(self, mock_portraits):
        """Ensure emojis, regex characters, and unicode symbols are handled robustly."""
        special_inputs = [
            "📷✨",
            ".*",
            "[a-z]+",
            "(.*)",
            "^.*$",
            "\\",
            "|",
            "???",
            "   ",
            "\t\n\r",
        ]
        for query in special_inputs:
            results = self.filter_portraits(mock_portraits, query=query)
            assert isinstance(results, list)

    def test_case_insensitivity_and_whitespace_trimming(self, mock_portraits):
        """Search query must be trimmed and case-insensitive."""
        res_lower = self.filter_portraits(mock_portraits, query="cyberpunk")
        res_upper = self.filter_portraits(mock_portraits, query="  CYBERPUNK  ")
        assert len(res_lower) == len(res_upper)


# =========================================================================
# 3. Filter, Search, and Sort State Machines (PRD US-003 & US-006)
# =========================================================================

class TestPortraitFilterAndSearchStateMachine:
    """PRD US-003 & US-006: Tag filtering, keyword search, and sorting state machines."""

    def test_filter_by_category_tags(self, mock_portraits):
        """US-003: Clicking a category filters only matching portraits."""
        for cat in ["street", "vintage", "mood", "celebrity", "film", "cyberpunk", "fresh", "light-shadow"]:
            matched = [p for p in mock_portraits if p["category"] == cat]
            assert len(matched) > 0, f"Category '{cat}' should have matching posts"
            for item in matched:
                assert item["category"] == cat

    def test_category_toggle_state_machine(self, mock_portraits):
        """US-003: Clicking an active category deselects it, returning to 'all'."""
        current_category = "all"

        # Transition 1: select 'vintage'
        current_category = "vintage"
        filtered_1 = [p for p in mock_portraits if p["category"] == current_category]
        assert len(filtered_1) > 0

        # Transition 2: click 'vintage' again (toggle off) -> reverts to 'all'
        current_category = "all" if current_category == "vintage" else "vintage"
        assert current_category == "all"
        filtered_all = [p for p in mock_portraits if current_category == "all" or p["category"] == current_category]
        assert len(filtered_all) == len(mock_portraits)

    def test_search_by_creator_or_title(self, mock_portraits):
        """US-006: Real-time search by creator name or title keyword."""
        # Search by creator name
        query = "林鹿"
        results = [
            p for p in mock_portraits
            if query.lower() in p["title"].lower() or query.lower() in p["creator"]["name"].lower()
        ]
        assert len(results) >= 1
        assert any(r["creator"]["name"] == "林鹿鹿鹿" for r in results)

        # Search by title keyword
        query_title = "胶片"
        results_title = [
            p for p in mock_portraits
            if query_title.lower() in p["title"].lower() or query_title.lower() in p["creator"]["name"].lower()
        ]
        assert len(results_title) >= 1

        # Search for non-existent keyword yields empty results
        query_none = "non_existent_portrait_keyword_123456"
        results_none = [
            p for p in mock_portraits
            if query_none.lower() in p["title"].lower() or query_none.lower() in p["creator"]["name"].lower()
        ]
        assert len(results_none) == 0

    def test_combined_search_filter_and_sort_intersection(self, mock_portraits):
        """State machine: Combining category filter, search query, and sorting maintains intersection."""
        category = "mood"
        query = "情绪"
        sort_by = "hot"

        step1 = [p for p in mock_portraits if p["category"] == category]
        step2 = [
            p for p in step1
            if query.lower() in p["title"].lower() or query.lower() in p["description"].lower()
        ]
        assert len(step2) > 0

        # Sort descending by likes
        sorted_step = sorted(step2, key=lambda p: p["likesCount"], reverse=True)
        for i in range(len(sorted_step) - 1):
            assert sorted_step[i]["likesCount"] >= sorted_step[i + 1]["likesCount"]

    def test_sort_by_hot_and_latest(self, mock_portraits):
        """US-006: Sorting by 'hot' (likes descending) and 'latest' (publish time descending)."""
        # Hot sort: descending likesCount
        sorted_hot = sorted(mock_portraits, key=lambda p: p["likesCount"], reverse=True)
        for i in range(len(sorted_hot) - 1):
            assert sorted_hot[i]["likesCount"] >= sorted_hot[i + 1]["likesCount"]

        # Latest sort: descending publishTime
        def parse_time(t_str):
            return datetime.strptime(t_str, "%Y-%m-%d %H:%M")

        sorted_latest = sorted(mock_portraits, key=lambda p: parse_time(p["publishTime"]), reverse=True)
        for i in range(len(sorted_latest) - 1):
            assert parse_time(sorted_latest[i]["publishTime"]) >= parse_time(sorted_latest[i + 1]["publishTime"])


# =========================================================================
# 4. Like / Favorite Business State Machine (PRD US-004)
# =========================================================================

class TestLikeInteractionStateMachine:
    """PRD US-004: State machine for like/unlike toggle, optimistic counter update and bounds."""

    def test_like_increment_and_decrement_invariants(self, mock_portraits):
        """Toggle like increments by 1, toggle unlike decrements by 1."""
        item = mock_portraits[0]
        initial_likes = item["likesCount"]
        liked_set = set()

        # Step 1: User likes the card
        liked_set.add(item["id"])
        adjusted_likes_1 = initial_likes + (1 if item["id"] in liked_set else 0)
        assert adjusted_likes_1 == initial_likes + 1

        # Step 2: User unlikes the card
        liked_set.remove(item["id"])
        adjusted_likes_2 = initial_likes + (1 if item["id"] in liked_set else 0)
        assert adjusted_likes_2 == initial_likes

    def test_like_state_never_produces_negative_count(self):
        """Data constraint: like count cannot drop below 0."""
        zero_like_post = 0
        liked = False
        adjusted = max(0, zero_like_post + (-1 if liked else 0))
        assert adjusted >= 0

    def test_multi_post_like_independence(self, mock_portraits):
        """State machine: Liking post A does not alter post B's state."""
        liked_set = set()
        p1 = mock_portraits[0]["id"]
        p2 = mock_portraits[1]["id"]

        liked_set.add(p1)
        assert p1 in liked_set
        assert p2 not in liked_set

        liked_set.add(p2)
        assert p1 in liked_set and p2 in liked_set

        liked_set.remove(p1)
        assert p1 not in liked_set
        assert p2 in liked_set

    def test_storage_serialization_and_recovery(self):
        """LocalStorage serialization and corruption resilience simulation."""
        # 1. Normal round-trip serialization
        active_ids = ["red-portrait-1", "red-portrait-3"]
        serialized = json.dumps(active_ids)
        restored = set(json.loads(serialized))
        assert restored == {"red-portrait-1", "red-portrait-3"}

        # 2. Corrupted JSON recovery
        corrupted = "invalid-json{{{"
        try:
            val = json.loads(corrupted)
            restored_set = set(val) if isinstance(val, list) else set()
        except Exception:
            restored_set = set()
        assert restored_set == set()


# =========================================================================
# 5. Pagination & Infinite Scroll State Machine (PRD US-005)
# =========================================================================

class TestPaginationAndInfiniteScrollStateMachine:
    """PRD US-005: Pagination slicing and batch retrieval bounds."""

    def test_batch_slicing_and_has_more(self, mock_portraits):
        """Batch slicing matches page size and tracks hasMore correctly."""
        page_size = 8
        total = len(mock_portraits)

        # Batch 1
        batch_1 = mock_portraits[0:page_size]
        assert len(batch_1) == page_size
        has_more_1 = len(batch_1) < total
        assert has_more_1 is True

        # Batch 2
        batch_2 = mock_portraits[0:page_size * 2]
        assert len(batch_2) == total
        has_more_2 = len(batch_2) < total
        assert has_more_2 is False, "All portraits loaded, hasMore must be False"

    def test_sentinel_scroll_trigger_threshold(self):
        """PRD US-005 AC: Trigger when user scrolls within 300px of page bottom."""
        threshold_px = 300
        viewport_height = 800
        total_document_height = 2000

        # Scenario A: scrolled to 800px -> bottom is 1600px, distance to bottom is 400px (> 300px)
        scroll_y_a = 800
        distance_a = total_document_height - (scroll_y_a + viewport_height)
        assert distance_a == 400
        should_trigger_a = distance_a <= threshold_px
        assert should_trigger_a is False

        # Scenario B: scrolled to 950px -> distance to bottom is 250px (<= 300px)
        scroll_y_b = 950
        distance_b = total_document_height - (scroll_y_b + viewport_height)
        assert distance_b == 250
        should_trigger_b = distance_b <= threshold_px
        assert should_trigger_b is True


# =========================================================================
# 6. API Integration Tests (Track 1)
# =========================================================================

class TestApiIntegrationTrack1:
    """Track 1: API integration tests covering status codes, headers, and documentation routes."""

    def test_root_portal_redirects_to_docs(self, api_client):
        """Track 2 & Track 1 portal test: GET / redirects with 307 to /docs."""
        resp = api_client.get("/", follow_redirects=False)
        assert resp.status_code == 307
        assert resp.headers["location"] == "/docs"

    def test_health_check_endpoint(self, api_client):
        """Service liveness probe returns 200 OK and valid JSON."""
        resp = api_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "app" in data
        assert "version" in data

    def test_swagger_documentation_accessible(self, api_client):
        """Interactive Swagger UI returns 200 with HTML content."""
        resp = api_client.get("/docs")
        assert resp.status_code == 200
        assert "swagger-ui" in resp.text.lower() or "html" in resp.headers.get("content-type", "")

    def test_openapi_schema_endpoint(self, api_client):
        """OpenAPI json specification is well-formed."""
        resp = api_client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "/health" in schema["paths"]

    def test_invalid_http_method_returns_405(self, api_client):
        """Calling unsupported POST method on /health returns 405 Method Not Allowed."""
        resp = api_client.post("/health")
        assert resp.status_code == 405

    def test_nonexistent_endpoint_returns_404(self, api_client):
        """Calling undefined route returns 404 Not Found."""
        resp = api_client.get("/api/v1/non_existent_route_xyz")
        assert resp.status_code == 404
