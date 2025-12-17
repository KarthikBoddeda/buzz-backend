"""
Batch Tweet Analysis Script
Reads tweets from tweets.json and runs classification on each
Saves results to analysis_results.json
"""

import json
import time
from datetime import datetime
from app.analyzer.classifier import classify_tweet

INPUT_FILE = "tweets.json"
OUTPUT_FILE = "analysis_results.json"


def load_tweets(filepath: str) -> list:
    """Load tweets from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_image_url(tweet: dict):
    """Extract the first image URL from tweet media if available"""
    media = tweet.get("media", [])
    for item in media:
        if item.get("type") == "photo":
            return item.get("url")
    return None


def analyze_tweets(tweets: list) -> list:
    """Analyze all tweets and return results"""
    results = []
    total = len(tweets)
    
    print(f"\n📊 Starting analysis of {total} tweets...\n")
    print("-" * 70)
    
    for i, tweet in enumerate(tweets, 1):
        tweet_id = tweet.get("id")
        tweet_text = tweet.get("full_text", "")
        image_url = extract_image_url(tweet)
        user = tweet.get("user", {})
        
        print(f"[{i}/{total}] Analyzing tweet {tweet_id}...")
        print(f"         User: @{user.get('screen_name', 'unknown')}")
        print(f"         Text: {tweet_text[:60]}..." if len(tweet_text) > 60 else f"         Text: {tweet_text}")
        if image_url:
            print(f"         Image: Yes")
        
        # Run classification
        result = classify_tweet(tweet_text, image_url)
        
        # Build result object
        analysis_result = {
            "tweet_id": tweet_id,
            "tweet_url": tweet.get("tweet_url"),
            "created_at": tweet.get("created_at"),
            "full_text": tweet_text,
            "user": {
                "name": user.get("name"),
                "screen_name": user.get("screen_name"),
                "followers_count": user.get("followers_count"),
                "is_verified": user.get("is_verified")
            },
            "has_image": image_url is not None,
            "image_url": image_url,
            "analysis": result.get("classification") if result.get("success") else None,
            "analysis_success": result.get("success", False),
            "analysis_error": result.get("error") if not result.get("success") else None
        }
        
        results.append(analysis_result)
        
        # Show quick result
        if result.get("success"):
            classification = result["classification"]
            spam_icon = "🚫" if classification.get("is_spam") else "✅"
            cat = classification.get("category", "Unknown")
            product = classification.get("product", "N/A")
            print(f"         Result: {spam_icon} {cat} | Product: {product}")
        else:
            print(f"         Result: ❌ Error - {result.get('error', 'Unknown error')}")
        
        print()
        
        # Small delay to avoid rate limiting
        if i < total:
            time.sleep(0.5)
    
    return results


def save_results(results: list, filepath: str):
    """Save analysis results to JSON file"""
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_tweets": len(results),
        "successful_analyses": sum(1 for r in results if r["analysis_success"]),
        "failed_analyses": sum(1 for r in results if not r["analysis_success"]),
        "results": results
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    return output


def print_summary(output: dict):
    """Print analysis summary"""
    results = output["results"]
    
    print("=" * 70)
    print("📈 ANALYSIS SUMMARY")
    print("=" * 70)
    
    print(f"\nTotal Tweets: {output['total_tweets']}")
    print(f"Successful: {output['successful_analyses']}")
    print(f"Failed: {output['failed_analyses']}")
    
    # Category breakdown
    categories = {}
    products = {}
    spam_count = 0
    
    for r in results:
        if r["analysis_success"] and r["analysis"]:
            analysis = r["analysis"]
            
            # Count spam
            if analysis.get("is_spam"):
                spam_count += 1
            
            # Count categories
            cat = analysis.get("category", "Unknown")
            categories[cat] = categories.get(cat, 0) + 1
            
            # Count products
            prod = analysis.get("product") or "Not Specified"
            products[prod] = products.get(prod, 0) + 1
    
    print(f"\n🚫 Spam Detected: {spam_count}")
    
    print(f"\n📂 Categories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   • {cat}: {count}")
    
    print(f"\n📦 Products:")
    for prod, count in sorted(products.items(), key=lambda x: -x[1]):
        print(f"   • {prod}: {count}")
    
    print(f"\n💾 Results saved to: {OUTPUT_FILE}")
    print("=" * 70)


def main():
    print("=" * 70)
    print("🐦 RAZORPAY BATCH TWEET ANALYZER")
    print("=" * 70)
    
    # Load tweets
    print(f"\n📂 Loading tweets from {INPUT_FILE}...")
    tweets = load_tweets(INPUT_FILE)
    print(f"   Found {len(tweets)} tweets")
    
    # Analyze tweets
    results = analyze_tweets(tweets)
    
    # Save results
    print(f"\n💾 Saving results to {OUTPUT_FILE}...")
    output = save_results(results, OUTPUT_FILE)
    
    # Print summary
    print_summary(output)


if __name__ == "__main__":
    main()

