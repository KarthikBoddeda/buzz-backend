"""
Application Configuration
Centralizes all configuration settings with environment variable support.
"""

import os
from pathlib import Path


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

