#!/usr/bin/env python3
"""
Dry run test - Send 3 test prompts to each model and check raw outputs.
This verifies that the framework can parse outputs from different models.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
framework_dir = Path(__file__).parent
parent_dir = framework_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# Test prompts (simple YAML generation tasks)
TEST_PROMPTS = [
    "Generate a YAML circuit with one mmi1x2 component named 'splitter' at position (0, 0).",
    "Create a YAML circuit with two mmi1x2 components: 'mmi1' at (0,0) and 'mmi2' at (200,0).",
    "Generate YAML for an MZI with two mmi1x2 splitters and one straight_heater_metal phase shifter."
]

SYSTEM_PROMPT = """You are a photonic circuit synthesis engine.
Generate valid YAML photonic circuits compatible with gdsfactory's generic_tech PDK.
Output only the YAML, no explanations."""


def test_model_agent(agent, model_name):
    """Test an agent with 3 prompts."""
    print(f"\n{'='*70}")
    print(f"Testing: {model_name}")
    print(f"{'='*70}")
    
    results = []
    for i, prompt in enumerate(TEST_PROMPTS, 1):
        print(f"\n--- Test Prompt {i}/3 ---")
        print(f"Prompt: {prompt[:60]}...")
        
        try:
            # Call the agent
            if hasattr(agent, 'ASK_LLM'):
                response = agent.ASK_LLM(SYSTEM_PROMPT, prompt)
            elif hasattr(agent, 'ask_llm'):
                response = agent.ask_llm(SYSTEM_PROMPT, prompt)
            elif hasattr(agent, 'generate'):
                full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
                response = agent.generate(full_prompt)
            else:
                print(f"❌ Agent doesn't have ASK_LLM, ask_llm, or generate method")
                return False
            
            # Check if response contains YAML
            has_yaml = 'instances:' in response or 'components:' in response
            has_markdown = '```yaml' in response or '```' in response
            
            print(f"✅ Response received ({len(response)} chars)")
            print(f"   Contains 'instances:': {has_yaml}")
            print(f"   Contains markdown: {has_markdown}")
            
            # Show first 200 chars
            preview = response[:200].replace('\n', ' ')
            print(f"   Preview: {preview}...")
            
            results.append({
                'prompt': i,
                'success': True,
                'length': len(response),
                'has_yaml': has_yaml,
                'has_markdown': has_markdown,
                'response': response
            })
            
        except Exception as e:
            print(f"❌ Error: {str(e)[:200]}")
            results.append({
                'prompt': i,
                'success': False,
                'error': str(e)
            })
    
    # Summary
    success_count = sum(1 for r in results if r.get('success', False))
    print(f"\n--- Summary for {model_name} ---")
    print(f"Success: {success_count}/3")
    if success_count > 0:
        avg_length = sum(r.get('length', 0) for r in results if r.get('success')) / success_count
        print(f"Average response length: {avg_length:.0f} chars")
    
    return success_count == 3


def main():
    """Run dry run tests for all models."""
    print("="*70)
    print("DRY RUN TEST - Testing Model Output Parsing")
    print("="*70)
    
    # Import create_agent
    from gd_picasso.test_with_llm import create_agent
    
    # Models to test
    models_to_test = [
        'gpt-4o',
        'deepseek-r1-api',
        'claude-sonnet-4.5',
        'kimi-thinking',
    ]
    
    results = {}
    
    for model_name in models_to_test:
        try:
            print(f"\n\n{'#'*70}")
            print(f"Creating agent for: {model_name}")
            print(f"{'#'*70}")
            
            agent = create_agent(model_name)
            if agent is None:
                print(f"❌ Failed to create agent for {model_name}")
                results[model_name] = False
                continue
            
            # Test the agent
            success = test_model_agent(agent, model_name)
            results[model_name] = success
            
        except Exception as e:
            print(f"❌ Error testing {model_name}: {e}")
            results[model_name] = False
    
    # Final summary
    print(f"\n\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")
    
    for model, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {model}")
    
    total_tested = len(results)
    total_passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {total_passed}/{total_tested} models passed all 3 tests")
    print("="*70)


if __name__ == '__main__':
    # Set API keys from environment
    required_keys = {
        'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
        'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY'),
        'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY'),
        'HF_API_TOKEN': os.getenv('HF_API_TOKEN') or os.getenv('HF_TOKEN'),
    }
    
    missing = [k for k, v in required_keys.items() if not v]
    if missing:
        print(f"⚠️  Missing API keys: {', '.join(missing)}")
        print("Some models may not be testable.")
    
    main()


