# SoulRed (soulred-social-platform)

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite / SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)
[![Vite / React](https://img.shields.io/badge/Vite-React%2018-646CFF.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-74%20pytest%20%7C%2037%20vitest%20(100%25)-brightgreen.svg)]()

**SoulRed** 是一款将“**小红书式高美感双列瀑布流视觉呈现**”与“**Soul / 青藤之恋深度社交基因**”融合一体的全新青年社交平台。平台以高颜值的生活方式图文和心情日记作为社交破冰触点，结合灵魂/兴趣契合度算法、每日精选互选推荐、即时私信破冰与亲密度养成体系，有效解决传统纯内容社区缺乏社交关系链沉淀，以及传统社交软件缺乏生动生活切片展示的痛点。

---

## 🌟 核心特性 (Key Features)

### 1. 📷 小红书风格双列瀑布流动态广场 (Xiaohongshu-Style Waterfall Feed)
- **自适应双列瀑布流**：支持 `1:1`、`3:4`、`4:3` 常用图片切图比例，预计算卡片高度并提供骨架屏色彩占位，彻底消除累积布局抖动（CLS）。
- **三频道瞬时切换**：顶部一键切换“推荐”、“附近”、“关注”三频道，毫秒级响应。
- **沉浸式卡片详情**：支持轮播图组、发布地点定位、心情标签与即时点赞爱心动画反馈。

### 2. 📝 轻量化图文与心情动态发布 (Rich-Media & Mood Notes)
- **多图组合发布**：单篇动态支持最多 9 张图片上传，支持自适应图片比例计算。
- **心情与圈子话题**：关联 1~5 个垂直兴趣话题标签（如 `#MBTI`、`#民谣livehouse`、`#周末去哪儿`）与心情状态（治愈中、求聊天、发呆等）。
- **断网恢复与草稿暂存**：本地与服务端草稿双重暂存机制，网络中断或误关页面可无损恢复。
- **内容风控过滤**：内置关键词与 AI 图文风控过滤机制，违规内容实时阻断与状态流转。

### 3. 🔮 灵魂与兴趣契合度匹配引擎 (Soul & QingTeng Matching Engine)
- **多维心理与兴趣星盘**：轻量级 MBTI 个性与价值观测评，自动计算生成多维“灵魂/兴趣星盘”。
- **灵魂雷达匹配**：基于多维特征向量余弦相似度（Cosine Similarity）算法，毫秒级召回在线契合度 $\ge 80\%$ 的合拍同好。
- **青藤每日精选推荐**：每日定时推送 5~10 张高契合度候选人名片，支持“心动 (Crush)”与“跳过 (Skip)”。
- **双向奔赴状态机**：双方互相心动时原子触发“双向奔赴 (Mutual Crush)”事件并自动建立私信通道；未经互选的陌生人单日仅限发送 1 条打招呼文本，杜绝骚扰。

### 4. 💬 实时私信、智能破冰与亲密度养成 (Real-Time IM & Chat Intimacy)
- **WebSocket 长连接网关**：基于 Starlette / FastAPI WebSocket 实现端到端低延迟通信与心跳保活。
- **情境化破冰指南**：自动提取双方共同话题标签与最新生活动态切片，智能生成破冰开场白。
- **亲密度等级点亮 (Soul-Style Intimacy)**：根据持续聊天天数与互动字数累加亲密度经验值（XP），阶梯式点亮亲密标识，解锁专属聊天气泡与合影挂件。
- **全功能消息交互**：支持 2 分钟消息撤回、已读回执、引用回复、单向删除与拉黑风控。

### 5. 👥 兴趣圈子与多级树状评论生态 (Interest Circles & Topic Squares)
- 覆盖艺术展览、户外徒步、同城交友、深夜树洞等垂直领域社群。
- 支持圈内“最新发布”与“精华热门”双维排序，圈主优质内容置顶。
- 多层级树状楼中楼评论体系，支持 `@` 提及互动、点赞排序与热评置顶。

### 6. 🛡️ 个性化社交档案与严苛隐私保护 (Persona & Privacy Security)
- **个性名片**：3D 拟态头像、背景墙封面、10 秒语音介绍名片与多维兴趣标签展示。
- **真实信任背书**：青藤之恋官方实名/学历/职业真实度认证体系与信誉徽章点亮。
- **精细化隐私控制**：支持隐藏真实物理距离、附近隐身、通讯录好友屏蔽。
- **企业级数据加密**：敏感用户凭据与手机号均基于 AES-256-GCM 强加密存储，客户端全链路脱敏。

---

## 📋 环境要求 (Prerequisites)

- **Python**：`>= 3.12`
- **Node.js**（可选，用于前端开发与构建）：`>= 18.0.0`
- **npm**：`>= 9.0.0`
- **操作系统**：macOS, Linux, 或 Windows (WSL2 推荐)

---

## 📦 安装指南 (Installation)

### 1. 克隆代码库 (Clone Repository)
```bash
git clone <repository_url> soulred-social-platform
cd soulred-social-platform
```

### 2. 创建并激活虚拟环境 (Virtual Environment)
```bash
python3 -m venv .venv
source .venv/bin/activate  # Linux / macOS
# 或者 Windows: .venv\Scripts\activate
```

### 3. 安装 Python 依赖 (Install Python Dependencies)

你可以选择通过 `requirements.txt` 或 `pip install .` 安装：

**方式 A：通过 requirements.txt 安装（推荐用于部署）**
```bash
pip install -r requirements.txt
```

**方式 B：通过 pyproject.toml 安装包（支持开发模式）**
```bash
pip install -e .
```

### 4. 安装前端依赖（可选）
如果需要本地开发 React 独立组件或运行前端构建：
```bash
npm install
```

---

## 🚀 启动与运行 (Running the Application)

### 1. 启动 SoulRed 后端 API 与静态 Web 服务
运行以下命令启动 FastAPI 服务（自动初始化 SQLite 数据库 `soulred.db` 并挂载内置双列瀑布流门户）：

```bash
uvicorn soulred.main:app --host 0.0.0.0 --port 8000 --reload
```

或者使用 Python 模块启动：
```bash
python -m uvicorn soulred.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 访问系统服务与交互入口
服务启动后，可在浏览器中直接访问以下地址：

| 入口 | URL 地址 | 说明 |
| :--- | :--- | :--- |
| **双列瀑布流 Web 演示门户** | [http://localhost:8000/](http://localhost:8000/) | 原生响应式双列瀑布流、频道切换、即时点赞与快捷体验入口 |
| **Swagger UI 交互式 API 文档** | [http://localhost:8000/docs](http://localhost:8000/docs) | 在线 API 调试、契约测试与 Schema 检查 |
| **ReDoc 规格文档** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | 清晰规范的 OpenAPI v3.1 规格文档 |
| **服务健康探针** | [http://localhost:8000/health](http://localhost:8000/health) | 返回 `{"status": "ok", "app": "SoulRed"}` |
| **WebSocket 即时通讯网关** | `ws://localhost:8000/ws/chat/{client_id}` | 实时双向私信通信网关 |

### 3. 运行前端开发服务器（可选）
如果需要使用 Vite 开发独立的 React 前端界面：
```bash
npm run dev
```
前端开发服务将运行在 `http://localhost:5173/`。

打包生产静态资源：
```bash
npm run build
```
编译产物将输出至 `dist/` 目录。

---

## 🧪 自动化测试套件 (Test Suite)

项目配备了完善的后端、前端与端到端自动化测试套件，测试通过率 100%（共计 111 项测试通过）：

### 1. 运行后端与集成测试 (Pytest)
执行全量后端测试（涵盖 REST API、WebSocket、算法服务、数据模型以及 Playwright 浏览器端到端测试）：

```bash
pytest
```

#### 针对特定模块运行测试：
```bash
# 运行 PRD US-001 ~ US-006 综合验收测试 (19 项)
pytest tests/test_soulred_prd_comprehensive.py

# 运行双列瀑布流核心测试 (25 项)
pytest tests/test_portrait_feed.py

# 运行核心领域服务与算法测试 (余弦相似度、瀑布流比例、亲密度)
pytest tests/test_services.py

# 运行 WebSocket 实时私信与单日频控测试
pytest tests/test_websocket.py

# 运行 Playwright 真实无头 Chrome 浏览器 E2E 测试
pytest tests/test_browser_e2e.py
```

### 2. 运行前端单元测试 (Vitest)
运行基于 Vitest + Testing Library 的前端组件与 Hook 测试（37 项测试）：

```bash
npm test
```

---

## 🏗️ 目录结构与模块说明 (Project Architecture)

```text
soulred-social-platform/
├── soulred/                     # 后端核心业务包
│   ├── api/                     # 控制器与路由层
│   │   ├── deps.py              # 依赖注入 (DB Session, JWT Auth)
│   │   ├── ws_chat.py           # WebSocket 实时私信长连接网关
│   │   └── v1/                  # REST API v1 端点
│   │       ├── auth.py          # 注册、登录、学历/实名认证
│   │       ├── chat.py          # 会话管理、消息历史、智能破冰
│   │       ├── circles.py       # 兴趣圈子、多级树状评论
│   │       ├── feed.py          # 小红书双列瀑布流 (推荐/附近/关注)
│   │       ├── matching.py      # 灵魂测评、灵魂雷达 (>=80%)、每日精选互选
│   │       ├── posts.py         # 动态发布、草稿暂存、点赞
│   │       └── users.py         # 社交档案、3D虚拟形象、隐私配置
│   ├── core/                    # 基础设施与安全模块
│   │   └── security.py          # AES-256-GCM、密码哈希、JWT 凭证
│   ├── models/                  # SQLAlchemy 2.0 ORM 数据模型
│   │   ├── base.py              # Base 模型与通用字段
│   │   ├── chat.py              # Conversation, Message, ChatIntimacy
│   │   ├── circle.py            # Circle, CircleMember, Comment
│   │   ├── match.py             # PersonalityProfile, DailyRecommendation, CrushMatch
│   │   ├── post.py              # Post, PostMedia, PostDraft, PostLike
│   │   └── user.py              # User, UserProfile, VerificationBadge, PrivacySetting
│   ├── schemas/                 # Pydantic v2 请求与响应数据契约
│   ├── services/                # 领域业务服务与核心算法
│   │   ├── auth_service.py      # 鉴权认证与手机号/凭据脱敏
│   │   ├── chat_service.py      # 破冰生成、亲密度经验值计算、消息撤回
│   │   ├── circle_service.py    # 圈子运营与递归评论树构建
│   │   ├── feed_service.py      # 双列瀑布流排列算法与频道分发
│   │   ├── matching_service.py  # 向量余弦相似度匹配与互选状态机
│   │   ├── post_service.py      # 图文发布、草稿箱与点赞事务
│   │   └── safety_service.py    # 违规词拦截与 AI 风控审核
│   ├── static/                  # 内置静态前端门户
│   │   └── index.html           # 瀑布流 Web 演示界面
│   ├── config.py                # 全局应用配置 (Pydantic-Settings)
│   ├── database.py              # 数据库引擎与 SessionLocal  фабрика
│   └── main.py                  # FastAPI 主应用入口
├── src/                         # 前端 React 源代码 (Vite + TailwindCSS)
│   ├── components/              # 瀑布流卡片与详情模态框组件
│   ├── hooks/                   # useMasonryColumns, useLikes 自定义 Hook
│   └── services/                # 前端存储与数据通信服务
├── tests/                       # 全量自动化测试集
│   ├── test_soulred_prd_comprehensive.py # PRD 验收标准测试
│   ├── test_portrait_feed.py    # 瀑布流端到端逻辑
│   ├── test_browser_e2e.py      # Playwright 浏览器渲染测试
│   ├── test_websocket.py        # WebSocket 长连接测试
│   └── ...
├── pyproject.toml               # Python 项目配置与打包元数据
├── requirements.txt             # 生产与开发 Python 依赖清单
├── package.json                 # Node.js 项目依赖与构建脚本
└── README.md                    # 项目官方指南文档
```

---

## 🔌 核心 API 快速体验 (API Quickstart)

### 1. 用户注册与登录
```bash
# 注册新用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "traveler_lin", "email": "lin@example.com", "password": "SecurePassword123!"}'

# 登录获取 JWT Access Token
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=traveler_lin&password=SecurePassword123!"
```

### 2. 获取双列瀑布流动态
```bash
# 获取推荐瀑布流（支持 channel=recommend | nearby | following）
curl -X GET "http://localhost:8000/api/v1/feed?channel=recommend&page=1&limit=10"
```

### 3. 发布图文生活切片
```bash
curl -X POST http://localhost:8000/api/v1/posts \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "周末在阿那亚海边看日落，海风非常治愈～",
    "images": [
      {"url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e", "aspect_ratio": 1.33}
    ],
    "tags": ["阿那亚", "海边日落", "周末去哪儿"],
    "mood": "治愈中",
    "location": "河北·秦皇岛"
  }'
```

### 4. 灵魂雷达高契合度搜索
```bash
curl -X GET http://localhost:8000/api/v1/matching/radar \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>"
```

### 5. 每日精选卡片互动（心动 Crush）
```bash
curl -X POST http://localhost:8000/api/v1/matching/daily-action \
  -H "Authorization: Bearer <YOUR_ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"target_user_id": "<TARGET_USER_UUID>", "action": "crush"}'
```

---

## 🔒 隐私与安全性保障 (Security & Privacy)

- **AES-256-GCM 密文存储**：手机号、实名凭证、敏感定位坐标在落盘时进行高强度信封加密。
- **动态脱敏**：对外输出接口严格实行个人身份信息脱敏（手机号中间 4 位隐藏、真实姓名掩码处理）。
- **反骚扰防护机制**：非互选好友单日仅限 1 条打招呼限制；支持即时加入黑名单阻断通信。
- **合规审计**：全量敏感词库实时检测，包含违规图文阻断与人工审核介入状态机。

---

## 📄 开源许可证 (License)

本项目采用 MIT 许可证，详情请参阅项目内许可文件。
