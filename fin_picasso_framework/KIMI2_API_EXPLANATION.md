# Kimi2 API Routing Explanation

## Why You See "novita" and "openai" in the URL

When using `moonshotai/Kimi-K2-Thinking:novita` with HuggingFace's `InferenceClient`, here's what happens:

### How HuggingFace Routes Models

1. **Model Name Format**: `moonshotai/Kimi-K2-Thinking:novita`
   - `moonshotai/Kimi-K2-Thinking` = Model name
   - `:novita` = Provider tag (tells HuggingFace which provider to use)

2. **Routing Process**:
   ```
   Your Code → HuggingFace InferenceClient → HuggingFace Router → Novita Provider → OpenAI-compatible API
   ```

3. **URL Structure**:
   - Base: `https://router.huggingface.co`
   - Provider: `/novita` (from the `:novita` tag)
   - API Format: `/v3/openai/chat/completions` (OpenAI-compatible endpoint)
   - **Full URL**: `https://router.huggingface.co/novita/v3/openai/chat/completions`

### Why This Happens

- **Novita** is a third-party provider that hosts the Kimi2 model
- Novita uses an **OpenAI-compatible API** format
- HuggingFace acts as a **router/proxy** that:
  - Accepts requests via their InferenceClient
  - Routes to the appropriate provider (novita)
  - Uses the provider's API format (OpenAI-compatible)

### This is Expected Behavior ✅

The URL structure is correct and expected. The timeouts (504 errors) are likely due to:
1. **Provider-side issues**: Novita's servers may be slow or overloaded
2. **Network latency**: Routing through HuggingFace → Novita adds latency
3. **Model loading**: The model may need to be loaded on Novita's servers

### Current Error Handling

The framework already handles this with:
- **Retry logic**: 5 retries with exponential backoff
- **Rate limit handling**: Special handling for 429 errors
- **Timeout handling**: Special handling for 504/503 errors
- **Longer delays for rate limits**: 5s → 15s → 45s → 135s

### Alternative Approaches

If timeouts persist, you could:

1. **Use Novita API directly** (bypass HuggingFace router):
   ```python
   import openai
   client = openai.OpenAI(
       api_key=os.environ["NOVITA_API_KEY"],
       base_url="https://api.novita.ai/v3"
   )
   ```

2. **Use a different provider** if available

3. **Increase timeout values** in the retry logic

### Current Status

The framework is correctly configured to use HuggingFace's InferenceClient with the provider tag. The 504 errors are external (provider/network issues), not a configuration problem.


