# High-Trust Dating Platform

A high-trust, real-name dating application engineered for 20–35 year-old singles seeking genuine, serious relationships. The platform eliminates superficial swiping, deceptive profiles, and review farming through:
- **Verified Educational Credentials & OCR Parsing**: Degree and diploma verification with encrypted object storage (AES-256-GCM) and privacy desensitization (displaying only tier and degree level).
- **Daily 10-Candidate Card Quota**: Curated matching pool resetting at midnight to prevent compulsive swiping fatigue.
- **Multi-Factor Candidate Exposure Ranking Engine**: 70% Bayesian reputation rating, 20% 72-hour cold-start boost, and 10% 48-hour recency bonus.
- **Mutual Double-Opt-In Matching & 1v1 IM**: Anonymous single-sided likes, automatic instant chat initialization, and 7-day 0-message circuit breaker dissolution.
- **Offline Dating Closed Loop with Dual Verification**: Structured in-chat invitations, dynamic TOTP QR code check-in (60s), 100m GPS geofencing, and mobile anti-spoofing defense.
- **Double-Blind Post-Date Reviews & Bayesian Reputation Smoothing**: Reviews unlock 2 hours after arrival, remaining blind until both submit or after 48 hours, with 30-day pair collusion cooldown.
- **Points Economy Engine**: Accrue points through milestone events (+100 edu verification, +5 daily login, +30 for high-rating dates, +50 for confirmed reports); spend points for top 10% targeted crush discovery and daily deck refresh.

---

## Quickstart

### Prerequisites
- Python 3.12+
- Virtual environment tool (e.g. `venv`, `conda`)

### Installation

1. **Clone and Navigate**:
   ```bash
   cd /Users/chz/workspace/auto-agent/workspaces/trust_social_app
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -e .
   ```

4. **Run the Application**:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Access Interactive API Docs**:
   - Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
   - ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Architecture Overview

```
src/
├── api/                        # Presentation Layer: FastAPI Route Controllers
│   ├── v1/
│   │   ├── auth.py             # User onboarding, login, credentials, admin audit
│   │   ├── chat.py             # 1v1 conversations, messages, WebSocket dispatch
│   │   ├── dates.py            # Date invitations, QR/GPS check-in, cancellations
│   │   ├── points.py           # Balance queries, ledger, daily login check-in
│   │   ├── recommendations.py  # Daily 10-card deck, swipe, targeted search, pack refresh
│   │   └── reviews.py          # Double-blind reviews and reputation queries
│   └── __init__.py             # Mounts all v1 endpoints under /api/v1
├── core/                       # Cross-Cutting Infrastructure & Security
│   ├── anti_spoofing.py        # Mock GPS, emulator, and hook detection
│   ├── crypto_oss.py           # AES-256-GCM private encrypted document storage & pre-signed URLs
│   ├── exceptions.py           # Domain exceptions and standardized AppErrorCode constants
│   └── security.py             # Password hashing (bcrypt), PyJWT tokens, and gating dependencies
├── models/                     # Data Access Layer: SQLAlchemy 2.0 ORM Entities
│   ├── chat.py                 # Conversation, ChatMessage
│   ├── dating.py               # DateInvitation, DateCheckIn, DateReview
│   ├── matching.py             # CandidateDeck, SwipeAction, Match
│   ├── points.py               # PointLedger, DailyActivityLog
│   └── user.py                 # User, EducationCredential
├── schemas/                    # Pydantic v2 DTOs with validation rules
│   ├── chat_schemas.py
│   ├── dating_schemas.py
│   ├── matching_schemas.py
│   ├── points_schemas.py
│   └── user_schemas.py
├── services/                   # Business Logic Domain Services
│   ├── auth_service.py         # Onboarding, age & tag validation, credential audit
│   ├── chat_service.py         # Message dispatch, unread tracking, 7-day circuit breaker
│   ├── dating_service.py       # Date invitation lifecycle, TOTP QR, GPS check-in, penalties
│   ├── matching_service.py     # 10-card quota, multi-factor exposure score, swipe & match
│   ├── ocr_service.py          # Credential OCR data extraction and school tier mapper
│   ├── points_service.py       # Ledger mutations, daily check-in, idempotency deduplication
│   ├── reputation_service.py   # Bayesian smoothing (m=5, C=3.5), double-blind reveal, collusion cooldown
│   └── websocket_manager.py    # Live WebSocket connection pool for sub-300ms delivery
├── config.py                   # Central settings using Pydantic Settings
├── database.py                 # Async SQLAlchemy engine, session maker, declarative base
└── main.py                     # FastAPI application factory and lifespan hooks
```

---

## Core Specifications & System State Machines

### 1. Education Verification State Machine
`unsubmitted` $\rightarrow$ `pending_review` $\rightarrow$ `verified` / `rejected`
- Only `verified` users can access the recommendation pool, swipe, chat, or date initiation.
- Upon verification, an onboarding bonus of **+100 points** is credited.

### 2. Multi-Factor Exposure Ranking Score
Candidates are ranked daily according to:
$$\text{Score} = 0.70 \times \text{BayesianReputation} + 0.20 \times \text{ColdStartBonus}(72\text{h}) + 0.10 \times \text{RecencyBonus}(48\text{h})$$

### 3. Bayesian Reputation Scoring & Collusion Cooldown
Public ratings are computed using a Bayesian average:
$$S = \frac{C \cdot m + \sum r_i}{m + v}$$
where baseline $C = 3.5$, prior weight $m = 5$, and $v$ is the count of eligible reviews.
- **Anti-Collusion**: Matches between the same pair within 30 days are flagged as `collusion_flagged` and excluded from reputation recalculation.

### 4. Offline Date State Machine & Penalties
`pending_acceptance` $\rightarrow$ `confirmed_pending_arrival` $\rightarrow$ `completed` / `cancelled_excused` / `no_show` / `expired`
- **Cancellation $\ge$ 4h prior**: Penalty-free (`cancelled_excused`).
- **Late cancellation (< 4h) or No-Show**: -0.5 reputation score deduction and -50 points deduction (`no_show`).

### 5. Inactive Chat Circuit Breaker
If 0 messages are exchanged within 7 days of matching, the conversation transitions to `archived_inactive`, the match dissolves, and any subsequent messaging attempt is rejected with `ERR_MATCH_EXPIRED`.

---

## Running Test Suite

Run the full async test suite covering all user stories (US-001 through US-015):
```bash
python -m pytest
```

Run test categories individually:
```bash
# Auth, Age/Tag validation, OCR parsing, Privacy Masking (US-001 to US-004)
python -m pytest tests/test_auth_and_gating.py

# 10-Card Quota, Multi-Factor Ranking, Mutual Match, Targeted Search (US-005, US-006, US-007, US-014, US-015)
python -m pytest tests/test_matching_and_ranking.py

# Instant Messaging, WebSocket dispatch, 7-Day Circuit Breaker (US-007, US-008)
python -m pytest tests/test_chat_and_circuit_breaker.py

# Offline Date Invitations, TOTP QR, 100m GPS Geofence, Anti-Spoofing, Cancellation (US-009, US-010, US-012)
python -m pytest tests/test_dating_and_checkin.py

# Double-Blind Review Reveal, Bayesian Average, 30-Day Anti-Collusion (US-011)
python -m pytest tests/test_reputation_and_review.py

# Points Economy Accrual, Deduplication Idempotency, Ledger Consistency (US-013, US-014, US-015)
python -m pytest tests/test_points_economy.py
```
