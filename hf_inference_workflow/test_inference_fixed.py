"""
Test script using proper InferenceClient setup per HuggingFace documentation.
This tests if the token has correct permissions.
"""
import os
from huggingface_hub import InferenceClient

# Get token from config or environment
try:
    from config import HF_API_TOKEN
except:
    HF_API_TOKEN = os.environ.get("HF_API_TOKEN", "")

print("="*70)
print("HUGGINGFACE INFERENCE API - PROPER TOKEN TEST")
print("="*70)

# Check token format
print(f"\n1️⃣ Token Check:")
if not HF_API_TOKEN or HF_API_TOKEN == "ENTER_YOUR_HF_TOKEN_HERE":
    print("  ❌ No valid token found!")
    print("\n  Please set HF_API_TOKEN in config.py or as environment variable")
    print("  Get token from: https://huggingface.co/settings/tokens/new")
    print("  IMPORTANT: Select 'Fine-grained' and enable 'Make calls to Inference Providers'")
    exit(1)

print(f"  Token format: {HF_API_TOKEN[:10]}...{HF_API_TOKEN[-5:]}")
print(f"  Length: {len(HF_API_TOKEN)} chars")

# Known working models on serverless API
test_models = [
    ("Qwen/Qwen2.5-Coder-32B-Instruct", "Best for code generation"),
    ("meta-llama/Llama-3.2-3B-Instruct", "Smaller, faster"),
    ("mistralai/Mistral-7B-Instruct-v0.3", "General purpose"),
    ("microsoft/Phi-3-mini-4k-instruct", "Compact model"),
]

print(f"\n2️⃣ Testing Models:\n")

success = False
working_model = None

for model_id, description in test_models:
    print(f"Testing: {model_id}")
    print(f"  Description: {description}")

    try:
        # Create client with specific model
        client = InferenceClient(model=model_id, token=HF_API_TOKEN)

        # Simple test query
        response = client.text_generation(
            "Write a Python function to add two numbers.",
            max_new_tokens=128,
            temperature=0.2,
        )

        print(f"  ✅ SUCCESS!")
        print(f"  Response preview: {response[:100]}...")
        print()

        success = True
        working_model = model_id
        break

    except Exception as e:
        error_msg = str(e)

        if "404" in error_msg or "not found" in error_msg.lower():
            print(f"  ❌ Model not available on serverless API")
        elif "401" in error_msg or "unauthorized" in error_msg.lower():
            print(f"  ❌ AUTHORIZATION ERROR - Token lacks permissions!")
            print(f"     Go to https://huggingface.co/settings/tokens/new")
            print(f"     Create 'Fine-grained' token with 'Make calls to Inference Providers'")
            break
        elif "403" in error_msg or "forbidden" in error_msg.lower():
            print(f"  ⚠️ Model requires PRO subscription or gated access")
        else:
            print(f"  ❌ Error: {error_msg[:100]}")

        print()

print("="*70)
if success:
    print(f"✅ SUCCESS! Your token works!")
    print(f"Working model: {working_model}")
    print(f"\nUpdate config.py:")
    print(f'DEFAULT_MODEL = "{working_model}"')
else:
    print("❌ No models worked. Possible issues:")
    print("1. Token lacks 'Make calls to Inference Providers' permission")
    print("2. Token is invalid or expired")
    print("3. Network/connectivity issues")
    print("\nCreate new fine-grained token at:")
    print("https://huggingface.co/settings/tokens/new")

print("="*70)
