# Token Issue Report

## Problem Found ❌

The token `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` is **INVALID**.

When tested against HuggingFace API:
```bash
curl https://huggingface.co/api/whoami \
  -H "Authorization: Bearer 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"
```

Response:
```json
{"error":"Invalid credentials in Authorization header"}
```

## Possible Causes

1. **Copy/Paste Error** - Token copied incorrectly (missing characters, extra spaces)
2. **Token Revoked** - Token was deleted or revoked after creation
3. **Wrong Token** - Copied a different token than intended
4. **Expired Token** - Token has expired (if it had an expiration date)

## How to Fix

### Step 1: Verify Token in Browser

1. Go to: https://huggingface.co/settings/tokens
2. Find the token you created
3. Verify it's listed and not revoked
4. Click "Copy" button (don't manually select/copy)

### Step 2: Test Token BEFORE Updating Code

Run this command with your token:
```bash
curl https://huggingface.co/api/whoami \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

Should return something like:
```json
{"name":"your-username","type":"user", ...}
```

NOT:
```json
{"error":"Invalid credentials in Authorization header"}
```

### Step 3: Update Config Only If Token Works

Once curl test succeeds, update [config.py](config.py):
```python
HF_API_TOKEN = os.getenv("HF_API_TOKEN", "YOUR_VERIFIED_TOKEN")
```

### Step 4: Run Verification Script

```bash
chmod +x hf_inference_workflow/verify_token.sh
./hf_inference_workflow/verify_token.sh YOUR_TOKEN_HERE
```

## Creating a New Token (If Needed)

If the token is truly invalid, create a new one:

1. Go to: https://huggingface.co/settings/tokens/new
2. Token type: **"Fine-grained"**
3. Name: "PICasso Inference API"
4. Permissions to enable:
   - ✅ **"Make calls to Inference Providers"**
   - ✅ **"Read access to contents of all public gated repos you can access"** (optional, for gated models)
5. Click "Create token"
6. **IMMEDIATELY copy the token** (you won't see it again)
7. Test with curl BEFORE saving to code

## Quick Test Command

Copy and paste your token here to test:
```bash
# Replace YOUR_TOKEN with your actual token
TOKEN="YOUR_TOKEN"
curl -s https://huggingface.co/api/whoami -H "Authorization: Bearer $TOKEN" | jq .
```

Should show your username if valid!

## Still Not Working?

If you've verified the token is valid but inference still fails, possible issues:

1. **Network/Firewall** - Your network might be blocking HuggingFace API
2. **Proxy Issues** - Corporate proxy might be interfering
3. **Model Availability** - The specific models might not be on serverless API
4. **API Changes** - HuggingFace may have changed their API

Try:
```bash
# Test basic connectivity
ping huggingface.co

# Test API reachability
curl -I https://api-inference.huggingface.co
```

## Need Help?

If issues persist, please provide:
1. Output of: `curl https://huggingface.co/api/whoami -H "Authorization: Bearer YOUR_TOKEN"`
2. Your HuggingFace username
3. Whether you have a free or PRO account
4. Any firewall/proxy configuration
