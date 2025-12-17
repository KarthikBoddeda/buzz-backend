"""
Application Configuration
Centralizes all configuration settings with environment variable support.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (override=True to reload)
load_dotenv(override=True)


# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_DIR = DATA_DIR / "db"

# Ensure directories exist
DB_DIR.mkdir(parents=True, exist_ok=True)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_DIR}/buzz.db")

# Twitter API credentials
TWITTER_AUTH_TOKEN = os.getenv(
    "TWITTER_AUTH_TOKEN",
    "318969313bcce70b4ce79ee0f2bd9894284b678c"
)
TWITTER_CSRF_TOKEN = os.getenv(
    "TWITTER_CSRF_TOKEN",
    "59129146a000bff89f83651651da577a80395b1e1aae8ebbdf7d9a9e89d21fcc59b544ba05665ae39ca5f08f02ae06cfc990ef24431ed2c308102b4b0fb8038d06ab3de67baeaa0c7f338bc4b13c8c70"
)
TWITTER_TRANSACTION_ID = os.getenv(
    "TWITTER_TRANSACTION_ID",
    "IZshTjw3WuAJ55XEPDofJEb0oHY0hLuMY45ZVlH9u3hUnirpqjRI6dMDiM1cEKniwmuh0yXMzhJRUvWD0lbOmkknd9YFIg"
)

# Azure OpenAI
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://siddh-m9gwv1hd-eastus2.cognitiveservices.azure.com"
)
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "hackon-fy26q3-gpt5")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

# Scraper settings
SCRAPER_SEARCH_QUERY = os.getenv("SCRAPER_SEARCH_QUERY", "Razorpay")
SCRAPER_INTERVAL_SECONDS = int(os.getenv("SCRAPER_INTERVAL_SECONDS", "30"))
SCRAPER_WINDOW_MINUTES = int(os.getenv("SCRAPER_WINDOW_MINUTES", "30"))
SCRAPER_MAX_RUNS = int(os.getenv("SCRAPER_MAX_RUNS", "3"))  # Limit runs for testing
SCRAPER_START_DATE = os.getenv("SCRAPER_START_DATE", "2025-11-01 00:00:00")  # Nov 1, 2025 morning

# LinkedIn API credentials (get from browser DevTools)
LINKEDIN_LI_AT = os.getenv("LINKEDIN_LI_AT")
LINKEDIN_JSESSIONID = os.getenv("LINKEDIN_JSESSIONID")

# =============================================================================
# COMPANIES CONFIGURATION
# =============================================================================
# Define Razorpay and its competitors for multi-company scraping
# Each company has:
#   - name: Internal identifier (stored in DB)
#   - keywords: Search terms to use (can include variations, handles, etc.)
#   - is_primary: True for Razorpay (our company), False for competitors

COMPANIES = {
    "razorpay": {
        "name": "razorpay",
        "display_name": "Razorpay",
        "keywords": ["Razorpay", "@Razorpay", "@RazorpayCare", "@RazorpayX"],
        "twitter_handles": ["Razorpay", "RazorpayCare", "RazorpayX"],
        "linkedin_company_id": "3788927",
        "is_primary": True,
        "category": "payment_gateway",
    },
    "payu": {
        "name": "payu",
        "display_name": "PayU",
        "keywords": ["PayU India", "@PayUIndia", "PayU payment"],
        "twitter_handles": ["PayUIndia"],
        "linkedin_company_id": "14619",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "cashfree": {
        "name": "cashfree",
        "display_name": "Cashfree Payments",
        "keywords": ["Cashfree", "@gocashfree", "Cashfree Payments"],
        "twitter_handles": ["gocashfree"],
        "linkedin_company_id": "9272569",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "paytm": {
        "name": "paytm",
        "display_name": "Paytm",
        "keywords": ["Paytm payment gateway", "@Paytm", "Paytm business"],
        "twitter_handles": ["Paytm", "Paytmcare"],
        "linkedin_company_id": "278129",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "phonepe": {
        "name": "phonepe",
        "display_name": "PhonePe",
        "keywords": ["PhonePe business", "@PhonePe", "PhonePe payment"],
        "twitter_handles": ["PhonePe", "PhonePeSupport"],
        "linkedin_company_id": "6429766",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "instamojo": {
        "name": "instamojo",
        "display_name": "Instamojo",
        "keywords": ["Instamojo", "@instamojo"],
        "twitter_handles": ["instamojo"],
        "linkedin_company_id": "3059986",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "ccavenue": {
        "name": "ccavenue",
        "display_name": "CCAvenue",
        "keywords": ["CCAvenue", "@CCAvenue"],
        "twitter_handles": ["CCAvenue"],
        "linkedin_company_id": "539559",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "stripe": {
        "name": "stripe",
        "display_name": "Stripe",
        "keywords": ["Stripe India", "@stripe", "Stripe payment"],
        "twitter_handles": ["stripe"],
        "linkedin_company_id": "628402",
        "is_primary": False,
        "category": "payment_gateway",
    },
    "juspay": {
        "name": "juspay",
        "display_name": "Juspay",
        "keywords": ["Juspay", "@juspay_tech", "Juspay payment"],
        "twitter_handles": ["juspay_tech"],
        "linkedin_company_id": "2647580",
        "is_primary": False,
        "category": "payment_gateway",
    },
}

def get_company(name: str) -> dict:
    """Get company config by name."""
    return COMPANIES.get(name.lower())

def get_all_companies() -> list:
    """Get list of all company names."""
    return list(COMPANIES.keys())

def get_competitors() -> list:
    """Get list of competitor company names (non-primary)."""
    return [k for k, v in COMPANIES.items() if not v.get("is_primary")]

def get_primary_company() -> str:
    """Get the primary company name (Razorpay)."""
    for k, v in COMPANIES.items():
        if v.get("is_primary"):
            return k
    return "razorpay"

