"""Test if HF API token is valid"""
from huggingface_hub import HfApi
from config import HF_API_TOKEN

print("Testing HuggingFace API Token...")
print(f"Token: {HF_API_TOKEN[:10]}...{HF_API_TOKEN[-5:]}")
print("="*70)

try:
    api = HfApi(token=HF_API_TOKEN)

    # Try to get user info (this validates the token)
    user_info = api.whoami()

    print(f"\n✅ Token is VALID!")
    print(f"Username: {user_info.get('name', 'N/A')}")
    print(f"Type: {user_info.get('type', 'N/A')}")

    # Check if token has inference permission
    print(f"\nToken scopes/auth: {user_info.get('auth', {})}")

except Exception as e:
    print(f"\n❌ Token validation failed: {e}")
    print("\n💡 Troubleshooting:")
    print("1. Get a new token from https://huggingface.co/settings/tokens")
    print("2. Ensure token has 'Read' permissions")
    print("3. For Inference API, token must be valid (not expired)")
