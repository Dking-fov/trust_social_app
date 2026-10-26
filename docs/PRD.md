# xiaohongshu-portrait-feed - 产品需求规格说明书 (PRD)

## 概述
A responsive Xiaohongshu-style (RED) visual exploration homepage dedicated to trending portrait photography. It features a responsive masonry waterfall grid showcasing popular portrait posts with high-resolution imagery, creator profiles, engagement metrics (likes, favorites), search and filter capabilities by trending tags, interactive lightbox preview with detailed creator notes, and smooth infinite scroll loading.

## 核心特性
- Responsive Masonry Waterfall Layout (双列/多列响应式瀑布流展示人物照片卡片，卡片自适应高度与平滑加载)
- Trending Portrait Card Component (包含高质量人物照片封面、标题、创作者头像与昵称、点赞数交互与高亮状态)
- Interactive Detail Modal / Lightbox (点击照片卡片弹出全屏/半屏详情浮层，支持高清大图预览、详细笔记描述、标签及互动区)
- Tag & Category Filter Bar (热门人物摄影标签导航栏，如'街拍穿搭'、'复古写真'、'情绪人像'、'艺人神颜'、'日系胶片'等快速筛选与高亮)
- Search and Sort Mechanism (支持按关键词搜索人物或摄影师，并支持按'最热'、'最新'、'点赞最多'等维度排序)
- Infinite Scroll & Mock Data Generation (基于虚拟滚动或触底无限加载模拟流行热度人物照片流，内置丰富高清人像摄影Mock数据)
- Like & Favorite Interactive Feedback (卡片及详情弹窗支持点赞收藏，具有微动效并实时更新点赞计数与本地持久化)

## 用户故事与验收标准
### US-001: Browse Trending Portrait Waterfall Grid
- **角色与目标**: visitor, to view a dynamic waterfall (masonry) feed of trending portrait photos on the homepage, I can effortlessly browse visually appealing high-popularity portrait photographs in a layout familiar to Xiaohongshu users
- **验收条件**:
  - [ ] Given the user visits the homepage, when the page loads, then high-resolution portrait cards are rendered in an unbalanced multi-column waterfall grid (2 columns on mobile, 3-4 columns on desktop).
  - [ ] Each card displays the portrait image cover, post title, author avatar, author nickname, and like count with an icon.
  - [ ] Images use progressive loading or skeleton shimmer placeholders before loading to avoid layout shifts.
  - [ ] Broken image links fallback gracefully to an elegant default portrait placeholder without breaking column flow.
### US-002: View Portrait Details and High-Res Preview
- **角色与目标**: user, to click any portrait card to open an interactive modal lightbox, I can inspect the full-resolution photo, read the creator's caption/tags, and see engagement details
- **验收条件**:
  - [ ] Given a portrait card on the feed, when the user clicks or taps the card, then a modal pops up displaying the full-size image alongside post text, author info, publication date, and associated tags.
  - [ ] The modal can be closed via a close button ('X'), clicking the background backdrop, or pressing the Esc key on keyboard.
  - [ ] Scrolling the modal content locks the background body scroll to prevent disorientation.
### US-003: Filter Portraits by Trending Tags
- **角色与目标**: user, to filter portrait posts by trending photography tags (e.g., '街拍穿搭', '情绪人像', '复古写真', '日系胶片'), I can quickly discover specific styles of trending person portraits that match my interests
- **验收条件**:
  - [ ] Given the top tag navigation bar, when the user clicks a specific category tag, then the waterfall feed filters instantaneously to show only cards matching that tag.
  - [ ] The active tag is visually highlighted with an active badge style (Xiaohongshu red pill style).
  - [ ] Clicking '全部' (All) or re-clicking the active tag clears the filter and restores all trending portraits.
### US-004: Like / Unlike Portrait Posts
- **角色与目标**: user, to click the like heart icon on any card or detail modal, I can express appreciation for popular portrait creators and see the like counter update immediately
- **验收条件**:
  - [ ] Given an unliked portrait card, when the user clicks the heart icon, then the icon turns solid red with a subtle spring bounce animation and the like counter increments by 1.
  - [ ] When the user clicks the liked heart icon again, it reverts to the outline state and decrements by 1.
  - [ ] Like state is synchronized between the feed card and the detail modal.
  - [ ] Like states persist in browser localStorage across page reloads.
### US-005: Infinite Scroll Feed Continuation
- **角色与目标**: user, more trending portraits to load automatically as I scroll near the bottom of the feed, I can continuously enjoy an uninterrupted discovery experience without manual pagination clicks
- **验收条件**:
  - [ ] Given the user scrolls within 300px of the page bottom, when scrolling stops or reaches threshold, then a loading indicator appears and the next batch of trending portrait cards is appended to the grid.
  - [ ] If no more items are available, a subtle footer message '已加载全部精彩内容' (All caught up) is displayed.
  - [ ] Throttling/debouncing is applied to scroll event listeners to prevent duplicate requests and maintain 60fps.
### US-006: Search and Sort Trending Portraits
- **角色与目标**: user, to search portraits by creator name or title keyword, and sort by '最热' (Hot) or '最新' (Latest), I can locate specific portraits and control the ranking order
- **验收条件**:
  - [ ] Given the search input in the header, when the user types a keyword, the cards filter in real-time or upon pressing Enter.
  - [ ] Given the sort switcher ('最热' / '最新'), clicking sorts the feed immediately by like count descending or publish time descending.
  - [ ] When a search yields 0 results, an empty state illustration with '未找到相关人像笔记' and a reset button is shown.