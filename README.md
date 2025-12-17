# Buzz Backend - Social Media Sentiment Analysis

AI-powered social media monitoring system for Razorpay and competitors. Scrapes Twitter & LinkedIn, classifies posts using Azure OpenAI, and provides actionable insights.

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Scrapers  │ ──▶ │  raw_post   │ ──▶ │  Classifier │ ──▶ │    posts    │
│ Twitter/LI  │     │   (DB)      │     │ Azure GPT   │     │   (DB)      │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
                                                          ┌─────────────┐
                                                          │  Slack/JIRA │
                                                          │  Integration│
                                                          └─────────────┘
```

## Features

- 🐦 **Twitter Scraping** - GraphQL API-based tweet fetching with full conversations
- 💼 **LinkedIn Scraping** - Selenium browser automation for content search
- 🏢 **Multi-Company Support** - Track Razorpay + 8 competitors (PayU, Cashfree, Paytm, etc.)
- 🤖 **AI Classification** - Azure OpenAI GPT for spam detection, categorization, sentiment
- 📊 **Scoring System** - Sentiment, Urgency, and Impact scores (1-10)
- 🎫 **Team Tracking** - Slack alerts, ticket creation, assignment workflow
- 🗄️ **SQLite Database** - Two-stage storage (raw → classified)
- ✅ **Incremental Scraping** - Checkpointing to avoid duplicate processing

## Project Structure

```
buzz-backend/
├── app/
│   ├── config.py                 # Configuration & environment variables
│   ├── scraper/
│   │   ├── twitter.py            # Twitter GraphQL API client
│   │   ├── linkedin_browser.py   # LinkedIn Selenium scraper
│   │   ├── multi_company.py      # Multi-company orchestrator
│   │   └── scheduler.py          # Continuous scraper
│   ├── analyzer/
│   │   ├── classifier.py         # Azure OpenAI classification
│   │   ├── batch.py              # Twitter batch processing
│   │   └── linkedin_batch.py     # LinkedIn batch processing
│   ├── api/
│   │   └── routes/               # FastAPI routes (TODO)
│   └── db/
│       ├── database.py           # SQLAlchemy setup
│       ├── models.py             # RawPost, Post, Conversation models
│       └── repository.py         # Database operations
├── data/
│   └── db/
│       └── buzz.db               # SQLite database
├── tests/
├── requirements.txt
└── README.md
```

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```bash
# Azure OpenAI (required for classification)
AZURE_OPENAI_API_KEY=your_api_key

# Twitter API (get from browser DevTools)
TWITTER_AUTH_TOKEN=your_auth_token
TWITTER_CSRF_TOKEN=your_csrf_token

# LinkedIn API (get from browser cookies)
LINKEDIN_LI_AT=your_li_at_cookie
LINKEDIN_JSESSIONID=your_jsessionid_cookie
```

### 3. Initialize Database

```bash
python3 -c "from app.db.database import init_db; init_db()"
```

## Usage

### Scrape LinkedIn (Recommended - More Reliable)

```bash
# Scrape all companies
python3 -m app.scraper.multi_company --platform linkedin --all --count 30

# Scrape specific companies
python3 -m app.scraper.multi_company --platform linkedin --companies razorpay cashfree payu

# Scrape with browser visible (for debugging)
python3 -m app.scraper.linkedin_browser --query "Razorpay" --count 20 --no-headless
```

### Scrape Twitter

```bash
# Scrape all companies (requires fresh tokens)
python3 -m app.scraper.multi_company --platform twitter --all --count 30

# Direct Twitter search
python3 -m app.scraper.twitter --query "Razorpay" --count 20
```

### Classify Posts

```bash
# Classify all unclassified LinkedIn posts
python3 -m app.analyzer.linkedin_batch --db

# Classify with stats
python3 -m app.analyzer.linkedin_batch --db --stats

# Classify specific company
python3 -m app.analyzer.linkedin_batch --db --company razorpay
```

### Query the Database

```bash
# Interactive SQLite
sqlite3 -header -column data/db/buzz.db

# Common queries
sqlite3 data/db/buzz.db "SELECT company, platform, COUNT(*) FROM raw_post GROUP BY company, platform;"
sqlite3 data/db/buzz.db "SELECT company, category, COUNT(*) FROM posts WHERE is_spam=0 GROUP BY company, category;"
```

## Database Schema

### `raw_post` - Raw Scraped Posts

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| post_id | VARCHAR(64) | Platform-specific ID |
| platform | VARCHAR(32) | `twitter` or `linkedin` |
| company | VARCHAR(64) | Company scraped for |
| full_text | TEXT | Post content |
| author_name | VARCHAR(256) | Author display name |
| author_username | VARCHAR(128) | Author handle |
| author_followers_count | INTEGER | Follower count |
| likes_count | INTEGER | Likes/reactions |
| comments_count | INTEGER | Comments/replies |
| post_url | VARCHAR(512) | Direct link |
| posted_at | DATETIME | When posted |
| scraped_at | DATETIME | When scraped |
| is_classified | BOOLEAN | Classification status |

### `posts` - Classified Posts

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| raw_post_id | INTEGER | FK to raw_post |
| company | VARCHAR(64) | Company |
| platform | VARCHAR(32) | Platform |
| **Classification** | | |
| is_spam | BOOLEAN | Spam flag |
| category | VARCHAR(64) | Praise, Complaint, etc. |
| product | VARCHAR(128) | Razorpay product |
| sentiment_score | INTEGER | 1-10 |
| urgency_score | INTEGER | 1-10 |
| impact_score | INTEGER | 1-10 |
| summary | TEXT | AI summary |
| key_issues | JSON | List of issues |
| suggested_action | TEXT | Recommended action |
| priority | VARCHAR(16) | critical/high/medium/low |
| **Team Tracking** | | |
| raised_on_slack | BOOLEAN | Slack alert sent |
| slack_channel | VARCHAR(128) | Slack channel |
| ticket_created | BOOLEAN | Ticket created |
| ticket_id | VARCHAR(64) | Ticket ID |
| ticket_url | VARCHAR(512) | Ticket URL |
| assigned_team | VARCHAR(128) | Assigned team |
| status | VARCHAR(32) | new/in_progress/resolved |
| resolution | TEXT | Resolution notes |

## Configured Companies

| Company | Type | Keywords |
|---------|------|----------|
| **Razorpay** | Primary | Razorpay, @Razorpay, @RazorpayCare |
| PayU | Competitor | PayU India, @PayUIndia |
| Cashfree | Competitor | Cashfree, @gocashfree |
| Paytm | Competitor | Paytm payment gateway, @Paytm |
| PhonePe | Competitor | PhonePe business, @PhonePe |
| Instamojo | Competitor | Instamojo, @instamojo |
| CCAvenue | Competitor | CCAvenue, @CCAvenue |
| Stripe | Competitor | Stripe India, @stripe |
| Juspay | Competitor | Juspay, @juspay_tech |

## Classification Categories

| Category | Description |
|----------|-------------|
| **Praise** | Positive feedback, appreciation |
| **Complaint** | Negative feedback (service working) |
| **Experience Breakage** | Technical issues, bugs, failures |
| **Feature Request** | Suggestions for improvements |
| **General** | Neutral mentions, news |

## Razorpay Products

Payment Gateway, Payment Links, Payment Pages, Subscriptions, Smart Collect, QR Codes, POS, Route, Razorpay X, Payroll, Capital, Tokenisation, Magic Checkout, Instant Settlements, Disputes, Dashboard, Support, Onboarding/KYC

## Updating Twitter Credentials

Twitter tokens expire frequently. To refresh:

1. Open [x.com](https://x.com) in Chrome and log in
2. Open DevTools (F12) → Network tab
3. Search for "Razorpay"
4. Find `SearchTimeline` request
5. Right-click → Copy as cURL
6. Extract values:

| Value | Location in cURL |
|-------|------------------|
| `auth_token` | Cookie `auth_token=XXX` |
| `csrf_token` | Cookie `ct0=XXX` or Header `x-csrf-token` |
| `GraphQL Query ID` | URL `/graphql/XXX/SearchTimeline` |

7. Update `.env` and reset state:

```bash
rm -f app/scraper/.twitter_tx_state.json
```

## Python API

```python
from app.db.database import get_db_session
from app.db.models import RawPost, Post

# Query raw posts
with get_db_session() as db:
    posts = db.query(RawPost).filter(
        RawPost.company == "razorpay",
        RawPost.platform == "linkedin"
    ).limit(10).all()
    
# Query classified posts
with get_db_session() as db:
    urgent = db.query(Post).filter(
        Post.urgency_score >= 8,
        Post.is_spam == False
    ).all()
```

---

Built for Razorpay Hackon FY26 Q3
