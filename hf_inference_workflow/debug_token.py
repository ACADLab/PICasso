"""
Deep diagnostic test to understand the exact API error
"""
import requests
from huggingface_hub import InferenceClient
from config import HF_API_TOKEN

print("="*70)
print("DEEP DIAGNOSTIC TEST - HuggingFace API")
print("="*70)

print(f"\n1️⃣ Token Info:")
print(f"   Format: {HF_API_TOKEN[:12]}...{HF_API_TOKEN[-8:]}")
print(f"   Length: {len(HF_API_TOKEN)} chars")

# Test 1: Direct API call to check token
print(f"\n2️⃣ Testing Token Validity (Direct API):")
headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
response = requests.get("https://huggingface.co/api/whoami", headers=headers)

print(f"   Status: {response.status_code}")
if response.status_code == 200:
    user_data = response.json()
    print(f"   ✅ Token is valid!")
    print(f"   Username: {user_data.get('name', 'N/A')}")
    print(f"   Type: {user_data.get('type', 'N/A')}")

    # Check auth info
    auth_info = user_data.get('auth', {})
    print(f"\n   Token Permissions:")
    for key, value in auth_info.items():
        print(f"     - {key}: {value}")
else:
    print(f"   ❌ Token invalid: {response.text}")

# Test 2: Try inference with detailed error
print(f"\n3️⃣ Testing Inference API (with detailed errors):")

test_models = [
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "microsoft/Phi-3-mini-4k-instruct",
]

for model_id in test_models:
    print(f"\n   Testing: {model_id}")

    try:
        client = InferenceClient(model=model_id, token=HF_API_TOKEN)

        # Try text generation
        response = client.text_generation(
            "Hello world",
            max_new_tokens=10,
        )

        print(f"   ✅ SUCCESS! Response: {response[:50]}...")
        break

    except Exception as e:
        error_str = str(e)
        print(f"   ❌ Error: {error_str}")

        # Parse the error for more details
        if "404" in error_str:
            print(f"      → Model not found on serverless API")
        elif "401" in error_str:
            print(f"      → Unauthorized - token issue")
        elif "403" in error_str:
            print(f"      → Forbidden - may need PRO or model gated")
        elif "503" in error_str:
            print(f"      → Service unavailable - model loading")

        # Extract the actual URL being called
        if "url:" in error_str.lower():
            print(f"      → Check URL in error above")

# Test 3: Try chat completion API instead
print(f"\n4️⃣ Testing Chat Completion API:")
print(f"   (Alternative API endpoint)")

try:
    client = InferenceClient(token=HF_API_TOKEN)

    # Try without specifying model (uses default routing)
    response = client.chat_completion(
        messages=[{"role": "user", "content": "Say hello"}],
        max_tokens=20,
    )

    print(f"   ✅ Chat API works!")
    print(f"   Response: {response.choices[0].message.content}")

except Exception as e:
    print(f"   ❌ Chat API failed: {str(e)[:200]}")

# Test 4: Check if we can list models
print(f"\n5️⃣ Checking Available Inference Providers:")
try:
    # Try to get model info from HF API
    url = "https://huggingface.co/api/models?pipeline_tag=text-generation&inference=warm&sort=trending&limit=5"
    response = requests.get(url)

    if response.status_code == 200:
        models = response.json()
        print(f"   Found {len(models)} trending warm models:")
        for model in models[:5]:
            print(f"     - {model.get('id', 'N/A')}")
    else:
        print(f"   ❌ Could not fetch model list")

except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)
