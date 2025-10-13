"""Test which models actually work with HF Inference API"""
from huggingface_hub import InferenceClient
from config import HF_API_TOKEN

# Test models to try
test_models = [
    "meta-llama/Meta-Llama-3-8B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    "bigcode/starcoder2-15b",
    "microsoft/phi-2",
    "mistralai/Mistral-7B-Instruct-v0.2",
]

client = InferenceClient(token=HF_API_TOKEN)

test_prompt = "Write a Python function that adds two numbers."

print("Testing HuggingFace Inference API models...")
print("="*70)

for model in test_models:
    print(f"\n🔍 Testing: {model}")
    try:
        # Try text_generation
        response = client.text_generation(
            prompt=test_prompt,
            model=model,
            max_new_tokens=50,
            temperature=0.3
        )
        print(f"  ✅ SUCCESS (text_generation)")
        print(f"  Response: {response[:100]}...")
        break  # Stop at first working model
    except Exception as e:
        error_str = str(e)
        if "404" in error_str:
            print(f"  ❌ Model not found (404)")
        elif "chat_completion" in error_str.lower():
            print(f"  ⚠️ Requires chat_completion instead")
            # Try chat completion
            try:
                response = client.chat_completion(
                    messages=[{"role": "user", "content": test_prompt}],
                    model=model,
                    max_tokens=50,
                )
                print(f"  ✅ SUCCESS (chat_completion)")
                print(f"  Response: {response.choices[0].message.content[:100]}...")
                break
            except Exception as e2:
                print(f"  ❌ Chat completion also failed: {str(e2)[:80]}")
        else:
            print(f"  ❌ Error: {str(e)[:80]}")

print("\n" + "="*70)
print("Testing complete!")
