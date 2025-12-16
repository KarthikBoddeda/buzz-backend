#!/usr/bin/env python3
"""
Twitter/X Search API Scraper
Fetches tweets using Twitter's GraphQL SearchTimeline API.

Usage:
    python fetch_tweets.py --query "Razorpay" --since 2025-03-03 --until 2025-03-05
    python fetch_tweets.py --query "Razorpay" --since 2025-03-03 --until 2025-03-05 --count 50
    python fetch_tweets.py --query "Razorpay" --since 2025-03-03 --until 2025-03-05 --output tweets.json
"""

import argparse
import json
import requests
import urllib.parse
from datetime import datetime
from typing import Optional
import csv
import os


class TransactionIdManager:
    """Manages the transaction ID, incrementing it for each request and persisting across runs."""
    
    # Base62 characters for incrementing
    CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    
    # File to persist the transaction ID
    STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".twitter_tx_state.json")
    
    def __init__(self, initial_id: str):
        # Try to load persisted state first
        persisted_id = self._load_state()
        if persisted_id:
            self.current_id = persisted_id
        else:
            self.current_id = initial_id
    
    def _load_state(self) -> Optional[str]:
        """Load persisted transaction ID from file."""
        try:
            if os.path.exists(self.STATE_FILE):
                with open(self.STATE_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("transaction_id")
        except Exception:
            pass
        return None
    
    def _save_state(self):
        """Persist current transaction ID to file."""
        try:
            with open(self.STATE_FILE, 'w') as f:
                json.dump({"transaction_id": self.current_id}, f)
        except Exception as e:
            print(f"Warning: Could not save transaction ID state: {e}")
    
    def get_next(self) -> str:
        """Get the current transaction ID and increment for next use."""
        current = self.current_id
        self.current_id = self._increment(self.current_id)
        self._save_state()  # Persist for next run
        return current
    
    def _increment(self, tx_id: str) -> str:
        """
        Increment the transaction ID.
        The last character is incremented in base62 style.
        If it overflows, it carries to the previous character.
        """
        if not tx_id:
            return tx_id
        
        chars = list(tx_id)
        i = len(chars) - 1
        
        while i >= 0:
            char = chars[i]
            if char in self.CHARS:
                idx = self.CHARS.index(char)
                if idx < len(self.CHARS) - 1:
                    # Simple increment
                    chars[i] = self.CHARS[idx + 1]
                    break
                else:
                    # Overflow, carry to previous
                    chars[i] = self.CHARS[0]
                    i -= 1
            else:
                # Non-alphanumeric character, skip
                i -= 1
        
        return ''.join(chars)


class TwitterSearchAPI:
    """Twitter Search API client using GraphQL endpoint."""
    
    BASE_URL = "https://x.com/i/api/graphql/bshMIjqDk8LTXTq4w91WKw/SearchTimeline"
    
    # Features required by the API
    FEATURES = {
        "rweb_video_screen_enabled": False,
        "profile_label_improvements_pcf_label_in_post_enabled": True,
        "responsive_web_profile_redirect_enabled": False,
        "rweb_tipjar_consumption_enabled": True,
        "verified_phone_label_enabled": True,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_timeline_navigation_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "premium_content_api_read_enabled": False,
        "communities_web_enable_tweet_community_results_fetch": True,
        "c9s_tweet_anatomy_moderator_badge_enabled": True,
        "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
        "responsive_web_grok_analyze_post_followups_enabled": True,
        "responsive_web_jetfuel_frame": True,
        "responsive_web_grok_share_attachment_enabled": True,
        "articles_preview_enabled": True,
        "responsive_web_edit_tweet_api_enabled": True,
        "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
        "view_counts_everywhere_api_enabled": True,
        "longform_notetweets_consumption_enabled": True,
        "responsive_web_twitter_article_tweet_consumption_enabled": True,
        "tweet_awards_web_tipping_enabled": False,
        "responsive_web_grok_show_grok_translated_post": False,
        "responsive_web_grok_analysis_button_from_backend": True,
        "creator_subscriptions_quote_tweet_preview_enabled": False,
        "freedom_of_speech_not_reach_fetch_enabled": True,
        "standardized_nudges_misinfo": True,
        "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
        "longform_notetweets_rich_text_read_enabled": True,
        "longform_notetweets_inline_media_enabled": True,
        "responsive_web_grok_image_annotation_enabled": True,
        "responsive_web_grok_imagine_annotation_enabled": True,
        "responsive_web_grok_community_note_auto_translation_is_enabled": False,
        "responsive_web_enhance_cards_enabled": False
    }
    
    def __init__(
        self,
        auth_token: str,
        csrf_token: str,
        bearer_token: str = "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        transaction_id: str = "D1r/HKLyEPoi/MKMVHaht4PQUPOZ251HMAuf64wl+WmEAw1UnvukjO2YQJs8GJwThEUb/QtHKpj1DZjTKuZiWedmi2kMDD"
    ):
        self.auth_token = auth_token
        self.csrf_token = csrf_token
        self.bearer_token = bearer_token
        self.tx_manager = TransactionIdManager(transaction_id)
        
        # Build cookie string
        self.cookies = {
            "auth_token": auth_token,
            "ct0": csrf_token,
            "lang": "en"
        }
    
    def _build_headers(self) -> dict:
        """Build headers for the API request."""
        return {
            "Accept": "*/*",
            "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "authorization": f"Bearer {self.bearer_token}",
            "content-type": "application/json",
            "x-client-transaction-id": self.tx_manager.get_next(),
            "x-csrf-token": self.csrf_token,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-client-language": "en",
        }
    
    def _build_query(self, query: str, since: Optional[str] = None, until: Optional[str] = None) -> str:
        """Build the raw query string with date filters."""
        raw_query = query
        if until:
            raw_query += f" until:{until}"
        if since:
            raw_query += f" since:{since}"
        return raw_query
    
    def search(
        self,
        query: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        count: int = 20,
        product: str = "Latest",
        cursor: Optional[str] = None
    ) -> dict:
        """
        Search for tweets matching the query.
        
        Args:
            query: Search query text (e.g., "Razorpay")
            since: Start date in YYYY-MM-DD format
            until: End date in YYYY-MM-DD format
            count: Number of tweets to fetch (default 20)
            product: "Latest" or "Top" (default "Latest")
            cursor: Pagination cursor for fetching more results
        
        Returns:
            Raw API response as dictionary
        """
        raw_query = self._build_query(query, since, until)
        
        variables = {
            "rawQuery": raw_query,
            "count": count,
            "querySource": "typed_query",
            "product": product,
            "withGrokTranslatedBio": False
        }
        
        if cursor:
            variables["cursor"] = cursor
        
        params = {
            "variables": json.dumps(variables),
            "features": json.dumps(self.FEATURES)
        }
        
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        
        response = requests.get(
            url,
            headers=self._build_headers(),
            cookies=self.cookies
        )
        
        response.raise_for_status()
        return response.json()
    
    def search_all(
        self,
        query: str,
        since: Optional[str] = None,
        until: Optional[str] = None,
        max_tweets: int = 100,
        product: str = "Latest"
    ) -> list:
        """
        Search and fetch all tweets up to max_tweets with pagination.
        
        Args:
            query: Search query text
            since: Start date in YYYY-MM-DD format
            until: End date in YYYY-MM-DD format
            max_tweets: Maximum number of tweets to fetch
            product: "Latest" or "Top"
        
        Returns:
            List of parsed tweet data
        """
        all_tweets = []
        cursor = None
        
        while len(all_tweets) < max_tweets:
            count = min(20, max_tweets - len(all_tweets))
            
            response = self.search(
                query=query,
                since=since,
                until=until,
                count=count,
                product=product,
                cursor=cursor
            )
            
            tweets, next_cursor = self.parse_response(response)
            
            if not tweets:
                break
            
            all_tweets.extend(tweets)
            
            if not next_cursor:
                break
            
            cursor = next_cursor
            print(f"Fetched {len(all_tweets)} tweets so far...")
        
        return all_tweets[:max_tweets]
    
    @staticmethod
    def parse_response(response: dict) -> tuple:
        """
        Parse the API response and extract useful tweet data.
        
        Returns:
            Tuple of (list of tweet dicts, next_cursor or None)
        """
        tweets = []
        next_cursor = None
        
        instructions = (
            response.get("data", {})
            .get("search_by_raw_query", {})
            .get("search_timeline", {})
            .get("timeline", {})
            .get("instructions", [])
        )
        
        for instruction in instructions:
            if instruction.get("type") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                
                for entry in entries:
                    entry_id = entry.get("entryId", "")
                    
                    # Check for cursor entries for pagination
                    if entry_id.startswith("cursor-bottom"):
                        content = entry.get("content", {})
                        next_cursor = content.get("value")
                        continue
                    
                    # Skip non-tweet entries
                    if not entry_id.startswith("tweet-"):
                        continue
                    
                    content = entry.get("content", {})
                    item_content = content.get("itemContent", {})
                    tweet_result = item_content.get("tweet_results", {}).get("result", {})
                    
                    if not tweet_result:
                        continue
                    
                    # Handle TweetWithVisibilityResults wrapper
                    if tweet_result.get("__typename") == "TweetWithVisibilityResults":
                        tweet_result = tweet_result.get("tweet", {})
                    
                    tweet_data = TwitterSearchAPI._extract_tweet_data(tweet_result)
                    if tweet_data:
                        tweets.append(tweet_data)
        
        return tweets, next_cursor
    
    @staticmethod
    def _extract_tweet_data(tweet_result: dict) -> Optional[dict]:
        """Extract useful data from a tweet result."""
        if not tweet_result:
            return None
        
        legacy = tweet_result.get("legacy", {})
        if not legacy:
            return None
        
        # Extract user info
        user_result = (
            tweet_result.get("core", {})
            .get("user_results", {})
            .get("result", {})
        )
        user_core = user_result.get("core", {})
        user_legacy = user_result.get("legacy", {})
        
        # Extract media URLs if present
        media_urls = []
        extended_entities = legacy.get("extended_entities", {})
        for media in extended_entities.get("media", []):
            media_info = {
                "type": media.get("type"),
                "url": media.get("media_url_https"),
                "expanded_url": media.get("expanded_url")
            }
            if media.get("type") == "video":
                variants = media.get("video_info", {}).get("variants", [])
                video_urls = [v for v in variants if v.get("content_type") == "video/mp4"]
                if video_urls:
                    # Get highest bitrate video
                    video_urls.sort(key=lambda x: x.get("bitrate", 0), reverse=True)
                    media_info["video_url"] = video_urls[0].get("url")
            media_urls.append(media_info)
        
        # Extract URLs from tweet
        urls = []
        for url_entity in legacy.get("entities", {}).get("urls", []):
            urls.append({
                "url": url_entity.get("url"),
                "expanded_url": url_entity.get("expanded_url"),
                "display_url": url_entity.get("display_url")
            })
        
        # Extract hashtags
        hashtags = [
            ht.get("text") for ht in legacy.get("entities", {}).get("hashtags", [])
        ]
        
        # Extract mentions
        mentions = [
            {
                "screen_name": m.get("screen_name"),
                "name": m.get("name"),
                "id": m.get("id_str")
            }
            for m in legacy.get("entities", {}).get("user_mentions", [])
        ]
        
        return {
            "id": tweet_result.get("rest_id"),
            "created_at": legacy.get("created_at"),
            "full_text": legacy.get("full_text"),
            "language": legacy.get("lang"),
            
            # Engagement metrics
            "favorite_count": legacy.get("favorite_count", 0),
            "retweet_count": legacy.get("retweet_count", 0),
            "reply_count": legacy.get("reply_count", 0),
            "quote_count": legacy.get("quote_count", 0),
            "bookmark_count": legacy.get("bookmark_count", 0),
            "view_count": int(tweet_result.get("views", {}).get("count", 0) or 0),
            
            # User info
            "user": {
                "id": user_result.get("rest_id"),
                "name": user_core.get("name"),
                "screen_name": user_core.get("screen_name"),
                "followers_count": user_legacy.get("followers_count", 0),
                "following_count": user_legacy.get("friends_count", 0),
                "is_verified": user_result.get("is_blue_verified", False),
                "profile_image_url": user_result.get("avatar", {}).get("image_url"),
                "description": user_legacy.get("description", "")
            },
            
            # Tweet metadata
            "is_reply": bool(legacy.get("in_reply_to_status_id_str")),
            "in_reply_to_tweet_id": legacy.get("in_reply_to_status_id_str"),
            "in_reply_to_user": legacy.get("in_reply_to_screen_name"),
            "is_quote": legacy.get("is_quote_status", False),
            "conversation_id": legacy.get("conversation_id_str"),
            
            # Entities
            "hashtags": hashtags,
            "mentions": mentions,
            "urls": urls,
            "media": media_urls,
            
            # Tweet URL
            "tweet_url": f"https://x.com/{user_core.get('screen_name')}/status/{tweet_result.get('rest_id')}"
        }


def save_to_json(tweets: list, filename: str):
    """Save tweets to a JSON file."""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tweets, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(tweets)} tweets to {filename}")


def save_to_csv(tweets: list, filename: str):
    """Save tweets to a CSV file (flattened structure)."""
    if not tweets:
        print("No tweets to save")
        return
    
    # Flatten the data for CSV
    flattened = []
    for tweet in tweets:
        flat = {
            "id": tweet["id"],
            "created_at": tweet["created_at"],
            "full_text": tweet["full_text"],
            "language": tweet["language"],
            "favorite_count": tweet["favorite_count"],
            "retweet_count": tweet["retweet_count"],
            "reply_count": tweet["reply_count"],
            "quote_count": tweet["quote_count"],
            "bookmark_count": tweet["bookmark_count"],
            "view_count": tweet["view_count"],
            "user_id": tweet["user"]["id"],
            "user_name": tweet["user"]["name"],
            "user_screen_name": tweet["user"]["screen_name"],
            "user_followers": tweet["user"]["followers_count"],
            "user_verified": tweet["user"]["is_verified"],
            "is_reply": tweet["is_reply"],
            "is_quote": tweet["is_quote"],
            "hashtags": ", ".join(tweet["hashtags"]),
            "tweet_url": tweet["tweet_url"]
        }
        flattened.append(flat)
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=flattened[0].keys())
        writer.writeheader()
        writer.writerows(flattened)
    
    print(f"Saved {len(tweets)} tweets to {filename}")


def print_tweets(tweets: list, limit: int = 10):
    """Print tweet summary to console."""
    print(f"\n{'='*80}")
    print(f"Found {len(tweets)} tweets")
    print(f"{'='*80}\n")
    
    for i, tweet in enumerate(tweets[:limit]):
        print(f"[{i+1}] @{tweet['user']['screen_name']} ({tweet['user']['name']})")
        print(f"    Followers: {tweet['user']['followers_count']:,}")
        print(f"    Created: {tweet['created_at']}")
        print(f"    Text: {tweet['full_text'][:200]}{'...' if len(tweet['full_text']) > 200 else ''}")
        print(f"    ❤️ {tweet['favorite_count']} | 🔁 {tweet['retweet_count']} | 💬 {tweet['reply_count']} | 👁️ {tweet['view_count']:,}")
        print(f"    URL: {tweet['tweet_url']}")
        print()
    
    if len(tweets) > limit:
        print(f"... and {len(tweets) - limit} more tweets")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch tweets from Twitter/X using the GraphQL Search API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python fetch_tweets.py --query "Razorpay" --since 2025-03-03 --until 2025-03-05
    python fetch_tweets.py --query "#Bitcoin" --since 2025-01-01 --count 100
    python fetch_tweets.py --query "from:elonmusk" --since 2025-01-01 --output elon_tweets.json
        """
    )
    
    # Required arguments
    parser.add_argument("--query", "-q", required=True, help="Search query (e.g., 'Razorpay', '#Bitcoin', 'from:username')")
    
    # Date filters
    parser.add_argument("--since", "-s", help="Start date (YYYY-MM-DD)")
    parser.add_argument("--until", "-u", help="End date (YYYY-MM-DD)")
    
    # Options
    parser.add_argument("--count", "-c", type=int, default=20, help="Number of tweets to fetch (default: 20)")
    parser.add_argument("--product", "-p", choices=["Latest", "Top"], default="Latest", help="Search product type (default: Latest)")
    parser.add_argument("--output", "-o", help="Output file path (supports .json or .csv)")
    parser.add_argument("--paginate", action="store_true", help="Fetch all tweets with pagination (up to --count)")
    
    # Authentication (should be set as environment variables or config file in production)
    parser.add_argument("--auth-token", default=os.environ.get("TWITTER_AUTH_TOKEN", "318969313bcce70b4ce79ee0f2bd9894284b678c"))
    parser.add_argument("--csrf-token", default=os.environ.get("TWITTER_CSRF_TOKEN", "59129146a000bff89f83651651da577a80395b1e1aae8ebbdf7d9a9e89d21fcc59b544ba05665ae39ca5f08f02ae06cfc990ef24431ed2c308102b4b0fb8038d06ab3de67baeaa0c7f338bc4b13c8c70"))
    parser.add_argument("--transaction-id", default=os.environ.get("TWITTER_TRANSACTION_ID", "D1r/HKLyEPoi/MKMVHaht4PQUPOZ251HMAuf64wl+WmEAw1UnvukjO2YQJs8GJwThEUb/QtHKpj1DZjTKuZiWedmi2kMDE"))
    
    args = parser.parse_args()
    
    # Validate dates if provided
    for date_arg, date_name in [(args.since, "since"), (args.until, "until")]:
        if date_arg:
            try:
                datetime.strptime(date_arg, "%Y-%m-%d")
            except ValueError:
                parser.error(f"Invalid {date_name} date format. Use YYYY-MM-DD")
    
    # Initialize API client
    api = TwitterSearchAPI(
        auth_token=args.auth_token,
        csrf_token=args.csrf_token,
        transaction_id=args.transaction_id
    )
    
    try:
        print(f"Searching for: {args.query}")
        if args.since:
            print(f"Since: {args.since}")
        if args.until:
            print(f"Until: {args.until}")
        print(f"Count: {args.count}")
        print()
        
        if args.paginate:
            tweets = api.search_all(
                query=args.query,
                since=args.since,
                until=args.until,
                max_tweets=args.count,
                product=args.product
            )
        else:
            response = api.search(
                query=args.query,
                since=args.since,
                until=args.until,
                count=args.count,
                product=args.product
            )
            tweets, _ = api.parse_response(response)
        
        # Print summary
        print_tweets(tweets)
        
        # Save to file if specified
        if args.output:
            if args.output.endswith('.csv'):
                save_to_csv(tweets, args.output)
            else:
                save_to_json(tweets, args.output)
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text if hasattr(e, 'response') else 'N/A'}")
        raise
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

