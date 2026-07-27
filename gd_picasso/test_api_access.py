#!/usr/bin/env python3
"""
Test API access for all model providers.
Verifies which models are accessible with the provided API keys.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
framework_dir = Path(__file__).parent
parent_dir = framework_dir.parent

# Load .env from project root
load_dotenv(parent_dir / ".env")

if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Debug prints (remove later)
print(f"Framework dir: {framework_dir}")
print(f"Parent dir: {parent_dir}")
print(f"Env file: {parent_dir / '.env'}")
print(f"Env exists: {(parent_dir / '.env').exists()}")
print(f"OPENAI_API_KEY loaded: {os.getenv('OPENAI_API_KEY') is not None}")
print(f"GEMINI_API_KEY loaded: {os.getenv('GEMINI_API_KEY') is not None}")

def test_openai_models():
    """Test OpenAI API access for GPT-5 and o3 models."""
    print("\n" + "="*70)
    print("Testing OpenAI API Access")
    print("="*70)
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set")
        return {}
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        models_to_test = ['gpt-4o', 'gpt-5', 'o3-mini', 'o3']
        accessible = {}
        
        for model in models_to_test:
            try:
                # Try to list models or make a simple test call
                # GPT-5 and o3 models might not support max_tokens, try without it first
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": "test"}],
                        max_tokens=5
                    )
                except Exception as e2:
                    # If max_tokens fails, try without it (for o3 models)
                    if "max_tokens" in str(e2).lower():
                        response = client.chat.completions.create(
                            model=model,
                            messages=[{"role": "user", "content": "test"}]
                        )
                    else:
                        raise
                accessible[model] = True
                print(f"✅ {model}: Accessible")
            except Exception as e:
                error_msg = str(e)
                if "model_not_found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    accessible[model] = False
                    print(f"❌ {model}: Not available (model not found)")
                elif "rate_limit" in error_msg.lower() or "429" in error_msg:
                    accessible[model] = True  # Model exists, just rate limited
                    print(f"⚠️  {model}: Accessible (rate limited)")
                else:
                    accessible[model] = False
                    print(f"❌ {model}: Error - {error_msg[:100]}")
        
        return accessible
    except ImportError:
        print("❌ openai package not installed")
        return {}
    except Exception as e:
        print(f"❌ OpenAI API test failed: {e}")
        return {}


def test_deepseek_api():
    """Test DeepSeek API access."""
    print("\n" + "="*70)
    print("Testing DeepSeek API Access")
    print("="*70)
    
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ DEEPSEEK_API_KEY not set")
        return {}
    
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
        
        models_to_test = ['deepseek-chat', 'deepseek-reasoner']
        accessible = {}
        
        for model in models_to_test:
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                )
                accessible[model] = True
                print(f"✅ {model}: Accessible")
            except Exception as e:
                error_msg = str(e)
                if "model_not_found" in error_msg.lower():
                    accessible[model] = False
                    print(f"❌ {model}: Not available")
                else:
                    accessible[model] = False
                    print(f"❌ {model}: Error - {error_msg[:100]}")
        
        return accessible
    except ImportError:
        print("❌ openai package not installed")
        return {}
    except Exception as e:
        print(f"❌ DeepSeek API test failed: {e}")
        return {}


def test_anthropic_api():
    """Test Anthropic API access."""
    print("\n" + "="*70)
    print("Testing Anthropic API Access")
    print("="*70)
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set")
        return {}
    
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        models_to_test = ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022']
        accessible = {}
        
        for model in models_to_test:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=5,
                    messages=[{"role": "user", "content": "test"}]
                )
                accessible[model] = True
                print(f"✅ {model}: Accessible")
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower():
                    accessible[model] = False
                    print(f"❌ {model}: Not available")
                else:
                    accessible[model] = False
                    print(f"❌ {model}: Error - {error_msg[:100]}")
        
        return accessible
    except ImportError:
        print("❌ anthropic package not installed (pip install anthropic)")
        return {}
    except Exception as e:
        print(f"❌ Anthropic API test failed: {e}")
        return {}


def test_gemini_api():
    """Test Google Gemini API access."""
    print("\n" + "="*70)
    print("Testing Google Gemini API Access")
    print("="*70)
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not set")
        return {}
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        models_to_test = ['gemini-2.0-flash-exp', 'gemini-2.5-pro', 'gemini-1.5-pro']
        accessible = {}
        
        for model in models_to_test:
            try:
                model_client = genai.GenerativeModel(model)
                response = model_client.generate_content("test", generation_config={"max_output_tokens": 5})
                accessible[model] = True
                print(f"✅ {model}: Accessible")
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower() or "404" in error_msg:
                    accessible[model] = False
                    print(f"❌ {model}: Not available")
                else:
                    accessible[model] = False
                    print(f"❌ {model}: Error - {error_msg[:100]}")
        
        return accessible
    except ImportError:
        print("❌ google-generativeai package not installed (pip install google-generativeai)")
        return {}
    except Exception as e:
        print(f"❌ Gemini API test failed: {e}")
        return {}


def test_huggingface_models():
    """Test HuggingFace API access for various models."""
    print("\n" + "="*70)
    print("Testing HuggingFace API Access")
    print("="*70)
    
    api_token = os.getenv('HF_TOKEN') or os.getenv('HF_API_TOKEN')
    if not api_token:
        print("❌ HF_TOKEN or HF_API_TOKEN not set")
        return {}
    
    models_to_test = [
        'moonshotai/Kimi-V2',
        'moonshotai/Kimi-K2-Thinking',
        'meta-llama/Llama-3.1-70B-Instruct',
        'Qwen/Qwen2.5-32B-Instruct',
        'mistralai/Mistral-Large-2407',
        'microsoft/Phi-4-mini'
    ]
    
    accessible = {}
    
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=api_token)
        
        for model in models_to_test:
            try:
                # Try a simple test call
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "test"}],
                    max_tokens=5
                )
                accessible[model] = True
                print(f"✅ {model}: Accessible")
            except Exception as e:
                error_msg = str(e)
                if "not found" in error_msg.lower() or "404" in error_msg:
                    accessible[model] = False
                    print(f"❌ {model}: Not available")
                else:
                    accessible[model] = False
                    print(f"❌ {model}: Error - {error_msg[:100]}")
        
        return accessible
    except ImportError:
        print("❌ huggingface_hub package not installed")
        return {}
    except Exception as e:
        print(f"❌ HuggingFace API test failed: {e}")
        return {}


def main():
    """Run all API access tests."""
    print("="*70)
    print("API Access Test - Checking Model Availability")
    print("="*70)
    
    results = {
        'openai': test_openai_models(),
        'deepseek': test_deepseek_api(),
        'anthropic': test_anthropic_api(),
        'gemini': test_gemini_api(),
        'huggingface': test_huggingface_models()
    }
    
    print("\n" + "="*70)
    print("Summary")
    print("="*70)
    
    total_accessible = 0
    total_tested = 0
    
    for provider, models in results.items():
        if models:
            accessible_count = sum(1 for v in models.values() if v)
            total_count = len(models)
            total_accessible += accessible_count
            total_tested += total_count
            print(f"{provider.upper()}: {accessible_count}/{total_count} models accessible")
    
    print(f"\nTotal: {total_accessible}/{total_tested} models accessible")
    print("="*70)
    
    return results


if __name__ == '__main__':
    main()

