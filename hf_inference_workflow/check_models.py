"""Quick script to check available models on HF Inference API"""
from huggingface_hub import InferenceClient
import os

# Get API token from config
from config import HF_API_TOKEN

print("Checking available HuggingFace Inference API models...")
print(f"Using token: {HF_API_TOKEN[:10]}...{HF_API_TOKEN[-5:]}")
print("="*70)

try:
    client = InferenceClient(token=HF_API_TOKEN)

    # List deployed models
    print("\n🔍 Listing deployed models...")
    models = client.list_deployed_models()

    print(f"\n✅ Found deployed models:")
    print(models)

    # Try to find code-related models
    if hasattr(models, 'frameworks'):
        print("\n📋 Available by framework:")
        for framework, framework_models in models.items():
            print(f"\n{framework}:")
            for model in framework_models[:10]:  # Show first 10
                print(f"  - {model}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Alternative: Try using chat completion instead of text_generation")
    print("   Models like Meta-Llama, Qwen, Mistral typically work better")
