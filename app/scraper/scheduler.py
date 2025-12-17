"""
Twitter Scraper Scheduler
Runs continuously, scraping tweets every 30 seconds.

Flow:
1. Check if entries exist in DB -> get latest conversation time
2. If no entries, start from SCRAPER_START_DATE (Nov 1, 2025)
3. Scrape tweets in 30-minute windows
4. For each tweet, fetch the full conversation
5. Store conversations with idempotency check on conversation_id
6. Update scraper state for resumability
"""

import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import (
    TWITTER_AUTH_TOKEN,
    TWITTER_CSRF_TOKEN,
    TWITTER_TRANSACTION_ID,
    SCRAPER_SEARCH_QUERY,
    SCRAPER_INTERVAL_SECONDS,
    SCRAPER_WINDOW_MINUTES,
    SCRAPER_MAX_RUNS,
    SCRAPER_START_DATE,
)
from app.db.database import get_db_session, init_db
from app.db.models import Conversation, ScraperState
from app.scraper.twitter import TwitterSearchAPI


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class TwitterScraper:
    """
    Production-ready Twitter scraper with:
    - Idempotency checks on conversation_id
    - Resumable scraping from last successful window
    - Full conversation fetching for each tweet
    - Configurable time windows and intervals
    """
    
    def __init__(
        self,
        search_query: str = SCRAPER_SEARCH_QUERY,
        window_minutes: int = SCRAPER_WINDOW_MINUTES,
        max_runs: int = SCRAPER_MAX_RUNS,
    ):
        self.search_query = search_query
        self.window_minutes = window_minutes
        self.max_runs = max_runs
        self.source = "twitter"
        
        # Initialize Twitter API client
        self.api = TwitterSearchAPI(
            auth_token=TWITTER_AUTH_TOKEN,
            csrf_token=TWITTER_CSRF_TOKEN,
            transaction_id=TWITTER_TRANSACTION_ID,
        )
        
        logger.info(f"Scraper initialized: query='{search_query}', window={window_minutes}min, max_runs={max_runs}")
    
    def get_start_time(self) -> datetime:
        """
        Determine the start time for scraping.
        
        Priority:
        1. If scraper_state exists, use last_window_end (to continue from where we left off)
        2. Otherwise, use SCRAPER_START_DATE (Nov 1, 2025)
        
        Returns:
            datetime: Start time for the next scrape window (UTC)
        """
        with get_db_session() as db:
            # Check scraper state for last window end
            state = db.query(ScraperState).filter(
                ScraperState.source == self.source,
                ScraperState.search_query == self.search_query,
            ).first()
            
            if state and state.last_window_end:
                last_end = state.last_window_end
                # Ensure timezone awareness
                if last_end.tzinfo is None:
                    last_end = last_end.replace(tzinfo=timezone.utc)
                # Start from where we left off
                logger.info(f"Resuming from last window end: {last_end}")
                return last_end
            
            # No existing state, start from configured date
            start_time = datetime.strptime(SCRAPER_START_DATE, "%Y-%m-%d %H:%M:%S")
            start_time = start_time.replace(tzinfo=timezone.utc)
            logger.info(f"No existing data, starting from: {start_time}")
            return start_time
    
    def get_run_count(self) -> int:
        """Get the current run count from scraper state."""
        with get_db_session() as db:
            state = db.query(ScraperState).filter(
                ScraperState.source == self.source,
                ScraperState.search_query == self.search_query,
            ).first()
            
            return state.run_count if state else 0
    
    def update_scraper_state(self, window_start: datetime, window_end: datetime):
        """Update scraper state after a successful run."""
        with get_db_session() as db:
            state = db.query(ScraperState).filter(
                ScraperState.source == self.source,
                ScraperState.search_query == self.search_query,
            ).first()
            
            if state:
                state.last_window_start = window_start
                state.last_window_end = window_end
                state.run_count += 1
            else:
                state = ScraperState(
                    source=self.source,
                    search_query=self.search_query,
                    last_window_start=window_start,
                    last_window_end=window_end,
                    run_count=1,
                )
                db.add(state)
            
            db.commit()
            logger.info(f"Scraper state updated: run #{state.run_count}")
    
    def conversation_exists(self, conversation_id: str) -> bool:
        """Check if a conversation already exists (idempotency check)."""
        with get_db_session() as db:
            exists = db.query(Conversation.id).filter(
                Conversation.conversation_id == conversation_id
            ).first() is not None
            return exists
    
    def save_conversation(self, conversation_data: dict) -> Optional[Conversation]:
        """
        Save a conversation to the database with idempotency check.
        
        Returns:
            Conversation if saved, None if already exists
        """
        conv_id = conversation_data.get("conversation_id")
        if not conv_id:
            main_tweet = conversation_data.get("main_tweet", {})
            conv_id = main_tweet.get("conversation_id")
        
        if not conv_id:
            logger.warning("Conversation has no conversation_id, skipping")
            return None
        
        # Idempotency check
        if self.conversation_exists(conv_id):
            logger.debug(f"Conversation {conv_id} already exists, skipping")
            return None
        
        with get_db_session() as db:
            conv = Conversation.from_twitter_conversation(
                conversation_data,
                search_query=self.search_query,
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)
            logger.info(f"Saved conversation {conv_id} with {conv.reply_count} replies")
            return conv
    
    def scrape_window(self, window_start: datetime, window_end: datetime) -> dict:
        """
        Scrape all tweets in a time window and fetch their conversations.
        
        Args:
            window_start: Start of time window
            window_end: End of time window
            
        Returns:
            Dict with stats: tweets_found, conversations_saved, duplicates_skipped
        """
        stats = {
            "tweets_found": 0,
            "conversations_saved": 0,
            "duplicates_skipped": 0,
            "errors": 0,
        }
        
        # Convert to timestamps for Twitter API
        since_time = int(window_start.timestamp())
        until_time = int(window_end.timestamp())
        
        logger.info(f"Scraping window: {window_start} to {window_end}")
        logger.info(f"Timestamps: since={since_time}, until={until_time}")
        
        try:
            # Fetch ALL tweets in the window (full pagination)
            tweets = self.api.fetch_all(
                query=self.search_query,
                since_time=since_time,
                until_time=until_time,
                product="Latest",
                max_pages=50,  # Safety limit
            )
            
            stats["tweets_found"] = len(tweets)
            logger.info(f"Found {len(tweets)} tweets in window")
            
            # Process each tweet - get unique conversation IDs
            conversation_ids = set()
            for tweet in tweets:
                conv_id = tweet.get("conversation_id")
                if conv_id:
                    conversation_ids.add(conv_id)
            
            logger.info(f"Found {len(conversation_ids)} unique conversations")
            
            # Fetch full conversation for each
            for conv_id in conversation_ids:
                try:
                    # Idempotency check before making API call
                    if self.conversation_exists(conv_id):
                        stats["duplicates_skipped"] += 1
                        logger.debug(f"Skipping existing conversation: {conv_id}")
                        continue
                    
                    # Fetch full conversation
                    logger.info(f"Fetching conversation: {conv_id}")
                    conversation_data = self.api.get_conversation_parsed(conv_id)
                    
                    # Save to database
                    saved = self.save_conversation(conversation_data)
                    if saved:
                        stats["conversations_saved"] += 1
                    else:
                        stats["duplicates_skipped"] += 1
                    
                    # Small delay to avoid rate limiting
                    time.sleep(0.5)
                    
                except Exception as e:
                    stats["errors"] += 1
                    logger.error(f"Error fetching conversation {conv_id}: {e}")
                    continue
            
        except Exception as e:
            logger.error(f"Error scraping window: {e}")
            raise
        
        return stats
    
    def run_once(self) -> dict:
        """
        Run a single scrape iteration.
        
        Returns:
            Dict with stats from the scrape
        """
        # Get start time (from DB or config)
        window_start = self.get_start_time()
        window_end = window_start + timedelta(minutes=self.window_minutes)
        
        # Don't scrape into the future
        now = datetime.now(timezone.utc)
        if window_end > now:
            window_end = now
        
        if window_start >= window_end:
            logger.info("Start time is in the future or equal to end time, nothing to scrape")
            return {"status": "skipped", "reason": "no_new_window"}
        
        # Scrape the window
        stats = self.scrape_window(window_start, window_end)
        
        # Update scraper state
        self.update_scraper_state(window_start, window_end)
        
        return stats
    
    def run(self):
        """
        Run the scraper continuously at configured intervals.
        Stops after max_runs iterations.
        """
        run_count = self.get_run_count()
        
        if run_count >= self.max_runs:
            logger.info(f"Already completed {run_count} runs (max={self.max_runs}), exiting")
            return
        
        remaining_runs = self.max_runs - run_count
        logger.info(f"Starting scraper: {remaining_runs} runs remaining")
        
        for i in range(remaining_runs):
            current_run = run_count + i + 1
            logger.info(f"\n{'='*60}")
            logger.info(f"RUN {current_run}/{self.max_runs}")
            logger.info(f"{'='*60}")
            
            try:
                stats = self.run_once()
                logger.info(f"Run {current_run} complete: {stats}")
                
            except Exception as e:
                logger.error(f"Run {current_run} failed: {e}")
            
            # Wait before next run (except for last run)
            if i < remaining_runs - 1:
                logger.info(f"Waiting {SCRAPER_INTERVAL_SECONDS} seconds before next run...")
                time.sleep(SCRAPER_INTERVAL_SECONDS)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraper completed all {self.max_runs} runs")
        logger.info(f"{'='*60}")


def main():
    """Main entry point for the scraper."""
    logger.info("Initializing database...")
    init_db()
    
    logger.info("Starting Twitter scraper...")
    scraper = TwitterScraper()
    scraper.run()


if __name__ == "__main__":
    main()

