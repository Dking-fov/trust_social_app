"""Dual-Track Quality Assurance: Track 2 - Browser End-to-End (E2E) Click Tests.
Tests root redirection, interactive Swagger UI documentation (/docs),
and real browser clicks on the Xiaohongshu Portrait Feed frontend according to PRD Acceptance Criteria.
"""

import http.server
import os
import socketserver
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from playwright.sync_api import sync_playwright

from src.main import app

SCREENSHOTS_DIR = Path("tests/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class UvicornServerThread(threading.Thread):
    """Background thread running FastAPI for real browser E2E tests."""
    def __init__(self, host="127.0.0.1", port=8008):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="warning")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


class StaticDistServerThread(threading.Thread):
    """Background thread running static HTTP server for built React frontend."""
    def __init__(self, host="127.0.0.1", port=4180):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.httpd = None

    def run(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory="dist", **kwargs)

            def log_message(self, format, *args):
                pass  # suppress noisy static request logs

        self.httpd = socketserver.TCPServer((self.host, self.port), Handler)
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


@pytest.fixture(scope="module")
def api_server():
    """Start uvicorn server in background and yield base URL."""
    server = UvicornServerThread(port=8008)
    server.start()
    time.sleep(1.0)
    yield "http://127.0.0.1:8008"
    server.stop()


@pytest.fixture(scope="module")
def frontend_server():
    """Start static server for built frontend and yield base URL."""
    server = StaticDistServerThread(port=4180)
    server.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:4180"
    server.stop()


@pytest.fixture(scope="module")
def browser_instance():
    """Launch headless Chromium browser."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


class TestTrack2BrowserE2E:
    """Track 2: Real browser end-to-end click verification."""

    def test_root_portal_redirection_and_swagger_ui_clicks(self, api_server, browser_instance):
        """Track 2 requirement:
        Ensure web portal root redirection (GET / -> /docs), Swagger interactive UI (/docs)
        can be opened in real browser, elements can be clicked, and no 404/500 errors occur.
        """
        page = browser_instance.new_page()
        network_errors = []

        def handle_response(response):
            if response.status >= 400:
                network_errors.append(f"{response.url}: status {response.status}")

        page.on("response", handle_response)

        # 1. Open root URL and verify redirect to /docs
        resp = page.goto(f"{api_server}/", wait_until="networkidle")
        assert resp is not None
        assert page.url.endswith("/docs"), f"Expected redirection to /docs, got {page.url}"
        assert resp.status == 200, f"Expected 200 OK after redirection, got {resp.status}"

        # 2. Verify Swagger UI elements rendered
        page.wait_for_selector(".swagger-ui", timeout=5000)
        assert page.locator(".swagger-ui").is_visible()

        # Capture root portal redirect snapshot
        root_screenshot_path = SCREENSHOTS_DIR / "root_portal.png"
        page.screenshot(path=str(root_screenshot_path))
        assert root_screenshot_path.exists() and root_screenshot_path.stat().st_size > 0

        # 3. Interactive click: expand /health endpoint
        health_summary = page.locator('.opblock-summary:has-text("/health")').first
        health_summary.click()
        page.wait_for_timeout(400)

        # 4. Click 'Try it out' button
        try_out_btn = page.locator("button.try-out__btn").first
        assert try_out_btn.is_visible()
        try_out_btn.click()
        page.wait_for_timeout(400)

        # 5. Click 'Execute' button
        exec_btn = page.locator("button.execute").first
        assert exec_btn.is_visible()
        exec_btn.click()

        # 6. Wait for response table and assert status code 200 returned
        page.wait_for_selector(".live-responses-table", timeout=5000)
        response_table_text = page.locator(".live-responses-table").inner_text()
        assert "200" in response_table_text, f"Expected HTTP 200 in live response table, found: {response_table_text}"
        assert "healthy" in response_table_text

        # Capture swagger docs click snapshot
        swagger_screenshot_path = SCREENSHOTS_DIR / "swagger_docs_click.png"
        page.screenshot(path=str(swagger_screenshot_path))
        assert swagger_screenshot_path.exists() and swagger_screenshot_path.stat().st_size > 0

        # Assert no 404 or 500 errors occurred
        assert len(network_errors) == 0, f"Detected network errors: {network_errors}"
        page.close()

    def test_xiaohongshu_waterfall_feed_and_card_components(self, frontend_server, browser_instance):
        """PRD US-001: Browse trending portrait waterfall grid, multi-column card layout,
        cover, title, creator info, like icon, and lazy loading.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        network_errors = []
        page.on("response", lambda r: network_errors.append(f"{r.url}: {r.status}") if r.status >= 400 else None)

        page.goto(frontend_server, wait_until="networkidle")

        # Verify page header brand
        assert "RED" in page.locator("header").inner_text()
        assert "人像精选" in page.locator("header").inner_text()

        # Verify waterfall grid is rendered with cards
        page.wait_for_selector('[data-testid="waterfall-grid"]', timeout=5000)
        cards = page.locator('[data-testid^="portrait-card-"]')
        card_count = cards.count()
        assert card_count >= 8, f"Expected at least 8 portrait cards, found {card_count}"

        # Verify card contents (image, title, author avatar & nickname, like button)
        first_card = cards.first
        title = first_card.locator("h2").inner_text()
        assert len(title) > 0, "Card must have title"
        assert first_card.locator("img").count() >= 2, "Card must have portrait image and author avatar"

        # Verify lazy loading attribute on cover images
        cover_img = first_card.locator("img").first
        assert cover_img.get_attribute("loading") == "lazy", "Cover image should use loading='lazy'"

        # Verify responsive 2-column layout on mobile viewport (<768px)
        mobile_page = browser_instance.new_page(viewport={"width": 375, "height": 667})
        mobile_page.goto(frontend_server, wait_until="networkidle")
        mobile_columns = mobile_page.locator('[data-testid^="waterfall-col-"]')
        assert mobile_columns.count() == 2, f"Expected 2 columns on mobile, found {mobile_columns.count()}"
        mobile_page.close()

        # Capture waterfall feed snapshot
        feed_screenshot_path = SCREENSHOTS_DIR / "xhs_waterfall_feed.png"
        page.screenshot(path=str(feed_screenshot_path))
        assert feed_screenshot_path.exists()
        assert len(network_errors) == 0, f"Detected network errors: {network_errors}"

        page.close()

    def test_portrait_detail_modal_lightbox_lifecycle(self, frontend_server, browser_instance):
        """PRD US-002: Click card to open modal lightbox, full-size image, caption, tags,
        body scroll locking, and close via close button, backdrop click, or Escape key.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        page.goto(frontend_server, wait_until="networkidle")

        # 1. Click first card
        first_card = page.locator('[data-testid^="portrait-card-"]').first
        card_title = first_card.locator("h2").inner_text()
        first_card.click()

        # 2. Verify modal opened
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', timeout=4000)
        modal = page.locator('[data-testid="portrait-detail-modal"]')
        assert modal.is_visible()

        modal_title = modal.locator("h1").inner_text()
        assert modal_title == card_title, "Modal title must match card title"
        assert modal.locator('[data-testid="modal-close-button"]').is_visible()

        # Check background body scroll locked (overflow: hidden)
        body_overflow = page.evaluate("() => document.body.style.overflow")
        assert body_overflow == "hidden", "Background body scroll must be locked when modal is open"

        # Capture modal screenshot
        modal_screenshot_path = SCREENSHOTS_DIR / "xhs_modal_detail.png"
        page.screenshot(path=str(modal_screenshot_path))
        assert modal_screenshot_path.exists()

        # 3. Close modal via close button
        page.locator('[data-testid="modal-close-button"]').click()
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', state="detached", timeout=3000)
        restored_overflow = page.evaluate("() => document.body.style.overflow")
        assert restored_overflow != "hidden", "Body overflow must be restored after modal close"

        # 4. Open again and close via ESC key
        page.locator('[data-testid^="portrait-card-"]').first.click()
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', timeout=3000)
        page.keyboard.press("Escape")
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', state="detached", timeout=3000)

        # 5. Open again and close via clicking backdrop (outside dialog)
        page.locator('[data-testid^="portrait-card-"]').first.click()
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', timeout=3000)
        page.locator('[data-testid="portrait-detail-modal"]').click(position={"x": 10, "y": 10})
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', state="detached", timeout=3000)

        page.close()

    def test_tag_filter_and_active_pill_highlight(self, frontend_server, browser_instance):
        """PRD US-003: Filter by trending photography tags, active badge highlight (red pill style),
        clear filter via '全部' and re-clicking active tag.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        page.goto(frontend_server, wait_until="networkidle")

        # Click '街拍穿搭' tag
        street_button = page.locator('button:has-text("街拍穿搭")')
        street_button.click()
        page.wait_for_timeout(400)

        # Active tag style: red background pill class
        btn_class = street_button.get_attribute("class") or ""
        assert "bg-red-brand" in btn_class or "text-white" in btn_class, "Active category must be visually highlighted"

        # Test re-clicking active tag restores '全部'
        street_button.click()
        page.wait_for_timeout(400)
        all_button = page.locator('button:has-text("全部")')
        all_class = all_button.get_attribute("class") or ""
        assert "bg-red-brand" in all_class or "text-white" in all_class, "Re-clicking active tag must restore '全部'"

        # Click '情绪人像' and then restore via clicking '全部'
        mood_button = page.locator('button:has-text("情绪人像")')
        mood_button.click()
        page.wait_for_timeout(400)
        all_button.click()
        page.wait_for_timeout(400)
        all_class = all_button.get_attribute("class") or ""
        assert "bg-red-brand" in all_class or "text-white" in all_class

        page.close()

    def test_like_and_unlike_interaction_and_localstorage_persistence(self, frontend_server, browser_instance):
        """PRD US-004: Like/unlike interactive counter updates, icon state change,
        modal synchronization, and persistence in localStorage across page reloads.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        page.goto(frontend_server, wait_until="networkidle")

        first_like_btn = page.locator('[data-testid^="like-btn-"]').first

        # 1. Click like
        first_like_btn.click()
        page.wait_for_timeout(300)

        # Like button should now show active red state
        svg_class = first_like_btn.locator("svg").get_attribute("class") or ""
        assert "fill-red-brand" in svg_class or "text-red-brand" in svg_class

        # Check localStorage has saved like using application key
        storage_value = page.evaluate("() => localStorage.getItem('red_portrait_liked_posts_v1')")
        assert storage_value is not None, "Liked posts must be saved in localStorage"
        assert len(storage_value) > 2, "Storage must contain post IDs array"

        # 2. Verify like state synchronized in Detail Modal
        page.locator('[data-testid^="portrait-card-"]').first.click()
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', timeout=3000)
        modal = page.locator('[data-testid="portrait-detail-modal"]')
        modal_like_btn = modal.locator('[data-testid="modal-like-button"]').first
        modal_svg = modal_like_btn.locator("svg").get_attribute("class") or ""
        assert "fill-red-brand" in modal_svg, "Modal like icon must reflect liked state"

        # Close modal
        page.keyboard.press("Escape")
        page.wait_for_selector('[data-testid="portrait-detail-modal"]', state="detached", timeout=3000)

        # 3. Reload page and verify like state persisted across page reloads
        page.reload(wait_until="networkidle")
        reloaded_like_btn = page.locator('[data-testid^="like-btn-"]').first
        reloaded_svg = reloaded_like_btn.locator("svg").get_attribute("class") or ""
        assert "fill-red-brand" in reloaded_svg or "text-red-brand" in reloaded_svg, "Like state must persist across page reload"

        # 4. Click again to unlike
        reloaded_like_btn.click()
        page.wait_for_timeout(300)
        unliked_svg = reloaded_like_btn.locator("svg").get_attribute("class") or ""
        assert "fill-red-brand" not in unliked_svg

        page.close()

    def test_infinite_scroll_and_all_caught_up_footer(self, frontend_server, browser_instance):
        """PRD US-005: Infinite scroll feed continuation when scrolling near bottom,
        loading indicator, next batch appended, and '已加载全部精彩内容' footer.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        page.goto(frontend_server, wait_until="networkidle")

        # Initial batch on homepage is 8 cards
        cards = page.locator('[data-testid^="portrait-card-"]')
        initial_count = cards.count()
        assert initial_count == 8, f"Initial page batch should be 8, found {initial_count}"

        # Scroll down to trigger infinite scroll load on main feed
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

        # Batch 2 loaded
        assert cards.count() > initial_count, f"Card count should increase after scroll, got {cards.count()}"

        # Now filter by a specific category with limited items (e.g. '街拍穿搭') to test end of feed
        street_btn = page.locator('button:has-text("街拍穿搭")')
        street_btn.click()
        page.wait_for_timeout(600)

        # Scroll to bottom of category
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

        # Verify '已加载全部精彩内容' is displayed
        all_caught_up = page.locator('text=已加载全部精彩内容')
        assert all_caught_up.is_visible(), "Footer must display '已加载全部精彩内容'"

        # Capture infinite scroll screenshot
        scroll_screenshot_path = SCREENSHOTS_DIR / "xhs_infinite_scroll.png"
        page.screenshot(path=str(scroll_screenshot_path))
        assert scroll_screenshot_path.exists()

        page.close()

    def test_search_and_sort_mechanisms_and_empty_state(self, frontend_server, browser_instance):
        """PRD US-006: Search input, empty state with '未找到相关人像笔记' and reset button,
        and sort dropdown option change.
        """
        page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
        page.goto(frontend_server, wait_until="networkidle")

        # 1. Search for nonexistent term
        search_input = page.locator('input[placeholder*="搜索"]')
        search_input.fill("未曾存在的搜索人像关键词XYZ_999")
        page.keyboard.press("Enter")
        page.wait_for_timeout(400)

        # Verify empty state appears
        empty_state = page.locator('h3:has-text("未找到相关人像笔记")')
        assert empty_state.is_visible()

        # Capture search empty state snapshot
        search_screenshot_path = SCREENSHOTS_DIR / "xhs_search_filter.png"
        page.screenshot(path=str(search_screenshot_path))
        assert search_screenshot_path.exists()

        # Click reset filters button
        reset_button = page.locator('button:has-text("重置筛选条件")')
        assert reset_button.is_visible()
        reset_button.click()
        page.wait_for_timeout(400)

        # Cards restored
        cards = page.locator('[data-testid^="portrait-card-"]')
        assert cards.count() >= 8

        # 2. Test sort dropdown
        sort_select = page.locator("select")
        sort_select.select_option(value="latest")
        page.wait_for_timeout(300)
        assert sort_select.input_value() == "latest"

        page.close()
