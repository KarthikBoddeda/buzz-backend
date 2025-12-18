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


class RawPost(Base):
    """
    Stores raw scraped posts from any platform (Twitter, LinkedIn, etc).
    This is the first stage before classification.
    """
    
    __tablename__ = "raw_post"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Platform-specific post ID (tweet_id, activity_id, etc)
    post_id = Column(String(64), nullable=False, index=True)
    
    # Source platform: twitter, linkedin
    platform = Column(String(32), nullable=False, index=True)
    
    # Company this data was scraped for (razorpay, paytm, phonepe, etc.)
    # Used to identify if this is about our company or competitors (leads/opportunities)
    company = Column(String(64), nullable=False, default="razorpay", index=True)
    
    # Unique constraint: platform + post_id
    # A post can only exist once per platform
    
    # Post content
    full_text = Column(Text, nullable=False)
    language = Column(String(10), nullable=True)
    
    # Author information
    author_id = Column(String(64), nullable=True)
    author_name = Column(String(256), nullable=True)
    author_username = Column(String(128), nullable=True, index=True)
    author_description = Column(Text, nullable=True)
    author_followers_count = Column(Integer, default=0)
    author_following_count = Column(Integer, default=0)
    author_connections_count = Column(Integer, default=0)
    author_is_verified = Column(Boolean, default=False)
    author_profile_url = Column(String(512), nullable=True)
    author_profile_image_url = Column(String(512), nullable=True)
    
    # Engagement metrics
    likes_count = Column(Integer, default=0)
    comments_count = Column(Integer, default=0)
    shares_count = Column(Integer, default=0)  # retweets for Twitter
    views_count = Column(Integer, default=0)
    
    # Post metadata
    post_url = Column(String(512), nullable=True)
    is_reply = Column(Boolean, default=False)
    is_quote = Column(Boolean, default=False)
    in_reply_to_post_id = Column(String(64), nullable=True)
    in_reply_to_user = Column(String(128), nullable=True)
    
    # Raw data as JSON (full API response for reference)
    raw_data = Column(JSON, nullable=True)
    
    # Search/scrape context
    search_query = Column(String(256), nullable=True, index=True)
    
    # Timestamps
    posted_at = Column(DateTime, nullable=True, index=True)  # When the post was created
    scraped_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    # Processing status
    is_classified = Column(Boolean, default=False, index=True)
    
    __table_args__ = (
        # Unique constraint on platform + post_id
        Index("ix_raw_post_platform_post_id", "platform", "post_id", unique=True),
        # For finding unclassified posts
        Index("ix_raw_post_is_classified_scraped_at", "is_classified", "scraped_at"),
        # For time-based queries
        Index("ix_raw_post_platform_posted_at", "platform", "posted_at"),
        # For company-specific queries
        Index("ix_raw_post_company_platform", "company", "platform"),
    )
    
    def __repr__(self):
        return f"<RawPost(id={self.id}, company={self.company}, platform={self.platform}, post_id={self.post_id})>"
    
    @classmethod
    def from_linkedin_post(cls, post_data: dict, search_query: str = None) -> "RawPost":
        """Create a RawPost from LinkedIn scraper data."""
        user = post_data.get("user", {})
        
        return cls(
            post_id=post_data.get("id") or post_data.get("urn", "").split(":")[-1],
            platform="linkedin",
            full_text=post_data.get("full_text") or post_data.get("text", ""),
            language=post_data.get("language", "en"),
            author_id=user.get("id"),
            author_name=post_data.get("author") or user.get("name"),
            author_username=post_data.get("author_username") or user.get("screen_name"),
            author_description=post_data.get("author_title") or user.get("description"),
            author_followers_count=post_data.get("followers_count") or user.get("followers_count", 0),
            author_connections_count=post_data.get("connections_count") or user.get("connections_count", 0),
            author_profile_url=post_data.get("author_profile_url") or user.get("profile_url"),
            author_profile_image_url=user.get("profile_image_url"),
            likes_count=post_data.get("likes") or post_data.get("favorite_count", 0),
            comments_count=post_data.get("comments") or post_data.get("reply_count", 0),
            shares_count=post_data.get("retweet_count", 0),
            views_count=post_data.get("view_count", 0),
            post_url=post_data.get("post_url"),
            is_reply=post_data.get("is_reply", False),
            raw_data=post_data,
            search_query=search_query,
        )
    
    @classmethod
    def from_twitter_post(cls, post_data: dict, search_query: str = None) -> "RawPost":
        """Create a RawPost from Twitter scraper data."""
        user = post_data.get("user", {})
        
        # Parse Twitter timestamp
        posted_at = None
        if post_data.get("created_at"):
            try:
                posted_at = datetime.strptime(
                    post_data["created_at"],
                    "%a %b %d %H:%M:%S %z %Y"
                )
            except (ValueError, TypeError):
                pass
        
        return cls(
            post_id=post_data.get("id", ""),
            platform="twitter",
            full_text=post_data.get("full_text", ""),
            language=post_data.get("language"),
            author_id=user.get("id"),
            author_name=user.get("name"),
            author_username=user.get("screen_name"),
            author_description=user.get("description"),
            author_followers_count=user.get("followers_count", 0),
            author_following_count=user.get("following_count", 0),
            author_is_verified=user.get("is_verified", False),
            author_profile_image_url=user.get("profile_image_url"),
            likes_count=post_data.get("favorite_count", 0),
            comments_count=post_data.get("reply_count", 0),
            shares_count=post_data.get("retweet_count", 0),
            views_count=post_data.get("view_count", 0),
            post_url=post_data.get("tweet_url"),
            is_reply=post_data.get("is_reply", False),
            is_quote=post_data.get("is_quote", False),
            in_reply_to_post_id=post_data.get("in_reply_to_tweet_id"),
            in_reply_to_user=post_data.get("in_reply_to_user"),
            raw_data=post_data,
            search_query=search_query,
            posted_at=posted_at,
        )


class Post(Base):
    """
    Stores classified/analyzed posts after the classifier layer.
    Links to the original raw post.
    """
    
    __tablename__ = "posts"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Reference to raw post
    raw_post_id = Column(Integer, nullable=False, index=True)
    
    # Company this data was scraped for (razorpay, paytm, phonepe, etc.)
    # Used to identify if this is about our company or competitors (leads/opportunities)
    company = Column(String(64), nullable=False, default="razorpay", index=True)
    
    # Denormalized post info (for easy querying without joins)
    platform = Column(String(32), nullable=True, index=True)  # twitter, linkedin
    post_id = Column(String(64), nullable=True, index=True)   # tweet_id or activity_id
    post_url = Column(String(512), nullable=True)
    posted_at = Column(DateTime, nullable=True, index=True)   # When the original post was created
    author_name = Column(String(256), nullable=True)
    author_username = Column(String(128), nullable=True)
    author_followers_count = Column(Integer, default=0)
    
    # Classification results
    is_spam = Column(Boolean, default=False, index=True)
    spam_reason = Column(Text, nullable=True)
    
    # Category: Praise, Complaint, Experience Breakage, Feature Request, Sales Opportunity
    category = Column(String(64), nullable=True, index=True)
    
    # Product mentioned (Payment Gateway, Razorpay X, etc.)
    product = Column(String(128), nullable=True, index=True)
    
    # Scores (1-10)
    sentiment_score = Column(Integer, nullable=True)
    urgency_score = Column(Integer, nullable=True)
    impact_score = Column(Integer, nullable=True)
    
    # Analysis details
    summary = Column(Text, nullable=True)
    key_issues = Column(JSON, nullable=True)  # List of issues
    suggested_action = Column(Text, nullable=True)
    
    # Analysis status
    analysis_success = Column(Boolean, default=True)
    analysis_error = Column(Text, nullable=True)
    
    # Full classification response
    classification_data = Column(JSON, nullable=True)
    
    # Processing metadata
    classified_at = Column(DateTime, server_default=func.now(), nullable=False)
    classifier_version = Column(String(32), nullable=True)  # For tracking model versions
    
    # Token usage (for cost tracking)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # ============================================
    # INTERNAL TEAM TRACKING
    # ============================================
    
    # Slack integration
    raised_on_slack = Column(Boolean, default=False, index=True)
    slack_channel = Column(String(128), nullable=True)
    slack_message_ts = Column(String(64), nullable=True)  # Slack message timestamp for threading
    slack_raised_at = Column(DateTime, nullable=True)
    slack_raised_by = Column(String(128), nullable=True)
    
    # Ticket tracking (Jira, Zendesk, etc.)
    ticket_created = Column(Boolean, default=False, index=True)
    ticket_id = Column(String(64), nullable=True, index=True)
    ticket_url = Column(String(512), nullable=True)
    ticket_system = Column(String(32), nullable=True)  # jira, zendesk, freshdesk
    ticket_created_at = Column(DateTime, nullable=True)
    
    # Team assignment
    assigned_team = Column(String(128), nullable=True, index=True)  # support, engineering, product
    assigned_to = Column(String(128), nullable=True)  # Individual assignee
    
    # Status tracking
    status = Column(String(32), default="new", index=True)  # new, acknowledged, in_progress, resolved, closed
    resolution = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    
    # Internal notes
    internal_notes = Column(Text, nullable=True)
    
    # Priority (computed from urgency + impact or manually set)
    priority = Column(String(16), nullable=True, index=True)  # low, medium, high, critical
    
    __table_args__ = (
        # For finding posts by category
        Index("ix_post_category_sentiment", "category", "sentiment_score"),
        # For finding high-urgency posts
        Index("ix_post_urgency_impact", "urgency_score", "impact_score"),
        # For product-specific queries
        Index("ix_post_product_category", "product", "category"),
        # For finding unactioned posts
        Index("ix_post_status_urgency", "status", "urgency_score"),
        # For Slack tracking
        Index("ix_post_slack_ticket", "raised_on_slack", "ticket_created"),
        # For company-specific queries
        Index("ix_post_company_category", "company", "category"),
        Index("ix_post_company_status", "company", "status"),
    )
    
    def __repr__(self):
        return f"<Post(id={self.id}, company={self.company}, platform={self.platform}, category={self.category})>"
    
    def compute_priority(self) -> str:
        """Compute priority based on urgency and impact scores."""
        if not self.urgency_score or not self.impact_score:
            return "medium"
        
        combined = (self.urgency_score + self.impact_score) / 2
        if combined >= 8:
            return "critical"
        elif combined >= 6:
            return "high"
        elif combined >= 4:
            return "medium"
        else:
            return "low"
    
    @classmethod
    def from_classification_result(
        cls, 
        raw_post_id: int, 
        classification: dict,
        usage: dict = None,
        raw_post_data: dict = None,
        company: str = "razorpay"
    ) -> "Post":
        """Create a Post from classifier output."""
        instance = cls(
            raw_post_id=raw_post_id,
            company=company,
            is_spam=classification.get("is_spam", False),
            spam_reason=classification.get("spam_reason"),
            category=classification.get("category"),
            product=classification.get("product"),
            sentiment_score=classification.get("sentiment_score"),
            urgency_score=classification.get("urgency_score"),
            impact_score=classification.get("impact_score"),
            summary=classification.get("summary"),
            key_issues=classification.get("key_issues"),
            suggested_action=classification.get("suggested_action"),
            classification_data=classification,
            analysis_success=True,
            prompt_tokens=usage.get("prompt_tokens", 0) if usage else 0,
            completion_tokens=usage.get("completion_tokens", 0) if usage else 0,
            total_tokens=usage.get("total_tokens", 0) if usage else 0,
        )
        
        # Add denormalized post data if provided
        if raw_post_data:
            instance.platform = raw_post_data.get("platform")
            instance.post_id = raw_post_data.get("post_id")
            instance.post_url = raw_post_data.get("post_url")
            instance.posted_at = raw_post_data.get("posted_at")
            instance.author_name = raw_post_data.get("author_name")
            instance.author_username = raw_post_data.get("author_username")
            instance.author_followers_count = raw_post_data.get("author_followers_count", 0)
            # Inherit company from raw post if not specified
            if raw_post_data.get("company"):
                instance.company = raw_post_data.get("company")
        
        # Compute priority
        instance.priority = instance.compute_priority()
        
        return instance

