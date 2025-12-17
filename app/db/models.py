"""
Database Models
Defines SQLAlchemy models for storing scraped data.
"""

from datetime import datetime
from typing import Optional
import json

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Index,
    Boolean,
    JSON,
)
from sqlalchemy.sql import func

from app.db.database import Base


class Conversation(Base):
    """
    Stores Twitter conversations with full thread data.
    
    Each row represents a unique conversation (thread) identified by conversation_id.
    The conversation JSON contains the main tweet and all replies.
    """
    
    __tablename__ = "conversations"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique conversation identifier from Twitter
    # This is the conversation_id from the main tweet
    conversation_id = Column(String(64), unique=True, nullable=False, index=True)
    
    # Source platform (for future extensibility: twitter, linkedin, etc.)
    source = Column(String(32), nullable=False, default="twitter")
    
    # The main/focal tweet ID that started the conversation
    main_tweet_id = Column(String(64), nullable=False, index=True)
    
    # Full conversation data as JSON
    # Contains: main_tweet, replies, and any other metadata
    conversation = Column(JSON, nullable=False)
    
    # Conversation metrics (denormalized for quick queries)
    reply_count = Column(Integer, default=0)
    
    # Search query that found this conversation
    search_query = Column(String(256), nullable=True)
    
    # Timestamps from the conversation
    started_at = Column(DateTime, nullable=True, index=True)  # When the main tweet was posted
    last_reply_at = Column(DateTime, nullable=True, index=True)  # When the last reply was posted
    
    # Scraper metadata
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Processing status
    is_analyzed = Column(Boolean, default=False, index=True)
    
    # Composite indexes for common query patterns
    __table_args__ = (
        # For querying by source and time range
        Index("ix_conversations_source_started_at", "source", "started_at"),
        # For finding unanalyzed conversations
        Index("ix_conversations_is_analyzed_created_at", "is_analyzed", "created_at"),
        # For pagination by time
        Index("ix_conversations_source_last_reply_at", "source", "last_reply_at"),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, conversation_id={self.conversation_id}, replies={self.reply_count})>"
    
    @classmethod
    def from_twitter_conversation(
        cls,
        conversation_data: dict,
        search_query: str = None
    ) -> "Conversation":
        """
        Create a Conversation instance from Twitter API response.
        
        Args:
            conversation_data: Dict with 'main_tweet', 'replies', 'conversation_id'
            search_query: The search query used to find this conversation
            
        Returns:
            Conversation instance (not yet added to session)
        """
        main_tweet = conversation_data.get("main_tweet", {})
        replies = conversation_data.get("replies", [])
        
        # Parse timestamps
        started_at = None
        last_reply_at = None
        
        if main_tweet and main_tweet.get("created_at"):
            try:
                # Twitter format: "Tue Dec 16 06:31:32 +0000 2025"
                started_at = datetime.strptime(
                    main_tweet["created_at"],
                    "%a %b %d %H:%M:%S %z %Y"
                )
            except (ValueError, TypeError):
                pass
        
        # Find the latest reply timestamp
        if replies:
            reply_times = []
            for reply in replies:
                if reply.get("created_at"):
                    try:
                        reply_time = datetime.strptime(
                            reply["created_at"],
                            "%a %b %d %H:%M:%S %z %Y"
                        )
                        reply_times.append(reply_time)
                    except (ValueError, TypeError):
                        pass
            if reply_times:
                last_reply_at = max(reply_times)
        
        # If no replies, last_reply_at is same as started_at
        if not last_reply_at:
            last_reply_at = started_at
        
        return cls(
            conversation_id=conversation_data.get("conversation_id") or main_tweet.get("conversation_id"),
            source="twitter",
            main_tweet_id=main_tweet.get("id", ""),
            conversation=conversation_data,
            reply_count=len(replies),
            search_query=search_query,
            started_at=started_at,
            last_reply_at=last_reply_at,
        )
    
    def get_main_tweet_text(self) -> Optional[str]:
        """Get the main tweet's full text."""
        if self.conversation and isinstance(self.conversation, dict):
            main_tweet = self.conversation.get("main_tweet", {})
            return main_tweet.get("full_text")
        return None
    
    def get_all_tweet_texts(self) -> list[str]:
        """Get all tweet texts (main + replies) in the conversation."""
        texts = []
        if self.conversation and isinstance(self.conversation, dict):
            main_tweet = self.conversation.get("main_tweet", {})
            if main_tweet.get("full_text"):
                texts.append(main_tweet["full_text"])
            
            for reply in self.conversation.get("replies", []):
                if reply.get("full_text"):
                    texts.append(reply["full_text"])
        return texts


class ScraperState(Base):
    """
    Tracks scraper state for resumable scraping.
    Stores the last successful scrape window for each source/query combination.
    """
    
    __tablename__ = "scraper_state"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Unique identifier for this scraper config
    source = Column(String(32), nullable=False)
    search_query = Column(String(256), nullable=False)
    
    # Last successful window
    last_window_start = Column(DateTime, nullable=True)
    last_window_end = Column(DateTime, nullable=True)
    
    # Run count
    run_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index("ix_scraper_state_source_query", "source", "search_query", unique=True),
    )
    
    def __repr__(self):
        return f"<ScraperState(source={self.source}, query={self.search_query}, runs={self.run_count})>"

