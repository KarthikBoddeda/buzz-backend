#!/usr/bin/env python3
"""
Database Query Tool
Query raw_posts and classified_posts tables.
"""

import argparse
import json
from tabulate import tabulate
from app.db.database import init_db, get_db_session
from app.db.models import RawPost, ClassifiedPost
from app.db.repository import get_classified_posts, get_classification_stats


def query_raw_posts(platform=None, limit=10, search=None):
    """Query raw posts."""
    with get_db_session() as db:
        query = db.query(RawPost)
        
        if platform:
            query = query.filter(RawPost.platform == platform)
        if search:
            query = query.filter(RawPost.full_text.ilike(f"%{search}%"))
        
        posts = query.order_by(RawPost.scraped_at.desc()).limit(limit).all()
        
        rows = []
        for p in posts:
            rows.append([
                p.id,
                p.platform,
                (p.author_name or "")[:20],
                (p.full_text or "")[:50] + "...",
                p.likes_count,
                p.is_classified
            ])
        
        print(tabulate(rows, headers=["ID", "Platform", "Author", "Text", "Likes", "Classified"]))
        print(f"\nTotal: {len(posts)} posts")


def query_classified(category=None, min_urgency=None, product=None, limit=10):
    """Query classified posts."""
    posts = get_classified_posts(
        category=category,
        min_urgency=min_urgency,
        product=product,
        limit=limit
    )
    
    rows = []
    for p in posts:
        raw = p["raw_post"]
        cls = p["classification"]
        rows.append([
            raw["id"],
            (raw["author_name"] or "")[:15],
            cls["category"],
            cls["sentiment_score"],
            cls["urgency_score"],
            cls["impact_score"],
            (cls["summary"] or "")[:40] + "..."
        ])
    
    print(tabulate(rows, headers=["ID", "Author", "Category", "Sent", "Urg", "Imp", "Summary"]))
    print(f"\nTotal: {len(posts)} posts")


def show_stats():
    """Show classification statistics."""
    stats = get_classification_stats()
    print(json.dumps(stats, indent=2))


def export_json(output_file, category=None, limit=100):
    """Export classified posts to JSON."""
    posts = get_classified_posts(category=category, limit=limit)
    
    with open(output_file, 'w') as f:
        json.dump(posts, f, indent=2, default=str)
    
    print(f"Exported {len(posts)} posts to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Query the buzz database")
    subparsers = parser.add_subparsers(dest="command", help="Command")
    
    # Raw posts
    raw_parser = subparsers.add_parser("raw", help="Query raw posts")
    raw_parser.add_argument("--platform", "-p", choices=["twitter", "linkedin"])
    raw_parser.add_argument("--search", "-s", help="Search in text")
    raw_parser.add_argument("--limit", "-l", type=int, default=10)
    
    # Classified posts
    cls_parser = subparsers.add_parser("classified", help="Query classified posts")
    cls_parser.add_argument("--category", "-c", choices=["Praise", "Complaint", "Experience Breakage", "Feature Request"])
    cls_parser.add_argument("--min-urgency", "-u", type=int, help="Minimum urgency score")
    cls_parser.add_argument("--product", help="Filter by product")
    cls_parser.add_argument("--limit", "-l", type=int, default=10)
    
    # Stats
    subparsers.add_parser("stats", help="Show classification statistics")
    
    # Export
    export_parser = subparsers.add_parser("export", help="Export to JSON")
    export_parser.add_argument("--output", "-o", default="export.json")
    export_parser.add_argument("--category", "-c")
    export_parser.add_argument("--limit", "-l", type=int, default=100)
    
    args = parser.parse_args()
    
    init_db()
    
    if args.command == "raw":
        query_raw_posts(platform=args.platform, limit=args.limit, search=args.search)
    elif args.command == "classified":
        query_classified(category=args.category, min_urgency=args.min_urgency, 
                        product=args.product, limit=args.limit)
    elif args.command == "stats":
        show_stats()
    elif args.command == "export":
        export_json(args.output, category=args.category, limit=args.limit)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

