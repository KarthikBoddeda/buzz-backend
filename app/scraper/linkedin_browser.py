#!/usr/bin/env python3
"""
LinkedIn Browser Scraper
Uses Selenium to search LinkedIn content like the browser does.

This bypasses API restrictions by automating the actual browser.

Usage:
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --db
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --date past-month
"""

import argparse
import json
import time
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import quote

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

# Database imports (optional - only used if --db flag is set)
DB_AVAILABLE = False
try:
    from app.db.database import init_db
    from app.db.repository import save_raw_posts_batch, get_scraped_post_ids
    DB_AVAILABLE = True
except ImportError:
    pass

# State file for checkpointing
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".linkedin_state.json")


def load_checkpoint() -> Dict:
    """Load checkpoint state from file."""
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load checkpoint: {e}")
    return {"scraped_urns": [], "last_query": None, "last_run": None}


def save_checkpoint(state: Dict):
    """Save checkpoint state to file."""
    try:
        state["last_run"] = datetime.now().isoformat()
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save checkpoint: {e}")


def load_existing_posts(output_file: str) -> List[Dict]:
    """Load existing posts from output file."""
    try:
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load existing posts: {e}")
    return []


class LinkedInBrowserScraper:
    """Selenium-based LinkedIn content scraper."""
    
    def __init__(self, li_at: str, jsessionid: str, headless: bool = True):
        """
        Initialize the browser scraper.
        
        Args:
            li_at: LinkedIn li_at cookie
            jsessionid: LinkedIn JSESSIONID cookie
            headless: Run browser in headless mode
        """
        self.li_at = li_at
        self.jsessionid = jsessionid
        self.headless = headless
        self.driver = None
        self.checkpoint = load_checkpoint()
    
    def _setup_driver(self):
        """Set up Chrome driver with cookies."""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Disable automation detection
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # First navigate to LinkedIn to set cookies
        self.driver.get("https://www.linkedin.com")
        time.sleep(2)
        
        # Add cookies
        self.driver.add_cookie({
            "name": "li_at",
            "value": self.li_at,
            "domain": ".linkedin.com",
            "path": "/",
        })
        self.driver.add_cookie({
            "name": "JSESSIONID",
            "value": f'"{self.jsessionid}"',
            "domain": ".linkedin.com",
            "path": "/",
        })
        
        # Refresh to apply cookies
        self.driver.refresh()
        time.sleep(2)
    
    def search_content(
        self,
        query: str,
        max_posts: Optional[int] = None,
        date_filter: str = None,  # past-24h, past-week, past-month
        incremental: bool = True,
        company: str = None,
        save_to_db: bool = False,
        search_query_for_db: str = None,
    ) -> List[Dict]:
        """
        Search LinkedIn for posts containing the query.
        
        Args:
            query: Search keyword
            max_posts: Maximum number of posts to fetch (None = all available)
            date_filter: Time filter (past-24h, past-week, past-month)
            incremental: Skip already scraped posts (checkpoint)
            company: Company name to associate with scraped posts
            save_to_db: Whether to save posts directly to database
            search_query_for_db: Search query to store in database
        
        Returns:
            List of post data (new posts only if incremental=True)
        """
        if not self.driver:
            self._setup_driver()
        
        # Get already scraped URNs for incremental mode
        scraped_urns = set(self.checkpoint.get("scraped_urns", [])) if incremental else set()
        if scraped_urns:
            print(f"📌 Checkpoint: {len(scraped_urns)} posts already scraped")
        
        # Build search URL
        search_url = f"https://www.linkedin.com/search/results/content/?keywords={quote(query)}&origin=GLOBAL_SEARCH_HEADER"
        
        if date_filter:
            filter_map = {
                "past-24h": "datePosted%3D%22past-24h%22",
                "past-week": "datePosted%3D%22past-week%22",
                "past-month": "datePosted%3D%22past-month%22",
            }
            if date_filter in filter_map:
                search_url += f"&filters={filter_map[date_filter]}"
        
        print(f"Navigating to: {search_url}")
        self.driver.get(search_url)
        
        # Wait for page to load
        time.sleep(3)
        
        posts = []
        new_posts = []
        scroll_count = 0
        max_scrolls = 50  # Safety limit
        prev_post_count = 0
        no_new_posts_count = 0
        
        while scroll_count < max_scrolls:
            # Check if we've hit max_posts limit
            if max_posts and len(new_posts) >= max_posts:
                break
            # Find all post containers using multiple selectors
            try:
                selectors = [
                    "div.feed-shared-update-v2",
                    "div[data-urn*='activity']",
                    "li.reusable-search__result-container",
                    "div.update-components-actor",
                ]
                
                post_elements = []
                for selector in selectors:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        post_elements = elements
                        break
                
                print(f"Found {len(post_elements)} post elements on page")
                
                for elem in post_elements:
                    try:
                        post_data = self._extract_post_from_element(elem)
                        if post_data and post_data.get("text"):
                            urn = post_data.get("urn")
                            
                            # Avoid duplicates within this session
                            if any(p.get("urn") == urn for p in posts):
                                continue
                            
                            posts.append(post_data)
                            
                            # Check if already scraped (checkpoint)
                            if urn and urn in scraped_urns:
                                print(f"  [skip] Already scraped: {post_data.get('author', 'Unknown')[:30]}")
                            else:
                                new_posts.append(post_data)
                                # Add to checkpoint
                                if urn:
                                    scraped_urns.add(urn)
                                print(f"  [{len(new_posts)}] {post_data.get('author', 'Unknown')[:30]}: {post_data.get('text', '')[:50]}...")
                    except Exception as e:
                        continue
                
            except Exception as e:
                print(f"Error finding posts: {e}")
            
            # Check if we got new posts in this scroll
            if len(new_posts) == prev_post_count:
                no_new_posts_count += 1
                if no_new_posts_count >= 3:
                    print("No new posts found after 3 scrolls, stopping...")
                    break
            else:
                no_new_posts_count = 0
            
            prev_post_count = len(new_posts)
            
            # Scroll down to load more
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            scroll_count += 1
        
        # Update checkpoint with newly scraped URNs
        self.checkpoint["scraped_urns"] = list(scraped_urns)
        self.checkpoint["last_query"] = query
        save_checkpoint(self.checkpoint)
        
        print(f"\n✅ Found {len(new_posts)} new posts (skipped {len(posts) - len(new_posts)} already scraped)")
        
        # Limit to max_posts if specified
        result_posts = new_posts[:max_posts] if max_posts else new_posts
        
        # Save to database if requested
        if save_to_db and result_posts and DB_AVAILABLE:
            db_result = save_raw_posts_batch(
                result_posts,
                platform="linkedin",
                search_query=search_query_for_db or query,
                company=company
            )
            print(f"💾 Database: Saved {db_result['saved']}, Skipped {db_result['skipped']}")
        
        return result_posts
    
    def _extract_post_from_element(self, element) -> Optional[Dict]:
        """Extract post data from a Selenium element."""
        try:
            # Get the full element text first
            full_text = element.text
            
            if not full_text or len(full_text) < 20:
                return None
            
            # Split by newlines to parse different parts
            lines = [l.strip() for l in full_text.split('\n') if l.strip()]
            
            if len(lines) < 2:
                return None
            
            # First line is usually author name
            author = lines[0] if lines else ""
            
            # Find the main post text (usually the longest paragraph)
            text = ""
            author_title = ""
            time_posted = ""
            
            for i, line in enumerate(lines):
                # Skip short lines that are likely metadata
                if len(line) < 10:
                    continue
                
                # Check for time indicators
                if any(t in line.lower() for t in ['ago', '• ', 'edited', 'hour', 'day', 'week', 'month']):
                    if len(line) < 50:
                        time_posted = line
                        continue
                
                # Author title is usually second line
                if i == 1 and not text:
                    author_title = line
                    continue
                
                # Main text is usually the longest content
                if len(line) > len(text) and len(line) > 50:
                    text = line
            
            if not text:
                # Take the longest line as text
                text = max(lines, key=len) if lines else ""
            
            if len(text) < 30:
                return None
            
            # Get post URL/URN from any links
            post_url = ""
            urn = ""
            try:
                # Try multiple selectors for finding the post link
                link_selectors = [
                    "a[href*='/feed/update/']",
                    "a[href*='activity']",
                    "a.app-aware-link[href*='linkedin.com']",
                    "a[data-control-name='update_link']",
                ]
                
                for selector in link_selectors:
                    links = element.find_elements(By.CSS_SELECTOR, selector)
                    for link in links:
                        href = link.get_attribute("href")
                        if href and "urn:li:activity:" in href:
                            # Extract URN
                            match = re.search(r'urn:li:activity:(\d+)', href)
                            if match:
                                activity_id = match.group(1)
                                urn = f"urn:li:activity:{activity_id}"
                                post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
                                break
                    if post_url:
                        break
                
                # If still no URL, try to extract from data attributes
                if not post_url:
                    data_urn = element.get_attribute("data-urn")
                    if data_urn and "activity" in data_urn:
                        match = re.search(r'activity:(\d+)', data_urn)
                        if match:
                            activity_id = match.group(1)
                            urn = f"urn:li:activity:{activity_id}"
                            post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{activity_id}/"
            except Exception as e:
                pass
            
            # Parse engagement from text
            likes = 0
            comments = 0
            try:
                numbers = re.findall(r'(\d+)\s*(reactions?|likes?|comments?)', full_text.lower())
                for num, type_ in numbers:
                    if 'like' in type_ or 'reaction' in type_:
                        likes = int(num)
                    elif 'comment' in type_:
                        comments = int(num)
            except:
                pass
            
            # Extract author profile URL and followers count
            author_profile_url = None
            author_username = None
            followers_count = 0
            try:
                # Find author profile link
                author_link_selectors = [
                    "a.update-components-actor__container-link",
                    "a.app-aware-link[href*='/in/']",
                    "a[href*='/in/']",
                    "a.update-components-actor__meta-link",
                ]
                for selector in author_link_selectors:
                    author_links = element.find_elements(By.CSS_SELECTOR, selector)
                    for link in author_links:
                        href = link.get_attribute("href")
                        if href and "/in/" in href:
                            author_profile_url = href.split("?")[0]
                            # Extract username from URL
                            match = re.search(r'/in/([^/]+)', href)
                            if match:
                                author_username = match.group(1)
                            break
                    if author_profile_url:
                        break
                
                # Try to extract follower count from subtitle (e.g., "10K followers")
                follower_patterns = [
                    r'([\d,]+\.?\d*)\s*[kK]?\s*followers?',
                    r'([\d,]+\.?\d*)\s*[kK]?\s*connections?',
                ]
                for pattern in follower_patterns:
                    match = re.search(pattern, full_text)
                    if match:
                        count_str = match.group(1).replace(",", "")
                        count = float(count_str)
                        if 'k' in full_text[match.end()-10:match.end()].lower():
                            count *= 1000
                        followers_count = int(count)
                        break
            except:
                pass
            
            # Extract activity ID for consistent ID field
            activity_id = urn.split(":")[-1] if urn else None
            
            return {
                "id": activity_id,
                "platform": "linkedin",
                "created_at": time_posted,
                "full_text": text,
                "language": "en",  # LinkedIn doesn't expose language in scraping
                "favorite_count": likes,
                "retweet_count": 0,  # LinkedIn doesn't have retweets
                "reply_count": comments,
                "quote_count": 0,
                "bookmark_count": 0,
                "view_count": 0,  # Not available in scraping
                "user": {
                    "id": author_username,
                    "name": author,
                    "screen_name": author_username or (author.lower().replace(" ", "_") if author else None),
                    "description": author_title,
                    "followers_count": followers_count,
                    "following_count": 0,
                    "is_verified": False,
                    "profile_image_url": None,
                    "profile_url": author_profile_url,
                },
                "is_reply": False,
                "in_reply_to_post_id": None,
                "in_reply_to_user": None,
                "is_quote": False,
                "hashtags": self._extract_hashtags(text),
                "mentions": self._extract_mentions(text),
                "urls": [],
                "media": [],
                "post_url": post_url if post_url else None,
                "urn": urn,
                # Keep original fields for compatibility
                "author": author,
                "author_title": author_title,
                "author_profile_url": author_profile_url,
                "author_username": author_username,
                "followers_count": followers_count,
                "text": text,
                "time_posted": time_posted,
                "likes": likes,
                "comments": comments,
            }
            
        except Exception as e:
            return None
    
    def _extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text."""
        if not text:
            return []
        hashtags = re.findall(r'#(\w+)', text)
        return hashtags
    
    def _extract_mentions(self, text: str) -> List[Dict]:
        """Extract @mentions from text."""
        if not text:
            return []
        mentions = re.findall(r'@(\w+)', text)
        return [{"screen_name": m, "name": m, "id": None} for m in mentions]
    
    def get_author_details(self, profile_url: str) -> Dict:
        """
        Fetch detailed author info from their profile page.
        
        Args:
            profile_url: LinkedIn profile URL
        
        Returns:
            dict with followers_count, connections_count, headline, etc.
        """
        if not self.driver:
            self._setup_driver()
        
        try:
            self.driver.get(profile_url)
            time.sleep(2)
            
            details = {
                "followers_count": 0,
                "connections_count": 0,
                "headline": None,
            }
            
            # Get page text
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Extract followers count
            follower_match = re.search(r'([\d,]+)\s*followers?', page_text, re.IGNORECASE)
            if follower_match:
                details["followers_count"] = int(follower_match.group(1).replace(",", ""))
            
            # Extract connections count
            conn_match = re.search(r'([\d,]+)\+?\s*connections?', page_text, re.IGNORECASE)
            if conn_match:
                details["connections_count"] = int(conn_match.group(1).replace(",", ""))
            
            # Try to get headline
            try:
                headline_elem = self.driver.find_element(By.CSS_SELECTOR, ".text-body-medium.break-words")
                details["headline"] = headline_elem.text
            except:
                pass
            
            return details
            
        except Exception as e:
            print(f"Error fetching author details: {e}")
            return {"followers_count": 0, "connections_count": 0, "headline": None}
    
    def enrich_posts_with_author_details(self, posts: List[Dict], max_profiles: int = None) -> List[Dict]:
        """
        Enrich posts with detailed author information.
        
        Args:
            posts: List of posts to enrich
            max_profiles: Max number of unique profiles to fetch (None = all)
        
        Returns:
            Enriched posts list
        """
        # Get unique author profiles
        profiles_to_fetch = {}
        for post in posts:
            profile_url = post.get("author_profile_url") or post.get("user", {}).get("profile_url")
            if profile_url and profile_url not in profiles_to_fetch:
                profiles_to_fetch[profile_url] = None
        
        print(f"\n📊 Fetching details for {len(profiles_to_fetch)} unique authors...")
        
        # Fetch profile details
        fetched = 0
        for profile_url in list(profiles_to_fetch.keys()):
            if max_profiles and fetched >= max_profiles:
                break
            
            print(f"  [{fetched + 1}] Fetching: {profile_url[:50]}...")
            details = self.get_author_details(profile_url)
            profiles_to_fetch[profile_url] = details
            fetched += 1
            time.sleep(1)  # Rate limiting
        
        # Enrich posts with fetched details
        for post in posts:
            profile_url = post.get("author_profile_url") or post.get("user", {}).get("profile_url")
            if profile_url and profiles_to_fetch.get(profile_url):
                details = profiles_to_fetch[profile_url]
                post["followers_count"] = details.get("followers_count", 0)
                post["connections_count"] = details.get("connections_count", 0)
                if post.get("user"):
                    post["user"]["followers_count"] = details.get("followers_count", 0)
                    post["user"]["connections_count"] = details.get("connections_count", 0)
        
        return posts
    
    def close(self):
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            self.driver = None


def save_to_json(data: list, filename: str, append: bool = False):
    """Save data to JSON file, optionally appending to existing."""
    existing = []
    if append and os.path.exists(filename):
        existing = load_existing_posts(filename)
        print(f"📂 Loaded {len(existing)} existing posts from {filename}")
    
    # Merge: add new posts, avoid duplicates by URN
    existing_urns = {p.get("urn") for p in existing if p.get("urn")}
    new_data = [p for p in data if p.get("urn") not in existing_urns]
    
    all_posts = existing + new_data
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Saved {len(all_posts)} total posts ({len(new_data)} new) to {filename}")


def print_posts(posts: List[Dict], limit: int = 20):
    """Print posts summary."""
    print(f"\n{'='*70}")
    print(f"Found {len(posts)} posts")
    print(f"{'='*70}\n")
    
    for i, post in enumerate(posts[:limit], 1):
        author = post.get('author', 'Unknown')
        followers = post.get('followers_count', 0) or post.get('user', {}).get('followers_count', 0)
        
        print(f"[{i}] {author}")
        if post.get('author_title'):
            print(f"    {post['author_title'][:60]}")
        if followers:
            print(f"    👥 {followers:,} followers")
        
        text = post.get("text", "")
        print(f"    {text[:150]}{'...' if len(text) > 150 else ''}")
        print(f"    👍 {post.get('likes', 0)} | 💬 {post.get('comments', 0)} | 📅 {post.get('time_posted', 'Unknown')}")
        
        if post.get("post_url"):
            print(f"    🔗 {post['post_url'][:80]}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Search LinkedIn content using browser automation (with checkpointing)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Search for Razorpay posts (incremental, fetches all new posts)
    python3 -m app.scraper.linkedin_browser --query "Razorpay"
    
    # Search with date filter
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --date past-month
    
    # Limit to 20 new posts
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --max 20
    
    # Full refresh (ignore checkpoint, re-scrape all)
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --full
    
    # Include author follower counts (fetches profile pages)
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --enrich-authors
    
    # Run with visible browser (for debugging)
    python3 -m app.scraper.linkedin_browser --query "Razorpay" --no-headless
    
    # Clear checkpoint
    python3 -m app.scraper.linkedin_browser --clear-checkpoint
        """
    )
    
    parser.add_argument("--query", "-q", help="Search keyword")
    parser.add_argument("--max", "-m", type=int, help="Max new posts to fetch (default: all)")
    parser.add_argument("--date", "-d", choices=["past-24h", "past-week", "past-month"],
                        help="Date filter")
    parser.add_argument("--output", "-o", default="linkedin_posts.json", help="Output file")
    parser.add_argument("--no-headless", action="store_true", help="Run with visible browser")
    parser.add_argument("--full", action="store_true", help="Full refresh, ignore checkpoint")
    parser.add_argument("--clear-checkpoint", action="store_true", help="Clear checkpoint and exit")
    parser.add_argument("--enrich-authors", action="store_true", 
                        help="Fetch detailed author info (followers, connections)")
    parser.add_argument("--max-profiles", type=int, default=10,
                        help="Max author profiles to fetch when using --enrich-authors")
    parser.add_argument("--db", action="store_true",
                        help="Save posts to database instead of JSON file")
    parser.add_argument("--company", "-c", default="razorpay",
                        help="Company this data is for (razorpay, paytm, phonepe, etc.)")
    
    # Auth
    parser.add_argument("--li-at", default=os.environ.get("LINKEDIN_LI_AT"))
    parser.add_argument("--jsessionid", default=os.environ.get("LINKEDIN_JSESSIONID"))
    
    args = parser.parse_args()
    
    # Handle clear checkpoint
    if args.clear_checkpoint:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("✅ Checkpoint cleared")
        else:
            print("No checkpoint to clear")
        return
    
    if not args.query:
        parser.error("--query is required")
    
    if not args.li_at or not args.jsessionid:
        print("❌ LinkedIn authentication required")
        print("Set LINKEDIN_LI_AT and LINKEDIN_JSESSIONID in .env")
        return
    
    # Check database availability if --db flag is used
    if args.db and not DB_AVAILABLE:
        print("❌ Database not available. Install dependencies or run without --db")
        return
    
    # Initialize database if using --db
    if args.db:
        init_db()
        print("💾 Saving to database")
    
    print(f"🔍 Searching LinkedIn for: {args.query}")
    if args.date:
        print(f"📅 Date filter: {args.date}")
    if args.full:
        print("🔄 Full refresh mode (ignoring checkpoint)")
    print()
    
    scraper = LinkedInBrowserScraper(
        li_at=args.li_at,
        jsessionid=args.jsessionid,
        headless=not args.no_headless,
    )
    
    try:
        posts = scraper.search_content(
            query=args.query,
            max_posts=args.max,
            date_filter=args.date,
            incremental=not args.full,
        )
        
        if posts:
            # Enrich with author details if requested
            if args.enrich_authors:
                posts = scraper.enrich_posts_with_author_details(
                    posts, 
                    max_profiles=args.max_profiles
                )
            
            print_posts(posts)
            
            # Save to database or JSON
            if args.db:
                result = save_raw_posts_batch(
                    posts, 
                    platform="linkedin", 
                    search_query=args.query,
                    company=args.company
                )
                print(f"\n💾 Database [{args.company}]: {result['saved']} saved, {result['skipped']} already existed")
            else:
                save_to_json(posts, args.output, append=not args.full)
        else:
            print("\n📭 No new posts found")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        raise
    finally:
        scraper.close()


if __name__ == "__main__":
    main()

