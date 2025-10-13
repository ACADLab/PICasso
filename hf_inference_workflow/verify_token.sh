#!/bin/bash

# Quick token verification script
# Usage: ./verify_token.sh YOUR_TOKEN_HERE

if [ -z "$1" ]; then
    echo "Usage: ./verify_token.sh YOUR_HF_TOKEN"
    echo ""
    echo "Or test the token in config.py:"
    echo "./verify_token.sh"
    exit 1
fi

TOKEN="${1}"

echo "============================================================"
echo "HuggingFace Token Verification"
echo "============================================================"
echo ""
echo "Testing token: ${TOKEN:0:12}...${TOKEN: -8}"
echo ""

# Test 1: Verify token is valid
echo "1️⃣ Checking token validity..."
RESPONSE=$(curl -s --max-time 10 https://huggingface.co/api/whoami \
    -H "Authorization: Bearer ${TOKEN}")

if echo "$RESPONSE" | grep -q "error"; then
    echo "   ❌ Token is INVALID!"
    echo "   Error: $RESPONSE"
    echo ""
    echo "   Please:"
    echo "   1. Go to https://huggingface.co/settings/tokens"
    echo "   2. Check if token exists and is not revoked"
    echo "   3. Create NEW token if needed"
    exit 1
else
    echo "   ✅ Token is VALID!"
    USERNAME=$(echo "$RESPONSE" | grep -oP '"name":"?\K[^",]+' | head -1)
    echo "   Username: $USERNAME"
fi

# Test 2: Try a simple inference
echo ""
echo "2️⃣ Testing inference API..."
INF_RESPONSE=$(curl -s --max-time 15 \
    https://api-inference.huggingface.co/models/microsoft/Phi-3-mini-4k-instruct \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"inputs": "Hello", "parameters": {"max_new_tokens": 5}}')

if echo "$INF_RESPONSE" | grep -q "error"; then
    ERROR_MSG=$(echo "$INF_RESPONSE" | grep -oP '"error":"?\K[^"]+')
    echo "   ❌ Inference failed: $ERROR_MSG"

    if echo "$INF_RESPONSE" | grep -q "404"; then
        echo "   → Model not available on serverless API"
    elif echo "$INF_RESPONSE" | grep -q "503"; then
        echo "   → Model is loading (try again in a moment)"
    fi
else
    echo "   ✅ Inference API works!"
fi

echo ""
echo "============================================================"
echo "Verification complete!"
echo "============================================================"
