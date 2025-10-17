"""
Quick test script to verify OpenAI API connection.

Run this to test your setup before running the full generation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from hf_inference_workflow.openai_api_client import OpenAIInferenceAgent
    from hf_inference_workflow.config import OPENAI_API_KEY, OPENAI_MODEL

    print("="*70)
    print("OpenAI API Connection Test")
    print("="*70)

    print(f"\n1. Configuration:")
    print(f"   Model: {OPENAI_MODEL}")
    print(f"   API Key: {'*' * 20}{OPENAI_API_KEY[-8:] if len(OPENAI_API_KEY) > 8 else 'NOT SET'}")

    print("\n2. Initializing OpenAI agent...")
    agent = OpenAIInferenceAgent(api_key=OPENAI_API_KEY, model=OPENAI_MODEL)
    print("   [OK] Agent initialized successfully")

    print("\n3. Testing API connection with simple query...")
    response = agent.ASK_LLM(
        system_prompt="You are a helpful assistant.",
        user_q="Write a Python function that returns 'Hello World'"
    )

    print("   [OK] API connection successful!")
    print(f"\n4. Response preview (first 200 chars):")
    print(f"   {response[:200]}...")

    print("\n" + "="*70)
    print("[SUCCESS] ALL TESTS PASSED - Ready to generate circuits!")
    print("="*70)

    print("\nNext steps:")
    print("1. Run full generation:")
    print("   python gen_data_openai_validated.py --problems test_20_problems.txt")
    print("\n2. Or start with a smaller test:")
    print("   python gen_data_openai_validated.py --problems problems.txt --samples 1")

except ImportError as e:
    print(f"\n[ERROR] Import Error: {e}")
    print("\nPlease install required packages:")
    print("   pip install openai gdsfactory pandas tqdm")
    sys.exit(1)

except Exception as e:
    print(f"\n[ERROR] {e}")
    print("\nTroubleshooting:")
    print("1. Check your OpenAI API key in config.py")
    print("2. Verify you have API credits at https://platform.openai.com/account/billing")
    print("3. Check your internet connection")
    sys.exit(1)
