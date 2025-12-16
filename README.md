# Buzz Backend - Razorpay Tweet Classifier

AI-powered tweet classification system for Razorpay social media monitoring. Analyzes tweets to detect spam, categorize feedback, identify relevant products, and score urgency/impact.

## Features

- 🔍 **Spam Detection** - Identifies spam tweets (job posts, unrelated mentions)
- 📂 **Category Classification** - Praise, Complaint, Experience Breakage, Feature Request
- 📦 **Product Identification** - Maps issues to specific Razorpay products (Payment Gateway, Razorpay X, Disputes, etc.)
- 📊 **Scoring** - Sentiment, Urgency, and Impact scores (1-10)
- 🖼️ **Image Analysis** - Analyzes attached screenshots for context (error messages, payment failures)

## Setup

### 1. Install Dependencies

```bash
pip install requests
```

### 2. Set Environment Variables

```bash
export AZURE_OPENAI_API_KEY="your_api_key_here"

# Optional (defaults provided)
export AZURE_OPENAI_ENDPOINT="https://your-endpoint.cognitiveservices.azure.com"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
export AZURE_OPENAI_API_VERSION="2025-01-01-preview"
```

## Usage

### Classify a Single Tweet

Edit `classify_tweet.py` and update the `main()` function:

```python
tweet = "Your tweet text here"
image_url = None  # or "https://image-url.com/image.jpg"
```

Run:
```bash
python3 classify_tweet.py
```

### Batch Analysis

Place tweets in `tweets.json` and run:

```bash
python3 analyze_tweets.py
```

Results saved to `analysis_results.json`.

## Output Format

```json
{
  "is_spam": false,
  "spam_reason": null,
  "category": "Experience Breakage",
  "product": "Payment Gateway",
  "sentiment_score": 3,
  "urgency_score": 8,
  "impact_score": 7,
  "summary": "User reports payment failure during checkout",
  "key_issues": ["Payment failure", "Timeout error"],
  "suggested_action": "Investigate payment gateway logs and reach out to user"
}
```

## Categories

| Category | Description |
|----------|-------------|
| Praise | Positive feedback, appreciation |
| Complaint | Negative feedback (service working) |
| Experience Breakage | Technical issues, bugs, failures |
| Feature Request | Suggestions for improvements |

## Supported Products

- Payment Gateway, Payment Links, Payment Pages, Payment Buttons
- Subscriptions, Smart Collect, QR Codes, POS
- Route, Razorpay X, Payroll, Capital
- Tokenisation, Magic Checkout, Instant Settlements
- Disputes, Dashboard, Support, Onboarding/KYC

## Files

| File | Description |
|------|-------------|
| `classify_tweet.py` | Core classification logic |
| `analyze_tweets.py` | Batch processing script |
| `fetch_tweets.py` | Twitter/X data fetcher |
| `test_azure_openai.py` | API connection test |
| `tweets.json` | Input tweets data |
| `analysis_results.json` | Output analysis results |

## API

Uses Azure OpenAI GPT model with vision capabilities for text + image analysis.

---

Built for Razorpay Hackon FY26 Q3

