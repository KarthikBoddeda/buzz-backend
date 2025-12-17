"""
LinkedIn Post Classification Batch Processor
Classifies LinkedIn posts similar to tweet classification.

Supports both JSON file input and database mode.
"""

import json
import time
import os
from datetime import datetime
from typing import List, Dict, Optional
from dotenv import load_dotenv

from app.analyzer.classifier import classify_tweet

load_dotenv()

# Database imports (optional)
DB_AVAILABLE = False
try:
    from app.db.database import init_db, get_db_session
    from app.db.models import RawPost, Post
    from app.db.repository import (
        get_unclassified_posts,
        save_classification,
        get_classification_stats,
        get_classified_posts,
    )
    DB_AVAILABLE = True
except ImportError as e:
    print(f"DB import error: {e}")
    pass


def load_linkedin_posts(file_path: str) -> List[Dict]:
    """Load LinkedIn posts from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def classify_linkedin_post(post: Dict) -> Dict:
    """
    Classify a single LinkedIn post.
    
    Args:
        post: LinkedIn post data
    
    Returns:
        dict: Classification result with post data
    """
    # Get the text content
    text = post.get("text", "") or post.get("full_text", "")
    
    if not text:
        return {
            "success": False,
            "error": "No text content in post",
            "post": post
        }
    
    # Get image URL if available
    image_url = None
    if post.get("media") and len(post["media"]) > 0:
        image_url = post["media"][0].get("url")
    
    # Classify using the existing classifier
    result = classify_tweet(text, image_url)
    
    return {
        "post": post,
        "classification": result.get("classification") if result.get("success") else None,
        "success": result.get("success", False),
        "error": result.get("error") if not result.get("success") else None,
        "usage": result.get("usage", {})
    }


def batch_classify_linkedin_posts(
    posts: List[Dict],
    delay_seconds: float = 0.2,
    max_posts: Optional[int] = None
) -> Dict:
    """
    Batch classify LinkedIn posts.
    
    Args:
        posts: List of LinkedIn posts
        delay_seconds: Delay between API calls to avoid rate limiting
        max_posts: Maximum number of posts to process (None for all)
    
    Returns:
        dict: Batch classification results with summary
    """
    results = []
    total = min(len(posts), max_posts) if max_posts else len(posts)
    
    print(f"\n{'='*70}")
    print(f"🔵 LINKEDIN POST CLASSIFIER - BATCH PROCESSING")
    print(f"{'='*70}")
    print(f"📊 Processing {total} posts...")
    print(f"{'='*70}\n")
    
    start_time = time.time()
    
    # Category counters
    categories = {
        "Praise": 0,
        "Complaint": 0,
        "Experience Breakage": 0,
        "Feature Request": 0,
        "Spam": 0,
        "Error": 0
    }
    
    # Product counters
    products = {}
    
    # Score totals for averaging
    sentiment_total = 0
    urgency_total = 0
    impact_total = 0
    successful_classifications = 0
    
    for i, post in enumerate(posts[:total]):
        print(f"[{i+1}/{total}] Processing: {post.get('author', 'Unknown')[:30]}...")
        
        result = classify_linkedin_post(post)
        results.append(result)
        
        if result["success"] and result["classification"]:
            classification = result["classification"]
            
            # Count categories
            if classification.get("is_spam"):
                categories["Spam"] += 1
            else:
                cat = classification.get("category", "Unknown")
                if cat in categories:
                    categories[cat] += 1
            
            # Count products
            product = classification.get("product")
            if product:
                products[product] = products.get(product, 0) + 1
            
            # Accumulate scores
            sentiment_total += classification.get("sentiment_score", 0)
            urgency_total += classification.get("urgency_score", 0)
            impact_total += classification.get("impact_score", 0)
            successful_classifications += 1
            
            # Print brief result
            cat_emoji = {
                "Praise": "🌟",
                "Complaint": "😤",
                "Experience Breakage": "🔥",
                "Feature Request": "💡"
            }
            cat = classification.get("category", "Unknown")
            spam = "🚫 SPAM" if classification.get("is_spam") else ""
            print(f"        → {cat_emoji.get(cat, '📌')} {cat} {spam}")
            print(f"          Sentiment: {classification.get('sentiment_score', 'N/A')}/10 | "
                  f"Urgency: {classification.get('urgency_score', 'N/A')}/10 | "
                  f"Impact: {classification.get('impact_score', 'N/A')}/10")
        else:
            categories["Error"] += 1
            print(f"        → ❌ Error: {result.get('error', 'Unknown error')}")
        
        # Delay to avoid rate limiting
        if i < total - 1:
            time.sleep(delay_seconds)
    
    elapsed_time = time.time() - start_time
    
    # Calculate averages
    avg_sentiment = sentiment_total / successful_classifications if successful_classifications > 0 else 0
    avg_urgency = urgency_total / successful_classifications if successful_classifications > 0 else 0
    avg_impact = impact_total / successful_classifications if successful_classifications > 0 else 0
    
    summary = {
        "total_processed": total,
        "successful": successful_classifications,
        "errors": categories["Error"],
        "processing_time_seconds": round(elapsed_time, 2),
        "categories": categories,
        "products": products,
        "average_scores": {
            "sentiment": round(avg_sentiment, 2),
            "urgency": round(avg_urgency, 2),
            "impact": round(avg_impact, 2)
        }
    }
    
    # Print summary
    print(f"\n{'='*70}")
    print("📊 CLASSIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Processed: {total} posts in {elapsed_time:.1f}s")
    print(f"   Successful: {successful_classifications} | Errors: {categories['Error']}")
    
    print(f"\n📂 Categories:")
    for cat, count in categories.items():
        if count > 0 and cat != "Error":
            print(f"   • {cat}: {count}")
    
    print(f"\n📦 Products mentioned:")
    for product, count in sorted(products.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   • {product}: {count}")
    
    print(f"\n📈 Average Scores:")
    print(f"   • Sentiment: {avg_sentiment:.1f}/10")
    print(f"   • Urgency: {avg_urgency:.1f}/10")
    print(f"   • Impact: {avg_impact:.1f}/10")
    print(f"{'='*70}\n")
    
    return {
        "results": results,
        "summary": summary
    }


def save_results(results: Dict, output_file: str):
    """Save classification results to JSON file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"💾 Results saved to: {output_file}")


def classify_from_database(
    platform: str = None,
    max_posts: int = 100,
    delay_seconds: float = 1.0
) -> Dict:
    """
    Classify unclassified posts from the database.
    Reads from raw_posts table and writes to classified_posts table.
    """
    if not DB_AVAILABLE:
        raise RuntimeError("Database not available. Install dependencies.")
    
    init_db()
    
    # Get unclassified posts
    raw_posts = get_unclassified_posts(platform=platform, limit=max_posts)
    total = len(raw_posts)
    
    if total == 0:
        print("📭 No unclassified posts found in database")
        return {"results": [], "summary": {"total_processed": 0}}
    
    print(f"\n{'='*70}")
    print(f"🔵 DATABASE CLASSIFICATION - BATCH PROCESSING")
    print(f"{'='*70}")
    print(f"📊 Processing {total} unclassified posts...")
    print(f"{'='*70}\n")
    
    start_time = time.time()
    
    # Category counters
    categories = {
        "Praise": 0,
        "Complaint": 0,
        "Experience Breakage": 0,
        "Feature Request": 0,
        "Spam": 0,
        "Error": 0
    }
    products = {}
    sentiment_total = 0
    urgency_total = 0
    impact_total = 0
    successful = 0
    
    results = []
    
    for i, raw_post in enumerate(raw_posts):
        print(f"[{i+1}/{total}] Processing: {raw_post.get('author_name') or 'Unknown'}...")
        
        # Classify
        result = classify_tweet(raw_post.get("full_text", ""))
        
        if result.get("success") and result.get("classification"):
            classification = result["classification"]
            usage = result.get("usage", {})
            
            # Save to database
            classified_id = save_classification(
                raw_post_id=raw_post["id"],
                classification=classification,
                usage=usage
            )
            
            # Count categories
            if classification.get("is_spam"):
                categories["Spam"] += 1
            else:
                cat = classification.get("category", "Unknown")
                if cat in categories:
                    categories[cat] += 1
            
            # Count products
            if classification.get("product"):
                products[classification["product"]] = products.get(classification["product"], 0) + 1
            
            # Accumulate scores
            sentiment_total += classification.get("sentiment_score", 0)
            urgency_total += classification.get("urgency_score", 0)
            impact_total += classification.get("impact_score", 0)
            successful += 1
            
            # Print result
            cat_emoji = {"Praise": "🌟", "Complaint": "😤", "Experience Breakage": "🔥", "Feature Request": "💡"}
            cat = classification.get("category", "Unknown")
            spam = "🚫 SPAM" if classification.get("is_spam") else ""
            print(f"        → {cat_emoji.get(cat, '📌')} {cat} {spam}")
            
            results.append({
                "raw_post_id": raw_post["id"],
                "classified_post_id": classified_id,
                "success": True
            })
        else:
            categories["Error"] += 1
            print(f"        → ❌ Error: {result.get('error', 'Unknown')}")
            results.append({
                "raw_post_id": raw_post["id"],
                "success": False,
                "error": result.get("error")
            })
        
        if i < total - 1:
            time.sleep(delay_seconds)
    
    elapsed_time = time.time() - start_time
    
    # Calculate averages
    avg_sentiment = sentiment_total / successful if successful > 0 else 0
    avg_urgency = urgency_total / successful if successful > 0 else 0
    avg_impact = impact_total / successful if successful > 0 else 0
    
    # Print summary
    print(f"\n{'='*70}")
    print("📊 CLASSIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Processed: {total} posts in {elapsed_time:.1f}s")
    print(f"   Successful: {successful} | Errors: {categories['Error']}")
    
    print(f"\n📂 Categories:")
    for cat, count in categories.items():
        if count > 0 and cat != "Error":
            print(f"   • {cat}: {count}")
    
    print(f"\n📦 Products mentioned:")
    for product, count in sorted(products.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   • {product}: {count}")
    
    print(f"\n📈 Average Scores:")
    print(f"   • Sentiment: {avg_sentiment:.1f}/10")
    print(f"   • Urgency: {avg_urgency:.1f}/10")
    print(f"   • Impact: {avg_impact:.1f}/10")
    print(f"{'='*70}\n")
    
    return {
        "results": results,
        "summary": {
            "total_processed": total,
            "successful": successful,
            "errors": categories["Error"],
            "processing_time_seconds": round(elapsed_time, 2),
            "categories": categories,
            "products": products,
            "average_scores": {
                "sentiment": round(avg_sentiment, 2),
                "urgency": round(avg_urgency, 2),
                "impact": round(avg_impact, 2)
            }
        }
    }


def show_database_stats():
    """Show classification statistics from the database."""
    if not DB_AVAILABLE:
        print("❌ Database not available")
        return
    
    init_db()
    stats = get_classification_stats()
    
    print(f"\n{'='*70}")
    print("📊 DATABASE CLASSIFICATION STATISTICS")
    print(f"{'='*70}")
    print(f"\n📈 Total classified: {stats['total']}")
    print(f"   Spam: {stats['spam_count']}")
    
    print(f"\n📂 Categories:")
    for cat, count in stats['categories'].items():
        print(f"   • {cat}: {count}")
    
    print(f"\n📦 Products:")
    for product, count in sorted(stats['products'].items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   • {product}: {count}")
    
    print(f"\n📈 Average Scores:")
    print(f"   • Sentiment: {stats['avg_scores']['sentiment']:.1f}/10")
    print(f"   • Urgency: {stats['avg_scores']['urgency']:.1f}/10")
    print(f"   • Impact: {stats['avg_scores']['impact']:.1f}/10")
    print(f"{'='*70}\n")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch classify posts (from file or database)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Classify from JSON file
    python3 -m app.analyzer.linkedin_batch --input razorpay_posts.json
    
    # Classify from database
    python3 -m app.analyzer.linkedin_batch --db
    
    # Classify LinkedIn posts from database
    python3 -m app.analyzer.linkedin_batch --db --platform linkedin --max 50
    
    # Show database statistics
    python3 -m app.analyzer.linkedin_batch --stats
        """
    )
    
    parser.add_argument("--input", "-i", help="Input JSON file with posts")
    parser.add_argument("--output", "-o", help="Output JSON file (default: <input>_classified.json)")
    parser.add_argument("--max", "-m", type=int, help="Maximum posts to process")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between API calls (seconds)")
    parser.add_argument("--db", action="store_true", help="Read from and write to database")
    parser.add_argument("--platform", choices=["twitter", "linkedin"], help="Filter by platform (with --db)")
    parser.add_argument("--stats", action="store_true", help="Show database classification statistics")
    
    args = parser.parse_args()
    
    # Show stats
    if args.stats:
        show_database_stats()
        return
    
    # Database mode
    if args.db:
        if not DB_AVAILABLE:
            print("❌ Database not available. Install dependencies.")
            return
        
        classify_from_database(
            platform=args.platform,
            max_posts=args.max or 100,
            delay_seconds=args.delay
        )
        return
    
    # File mode
    if not args.input:
        parser.error("--input is required when not using --db")
    
    # Load posts
    print(f"\n📂 Loading posts from: {args.input}")
    posts = load_linkedin_posts(args.input)
    print(f"   Found {len(posts)} posts")
    
    # Classify
    results = batch_classify_linkedin_posts(
        posts=posts,
        delay_seconds=args.delay,
        max_posts=args.max
    )
    
    # Save results
    output_file = args.output or args.input.replace(".json", "_classified.json")
    save_results(results, output_file)


if __name__ == "__main__":
    main()

