# Buzz Backend - Razorpay Social Media Sentiment Analysis

AI-powered social media monitoring system for Razorpay. Scrapes tweets, fetches full conversations, analyzes sentiment, and provides APIs for insights.

## Architecture

```
Scraper → Conversations DB → Analyzer → Analysis DB → Web APIs
```

## Features

- 🔄 **Continuous Scraping** - Scrapes Twitter every 30 seconds in 30-minute windows
- 💬 **Full Conversations** - Fetches complete threads with all replies
- 🗄️ **SQLite Database** - Persistent storage with idempotency checks
- 🔍 **Spam Detection** - Identifies spam tweets (job posts, unrelated mentions)
- 📂 **Category Classification** - Praise, Complaint, Experience Breakage, Feature Request
- 📦 **Product Identification** - Maps issues to Razorpay products
- 📊 **Scoring** - Sentiment, Urgency, and Impact scores (1-10)
- 🖼️ **Image Analysis** - Analyzes attached screenshots

## Project Structure

```
hackon/
├── app/
│   ├── config.py              # Configuration & environment variables
│   ├── scraper/
│   │   ├── twitter.py         # Twitter API client
│   │   └── scheduler.py       # Continuous scraper (30s intervals)
│   ├── analyzer/
│   │   ├── classifier.py      # Tweet classification (Azure OpenAI)
│   │   └── batch.py           # Batch processing
│   ├── api/
│   │   └── routes/            # FastAPI routes (TODO)
│   └── db/
│       ├── database.py        # SQLAlchemy setup
│       └── models.py          # Conversation & ScraperState models
├── data/
│   ├── db/
│   │   └── buzz.db            # SQLite database
│   └── *.json                 # Sample data files
├── tests/
├── requirements.txt
└── README.md
```

## Setup

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Set Environment Variables

```bash
# Twitter API (get from browser DevTools)
export TWITTER_AUTH_TOKEN="your_auth_token"
export TWITTER_CSRF_TOKEN="your_csrf_token"

# Azure OpenAI (for classification)
export AZURE_OPENAI_API_KEY="your_api_key"
```

## Usage

### Run the Scraper

```bash
# Start continuous scraping (3 runs by default, 30s apart)
python3 -m app.scraper.scheduler

# Run more scrapes (reset run counter)
sqlite3 data/db/buzz.db "UPDATE scraper_state SET run_count = 0;"
python3 -m app.scraper.scheduler
```

**Scraper Behavior:**
- Starts from Nov 1, 2025 (or last scraped window)
- Scrapes 30-minute windows
- Fetches all tweets with full pagination
- Gets complete conversations with replies
- Idempotency check on `conversation_id`

### Query the Database

**SQLite CLI:**
```bash
# Interactive mode
sqlite3 data/db/buzz.db

# One-liner with formatting
sqlite3 -header -column data/db/buzz.db "SELECT * FROM conversations;"
```

**Common Queries:**
```sql
-- View all conversations
SELECT id, conversation_id, reply_count, started_at FROM conversations;

-- Get tweet text
SELECT json_extract(conversation, '$.main_tweet.full_text') FROM conversations;

-- Find conversations with replies
SELECT * FROM conversations WHERE reply_count > 0;

-- Check scraper progress
SELECT * FROM scraper_state;

-- Get author info
SELECT 
    json_extract(conversation, '$.main_tweet.user.screen_name') as author,
    json_extract(conversation, '$.main_tweet.user.followers_count') as followers
FROM conversations;
```

**Python:**
```python
from app.db.database import get_db_session
from app.db.models import Conversation

with get_db_session() as db:
    convs = db.query(Conversation).filter(Conversation.reply_count > 0).all()
    for c in convs:
        print(f"@{c.conversation['main_tweet']['user']['screen_name']}")
        print(f"Text: {c.get_main_tweet_text()}")
        print(f"Replies: {c.reply_count}")
```

### Classify Tweets

```bash
# Single tweet classification
python3 -m app.analyzer.classifier

# Batch analysis
python3 -m app.analyzer.batch
```

## Database Schema

### conversations
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| conversation_id | VARCHAR(64) | Unique Twitter conversation ID |
| source | VARCHAR(32) | "twitter" |
| main_tweet_id | VARCHAR(64) | Focal tweet ID |
| conversation | JSON | Full conversation data |
| reply_count | INTEGER | Number of replies |
| search_query | VARCHAR(256) | Query used to find it |
| started_at | DATETIME | When conversation started |
| last_reply_at | DATETIME | Latest reply time |
| is_analyzed | BOOLEAN | Analysis status |
| created_at | DATETIME | When scraped |

### scraper_state
| Column | Type | Description |
|--------|------|-------------|
| source | VARCHAR(32) | "twitter" |
| search_query | VARCHAR(256) | Search query |
| run_count | INTEGER | Number of completed runs |
| last_window_start | DATETIME | Start of last scraped window |
| last_window_end | DATETIME | End of last scraped window |

## Configuration

Edit `app/config.py` or use environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPER_SEARCH_QUERY` | "Razorpay" | Twitter search query |
| `SCRAPER_INTERVAL_SECONDS` | 30 | Seconds between scrape runs |
| `SCRAPER_WINDOW_MINUTES` | 30 | Time window per scrape |
| `SCRAPER_MAX_RUNS` | 3 | Max runs before stopping |
| `SCRAPER_START_DATE` | "2025-11-01 00:00:00" | Initial start date |

## Classification Output

```json
{
  "is_spam": false,
  "category": "Experience Breakage",
  "product": "Payment Gateway",
  "sentiment_score": 3,
  "urgency_score": 8,
  "impact_score": 7,
  "summary": "User reports payment failure during checkout",
  "key_issues": ["Payment failure", "Timeout error"],
  "suggested_action": "Investigate logs and reach out to user"
}
```

## Categories

| Category | Description |
|----------|-------------|
| Praise | Positive feedback, appreciation |
| Complaint | Negative feedback (service working) |
| Experience Breakage | Technical issues, bugs, failures |
| Feature Request | Suggestions for improvements |

## Supported Razorpay Products

Payment Gateway, Payment Links, Payment Pages, Payment Buttons, Subscriptions, Smart Collect, QR Codes, POS, Route, Razorpay X, Payroll, Capital, Tokenisation, Magic Checkout, Instant Settlements, Disputes, Dashboard, Support, Onboarding/KYC

---

Built for Razorpay Hackon FY26 Q3
