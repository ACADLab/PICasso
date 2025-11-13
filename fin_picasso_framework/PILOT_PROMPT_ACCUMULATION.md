# Pilot Prompt Accumulation System

## ✅ YES - The Pilot Prompt Grows and Accumulates Knowledge!

The pilot prompt system is designed to **learn from every error** and **accumulate knowledge across all runs**. It does NOT clear rules between runs.

## How It Works

### 1. **Permanent Storage**
- Rules are saved to: `fin_picasso_framework/pilot_rules.json`
- This file persists across all runs
- Rules are **never automatically cleared**

### 2. **Loading on Startup**
```python
# On framework startup:
pilot_prompt_updater = PilotPromptUpdater()
# → Automatically loads existing rules from pilot_rules.json
# → If file doesn't exist, starts with empty rules
# → If file exists, loads ALL previously learned rules
```

### 3. **Learning After Each Failure**
```python
# After pass@1, pass@2, pass@3 failures:
# 1. Error is detected
# 2. Error is analyzed
# 3. New rule is generated (e.g., "CRITICAL: Always close brackets - r.area() not r.area(")
# 4. Rule is APPENDED to existing rules (not replaced)
# 5. Rules are saved to file immediately
```

### 4. **Accumulation Process**
- **Run 1**: Learns 3 rules → Saves to file
- **Run 2**: Loads 3 rules → Learns 2 more → Saves 5 rules total
- **Run 3**: Loads 5 rules → Learns 1 more → Saves 6 rules total
- **Run N**: Loads all previous rules → Learns new ones → Saves accumulated total

### 5. **Duplicate Prevention**
- Before adding a new rule, the system checks if a similar rule already exists
- Prevents duplicate rules (e.g., won't add "close brackets" twice)
- Only adds genuinely new patterns

## Example Flow

### First Run (No Prior Rules)
```
1. Framework starts → Loads pilot_rules.json → Empty (0 rules)
2. LLM generates code with syntax error: "r.area(" (missing closing paren)
3. Pilot detects error → Analyzes → Generates rule:
   "CRITICAL: Always close all parentheses. Check function calls like r.area() not r.area("
4. Rule is saved to pilot_rules.json (now has 1 rule)
```

### Second Run (With Prior Rules)
```
1. Framework starts → Loads pilot_rules.json → Has 1 rule from previous run
2. Pilot prompt includes: "⚠️ CRITICAL: Always close all parentheses..."
3. LLM generates code with different error: "missing }" (missing closing brace)
4. Pilot detects error → Analyzes → Generates new rule:
   "CRITICAL: Always close all brackets and braces. Check for missing '}'"
5. Rule is APPENDED → pilot_rules.json now has 2 rules
```

### Third Run (With Accumulated Rules)
```
1. Framework starts → Loads pilot_rules.json → Has 2 rules from previous runs
2. Pilot prompt includes BOTH rules:
   - "⚠️ CRITICAL: Always close all parentheses..."
   - "⚠️ CRITICAL: Always close all brackets and braces..."
3. LLM is now warned about BOTH common mistakes
4. If new error occurs → New rule is added → Total: 3 rules
```

## Key Features

### ✅ **Persistence**
- Rules survive framework restarts
- Rules survive system reboots
- Rules are stored in JSON file (human-readable)

### ✅ **Accumulation**
- Rules are **appended**, never replaced
- Each run adds to the knowledge base
- Framework gets smarter over time

### ✅ **Immediate Application**
- Rules learned in pass@1 are available for pass@2
- Rules learned in Run 1 are available for Run 2
- No delay - instant learning

### ✅ **Format Migration**
- Automatically migrates old-format rules to new format
- Handles both dict-based (old) and string-based (new) rules
- Backward compatible

## Verification

To verify rules are accumulating:

```bash
# Check current rules
cat fin_picasso_framework/pilot_rules.json

# Or in Python
from fin_picasso_framework.pilot.pilot_prompt_updater import PilotPromptUpdater
updater = PilotPromptUpdater()
print(f"Current rules: {len(updater.learned_rules.get('custom_patterns', []))}")
for i, rule in enumerate(updater.learned_rules.get('custom_patterns', []), 1):
    print(f"{i}. {rule[:100]}...")
```

## Manual Reset (If Needed)

If you want to clear rules (not recommended, but possible):

```bash
# Backup first
cp fin_picasso_framework/pilot_rules.json fin_picasso_framework/pilot_rules.json.backup

# Clear rules
echo '{"custom_patterns": [], "error_patterns": {}, "prevention_rules": [], "template_suggestions": []}' > fin_picasso_framework/pilot_rules.json
```

## Summary

**The pilot prompt is a learning system that:**
- ✅ Loads existing rules on startup
- ✅ Learns from every error
- ✅ Saves rules immediately after learning
- ✅ Accumulates knowledge across all runs
- ✅ Never clears rules automatically
- ✅ Gets smarter with each run

**The framework improves over time because it remembers what it learned!**


