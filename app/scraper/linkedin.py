#!/usr/bin/env python3
"""
LinkedIn Scraper
Fetches posts from LinkedIn using the internal Voyager API.

Features:
- Fetch posts from a company page (by company name or ID)
- Fetch posts from your personalized feed
- Get comments on specific posts

Usage:
    python linkedin.py --company razorpay --count 20
    python linkedin.py --feed --count 50 --filter "Razorpay"
    python linkedin.py --post <post_urn> --comments

Note: Requires LinkedIn session cookies from browser DevTools.
"""

import argparse
import json
import requests
import urllib.parse
from datetime import datetime
from typing import Optional, List, Dict
import os
import urllib3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Disable SSL warnings for corporate proxy environments
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LinkedInAPI:
    """LinkedIn API client using internal Voyager API."""
    
    BASE_URL = "https://www.linkedin.com/voyager/api"
    
    # Known company IDs for quick lookup
    COMPANY_IDS = {
        "razorpay": "2494689",
        "stripe": "3518668",
        "paytm": "1453987",
        "phonepe": "9354183",
    }
    
    def __init__(
        self,
        li_at: str,
        jsessionid: str,
        user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ):
        """
        Initialize LinkedIn API client.
        
        Args:
            li_at: LinkedIn authentication cookie (li_at)
            jsessionid: LinkedIn session ID cookie (JSESSIONID)
            user_agent: Browser user agent string
        """
        self.li_at = li_at
        self.jsessionid = jsessionid.strip('"')
        self.user_agent = user_agent
        
        self.cookies = {
            "li_at": li_at,
            "JSESSIONID": f'"{self.jsessionid}"',
            "lang": "v=2&lang=en-us",
        }
    
    def _build_headers(self) -> dict:
        """Build headers for the API request."""
        return {
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": self.user_agent,
            "x-li-lang": "en_US",
            "x-restli-protocol-version": "2.0.0",
            "csrf-token": self.jsessionid,
        }
    
    def get_company_posts(
        self,
        company_name: str = None,
        company_id: str = None,
        count: int = 20,
        start: int = 0,
    ) -> List[Dict]:
        """
        Fetch posts from a company's LinkedIn page.
        
        Args:
            company_name: Company universal name (e.g., "razorpay")
            company_id: Company ID (if known)
            count: Number of posts to fetch
            start: Pagination offset
        
        Returns:
            List of parsed post data
        """
        # Get company ID if not provided
        if not company_id:
            company_id = self.COMPANY_IDS.get(company_name.lower())
        
        if not company_id:
            # Try to look up company ID
            company_id = self._lookup_company_id(company_name)
        
        if not company_id:
            print(f"Could not find company: {company_name}")
            return []
        
        # Fetch company feed
        urn = urllib.parse.quote(f"urn:li:organization:{company_id}")
        url = f"{self.BASE_URL}/feed/updatesV2?count={count}&moduleKey=ORGANIZATION_MEMBER_FEED_DESKTOP&q=feed&start={start}&urn={urn}"
        
        response = requests.get(
            url,
            headers=self._build_headers(),
            cookies=self.cookies,
            verify=False
        )
        
        if response.status_code != 200:
            print(f"Error fetching company posts: {response.status_code}")
            return []
        
        return self._parse_feed_response(response.json())
    
    def get_my_feed(
        self,
        count: int = 100,
        filter_keyword: str = None,
        since_date: str = None,
        until_date: str = None,
    ) -> List[Dict]:
        """
        Fetch posts from your personalized LinkedIn feed.
        
        Args:
            count: Number of posts to fetch (fetches more to filter)
            filter_keyword: Optional keyword to filter posts by
            since_date: Start date in YYYY-MM-DD format
            until_date: End date in YYYY-MM-DD format
        
        Returns:
            List of parsed post data
        """
        # Fetch a large batch from feed
        url = f"{self.BASE_URL}/feed/updatesV2?count=100&q=feed&moduleKey=FEED_DESKTOP"
        
        response = requests.get(
            url,
            headers=self._build_headers(),
            cookies=self.cookies,
            verify=False
        )
        
        if response.status_code != 200:
            # Try alternate endpoint
            url = f"{self.BASE_URL}/feed/updatesV2?count=100&q=feed"
            response = requests.get(
                url,
                headers=self._build_headers(),
                cookies=self.cookies,
                verify=False
            )
            
            if response.status_code != 200:
                print(f"Error fetching feed: {response.status_code}")
                return []
        
        posts = self._parse_feed_response(response.json())
        print(f"Fetched {len(posts)} posts from feed")
        
        # Filter by date range
        if since_date or until_date:
            posts = self._filter_by_date(posts, since_date, until_date)
            print(f"After date filter: {len(posts)} posts")
        
        # Filter by keyword in text field only
        if filter_keyword:
            keyword_lower = filter_keyword.lower()
            filtered = [p for p in posts if keyword_lower in p.get("text", "").lower()]
            print(f"Found {len(filtered)} posts containing '{filter_keyword}' in text")
            posts = filtered
        
        return posts[:count]
    
    def _filter_by_date(self, posts: List[Dict], since_date: str, until_date: str) -> List[Dict]:
        """Filter posts by date range based on relative time strings."""
        from datetime import datetime, timedelta
        import re
        
        now = datetime.now()
        
        # Parse date strings
        since_dt = datetime.strptime(since_date, "%Y-%m-%d") if since_date else None
        until_dt = datetime.strptime(until_date, "%Y-%m-%d") if until_date else None
        
        # Add a day to until_date to include posts from that day
        if until_dt:
            until_dt = until_dt + timedelta(days=1)
        
        filtered = []
        for post in posts:
            created_at = post.get("created_at", "")
            
            # Parse relative time like "5d", "1w", "2mo"
            post_date = self._parse_relative_time(created_at, now)
            
            if post_date:
                post["parsed_date"] = post_date.strftime("%Y-%m-%d")
                
                # Check if within range
                if since_dt and post_date < since_dt:
                    continue
                if until_dt and post_date >= until_dt:
                    continue
                
                filtered.append(post)
        
        return filtered
    
    @staticmethod
    def _parse_relative_time(time_str: str, now: datetime) -> Optional[datetime]:
        """Parse LinkedIn's relative time strings like '5d', '1w', '2mo' into datetime."""
        from datetime import timedelta
        import re
        
        if not time_str:
            return None
        
        time_str = time_str.lower().strip()
        
        # Match patterns like "5d", "1w", "2mo", "3h", "1y"
        patterns = [
            (r'(\d+)\s*m(?:in)?(?:ute)?s?\s*[•·]?', 'minutes'),
            (r'(\d+)\s*h(?:our)?s?\s*[•·]?', 'hours'),
            (r'(\d+)\s*d(?:ay)?s?\s*[•·]?', 'days'),
            (r'(\d+)\s*w(?:eek)?s?\s*[•·]?', 'weeks'),
            (r'(\d+)\s*mo(?:nth)?s?\s*[•·]?', 'months'),
            (r'(\d+)\s*y(?:ear)?s?\s*[•·]?', 'years'),
        ]
        
        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                value = int(match.group(1))
                
                if unit == 'minutes':
                    return now - timedelta(minutes=value)
                elif unit == 'hours':
                    return now - timedelta(hours=value)
                elif unit == 'days':
                    return now - timedelta(days=value)
                elif unit == 'weeks':
                    return now - timedelta(weeks=value)
                elif unit == 'months':
                    return now - timedelta(days=value * 30)
                elif unit == 'years':
                    return now - timedelta(days=value * 365)
        
        return None
    
    def get_post_comments(
        self,
        post_urn: str,
        count: int = 50,
    ) -> List[Dict]:
        """
        Fetch comments for a specific post.
        
        Args:
            post_urn: Post URN (e.g., "urn:li:activity:7123456789")
            count: Number of comments to fetch
        
        Returns:
            List of parsed comment data
        """
        all_comments = []
        start = 0
        per_page = 20
        
        encoded_urn = urllib.parse.quote(post_urn)
        
        while len(all_comments) < count:
            url = f"{self.BASE_URL}/feed/comments?count={per_page}&q=comments&sortOrder=RELEVANCE&start={start}&updateId={encoded_urn}"
            
            response = requests.get(
                url,
                headers=self._build_headers(),
                cookies=self.cookies,
                verify=False
            )
            
            if response.status_code != 200:
                print(f"Error fetching comments: {response.status_code}")
                break
            
            comments = self._parse_comments_response(response.json())
            
            if not comments:
                break
            
            all_comments.extend(comments)
            start += per_page
            
            if len(comments) < per_page:
                break
        
        return all_comments[:count]
    
    def get_conversation(self, post_urn: str) -> Dict:
        """
        Fetch a post and all its comments.
        
        Args:
            post_urn: Post URN
        
        Returns:
            Dictionary with post and comments
        """
        result = {
            "post": None,
            "comments": [],
            "post_urn": post_urn,
        }
        
        # Get post details
        try:
            encoded_urn = urllib.parse.quote(post_urn)
            url = f"{self.BASE_URL}/feed/updates/{encoded_urn}"
            
            response = requests.get(
                url,
                headers=self._build_headers(),
                cookies=self.cookies,
                verify=False
            )
            
            if response.status_code == 200:
                posts = self._parse_feed_response(response.json())
                if posts:
                    result["post"] = posts[0]
        except Exception as e:
            print(f"Error fetching post: {e}")
        
        # Get comments
        result["comments"] = self.get_post_comments(post_urn)
        
        return result
    
    def _lookup_company_id(self, company_name: str) -> Optional[str]:
        """Look up company ID by universal name."""
        url = f"{self.BASE_URL}/organization/companies?decorationId=com.linkedin.voyager.deco.organization.web.WebFullCompanyMain-12&q=universalName&universalName={company_name}"
        
        response = requests.get(
            url,
            headers=self._build_headers(),
            cookies=self.cookies,
            verify=False
        )
        
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            if elements:
                urn = elements[0].get("entityUrn", "")
                if urn:
                    return urn.split(":")[-1]
        
        return None
    
    def _parse_feed_response(self, response: dict) -> List[Dict]:
        """Parse feed response and extract posts."""
        posts = []
        included = response.get("included", [])
        
        for item in included:
            if "UpdateV2" not in item.get("$type", ""):
                continue
            
            post_data = self._extract_post_data(item, included)
            if post_data and post_data.get("text"):
                posts.append(post_data)
        
        return posts
    
    def _parse_comments_response(self, response: dict) -> List[Dict]:
        """Parse comments response."""
        comments = []
        included = response.get("included", [])
        
        for item in included:
            if "Comment" not in item.get("$type", ""):
                continue
            
            comment_data = self._extract_comment_data(item, included)
            if comment_data:
                comments.append(comment_data)
        
        return comments
    
    def _extract_post_data(self, item: dict, included: list) -> Optional[Dict]:
        """Extract post data from feed item."""
        try:
            # Get text content
            commentary = item.get("commentary", {})
            text = ""
            if commentary:
                text = commentary.get("text", {}).get("text", "")
            
            # Get author info
            actor = item.get("actor", {})
            author_name = actor.get("name", {}).get("text", "")
            author_desc = actor.get("description", {}).get("text", "")
            author_urn = actor.get("urn", "")
            
            # Get engagement stats
            social = item.get("socialDetail", {})
            counts = social.get("totalSocialActivityCounts", {}) if social else {}
            likes = counts.get("numLikes", 0)
            comments_count = counts.get("numComments", 0)
            shares = counts.get("numShares", 0)
            
            # Get URN and URL
            urn = item.get("updateMetadata", {}).get("urn", "") or item.get("urn", "")
            
            # Get timestamp
            created_at = actor.get("subDescription", {}).get("text", "")
            
            # Get media
            content = item.get("content", {})
            media = []
            if content:
                images = content.get("images", [])
                for img in images:
                    url = img.get("url", "")
                    if url:
                        media.append({"type": "image", "url": url})
                
                video = content.get("videoComponent", {})
                if video:
                    url = video.get("videoUrl", "")
                    if url:
                        media.append({"type": "video", "url": url})
            
            return {
                "urn": urn,
                "text": text,
                "author": {
                    "name": author_name,
                    "description": author_desc,
                    "urn": author_urn,
                },
                "engagement": {
                    "likes": likes,
                    "comments": comments_count,
                    "shares": shares,
                },
                "created_at": created_at,
                "media": media,
                "post_url": f"https://www.linkedin.com/feed/update/{urn}" if urn else None,
            }
        except Exception as e:
            print(f"Error parsing post: {e}")
            return None
    
    def _extract_comment_data(self, item: dict, included: list) -> Optional[Dict]:
        """Extract comment data."""
        try:
            # Get comment text
            comment_obj = item.get("comment", {})
            values = comment_obj.get("values", [])
            text = values[0].get("value", "") if values else ""
            
            # Get commenter info
            commenter = item.get("commenter", {})
            commenter_urn = ""
            commenter_name = ""
            
            # Try to find mini profile
            for key, val in commenter.items():
                if isinstance(val, dict) and "miniProfile" in val:
                    commenter_urn = val.get("miniProfile", "")
                    break
            
            # Look up commenter name in included
            for inc in included:
                if inc.get("entityUrn") == commenter_urn:
                    commenter_name = f"{inc.get('firstName', '')} {inc.get('lastName', '')}".strip()
                    break
            
            # Get engagement
            social = item.get("socialDetail", {})
            likes = social.get("totalSocialActivityCounts", {}).get("numLikes", 0) if social else 0
            
            # Get timestamp
            created_time = item.get("createdTime", 0)
            created_at = ""
            if created_time:
                created_at = datetime.fromtimestamp(created_time / 1000).isoformat()
            
            return {
                "text": text,
                "author": {
                    "name": commenter_name,
                    "urn": commenter_urn,
                },
                "likes": likes,
                "created_at": created_at,
            }
        except Exception as e:
            print(f"Error parsing comment: {e}")
            return None


def save_to_json(data, filename: str):
    """Save data to JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    count = len(data) if isinstance(data, list) else 1
    print(f"Saved {count} items to {filename}")


def print_posts(posts: List[Dict], limit: int = 10):
    """Print posts summary."""
    print(f"\n{'='*70}")
    print(f"Found {len(posts)} posts")
    print(f"{'='*70}\n")
    
    for i, post in enumerate(posts[:limit], 1):
        author = post.get("author", {})
        engagement = post.get("engagement", {})
        
        print(f"[{i}] {author.get('name', 'Unknown')}")
        if author.get("description"):
            print(f"    {author['description'][:60]}")
        
        text = post.get("text", "")
        print(f"    {text[:150]}{'...' if len(text) > 150 else ''}")
        
        print(f"    👍 {engagement.get('likes', 0)} | 💬 {engagement.get('comments', 0)} | 🔁 {engagement.get('shares', 0)}")
        print(f"    📅 {post.get('created_at', 'Unknown')}")
        
        if post.get("post_url"):
            print(f"    🔗 {post['post_url']}")
        print()
    
    if len(posts) > limit:
        print(f"... and {len(posts) - limit} more posts")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch posts from LinkedIn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Fetch Razorpay company posts
    python linkedin.py --company razorpay --count 20
    
    # Fetch your feed, filter for Razorpay mentions
    python linkedin.py --feed --count 50 --filter "Razorpay"
    
    # Get comments on a specific post
    python linkedin.py --post "urn:li:activity:123" --comments
        """
    )
    
    # Mode selection
    parser.add_argument("--company", "-c", help="Company name to fetch posts from")
    parser.add_argument("--feed", "-f", action="store_true", help="Fetch your personalized feed")
    parser.add_argument("--post", "-p", help="Post URN to fetch")
    
    # Options
    parser.add_argument("--count", "-n", type=int, default=20, help="Number of posts to fetch")
    parser.add_argument("--filter", help="Filter posts by keyword in text (for --feed)")
    parser.add_argument("--since", help="Start date YYYY-MM-DD (for --feed)")
    parser.add_argument("--until", help="End date YYYY-MM-DD (for --feed)")
    parser.add_argument("--comments", action="store_true", help="Include comments (for --post)")
    parser.add_argument("--output", "-o", default="linkedin_posts.json", help="Output file")
    
    # Authentication
    parser.add_argument("--li-at", default=os.environ.get("LINKEDIN_LI_AT"))
    parser.add_argument("--jsessionid", default=os.environ.get("LINKEDIN_JSESSIONID"))
    
    args = parser.parse_args()
    
    # Validate auth
    if not args.li_at or not args.jsessionid:
        print("❌ LinkedIn authentication required")
        print("\nSet in .env file or environment:")
        print("  LINKEDIN_LI_AT=your_cookie")
        print("  LINKEDIN_JSESSIONID=your_cookie")
        print("\nGet from: Browser DevTools → Application → Cookies → linkedin.com")
        return
    
    # Initialize API
    api = LinkedInAPI(li_at=args.li_at, jsessionid=args.jsessionid)
    
    try:
        if args.post:
            # Fetch specific post
            print(f"Fetching post: {args.post}")
            
            if args.comments:
                result = api.get_conversation(args.post)
                post = result.get("post")
                comments = result.get("comments", [])
                
                if post:
                    print(f"\n📝 Post by: {post['author']['name']}")
                    print(f"   {post['text'][:200]}...")
                    print(f"\n💬 {len(comments)} comments")
                    
                    for c in comments[:5]:
                        print(f"\n   → {c['author']['name']}: {c['text'][:100]}...")
                
                save_to_json(result, args.output)
            else:
                result = api.get_conversation(args.post)
                if result.get("post"):
                    print_posts([result["post"]])
                    save_to_json(result["post"], args.output)
        
        elif args.company:
            # Fetch company posts
            print(f"Fetching posts from: {args.company}")
            posts = api.get_company_posts(company_name=args.company, count=args.count)
            print_posts(posts)
            save_to_json(posts, args.output)
        
        elif args.feed:
            # Fetch personal feed
            print("Fetching your feed...")
            if args.filter:
                print(f"Filtering for: {args.filter}")
            if args.since or args.until:
                print(f"Date range: {args.since or 'any'} to {args.until or 'any'}")
            
            posts = api.get_my_feed(
                count=args.count, 
                filter_keyword=args.filter,
                since_date=args.since,
                until_date=args.until,
            )
            print_posts(posts)
            save_to_json(posts, args.output)
        
        else:
            print("Please specify --company, --feed, or --post")
            parser.print_help()
    
    except requests.exceptions.HTTPError as e:
        print(f"❌ HTTP Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
