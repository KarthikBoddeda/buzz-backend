"""
Azure OpenAI API Test Script
Tests both text chat completion and image/vision capabilities
"""

import requests
import base64
import json
import os

# Azure OpenAI Configuration (from environment variables)
ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://siddh-m9gwv1hd-eastus2.cognitiveservices.azure.com")
DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "hackon-fy26q3-gpt5")
API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
API_KEY = os.getenv("AZURE_OPENAI_API_KEY")

if not API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")

# Full API URL
API_URL = f"{ENDPOINT}/openai/deployments/{DEPLOYMENT}/chat/completions?api-version={API_VERSION}"

# Headers
headers = {
    "Content-Type": "application/json",
    "api-key": API_KEY
}


def test_text_completion():
    """Test basic text chat completion"""
    print("=" * 60)
    print("Testing TEXT Chat Completion...")
    print("=" * 60)
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Hello! Can you tell me a short joke about programming?"
            }
        ],
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print("\n✅ Text completion successful!")
        print(f"\nModel: {result.get('model', 'N/A')}")
        print(f"\nResponse:\n{result['choices'][0]['message']['content']}")
        print(f"\nUsage: {result.get('usage', {})}")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n❌ HTTP Error: {e}")
        print(f"Response: {response.text}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def test_image_support():
    """Test if the model supports image/vision capabilities"""
    print("\n" + "=" * 60)
    print("Testing IMAGE/Vision Support...")
    print("=" * 60)
    
    # Using a sample image URL (a simple test image)
    sample_image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png"
    
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant that can analyze images."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "What do you see in this image? Describe it briefly."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": sample_image_url
                        }
                    }
                ]
            }
        ],
        "max_tokens": 300,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        print("\n✅ Image/Vision support CONFIRMED!")
        print(f"\nModel: {result.get('model', 'N/A')}")
        print(f"\nImage Analysis Response:\n{result['choices'][0]['message']['content']}")
        print(f"\nUsage: {result.get('usage', {})}")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"\n⚠️  HTTP Error: {e}")
        error_detail = response.text
        print(f"Response: {error_detail}")
        
        # Check if it's a "not supported" error
        if "image" in error_detail.lower() or "vision" in error_detail.lower():
            print("\n❌ Image/Vision is NOT supported by this deployment.")
        else:
            print("\n⚠️  Could not determine image support. Error may be unrelated.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def get_model_info():
    """Try to get model capabilities info"""
    print("\n" + "=" * 60)
    print("API Configuration Info")
    print("=" * 60)
    print(f"\nEndpoint: {ENDPOINT}")
    print(f"Deployment: {DEPLOYMENT}")
    print(f"API Version: {API_VERSION}")
    print(f"Full URL: {API_URL}")


if __name__ == "__main__":
    print("\n🚀 Azure OpenAI API Test Script\n")
    
    # Show configuration
    get_model_info()
    
    # Test text completion
    text_success = test_text_completion()
    
    # Test image support
    image_success = test_image_support()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Text Completion: {'✅ Working' if text_success else '❌ Failed'}")
    print(f"Image/Vision Support: {'✅ Supported' if image_success else '❌ Not Supported or Failed'}")
    print("=" * 60 + "\n")

