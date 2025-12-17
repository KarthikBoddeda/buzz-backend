"""
Database Repository
Helper functions for CRUD operations on posts.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.db.models import RawPost, Post
from app.db.database import get_db_session

# Alias for backwards compatibility
ClassifiedPost = Post


def save_raw_post(post_data: dict, platform: str, search_query: str = None, company: str = "razorpay") -> Optional[RawPost]:
    """
    Save a raw post to the database.
    Returns the saved post, or None if it already exists.
    
    Args:
        post_data: Raw post data from scraper
        platform: Source platform (twitter, linkedin)
        search_query: Search query used to find this post
        company: Company this data was scraped for (razorpay, paytm, etc.)
    """
    with get_db_session() as db:
        # Check if post already exists
        post_id = post_data.get("id") or post_data.get("urn", "").split(":")[-1]
        existing = db.query(RawPost).filter(
            and_(RawPost.platform == platform, RawPost.post_id == post_id)
        ).first()
        
        if existing:
            return None  # Already exists
        
        # Create new post based on platform
        if platform == "linkedin":
            raw_post = RawPost.from_linkedin_post(post_data, search_query)
        elif platform == "twitter":
            raw_post = RawPost.from_twitter_post(post_data, search_query)
        else:
            raise ValueError(f"Unknown platform: {platform}")
        
        # Set company
        raw_post.company = company
        
        db.add(raw_post)
        db.flush()
        db.refresh(raw_post)
        return raw_post


def save_raw_posts_batch(
    posts: List[dict], 
    platform: str, 
    search_query: str = None,
    company: str = "razorpay"
) -> Dict[str, int]:
    """
    Save multiple raw posts to the database.
    Returns counts of saved and skipped posts.
    
    Args:
        posts: List of raw post data from scraper
        platform: Source platform (twitter, linkedin)
        search_query: Search query used to find these posts
        company: Company this data was scraped for (razorpay, paytm, etc.)
    """
    saved = 0
    skipped = 0
    
    with get_db_session() as db:
        for post_data in posts:
            post_id = post_data.get("id") or post_data.get("urn", "").split(":")[-1]
            
            # Check if exists
            existing = db.query(RawPost).filter(
                and_(RawPost.platform == platform, RawPost.post_id == post_id)
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            # Create new post
            if platform == "linkedin":
                raw_post = RawPost.from_linkedin_post(post_data, search_query)
            elif platform == "twitter":
                raw_post = RawPost.from_twitter_post(post_data, search_query)
            else:
                continue
            
            # Set company
            raw_post.company = company
            
            db.add(raw_post)
            saved += 1
        
        db.commit()
    
    return {"saved": saved, "skipped": skipped}


def get_unclassified_posts(
    platform: str = None,
    company: str = None,
    limit: int = 100
) -> List[Dict]:
    """Get posts that haven't been classified yet. Returns as dictionaries."""
    with get_db_session() as db:
        query = db.query(RawPost).filter(RawPost.is_classified == False)
        
        if platform:
            query = query.filter(RawPost.platform == platform)
        if company:
            query = query.filter(RawPost.company == company)
        
        posts = query.order_by(RawPost.scraped_at.desc()).limit(limit).all()
        
        # Convert to dictionaries to avoid detached session issues
        return [
            {
                "id": p.id,
                "post_id": p.post_id,
                "platform": p.platform,
                "company": p.company,
                "full_text": p.full_text,
                "language": p.language,
                "author_id": p.author_id,
                "author_name": p.author_name,
                "author_username": p.author_username,
                "author_description": p.author_description,
                "author_followers_count": p.author_followers_count,
                "author_following_count": p.author_following_count,
                "author_connections_count": p.author_connections_count,
                "author_is_verified": p.author_is_verified,
                "author_profile_url": p.author_profile_url,
                "likes_count": p.likes_count,
                "comments_count": p.comments_count,
                "shares_count": p.shares_count,
                "views_count": p.views_count,
                "post_url": p.post_url,
                "is_reply": p.is_reply,
                "search_query": p.search_query,
                "posted_at": p.posted_at,
                "scraped_at": p.scraped_at,
            }
            for p in posts
        ]


def get_raw_post_by_id(post_id: int) -> Optional[RawPost]:
    """Get a raw post by its database ID."""
    with get_db_session() as db:
        return db.query(RawPost).filter(RawPost.id == post_id).first()


def save_classification(
    raw_post_id: int,
    classification: dict,
    usage: dict = None,
    raw_post_data: dict = None,
    company: str = None
) -> int:
    """
    Save classification results and mark raw post as classified.
    Returns the classified post ID.
    """
    with get_db_session() as db:
        # Get raw post data if not provided
        raw_post = db.query(RawPost).filter(RawPost.id == raw_post_id).first()
        if not raw_post_data and raw_post:
            raw_post_data = {
                "platform": raw_post.platform,
                "post_id": raw_post.post_id,
                "post_url": raw_post.post_url,
                "posted_at": raw_post.posted_at,
                "author_name": raw_post.author_name,
                "author_username": raw_post.author_username,
                "author_followers_count": raw_post.author_followers_count,
                "company": raw_post.company,
            }
        
        # Use company from raw_post if not specified
        if not company and raw_post:
            company = raw_post.company
        
        # Create classified post
        classified = Post.from_classification_result(
            raw_post_id=raw_post_id,
            classification=classification,
            usage=usage,
            raw_post_data=raw_post_data,
            company=company or "razorpay"
        )
        db.add(classified)
        
        # Mark raw post as classified
        if raw_post:
            raw_post.is_classified = True
        
        db.commit()
        db.refresh(classified)
        return classified.id  # Return ID instead of object


def get_classified_posts(
    category: str = None,
    product: str = None,
    min_urgency: int = None,
    min_impact: int = None,
    is_spam: bool = None,
    platform: str = None,
    company: str = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Get classified posts with their raw post data.
    Returns joined data for display.
    """
    with get_db_session() as db:
        query = db.query(Post, RawPost).join(
            RawPost, Post.raw_post_id == RawPost.id
        )
        
        if category:
            query = query.filter(Post.category == category)
        if product:
            query = query.filter(Post.product == product)
        if min_urgency:
            query = query.filter(Post.urgency_score >= min_urgency)
        if min_impact:
            query = query.filter(Post.impact_score >= min_impact)
        if is_spam is not None:
            query = query.filter(Post.is_spam == is_spam)
        if platform:
            query = query.filter(RawPost.platform == platform)
        if company:
            query = query.filter(Post.company == company)
        
        results = query.order_by(Post.classified_at.desc()).limit(limit).all()
        
        # Format results
        return [
            {
                "raw_post": {
                    "id": raw.id,
                    "post_id": raw.post_id,
                    "platform": raw.platform,
                    "company": raw.company,
                    "full_text": raw.full_text,
                    "author_name": raw.author_name,
                    "author_username": raw.author_username,
                    "author_followers_count": raw.author_followers_count,
                    "likes_count": raw.likes_count,
                    "comments_count": raw.comments_count,
                    "post_url": raw.post_url,
                    "posted_at": raw.posted_at.isoformat() if raw.posted_at else None,
                    "scraped_at": raw.scraped_at.isoformat() if raw.scraped_at else None,
                },
                "classification": {
                    "id": classified.id,
                    "company": classified.company,
                    "is_spam": classified.is_spam,
                    "category": classified.category,
                    "product": classified.product,
                    "sentiment_score": classified.sentiment_score,
                    "urgency_score": classified.urgency_score,
                    "impact_score": classified.impact_score,
                    "summary": classified.summary,
                    "key_issues": classified.key_issues,
                    "suggested_action": classified.suggested_action,
                    "classified_at": classified.classified_at.isoformat() if classified.classified_at else None,
                }
            }
            for classified, raw in results
        ]


def get_classification_stats(platform: str = None, company: str = None) -> Dict[str, Any]:
    """Get statistics about classified posts."""
    with get_db_session() as db:
        # Base query
        query = db.query(Post, RawPost).join(
            RawPost, Post.raw_post_id == RawPost.id
        )
        
        if platform:
            query = query.filter(RawPost.platform == platform)
        if company:
            query = query.filter(Post.company == company)
        
        results = query.all()
        
        if not results:
            return {"total": 0, "categories": {}, "products": {}, "avg_scores": {}}
        
        # Count categories
        categories = {}
        products = {}
        sentiment_total = 0
        urgency_total = 0
        impact_total = 0
        spam_count = 0
        
        for classified, raw in results:
            # Categories
            cat = classified.category or "Unknown"
            categories[cat] = categories.get(cat, 0) + 1
            
            # Products
            if classified.product:
                products[classified.product] = products.get(classified.product, 0) + 1
            
            # Scores
            if classified.sentiment_score:
                sentiment_total += classified.sentiment_score
            if classified.urgency_score:
                urgency_total += classified.urgency_score
            if classified.impact_score:
                impact_total += classified.impact_score
            
            if classified.is_spam:
                spam_count += 1
        
        total = len(results)
        
        return {
            "total": total,
            "spam_count": spam_count,
            "categories": categories,
            "products": products,
            "avg_scores": {
                "sentiment": round(sentiment_total / total, 2) if total > 0 else 0,
                "urgency": round(urgency_total / total, 2) if total > 0 else 0,
                "impact": round(impact_total / total, 2) if total > 0 else 0,
            }
        }


def get_post_exists(platform: str, post_id: str) -> bool:
    """Check if a post already exists in the database."""
    with get_db_session() as db:
        return db.query(RawPost).filter(
            and_(RawPost.platform == platform, RawPost.post_id == post_id)
        ).first() is not None


def get_scraped_post_ids(platform: str) -> set:
    """Get all post IDs already scraped for a platform."""
    with get_db_session() as db:
        results = db.query(RawPost.post_id).filter(
            RawPost.platform == platform
        ).all()
        return {r[0] for r in results}


# ============================================
# INTERNAL TEAM TRACKING FUNCTIONS
# ============================================

def mark_raised_on_slack(
    post_id: int,
    channel: str,
    message_ts: str = None,
    raised_by: str = None
) -> bool:
    """Mark a post as raised on Slack."""
    with get_db_session() as db:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        
        post.raised_on_slack = True
        post.slack_channel = channel
        post.slack_message_ts = message_ts
        post.slack_raised_at = datetime.now()
        post.slack_raised_by = raised_by
        post.status = "acknowledged" if post.status == "new" else post.status
        
        db.commit()
        return True


def create_ticket(
    post_id: int,
    ticket_id: str,
    ticket_url: str = None,
    ticket_system: str = "jira"
) -> bool:
    """Mark a post as having a ticket created."""
    with get_db_session() as db:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        
        post.ticket_created = True
        post.ticket_id = ticket_id
        post.ticket_url = ticket_url
        post.ticket_system = ticket_system
        post.ticket_created_at = datetime.now()
        post.status = "in_progress" if post.status in ["new", "acknowledged"] else post.status
        
        db.commit()
        return True


def assign_post_to_team(
    post_id: int,
    team: str,
    assignee: str = None
) -> bool:
    """Assign a post to a team/person."""
    with get_db_session() as db:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        
        post.assigned_team = team
        post.assigned_to = assignee
        post.status = "in_progress" if post.status in ["new", "acknowledged"] else post.status
        
        db.commit()
        return True


def resolve_post(
    post_id: int,
    resolution: str
) -> bool:
    """Mark a post as resolved."""
    with get_db_session() as db:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        
        post.status = "resolved"
        post.resolution = resolution
        post.resolved_at = datetime.now()
        
        db.commit()
        return True


def add_internal_note(
    post_id: int,
    note: str
) -> bool:
    """Add an internal note to a post."""
    with get_db_session() as db:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            return False
        
        if post.internal_notes:
            post.internal_notes += f"\n\n[{datetime.now().isoformat()}] {note}"
        else:
            post.internal_notes = f"[{datetime.now().isoformat()}] {note}"
        
        db.commit()
        return True


def get_actionable_posts(
    min_urgency: int = 5,
    status: str = None,
    not_on_slack: bool = False,
    no_ticket: bool = False,
    company: str = None,
    limit: int = 50
) -> List[Dict]:
    """Get posts that need attention."""
    with get_db_session() as db:
        query = db.query(Post).filter(
            Post.is_spam == False,
            Post.urgency_score >= min_urgency
        )
        
        if status:
            query = query.filter(Post.status == status)
        if not_on_slack:
            query = query.filter(Post.raised_on_slack == False)
        if no_ticket:
            query = query.filter(Post.ticket_created == False)
        if company:
            query = query.filter(Post.company == company)
        
        posts = query.order_by(
            Post.urgency_score.desc(),
            Post.impact_score.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": p.id,
                "company": p.company,
                "platform": p.platform,
                "post_id": p.post_id,
                "post_url": p.post_url,
                "author_name": p.author_name,
                "category": p.category,
                "product": p.product,
                "urgency_score": p.urgency_score,
                "impact_score": p.impact_score,
                "priority": p.priority,
                "summary": p.summary,
                "key_issues": p.key_issues,
                "suggested_action": p.suggested_action,
                "status": p.status,
                "raised_on_slack": p.raised_on_slack,
                "ticket_created": p.ticket_created,
                "ticket_id": p.ticket_id,
                "assigned_team": p.assigned_team,
            }
            for p in posts
        ]


def get_team_dashboard_stats(company: str = None) -> Dict:
    """Get statistics for team dashboard."""
    with get_db_session() as db:
        base_query = db.query(Post).filter(Post.is_spam == False)
        if company:
            base_query = base_query.filter(Post.company == company)
        
        total = base_query.count()
        
        # Status breakdown
        status_counts = {}
        for status in ["new", "acknowledged", "in_progress", "resolved", "closed"]:
            query = db.query(Post).filter(
                Post.is_spam == False,
                Post.status == status
            )
            if company:
                query = query.filter(Post.company == company)
            status_counts[status] = query.count()
        
        # High urgency not actioned
        query = db.query(Post).filter(
            Post.is_spam == False,
            Post.urgency_score >= 7,
            Post.status == "new"
        )
        if company:
            query = query.filter(Post.company == company)
        high_urgency_new = query.count()
        
        # Posts raised on Slack
        query = db.query(Post).filter(Post.raised_on_slack == True)
        if company:
            query = query.filter(Post.company == company)
        on_slack = query.count()
        
        # Tickets created
        query = db.query(Post).filter(Post.ticket_created == True)
        if company:
            query = query.filter(Post.company == company)
        with_tickets = query.count()
        
        # By category
        category_counts = {}
        for cat in ["Praise", "Complaint", "Experience Breakage", "Feature Request"]:
            query = db.query(Post).filter(
                Post.is_spam == False,
                Post.category == cat
            )
            if company:
                query = query.filter(Post.company == company)
            category_counts[cat] = query.count()
        
        return {
            "total_posts": total,
            "status": status_counts,
            "high_urgency_pending": high_urgency_new,
            "raised_on_slack": on_slack,
            "tickets_created": with_tickets,
            "categories": category_counts,
        }

