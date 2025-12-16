"""
Razorpay Tweet Classification Script
Classifies tweets into categories: Spam, Praise, Complaint, Experience Breakage, Feature Request
With scoring
"""

import requests
import json
import sys
import os

# Azure OpenAI Configuration (from environment variables)
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://siddh-m9gwv1hd-eastus2.cognitiveservices.azure.com")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "hackon-fy26q3-gpt5")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

if not API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")

API_URL = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": API_KEY
}

# Static classification prompt
CLASSIFICATION_PROMPT = """You are a social media analyst for Razorpay, a leading payment gateway company in India.

Your task is to analyze tweets mentioning Razorpay and classify them according to the following criteria:

## 1. SPAM DETECTION
Determine if the tweet is spam or legitimate.
- is_spam: true/false
- spam_reason: (if spam, explain why; otherwise null)

## 2. CATEGORY CLASSIFICATION
Classify the tweet into ONE of these categories:
- "Praise" - Positive feedback, appreciation, or compliments about Razorpay
- "Complaint" - Negative feedback, dissatisfaction, or grievances (but service is working)
- "Experience Breakage" - Technical issues, bugs, service outages, payment failures, or broken functionality
- "Feature Request" - Suggestions for new features or improvements

## 3. RAZORPAY PRODUCT IDENTIFICATION
Identify which Razorpay product(s) the tweet is related to. Choose from:
- "Payment Gateway" - Online payment acceptance, checkout, APIs
- "Payment Links" - Shareable payment links
- "Payment Pages" - No-code payment pages
- "Payment Buttons" - Embeddable payment buttons
- "Subscriptions" - Recurring payments
- "Smart Collect" - Virtual accounts, automated reconciliation
- "QR Codes" - QR-based payments
- "POS" - Point of sale terminals
- "Route" - Split payments, marketplace payouts
- "Razorpay X" - Business banking, payouts, vendor payments
- "Payroll" - Salary disbursement, compliance
- "Capital" - Business loans, credit line
- "Tokenisation" - Card tokenization
- "Magic Checkout" - One-click checkout
- "Instant Settlements" - Fast settlement
- "Disputes" - Chargebacks, refund issues
- "Dashboard" - Razorpay dashboard/portal
- "Support" - Customer support experience
- "Onboarding/KYC" - Account activation, verification
- "General" - General mention, not product-specific

If the tweet doesn't mention or relate to any specific product, set to null.

## 4. SCORING
Provide scores on a scale of 1-10:
- sentiment_score: Overall sentiment (1=very negative, 5=neutral, 10=very positive)
- urgency_score: How urgent is this for Razorpay to address (1=not urgent, 10=critical)
- impact_score: Potential business/reputation impact (1=low, 10=high)

## 5. ADDITIONAL ANALYSIS
- summary: A brief one-line summary of the tweet
- key_issues: List any specific issues or topics mentioned
- suggested_action: What action should Razorpay take (if any)

IMPORTANT: 
- If an image is attached, analyze it carefully as it may contain screenshots of errors, payment failures, or other relevant information.
- Consider the context of Razorpay being a payment gateway - issues with payments are high priority.
- Be objective and accurate in your classification.
- For product identification, look for specific keywords, error messages, or context clues in both text and images.

Respond ONLY with valid JSON in this exact format:
{
    "is_spam": boolean,
    "spam_reason": string or null,
    "category": "Praise" | "Complaint" | "Experience Breakage" | "Feature Request",
    "product": string or null,
    "sentiment_score": number (1-10),
    "urgency_score": number (1-10),
    "impact_score": number (1-10),
    "summary": string,
    "key_issues": [string],
    "suggested_action": string
}"""


def classify_tweet(tweet_text: str, image_url: str = None) -> dict:
    """
    Classify a tweet about Razorpay
    
    Args:
        tweet_text: The text content of the tweet
        image_url: Optional URL of an image attached to the tweet
    
    Returns:
        dict: Classification results
    """
    
    # Build the user message content
    user_content = []
    
    # Add the tweet text
    user_content.append({
        "type": "text",
        "text": f"Analyze and classify this tweet:\n\n\"{tweet_text}\""
    })
    
    # Add image if provided
    if image_url:
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": image_url
            }
        })
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": CLASSIFICATION_PROMPT
            },
            {
                "role": "user",
                "content": user_content
            }
        ],
        "max_tokens": 500,
        "temperature": 0.3  # Lower temperature for more consistent classification
    }
    
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        
        result = response.json()
        content = result['choices'][0]['message']['content']
        
        # Parse the JSON response
        # Handle potential markdown code blocks
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        classification = json.loads(content)
        return {
            "success": True,
            "classification": classification,
            "usage": result.get("usage", {})
        }
        
    except requests.exceptions.HTTPError as e:
        return {
            "success": False,
            "error": f"HTTP Error: {e}",
            "details": response.text
        }
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse response as JSON: {e}",
            "raw_response": content
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def main():
    # Example tweet
    tweet = """
    I am an indian merchant. Why is it showing US dollars. Also i don't see any logos - unloaded images in the footer. So bad.
    """
    # image_url = "https://pbs.twimg.com/media/G8S2k-ba4AMfNvt?format=jpg&name=medium"
    # For Google Drive images, use this format: https://drive.google.com/uc?export=view&id=YOUR_FILE_ID
    image_url = "https://drive.google.com/uc?export=view&id=148-YuK-82KIha5EwzzqMTjvlxsRJglMQ"
    print("=" * 70)
    print("🐦 RAZORPAY TWEET CLASSIFIER")
    print("=" * 70)
    print(f"\n📝 Tweet: \"{tweet}\"")
    if image_url:
        print(f"🖼️  Image: {image_url}")
    print("\n" + "-" * 70)
    print("Analyzing tweet...")
    print("-" * 70 + "\n")
    
    result = classify_tweet(tweet, image_url)
    
    if result["success"]:
        classification = result["classification"]
        
        print("✅ CLASSIFICATION RESULTS\n")
        
        # Spam Detection
        spam_status = "🚫 SPAM" if classification.get("is_spam") else "✅ Legitimate"
        print(f"Spam Detection: {spam_status}")
        if classification.get("spam_reason"):
            print(f"   Reason: {classification['spam_reason']}")
        
        # Category
        category_emoji = {
            "Praise": "🌟",
            "Complaint": "😤",
            "Experience Breakage": "🔥",
            "Feature Request": "💡"
        }
        cat = classification.get("category", "Unknown")
        print(f"\nCategory: {category_emoji.get(cat, '📌')} {cat}")
        
        # Product
        product = classification.get("product")
        if product:
            print(f"Product: 📦 {product}")
        else:
            print(f"Product: ➖ Not product-specific")
        
        # Scores
        print(f"\n📊 Scores:")
        print(f"   Sentiment:  {'🟢' if classification.get('sentiment_score', 0) > 6 else '🟡' if classification.get('sentiment_score', 0) > 4 else '🔴'} {classification.get('sentiment_score', 'N/A')}/10")
        print(f"   Urgency:    {'🔴' if classification.get('urgency_score', 0) > 7 else '🟡' if classification.get('urgency_score', 0) > 4 else '🟢'} {classification.get('urgency_score', 'N/A')}/10")
        print(f"   Impact:     {'🔴' if classification.get('impact_score', 0) > 7 else '🟡' if classification.get('impact_score', 0) > 4 else '🟢'} {classification.get('impact_score', 'N/A')}/10")
        
        # Summary
        print(f"\n📋 Summary: {classification.get('summary', 'N/A')}")
        
        # Key Issues
        if classification.get("key_issues"):
            print(f"\n🔑 Key Issues:")
            for issue in classification["key_issues"]:
                print(f"   • {issue}")
        
        # Suggested Action
        print(f"\n💡 Suggested Action: {classification.get('suggested_action', 'N/A')}")
        
        # Raw JSON
        print("\n" + "-" * 70)
        print("📄 Raw JSON Response:")
        print(json.dumps(classification, indent=2))
        
    else:
        print(f"❌ Error: {result.get('error')}")
        if result.get("details"):
            print(f"Details: {result['details']}")
        if result.get("raw_response"):
            print(f"Raw response: {result['raw_response']}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

