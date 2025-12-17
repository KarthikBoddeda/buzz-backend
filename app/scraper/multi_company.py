#!/usr/bin/env python3
"""
Multi-Company Scraper
Scrapes social media data for Razorpay and its competitors.

Usage:
    # Scrape all companies on Twitter
    python -m app.scraper.multi_company --platform twitter --all
    
    # Scrape specific competitors on Twitter
    python -m app.scraper.multi_company --platform twitter --companies cashfree payu
    
    # Scrape Razorpay + top competitors on LinkedIn
    python -m app.scraper.multi_company --platform linkedin --companies razorpay cashfree payu
    
    # List all configured companies
    python -m app.scraper.multi_company --list
"""

import argparse
import json
import time
from datetime import datetime
from typing import List, Dict, Optional

from app.config import (
    COMPANIES, 
    get_company, 
    get_all_companies, 
    get_competitors,
    get_primary_company,
    LINKEDIN_LI_AT,
    LINKEDIN_JSESSIONID,
    TWITTER_AUTH_TOKEN,
    TWITTER_CSRF_TOKEN,
)
from app.db.database import init_db
from app.db.repository import save_raw_posts_batch, get_classification_stats


def list_companies():
    """Display all configured companies."""
    print("\n" + "="*70)
    print("📊 CONFIGURED COMPANIES")
    print("="*70 + "\n")
    
    print(f"{'Name':<15} {'Display':<20} {'Type':<10} {'Keywords'}")
    print("-"*70)
    
    for name, config in COMPANIES.items():
        primary = "⭐ PRIMARY" if config.get("is_primary") else "competitor"
        keywords = ", ".join(config.get("keywords", [])[:2])
        if len(config.get("keywords", [])) > 2:
            keywords += "..."
        print(f"{name:<15} {config['display_name']:<20} {primary:<10} {keywords}")
    
    print("\n" + "="*70)
    print(f"Total: {len(COMPANIES)} companies ({len(get_competitors())} competitors)")
    print("="*70 + "\n")


def scrape_twitter(
    companies: List[str],
    count_per_company: int = 50,
    save_to_db: bool = True
) -> Dict:
    """Scrape Twitter for multiple companies."""
    from app.scraper.twitter import TwitterSearchAPI
    
    if not TWITTER_AUTH_TOKEN or not TWITTER_CSRF_TOKEN:
        print("❌ Twitter credentials not configured in .env")
        print("   Set TWITTER_AUTH_TOKEN and TWITTER_CSRF_TOKEN")
        return {"error": "Missing Twitter credentials"}
    
    results = {
        "platform": "twitter",
        "scraped_at": datetime.now().isoformat(),
        "companies": {}
    }
    
    api = TwitterSearchAPI(auth_token=TWITTER_AUTH_TOKEN, csrf_token=TWITTER_CSRF_TOKEN)
    
    for company_name in companies:
        company = get_company(company_name)
        if not company:
            print(f"⚠️  Unknown company: {company_name}, skipping...")
            continue
        
        print(f"\n{'='*60}")
        print(f"🐦 Scraping Twitter for: {company['display_name']}")
        print(f"{'='*60}")
        
        all_tweets = []
        
        # Search using each keyword
        for keyword in company.get("keywords", [company_name])[:2]:  # Limit to 2 keywords
            print(f"\n  🔍 Searching: '{keyword}'")
            try:
                tweets = api.search_all(
                    query=keyword,
                    max_tweets=count_per_company // len(company.get("keywords", [keyword])[:2])
                )
                print(f"     Found {len(tweets)} tweets")
                all_tweets.extend(tweets)
            except Exception as e:
                print(f"     ❌ Error: {e}")
            
            time.sleep(2)  # Rate limiting
        
        # Deduplicate by tweet ID
        seen_ids = set()
        unique_tweets = []
        for tweet in all_tweets:
            tweet_id = tweet.get("id")
            if tweet_id and tweet_id not in seen_ids:
                seen_ids.add(tweet_id)
                unique_tweets.append(tweet)
        
        print(f"\n  📊 Total unique tweets: {len(unique_tweets)}")
        
        # Save to database
        if save_to_db and unique_tweets:
            result = save_raw_posts_batch(
                unique_tweets,
                platform="twitter",
                search_query=company.get("keywords", [company_name])[0],
                company=company_name
            )
            print(f"  💾 Saved: {result['saved']}, Skipped: {result['skipped']}")
        
        results["companies"][company_name] = {
            "tweets_found": len(unique_tweets),
            "keywords_searched": company.get("keywords", [])[:2]
        }
    
    return results


def scrape_linkedin(
    companies: List[str],
    count_per_company: int = 50,
    save_to_db: bool = True,
    headless: bool = True
) -> Dict:
    """Scrape LinkedIn for multiple companies using browser automation."""
    from app.scraper.linkedin_browser import LinkedInBrowserScraper
    
    if not LINKEDIN_LI_AT or not LINKEDIN_JSESSIONID:
        print("❌ LinkedIn credentials not configured in .env")
        print("   Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID")
        return {"error": "Missing LinkedIn credentials"}
    
    results = {
        "platform": "linkedin",
        "scraped_at": datetime.now().isoformat(),
        "companies": {}
    }
    
    scraper = LinkedInBrowserScraper(
        li_at=LINKEDIN_LI_AT,
        jsessionid=LINKEDIN_JSESSIONID,
        headless=headless
    )
    
    try:
        for company_name in companies:
            company = get_company(company_name)
            if not company:
                print(f"⚠️  Unknown company: {company_name}, skipping...")
                continue
            
            print(f"\n{'='*60}")
            print(f"💼 Scraping LinkedIn for: {company['display_name']}")
            print(f"{'='*60}")
            
            # Use primary keyword for search
            keyword = company.get("keywords", [company_name])[0]
            print(f"\n  🔍 Searching: '{keyword}'")
            
            try:
                posts = scraper.search_content(
                    query=keyword,
                    company=company_name,
                    max_posts=count_per_company,
                    date_filter="past-month",
                    incremental=True,
                    save_to_db=save_to_db,
                    search_query_for_db=keyword
                )
                
                print(f"\n  📊 Found {len(posts)} posts")
                
                results["companies"][company_name] = {
                    "posts_found": len(posts),
                    "keyword_searched": keyword
                }
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                results["companies"][company_name] = {"error": str(e)}
            
            time.sleep(3)  # Rate limiting between companies
            
    finally:
        scraper.close()
    
    return results


def show_stats(companies: List[str] = None):
    """Show database statistics for companies."""
    from app.db.database import get_db_session
    from app.db.models import RawPost, Post
    from sqlalchemy import func
    
    print("\n" + "="*70)
    print("📊 DATABASE STATISTICS")
    print("="*70 + "\n")
    
    with get_db_session() as db:
        # Raw posts by company and platform
        raw_stats = db.query(
            RawPost.company,
            RawPost.platform,
            func.count(RawPost.id).label("count")
        ).group_by(RawPost.company, RawPost.platform).all()
        
        print("📁 Raw Posts:")
        print(f"  {'Company':<15} {'Platform':<12} {'Count'}")
        print("  " + "-"*40)
        for stat in raw_stats:
            if companies is None or stat.company in companies:
                print(f"  {stat.company or 'unknown':<15} {stat.platform:<12} {stat.count}")
        
        # Classified posts by company, platform, category
        print("\n📈 Classified Posts (non-spam):")
        class_stats = db.query(
            Post.company,
            Post.platform,
            Post.category,
            func.count(Post.id).label("count")
        ).filter(Post.is_spam == False).group_by(
            Post.company, Post.platform, Post.category
        ).order_by(Post.company, Post.platform, func.count(Post.id).desc()).all()
        
        print(f"  {'Company':<15} {'Platform':<12} {'Category':<20} {'Count'}")
        print("  " + "-"*55)
        for stat in class_stats:
            if companies is None or stat.company in companies:
                print(f"  {stat.company or 'unknown':<15} {stat.platform:<12} {stat.category or 'N/A':<20} {stat.count}")
    
    print("\n" + "="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Company Social Media Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # List all configured companies
    python -m app.scraper.multi_company --list
    
    # Scrape Twitter for Razorpay only
    python -m app.scraper.multi_company --platform twitter --companies razorpay
    
    # Scrape Twitter for all companies
    python -m app.scraper.multi_company --platform twitter --all --count 30
    
    # Scrape LinkedIn for Razorpay and competitors
    python -m app.scraper.multi_company --platform linkedin --companies razorpay cashfree payu
    
    # Show database stats
    python -m app.scraper.multi_company --stats
        """
    )
    
    parser.add_argument("--platform", "-p", choices=["twitter", "linkedin"], 
                        help="Platform to scrape")
    parser.add_argument("--companies", "-c", nargs="+", 
                        help="Companies to scrape (e.g., razorpay cashfree payu)")
    parser.add_argument("--all", "-a", action="store_true",
                        help="Scrape all configured companies")
    parser.add_argument("--competitors", action="store_true",
                        help="Scrape only competitors (not Razorpay)")
    parser.add_argument("--count", "-n", type=int, default=50,
                        help="Posts to fetch per company (default: 50)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List all configured companies")
    parser.add_argument("--stats", "-s", action="store_true",
                        help="Show database statistics")
    parser.add_argument("--no-db", action="store_true",
                        help="Don't save to database (print only)")
    parser.add_argument("--no-headless", action="store_true",
                        help="Show browser window (LinkedIn only)")
    
    args = parser.parse_args()
    
    # Initialize database
    init_db()
    
    # Handle special commands
    if args.list:
        list_companies()
        return
    
    if args.stats:
        show_stats(args.companies)
        return
    
    # Determine which companies to scrape
    if args.all:
        companies = get_all_companies()
    elif args.competitors:
        companies = get_competitors()
    elif args.companies:
        companies = args.companies
    else:
        parser.error("Specify --companies, --all, or --competitors")
        return
    
    if not args.platform:
        parser.error("Specify --platform (twitter or linkedin)")
        return
    
    print(f"\n🚀 Starting multi-company scrape")
    print(f"   Platform: {args.platform}")
    print(f"   Companies: {', '.join(companies)}")
    print(f"   Posts per company: {args.count}")
    print(f"   Save to DB: {not args.no_db}")
    
    # Run the scraper
    if args.platform == "twitter":
        results = scrape_twitter(
            companies=companies,
            count_per_company=args.count,
            save_to_db=not args.no_db
        )
    elif args.platform == "linkedin":
        results = scrape_linkedin(
            companies=companies,
            count_per_company=args.count,
            save_to_db=not args.no_db,
            headless=not args.no_headless
        )
    
    # Print summary
    print("\n" + "="*60)
    print("📊 SCRAPE SUMMARY")
    print("="*60)
    for company, stats in results.get("companies", {}).items():
        display = get_company(company)["display_name"] if get_company(company) else company
        if "error" in stats:
            print(f"  ❌ {display}: {stats['error']}")
        else:
            count = stats.get("tweets_found") or stats.get("posts_found", 0)
            print(f"  ✅ {display}: {count} posts")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()

