# soulred-social-platform - 系统架构设计规格书

## 技术栈选型
- **cryptography**: Cryptography (AES-256-GCM) + Passlib (bcrypt) + PyJWT
- **database**: SQLAlchemy 2.0+ (SQLite in-memory for testing, PostgreSQL ready)
- **framework**: FastAPI 0.115+ (ASGI, Starlette)
- **frontend_portal**: HTML5 / CSS3 Responsive Dual-Column Waterfall (Native Vanilla JS, zero bundle build required)
- **language**: Python 3.12
- **realtime**: Starlette WebSocket + ConnectionManager with Heartbeat & Backoff
- **testing**: pytest 8.3+, pytest-asyncio, httpx (TestClient)
- **validation**: Pydantic v2 + Pydantic-Settings

## 第三方依赖清单
- fastapi>=0.115.0
- uvicorn[standard]>=0.30.0
- pydantic>=2.8.0
- pydantic-settings>=2.4.0
- sqlalchemy>=2.0.30
- passlib[bcrypt]>=1.7.4
- pyjwt>=2.9.0
- cryptography>=43.0.0
- python-multipart>=0.0.9
- httpx>=0.27.0
- pytest>=8.3.0
- pytest-asyncio>=0.24.0
- websockets>=12.0

## 规划文件树结构 ({len(state.architecture.file_tree)} 个模块)
- `requirements.txt`: 项目依赖声明文件，涵盖 Web、数据库、安全加解密、WebSocket 及自动化测试套件 (Symbols: fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, passlib, pyjwt, cryptography, httpx, pytest, pytest-asyncio, websockets)
- `soulred/__init__.py`: SoulRed 平台核心包初始化及版本号声明 (Symbols: __version__)
- `soulred/config.py`: 基于 Pydantic-Settings 的全局配置管理，包括数据库连接串、JWT 密钥、AES 密钥及服务端口配置 (Symbols: Settings, get_settings)
- `soulred/database.py`: SQLAlchemy 数据库引擎、连接会话工厂、声明基类及初始化表结构入口 (Symbols: engine, SessionLocal, Base, get_db, init_db)
- `soulred/utils/__init__.py`: 工具类模块初始化 (Symbols: )
- `soulred/utils/crypto.py`: AES-256-GCM 敏感数据加解密工具、bcrypt 密码哈希与 JWT 身份凭证生成校验工具 (Symbols: encrypt_field, decrypt_field, hash_password, verify_password, create_access_token, decode_access_token)
- `soulred/models/__init__.py`: 导出所有 SQLAlchemy ORM 模型以供持久化与数据库表自动迁移注册 (Symbols: Base, User, UserProfile, VerificationBadge, PrivacySetting, Post, PostImage, PostLike, PostDraft, PersonalityQuizResult, DailyRecommendation, CrushMatch, ChatConversation, ChatMessage, IntimacyRecord, InterestCircle, CircleMember, CircleComment)
- `soulred/models/base.py`: 通用模型基类，提供 UUID 主键、创建/更新时间戳及软删除支持 (Symbols: TimestampMixin, UUIDPrimaryKeyMixin, SoftDeleteMixin)
- `soulred/models/user.py`: 用户主账号、个性化社交主页档案（3D虚拟形象/语音名片/MBTI）、青藤式学历/职业认证徽章与隐私配置数据模型 (Symbols: User, UserProfile, VerificationBadge, PrivacySetting, VerificationStatusEnum, GenderEnum)
- `soulred/models/post.py`: 小红书风格动态帖子、自适应多图卡片元数据（1:1/3:4/4:3）、点赞记录及草稿暂存模型 (Symbols: Post, PostImage, PostLike, PostDraft, AspectRatioEnum, PostStatusEnum, MoodTagEnum)
- `soulred/models/match.py`: 个性/价值观测试答卷星盘、青藤风格每日精选卡片推送记录及双向奔赴心动互选模型 (Symbols: PersonalityQuizResult, DailyRecommendation, CrushMatch, CrushStatusEnum)
- `soulred/models/chat.py`: 即时通讯会话、私信消息体（文本/表情/语音/图片/已读/撤回）与亲密度点亮经验值模型 (Symbols: ChatConversation, ChatMessage, IntimacyRecord, MessageTypeEnum, IntimacyLevelEnum)
- `soulred/models/circle.py`: 兴趣圈子社群、成员归属关系以及多层级楼中楼互动评论树模型 (Symbols: InterestCircle, CircleMember, CircleComment, CircleRoleEnum, CircleCategoryEnum)
- `soulred/schemas/__init__.py`: 统一导出系统各模块 Pydantic 请求与响应契约 Schema (Symbols: UserCreate, UserLogin, UserProfileResponse, PostCreate, PostWaterfallCard, PostDetailResponse, QuizSubmitSchema, DailyCardResponse, MessageSendSchema, MessageResponse, CircleResponse, CommentResponse)
- `soulred/schemas/user.py`: 用户注册、登录凭证、社交档案更新、隐私中心设置与官方实名/学历认证 Pydantic 校验模型 (Symbols: UserCreate, UserLogin, TokenResponse, UserProfileUpdate, UserProfileResponse, PrivacySettingSchema, VerificationSubmitSchema)
- `soulred/schemas/post.py`: 小红书双列瀑布流卡片响应体、动态图文发布、本地草稿暂存及点赞交互 Pydantic 校验模型 (Symbols: PostCreate, PostImageSchema, PostWaterfallCard, PostDetailResponse, PostDraftSave, PostLikeToggleResponse)
- `soulred/schemas/match.py`: 灵魂测试提交、Soul 雷达匹配卡片（相似度>80%）、每日推荐卡片与双向奔赴心动操作 Pydantic 校验模型 (Symbols: QuizSubmitSchema, QuizResultResponse, SoulRadarMatchCard, DailyCardResponse, CrushActionRequest, CrushActionResponse)
- `soulred/schemas/chat.py`: WebSocket/REST 实时消息收发、智能破冰话术推荐、亲密度等级进展与消息撤回 Pydantic 校验模型 (Symbols: MessageSendSchema, MessageResponse, ConversationSummaryResponse, IcebreakerResponse, IntimacyStatusResponse, MessageRecallRequest)
- `soulred/schemas/circle.py`: 兴趣圈子创建、圈子详情、多层级树状评论及内容风控审核 Pydantic 校验模型 (Symbols: CircleCreateSchema, CircleResponse, CommentCreateSchema, CommentResponse, CommentTreeResponse, ModerationActionSchema)
- `soulred/services/__init__.py`: 核心领域业务服务与算法模块统一导出 (Symbols: AuthService, ContentSafetyService, PostService, FeedService, MatchingService, ChatService, CircleService)
- `soulred/services/safety_service.py`: AI 多模态与文本风控审核服务，实现涉黄涉政与引流欺诈敏感词实时拦截和状态流转 (Symbols: ContentSafetyService, check_text_safety, check_image_safety, review_post_content)
- `soulred/services/auth_service.py`: 用户注册、密码验证、JWT 签发、实名/学历认证审核及数据脱敏服务 (Symbols: AuthService, register_user, authenticate_user, submit_verification, apply_privacy_filters)
- `soulred/services/post_service.py`: 动态图文发布、草稿自动保存恢复、点赞计数器缓存更新与动态详情组装服务 (Symbols: PostService, create_post, save_draft, get_draft, toggle_like, get_post_detail)
- `soulred/services/feed_service.py`: 小红书式双列瀑布流排序计算引擎，支持卡片自适应宽高比、图片角标及多频道切换排序 (Symbols: FeedService, get_waterfall_feed, calculate_card_aspect_ratio, rank_feed_items)
- `soulred/services/matching_service.py`: Soul 风格多维特征向量余弦相似度算法、青藤每日精选互选流转与陌生人首句打招呼防骚扰频控 (Symbols: MatchingService, calculate_soul_similarity, search_soul_radar, generate_daily_recommendations, handle_crush_action, check_stranger_message_limit)
- `soulred/services/chat_service.py`: 即时通讯业务服务，实现基于共同爱好的智能破冰话术推荐、亲密度经验值计算与字母点亮状态机 (Symbols: ChatService, generate_icebreakers, record_message, calculate_intimacy_gain, recall_message, get_conversation_history)
- `soulred/services/circle_service.py`: 兴趣圈子与社群互动服务，负责圈子管理、多层级楼中楼评论树递归构建及违规封禁操作 (Symbols: CircleService, list_circles, join_circle, post_comment, build_comment_tree, moderate_content)
- `tests/test_services.py`: 领域业务算法单元测试，全面覆盖契合度打分、瀑布流宽高计算、亲密度晋升及风控拦截逻辑 (Symbols: test_soul_similarity_calc, test_waterfall_card_aspect_ratio, test_intimacy_xp_progression, test_safety_keyword_interception, test_stranger_greeting_quota)
- `soulred/api/__init__.py`: Web API 根路由包初始化与总路由聚合 (Symbols: api_router)
- `soulred/api/deps.py`: FastAPI 依赖注入组件，提供数据库 Session、JWT 令牌校验与当前登录用户身份上下文 (Symbols: get_db_session, get_current_user, get_current_active_user)
- `soulred/api/v1/__init__.py`: 聚合各业务模块的 v1 版本 REST API 路由分发器 (Symbols: v1_router)
- `soulred/api/v1/auth.py`: 用户注册、登录凭证下发与真实度认证提交 REST 控制器 (Symbols: router, register, login, submit_verification)
- `soulred/api/v1/users.py`: 个人社交主页档案查询修改、3D虚拟形象设置与颗粒度隐私设置切换 REST 控制器 (Symbols: router, get_my_profile, update_profile, update_privacy_settings, get_user_persona)
- `soulred/api/v1/feed.py`: 小红书双列瀑布流动态广场接口（支持推荐、附近、关注三主频道无缝切换）REST 控制器 (Symbols: router, get_waterfall_feed)
- `soulred/api/v1/posts.py`: 动态发布、本地草稿读写、动态详情沉浸展示与快速爱心点赞 REST 控制器 (Symbols: router, create_post, save_draft, get_my_draft, get_post, toggle_like)
- `soulred/api/v1/matching.py`: 灵魂星盘测评提交、在线雷达匹配（相似度>80%）、每日精选卡片与双向心动 REST 控制器 (Symbols: router, submit_quiz, get_soul_radar, get_daily_recommendations, post_crush_action)
- `soulred/api/v1/chat.py`: 私信会话列表、历史记录检索、智能破冰话术获取与亲密度密友树状态 REST 控制器 (Symbols: router, list_conversations, get_chat_history, get_icebreakers, get_intimacy_status, recall_message)
- `soulred/api/v1/circles.py`: 兴趣圈子广场、加入圈子、多级楼中楼评论发表与热评置顶展示 REST 控制器 (Symbols: router, list_circles, join_circle, get_circle_posts, create_comment, get_comment_tree)
- `soulred/api/ws_chat.py`: WebSocket 实时私信长连接网关（端到端延迟<200ms），包含在线连接管理、心跳保活与瞬断补偿 (Symbols: ConnectionManager, manager, websocket_chat_endpoint)
- `soulred/static/index.html`: 内置小红书风格双列瀑布流高颜值前端交互 Demo 门户，支持响应式布局、爱心互动及 /docs 导航，专供真实浏览器 E2E 点击验证 (Symbols: renderWaterfallCards, switchChannel, toggleCardLike, loadDemoData)
- `soulred/main.py`: FastAPI 应用主入口，挂载全局中间件、静态资源、生命周期钩子、系统自检健康探针及交互门户 (Symbols: app, lifespan, health_check, root_portal)
- `tests/__init__.py`: 测试包根初始化声明 (Symbols: )
- `tests/conftest.py`: Pytest 全局夹具，提供内存 SQLite 隔离测试会话、TestClient、模拟用户及认证 Header (Symbols: db_session, client, test_user_a, test_user_b, auth_headers_user_a, auth_headers_user_b)
- `tests/test_models.py`: 底层 ORM 数据实体持久化、级联关系与 AES-256 加解密工具自动化测试用例 (Symbols: test_crypto_aes_gcm, test_user_model_creation, test_post_image_relationships, test_chat_intimacy_relationships)
- `tests/test_api_endpoints.py`: REST API 全链路集成测试，覆盖用户注册登录、瀑布流三频道切换、动态发布点赞、互选心动与圈子评论 (Symbols: test_auth_flow, test_waterfall_feed_channels, test_post_creation_and_like, test_matching_and_crush_flow, test_circle_comments)
- `tests/test_websocket.py`: WebSocket 实时长连接端到端集成测试，覆盖双向消息投递与陌生人单日限额频控校验 (Symbols: test_websocket_direct_message_exchange, test_websocket_stranger_daily_limit)

## 设计原则
### SoulRed 社交平台系统架构设计与设计原则 (System Architectural Design)

#### 1. 架构设计哲学与分层策略 (Clean Layered Architecture)
本项目采用现代化分层架构（Clean / Hexagonal Architecture 思想），实现高内聚、低耦合。各层职责严格隔离：
- **存储与规范层 (Data & Persistence Layer)**：统一定义 SQLAlchemy ORM 模型、Pydantic v2 输入输出契约及全局安全加解密机制，确保数据原子性与一致性。
- **核心领域服务层 (Domain Services & Business State Machines)**：承载小红书式瀑布流生成、Soul 风格灵魂契合度与青藤精选推荐算法、即时通讯亲密度养成状态机及 AI 风控审核，不依赖具体 HTTP 协议，具备极高的可测试性与复用性。
- **接口与网关层 (API Gateway & Real-time Layer)**：提供基于 FastAPI 的 RESTful API 路由与低延迟 WebSocket 长连接网关，并集成静态瀑布流前端展示门户，保障 Browser E2E 测试及生产环境开箱即用。

#### 2. 小红书风格双列自适应瀑布流算法 (Xiaohongshu-Style Waterfall Feed)
- **宽高比自适应与骨架屏预计算**：支持主流切图比例（1:1 正方形, 3:4 经典人像, 4:3 横构图）。Feed 接口直接返回计算好的卡片预估高度 `aspect_ratio` 与骨架屏色彩标记，前端双列渲染无需等待图片异步加载完成即可精准分配左右列高度平衡，杜绝页面加载闪烁与布局颠簸（Cumulative Layout Shift, CLS）。
- **多频道高效分发**：支持“推荐 (Recommend)”、“附近 (Nearby)”、“关注 (Following)”三频道独立索引排序；推荐频道融入时效性衰减（Time-decay）与互动热度（Likes + Comments）混合打分，附近频道基于地理距离切片，响应耗时严格控制在 800ms 内。

#### 3. 灵魂与青藤互选推荐匹配引擎 (Matching & Recommendation Engine)
- **灵魂星盘与多维契合度向量算法**：用户完成包含 MBTI 性格、生活习惯与交友期望的轻量测试后，向量化为多维特征数组。Soul 风格“灵魂雷达”采用余弦相似度（Cosine Similarity）与加权欧氏距离，毫秒级筛选出契合度 >= 80% 的在线用户。
- **青藤每日精选与双向奔赴状态机**：每日凌晨由推荐引擎离线生成 5-10 张专属精选推荐卡片；用户支持“心动 (Crush)”或“跳过 (Skip)”。当双方互相心动时，原子性触发 `CrushStatusEnum.MUTUAL`（双向奔赴）事件，触发系统级动画消息并自动初始化专属私聊会话通道。
- **陌生人反骚扰防线**：未经互选或非好友关系的陌生人，限制单日仅可发送 1 条打招呼纯文本消息，禁止发送图片及语音，从底层杜绝垃圾引流与骚扰。

#### 4. 即时通讯与亲密度进阶状态机 (Real-Time IM & Chat Intimacy Lifecycle)
- **高并发低延迟长连接网关**：基于 Starlette WebSocket 构建连接管理器（ConnectionManager），支持单节点数千并发连接、消息端到端投递 P95 < 200ms、离线消息持久化存储与上线拉取补偿。
- **智能破冰指南生成**：根据聊天双方的兴趣标签交集（如共同去过的展馆、同类音乐标签、相同 MBTI）动态提取关键词，自动合成破冰首句建议（如：“你们都喜欢 #民谣livehouse，聊聊最近去过的现场吧”）。
- **亲密度点亮机制 (Soul-Style Intimacy Level)**：通过持续互动天数累积与聊天字数（每日设上限防作弊）计算亲密度经验值 (XP)，阶梯式点亮字母与亲密徽章（从“初识萌芽”到“挚友星辰”），解锁专属聊天气泡与合影挂件。
- **消息撤回与安全风控**：支持在 2 分钟时限内撤回消息，并提供两步式快速拉黑与举报入口。

#### 5. 内容安全风控与合规保障 (Content Safety & Risk Control)
- **多层级实时风控引擎**：在动态发布、评论提交和私信通信的关键链路中，前置接入敏感词实时正则阻断、涉政涉黄涉暴特征识别及引流诈骗模式检测。
- **违规处置分级机制**：违规内容自动阻断；高可疑内容转入人工待审队列；涉事账户根据严重程度触发警告、禁言或即时封禁。

#### 6. 严苛隐私防护与零知识保护 (Privacy & Credential Security)
- **敏感数据 AES-256 加密**：用户手机号、实名认证信息、身份证件摘要等核心凭据在入库前采用 AES-256-GCM 高强度密文存储，查询时按需脱敏解密，防御数据库拖库泄露。
- **颗粒度隐私控制**：用户可一键开启“隐藏距离”、“不让附近的人看到我”及“通讯录联系人隐身”，系统在公域 Feed 与雷达搜索中严格过滤隐身用户坐标。

#### 7. 并行工程分工策略 (Parallel Engineering Strategy)
严格解耦为 3 个子模块，各工程师基于固定的文件边界与强类型接口规范并行开发：
1. **Module 1 (mod_data_model)**：率先完成数据库模型、Pydantic 契约、加密工具与配置，奠定系统数据地基；
2. **Module 2 (mod_business_logic)**：并发实现瀑布流算子、推荐匹配、亲密度与风控逻辑，依托单元测试进行独立验证；
3. **Module 3 (mod_api_gateway)**：并行搭建 REST 控制器、WebSocket 实时网关及 Web 前端 Portal，并执行双轨自动化回归测试。