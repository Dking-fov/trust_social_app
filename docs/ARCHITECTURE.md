# soulred-social-platform - 系统架构设计规格书

## 技术栈选型
- **authentication**: python-jose 3.3.0, passlib[bcrypt] 1.7.4
- **database**: SQLite 3 + SQLAlchemy 2.0 (AsyncIO with aiosqlite)
- **encryption**: Cryptography 43.0+ (AES-256-GCM / PBKDF2HMAC)
- **frontend**: HTML5, CSS3 (Modern Dual-Column CSS Grid/Flex Waterfall, Dark Aesthetic UI), Vanilla ES6 JavaScript (Native WebSockets, Lightbox, Canvas Radar Animation)
- **language**: Python 3.12
- **realtime**: FastAPI WebSocket + asyncio In-Memory PubSub/Broadcast Manager
- **server**: Uvicorn 0.32.0+
- **testing**: pytest 8.3+, pytest-asyncio 0.24+, httpx 0.27+
- **validation**: Pydantic 2.9+ (pydantic-settings 2.5+)
- **web_framework**: FastAPI 0.115.0+

## 第三方依赖清单
- fastapi>=0.115.0
- uvicorn[standard]>=0.32.0
- sqlalchemy>=2.0.35
- aiosqlite>=0.20.0
- pydantic>=2.9.0
- pydantic-settings>=2.5.0
- cryptography>=43.0.0
- python-jose[cryptography]>=3.3.0
- passlib[bcrypt]>=1.7.4
- python-multipart>=0.0.12
- pytest>=8.3.0
- pytest-asyncio>=0.24.0
- httpx>=0.27.0
- websockets>=13.0

## 规划文件树结构 ({len(new_arch.file_tree)} 个模块)
- `soulred/config.py`: 全局配置中心，通过 Pydantic Settings 管理数据库连接、JWT 密钥、AES-256 加密盐、限流阈值及风控策略配置。 (Symbols: Settings, get_settings)
- `soulred/database.py`: 异步数据库引擎与会话工厂，声明式 Base 模型及数据库自动化初始化生命周期管理。 (Symbols: Base, engine, async_session_maker, get_db, init_db)
- `soulred/models/user.py`: 用户身份、个人资料档案、真实度认证信息、隐私偏好设置与灵魂星盘标签的 SQLAlchemy ORM 实体定义。 (Symbols: User, UserProfile, UserVerification, UserPrivacySettings, SoulStarChart)
- `soulred/models/feed.py`: 小红书式图文动态、多图媒体宽高比元数据、话题标签与点赞收藏关系的 ORM 实体定义。 (Symbols: Post, PostMedia, Tag, PostLike, PostBookmark)
- `soulred/models/social.py`: 社交匹配关系、IM 对话会话、私信消息、亲密度等级记录、兴趣圈子与多层级楼中楼评论的 ORM 实体定义。 (Symbols: MatchRelation, ChatConversation, ChatMessage, IntimacyRecord, Circle, CircleMember, Comment)
- `soulred/schemas/user.py`: 用户注册登录、个人资料展示/编辑、隐私中心开关及真实度凭证提交的 Pydantic 请求/响应契约模型。 (Symbols: UserRegisterRequest, UserLoginRequest, TokenResponse, UserProfileResponse, UserPrivacyUpdateRequest, VerificationSubmitRequest)
- `soulred/schemas/feed.py`: 动态发布、草稿箱暂存、双列瀑布流卡片展示（含图片宽高比）、详情浮层及点赞互动的 Pydantic 契约模型。 (Symbols: PostCreateRequest, PostCardResponse, PostDetailResponse, FeedQueryFilter, PostLikeResponse, DraftSaveRequest)
- `soulred/schemas/social.py`: 灵魂雷达匹配、每日精选互选、WebSocket 消息数据包、亲密度成长数据、兴趣圈子与多层级评论树的 Pydantic 契约模型。 (Symbols: RadarMatchResponse, DailyPickActionRequest, DailyPickCardResponse, ChatMessagePayload, ChatMessageResponse, IntimacyLevelResponse, CircleResponse, CommentCreateRequest, CommentTreeResponse)
- `soulred/utils/crypto.py`: 基于 AES-256-GCM 的敏感字段加解密工具，以及手机号、姓名等隐私数据的脱敏掩码处理器。 (Symbols: CryptoManager, encrypt_sensitive_data, decrypt_sensitive_data, mask_phone_number, mask_real_name)
- `tests/conftest.py`: Pytest 共享测试夹具，提供 SQLite in-memory 异步测试数据库、HTTPX 测试客户端、预置模拟用户与测试授权 Token。 (Symbols: async_db_session, test_client, auth_headers_user_a, auth_headers_user_b, sample_posts_data)
- `soulred/services/auth_service.py`: 用户身份认证服务，包含 Bcrypt 口令哈希校验、JWT 鉴权凭证签发与身份核验逻辑。 (Symbols: AuthService, hash_password, verify_password, create_access_token, verify_access_token, register_user, authenticate_user)
- `soulred/services/matching_service.py`: 灵魂与兴趣匹配核心算法服务，负责星盘契合度打分、雷达实时在线匹配、青藤风格每日精选生成与双向心动奔赴触发。 (Symbols: MatchingService, calculate_affinity_score, search_radar_matches, generate_daily_picks, handle_pick_action, check_mutual_spark, can_send_stranger_message)
- `soulred/services/feed_service.py`: 双列瀑布流动态检索与分发服务，支持频道过滤（推荐/附近/关注）、图片宽高比占位计算、草稿自动保存与点赞联动。 (Symbols: FeedService, create_post, get_waterfall_feed, get_post_detail, toggle_post_like, save_draft, get_draft)
- `soulred/services/im_service.py`: WebSocket 实时私信通讯引擎，负责长连接注册分发、离线消息补偿、已读/撤回/引用处理及陌生人单日发言限频。 (Symbols: ConnectionManager, IMService, connect_client, disconnect_client, send_private_message, mark_messages_read, recall_message, get_conversation_history)
- `soulred/services/intimacy_service.py`: 亲密度进阶状态机服务，根据聊天字数与连续互动天数累积 EXP，驱动密友树等级升级并解锁专属装扮徽章。 (Symbols: IntimacyService, record_chat_interaction, calculate_intimacy_level, get_intimacy_status, unlock_decorations)
- `soulred/services/moderation_service.py`: 多模态内容风控合规审核服务，执行敏感词实时拦截、垃圾广告识别、举报处理与违规用户信用惩戒。 (Symbols: ModerationService, check_text_compliance, check_image_compliance, sanitize_text, report_violation, apply_penalty)
- `soulred/services/circle_service.py`: 兴趣圈子与社群互动服务，负责圈子加入/退出、最新/热门动态置顶、楼中楼多级评论递归树构建。 (Symbols: CircleService, list_circles, join_circle, leave_circle, create_comment, get_comments_tree, pin_comment, toggle_comment_like)
- `tests/test_matching_algorithm.py`: 灵魂匹配契合度算法、每日精选流转、陌生人单日限制与双向奔赴触发逻辑的独立单元测试集。 (Symbols: test_affinity_score_calculation, test_radar_match_filtering, test_daily_picks_cycle, test_stranger_greeting_rate_limit, test_mutual_spark_connection)
- `tests/test_feed_and_circles.py`: 动态发布、瀑布流宽高比预留、频道筛选、圈子多层评论树与风控拦截的业务逻辑集成测试集。 (Symbols: test_create_post_success, test_waterfall_aspect_ratio_computation, test_feed_channel_filtering, test_circle_nested_comments_tree, test_content_moderation_interception)
- `soulred/api/deps.py`: FastAPI 统一依赖注入容器，提供数据库会话、当前登录用户提取、权限检查与服务单例注入。 (Symbols: get_current_user, get_current_active_user, get_db_session, get_auth_service, get_feed_service, get_matching_service, get_im_service)
- `soulred/api/auth.py`: 用户注册、密码登录与个人登录凭证自检的 RESTful 路由控制器。 (Symbols: router, register, login, get_me)
- `soulred/api/feeds.py`: 双列瀑布流动态获取、图文发布、详情浮层拉取、点赞收藏与草稿存取的 RESTful 路由控制器。 (Symbols: router, get_feed, create_post_endpoint, get_post_detail_endpoint, like_post, save_user_draft, get_user_draft)
- `soulred/api/matching.py`: 灵魂星盘测试提交、在线雷达扫描匹配、青藤每日精选推荐与心动互选的 RESTful 路由控制器。 (Symbols: router, get_radar_matches, get_daily_picks, action_daily_pick, submit_star_chart_quiz)
- `soulred/api/chat.py`: WebSocket 实时私信长连接端点，以及历史消息查询、智能破冰话题建议与亲密度展示的 HTTP 辅助路由。 (Symbols: router, websocket_chat_endpoint, get_conversations, get_chat_history, get_icebreaker_recommendations, get_intimacy_info)
- `soulred/api/circles.py`: 兴趣圈子分类列表、加入社群、发布圈子动态与楼中楼多级评论互动的 RESTful 路由控制器。 (Symbols: router, get_circles_list, join_circle_endpoint, get_circle_posts, create_comment_endpoint, get_post_comments)
- `soulred/api/profile.py`: 个人主页展示/编辑、10 秒语音名片设置、真实度认证加密凭证提交与隐私中心偏好管理的 RESTful 路由控制器。 (Symbols: router, get_user_profile, update_user_profile, submit_verification, get_privacy_settings, update_privacy_settings)
- `soulred/main.py`: FastAPI 应用程序核心主入口，集成全局 CORS、异常拦截中间件、静态文件挂载与生命周期管理。 (Symbols: app, lifespan, main)
- `soulred/static/index.html`: 高美感单页应用主骨架，集成双列瀑布流广场、沉浸式卡片详情 Lightbox 浮层、灵魂雷达扫描浮动视窗与即时聊天面板。 (Symbols: <!DOCTYPE html>, app-container, waterfall-container, radar-modal, chat-drawer, detail-lightbox)
- `soulred/static/css/style.css`: 全局现代化暗色极简设计风格样式表，包含双列流错落网格、骨架屏微动效、卡片点赞心动数字联动与雷达扫描波纹动效。 (Symbols: :root, .waterfall-grid, .note-card, .radar-canvas, .intimacy-badge, .lightbox-overlay)
- `soulred/static/js/app.js`: 前端客户端状态与交互管理脚本，驱动瀑布流无限滚动、卡片图片比例自适应计算、WebSocket 自动重连与私信收发。 (Symbols: SoulRedApp, initWaterfall, initWebSocket, renderCards, openPostLightbox, triggerRadarScan, sendChatMessage)
- `tests/test_auth_and_profile.py`: 用户注册登录鉴权、个人档案定制、隐私中心开关与 AES-256 凭证加密脱敏的端到端接口测试集。 (Symbols: test_user_register_and_login, test_profile_update_and_voice_intro, test_privacy_settings_distance_hidden, test_verification_encryption_and_masking)
- `tests/test_im_and_intimacy.py`: WebSocket 实时私信收发、智能破冰话术推荐、亲密度等级解锁与消息撤回已读标记的端到端测试集。 (Symbols: test_websocket_realtime_chat_delivery, test_icebreaker_recommendations, test_intimacy_level_progression, test_message_recall_and_read_receipt)

## 设计原则
### 1. 架构设计原则与分层体系 (Architectural Principles & Layering)
- **整洁分层与单一职责 (Clean Architecture & SRP)**：系统严格划分为数据持久化层 (Persistence/Schemas)、核心业务与算法服务层 (Domain Services)、以及 Web API 与交互呈现层 (API & Presentation)。层级间单向依赖，高层依赖抽象契约，杜绝反向循环依赖。
- **全异步无阻塞 I/O (AsyncIO & Reactive Concurrency)**：基于 Python 3.12 原生 AsyncIO、FastAPI 与 SQLAlchemy 2.0 异步引擎 (aiosqlite)，实现双列瀑布流 Feed 高并发检索与 WebSocket 毫秒级私信收发。
- **双列瀑布流防抖动与骨架屏预计算 (CLS Elimination)**：在数据模型层持久化存储图片宽高比 (aspect_ratio)，服务端直接下发卡片相对高度，前端据此在图片加载完成前精确预留占位高度，杜绝布局偏移 (Cumulative Layout Shift)，保证 60 FPS 滚动流畅度。
- **混合社交模式解耦 (Dual Social Engine)**：将“小红书式图文消费/生活切片分享”与“Soul/青藤式灵魂算法契合/亲密度进阶”解耦为独立业务服务，通过统一的社交关系链状态机连接。

### 2. 模块划分与并行研发策略 (Modularity & Parallel Engineering Strategy)
- **Module 1 (module_data_persistence)**：由资深数据工程师负责，产出数据库实体、Pydantic 契约模型与加解密基础设施。对外提供稳定的数据类型与持久化接口。
- **Module 2 (module_core_domain)**：由算法与核心业务工程师负责，并发实现灵魂契合度计算 (向量余弦/Jaccard 混合加权)、双列流分发过滤、WebSocket 连接管理、AI 敏感词风控拦截、以及亲密度树等级跃迁算法。
- **Module 3 (module_api_web_interface)**：由全栈/API 工程师负责，挂载 FastAPI 路由端点、依赖注入鉴权中间件、静态资源托管，并基于现代暗色高对比度审美 (Linear/Soul/RED 风格) 构建双列瀑布流、动态详情 Lightbox 浮层与雷达扫描动效。

### 3. 数据安全与隐私合规防护 (Security, Privacy & Compliance)
- **敏感隐私加密存储 (AES-256-GCM)**：手机号、实名认证信息、职业证书等 PII 敏感信息在写入数据库前通过 Cryptography AES-256-GCM 加密，数据库底层不存明文；响应层严格执行脱敏脱壳掩码展示。
- **防骚扰与限频风控 (Anti-Harassment Throttling)**：陌生人单日仅限发送 1 条纯文本招呼，禁止多媒体附件；双向“心动奔赴”后方可解锁多媒体会话并激活亲密度成长链。
- **多层级内容安全审查 (Multi-tiered Moderation)**：文本发布实时执行敏感词正则前置拦截；图片与富文本经由风控服务多模态打标，可疑内容标记存入审核缓冲池并在前台实施软隔离。

### 4. 测试与验证策略 (Testing & Reliability)
- **分层测试体系**：单元测试覆盖核心算法 (契合度打分、亲密度进阶状态机、敏感词脱敏)，集成测试覆盖完整 RESTful API 契约，异步端到端测试验证 WebSocket 双向通讯和实时收发。
- **测试隔离与可复现性**：使用 pytest-asyncio 与 SQLite in-memory 异步测试夹具，测试之间自动重置数据库状态，保障 CI/CD 流水线百毫秒级快速运行。