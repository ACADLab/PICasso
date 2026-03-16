# HuggingFace Inference API - Token Setup Guide

## Problem
The current token is returning 404 errors for all models, which means:
1. The token lacks proper permissions for Inference API
2. The token may be invalid or expired
3. Need to create a **fine-grained token** with specific permissions

## Solution: Create a Fine-Grained Token

### Step 1: Generate New Token
1. Go to: https://huggingface.co/settings/tokens/new
2. Select **"Fine-grained"** token type
3. Give it a name (e.g., "PICasso Inference API")

### Step 2: Set Permissions
Enable the following permission:
- ✅ **"Make calls to Inference Providers"**

### Step 3: Copy Token
1. Copy the generated token (starts with `hf_...`)
2. Update it in `config.py`:
   ```python
   HF_API_TOKEN = "hf_YOUR_NEW_TOKEN_HERE"
   ```
   OR set as environment variable:
   ```bash
   export HF_API_TOKEN="hf_YOUR_NEW_TOKEN_HERE"
   ```

## Testing the Token

Run this test to verify the token works:

```bash
python hf_inference_workflow/test_inference_fixed.py
```

## Known Working Models

Once token is fixed, try these models (confirmed to work on serverless API):

1. **Qwen2.5-Coder-32B-Instruct** - Best for code generation
2. **meta-llama/Llama-3.2-3B-Instruct** - Smaller, faster
3. **mistralai/Mistral-7B-Instruct-v0.3** - Good general purpose

## Free Tier Limits

HuggingFace provides a generous free tier:
- Multiple requests per second
- Suitable for development and testing
- PRO subscription provides more credits if needed

## References
- Token Creation: https://huggingface.co/settings/tokens/new
- Inference Providers Docs: https://huggingface.co/docs/inference-providers/en/index
- Model Playground: https://huggingface.co/playground
