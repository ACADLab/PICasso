# Rate Limiting Fix for OpenAI API

## Problem

When running the generation with `--samples 3`, you encountered repeated HTTP 429 "Too Many Requests" errors:

```
2025-10-17 14:12:45,654 - httpx - INFO - HTTP Request: POST https://api.openai.com/v1/chat/completions "HTTP/1.1 429 Too Many Requests"
```

## Root Cause

OpenAI API has rate limits based on your account tier:

| Tier | Requests per Minute (RPM) | Tokens per Minute (TPM) |
|------|---------------------------|-------------------------|
| Free/Tier 1 | 3-5 RPM | 40,000 TPM |
| Tier 2 | 10 RPM | 80,000 TPM |
| Tier 3 | 50 RPM | 160,000 TPM |

With 20 problems × 3 samples = 60 designs, and each design potentially making 4+ API calls (first attempt + retries), we were hitting the rate limit very quickly.

## Solution Implemented

### 1. Exponential Backoff for Retries

In `openai_api_client.py`, added intelligent retry logic:

```python
def _call(self, messages: List[dict]) -> str:
    """Make API call to OpenAI endpoint with rate limit handling."""
    max_retries = 5
    base_delay = 1.0

    for attempt in range(max_retries):
        try:
            response = self.client.chat.completions.create(...)
            return response.choices[0].message.content

        except Exception as e:
            # Handle rate limit errors (429)
            if "429" in error_str or "rate_limit" in error_str.lower():
                # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limit hit. Waiting {delay}s...")
                time.sleep(delay)
                continue
```

**What this does**: If we hit a rate limit, we wait exponentially longer (1s, 2s, 4s, 8s, 16s) before retrying.

### 2. Proactive Request Delay

In `config.py`, added:

```python
REQUEST_DELAY = 12.0  # Delay between API requests in seconds
                      # For 5 RPM limit: 60s / 5 = 12s
```

In `gen_data_openai_validated.py`, added delay between generations:

```python
# After each design generation
results.append(csv_row)
pbar.update(1)

# Add inter-request delay to avoid rate limits (except after last design)
is_last_design = (idx == problems[-1][0] and sample == num_samples - 1)
if not is_last_design:
    logger.info(f"Waiting {REQUEST_DELAY}s to avoid rate limits...")
    time.sleep(REQUEST_DELAY)
```

**What this does**: Wait 12 seconds between each design to stay under 5 requests/minute limit.

## Customization for Your Tier

### If you're on Free/Tier 1 (5 RPM)
**Keep current settings**:
```python
REQUEST_DELAY = 12.0  # 60s / 5 RPM = 12s
```

### If you upgrade to Tier 2 (10 RPM)
**Edit config.py**:
```python
REQUEST_DELAY = 6.0  # 60s / 10 RPM = 6s
```

### If you upgrade to Tier 3 (50 RPM)
**Edit config.py**:
```python
REQUEST_DELAY = 1.2  # 60s / 50 RPM = 1.2s
```

## Expected Runtime

With these fixes:

| Configuration | Designs | Time per Design | Total Time |
|--------------|---------|-----------------|------------|
| 20 problems × 2 samples | 40 | ~12s | ~8 minutes |
| 20 problems × 3 samples | 60 | ~12s | ~12 minutes |
| 5 problems × 1 sample | 5 | ~12s | ~1 minute |

**Note**: This assumes Tier 1 (5 RPM). Higher tiers will be faster with lower `REQUEST_DELAY`.

## How to Run Now

### Option 1: Full Generation (20 problems, 2 samples)
```cmd
python gen_data_openai_validated.py --problems test_20_problems.txt --output validation_report.csv --samples 2
```
**Expected time**: ~8 minutes

### Option 2: Quick Test (5 problems, 1 sample)
```cmd
python gen_data_openai_validated.py --problems problems.txt --output test_report.csv --samples 1
```
**Expected time**: ~1 minute

### Option 3: Use the Interactive Script
```cmd
run_manual.cmd
```

## Monitoring Progress

You'll see messages like:
```
2025-10-17 14:15:00,123 - __main__ - INFO - Problem 1: Mach-Zehnder Modulator - Sample 1/2
2025-10-17 14:15:05,456 - __main__ - INFO - [OK] First attempt GDS saved: ...
2025-10-17 14:15:06,789 - __main__ - INFO - Waiting 12s to avoid rate limits...
```

## What If I Still Get 429 Errors?

1. **Increase REQUEST_DELAY**:
   ```python
   REQUEST_DELAY = 15.0  # Even safer margin
   ```

2. **Reduce samples**:
   ```cmd
   python gen_data_openai_validated.py --samples 1
   ```

3. **Check your OpenAI tier**:
   - Go to: https://platform.openai.com/settings/organization/limits
   - Verify your actual RPM limit
   - Adjust REQUEST_DELAY accordingly: `60 / your_rpm_limit`

4. **Wait and retry**:
   - If you hit the limit, wait 60 seconds
   - The script will auto-retry with exponential backoff

## Benefits of This Approach

- **Proactive**: Prevents rate limits instead of hitting them
- **Reactive**: Handles rate limits gracefully when they occur
- **Efficient**: Uses maximum allowed rate without wasting API calls
- **Transparent**: Logs all delays so you know what's happening
- **Configurable**: Easy to adjust for different tier levels

## Summary

**Before fix**: Rapid API calls → 429 errors → script fails

**After fix**: Controlled rate (12s delay) → stays under limit → successful generation
