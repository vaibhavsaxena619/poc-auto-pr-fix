# Self-Learning Error Classifier - Quick Start Guide

## 5-Minute Setup

### 1. **Verify Files Are in Place**
```bash
ls -la
# Should have:
# - learning_classifier.py       ✅ Learning engine
# - github_webhook_handler.py    ✅ Webhook processor  
# - manage_learning.py           ✅ Management CLI
# - build_fix_v2.py             ✅ Updated with learning integration
# - LEARNING_SYSTEM.md          ✅ Full documentation
```

### 2. **Test Learning System Locally**
```bash
# View learning stats (will create empty DB if needed)
python3 manage_learning.py stats

# Expected output:
# 📊 LEARNING CLASSIFIER STATISTICS
# ┌──────────────────────────────────┬─────────┐
# │ Total Patterns Tracked           │    0    │
# │ Patterns Promoted to HIGH        │    0    │
# │ Total Fixes Attempted            │    0    │
# │ Total Fixes Successful           │    0    │
# └──────────────────────────────────┴─────────┘
```

### 3. **Run a Test Build**
```bash
# Trigger Release branch build in Jenkins
# (Or run build_fix_v2.py locally with test Java file)

python3 build_fix_v2.py test-file.java

# Look for learning output:
# "📈 Learning boost: +0.05 confidence (historical success)"
```

### 4. **Set Up GitHub Webhook** (One-time)
```
1. Go to your repo: Settings → Webhooks
2. Click "Add webhook"
3. Payload URL: https://your-jenkins.com/github-webhook/
4. Content type: application/json
5. Events: Pull requests
6. Click "Add webhook"
```

### 5. **Monitor Learning**
```bash
# After first PR is merged, check:
python3 manage_learning.py patterns

# Should show tracked patterns with success rates
```

---

## How It Works (Simple Version)

```
┌─────────────────┐
│ Error in Build  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│ Is it a SAFE pattern? (HIGH)    │
└────────┬────────────────────────┘
         │
    YES  │ NO
         │  │
         │  ▼
         │ ┌──────────────────────────┐
         │ │ Create PR for review     │
         │ │ (developer decides)      │
         │ └────────────┬─────────────┘
         │              │
         └──────────┬───┘
                    ▼
         ┌──────────────────────┐
         │ PR Merged? → SUCCESS │
         │ PR Closed? → FAILURE │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ Learn from outcome   │
         │ Update confidence    │
         └──────────┬───────────┘
                    │
         ┌──────────▼───────────┐
         │ 5 successes?         │
         │ YES → PROMOTE! 🚀    │
         │ Now auto-fix similar │
         │ errors next time     │
         └──────────────────────┘
```

---

## Commands Reference

### View Learning Status
```bash
# Overall statistics
python3 manage_learning.py stats

# All tracked patterns
python3 manage_learning.py patterns

# Patterns that have been promoted to HIGH
python3 manage_learning.py promoted

# Details on specific pattern
python3 manage_learning.py pattern business_logic
```

### Manage Learning
```bash
# Reset learning database (fresh start)
python3 manage_learning.py reset

# Manually promote a pattern (advanced)
python3 manage_learning.py promote "NullPointerException" "business_logic"
```

---

## Expected Timeline

### Week 1: Learning Begins
```
Day 1: System deployed
       - First low-confidence errors create PRs
       - Learning DB created: error_learning.json
       
Day 2-5: Developers merge PRs
       - Webhook records successes
       - Learning DB updated with outcomes
       - Confidence scores starting to boost
```

### Week 2-3: Patterns Emerge
```
Day 10-15: First pattern reaches promotion
       - Error type X has 5 successful fixes
       - 📈 PATTERN PROMOTED: low:business_logic
       - Next similar error will be auto-fixed!
```

### Month 1: Learning Mature
```
- Multiple patterns promoted to HIGH
- AUTO-FIX rate increasing
- Manual review PR rate decreasing
- System becoming more efficient
```

---

## Real-World Example

### Scenario: NullPointerException Pattern

**Day 1 - First NullPointerException**
```
Build Error: java.lang.NullPointerException at line 42
Classification: LOW-confidence (0.1)
Action: ⏳ Create PR for review
Result: Merged by developer ✅
```

**Day 2 - Similar NullPointerException**
```
Build Error: java.lang.NullPointerException at line 73
Classification: LOW-confidence (0.1)
Learning Boost: +0.04 (success rate 50%)
Adjusted Confidence: 0.14
Action: ⏳ Create PR for review  
Result: Merged by developer ✅
```

**Day 3-5 - More NullPointerExceptions**
```
Similar errors occur 3 more times
All merged successfully
Consecutive Successes: 5/5
```

**Day 6 - PROMOTION!**
```
Learning Check:
- NullPointerException pattern
- 5 consecutive successes ✅
- Success rate: 100%

ACTION: 📈 PROMOTE to HIGH-CONFIDENCE!

Update: build_fix_v2.py recognizes this as AUTO-FIXABLE

Output:
  ✅ PATTERN PROMOTED: business_logic
  New confidence: 0.9 (was 0.1)
  Success rate: 100%
```

**Day 7+ - NullPointerException Auto-Fixed**
```
Build Error: java.lang.NullPointerException
Classification: HIGH-confidence (0.9)
Action: ✅ AUTO-FIX (no PR needed!)
Result: Fixed, compiled, pushed directly
```

---

## Troubleshooting

### Q: Learning DB not updating?
**A:** Check that:
1. Webhook is configured in GitHub repo settings
2. Jenkins can receive GitHub events
3. `error_learning.json` file has write permissions
4. Check logs: `python3 manage_learning.py stats`

### Q: Pattern not promoting despite successes?
**A:** Verify:
1. PR titles include `[Auto-Fix]` (required for detection)
2. Error patterns are captured in PR body
3. Run `python3 manage_learning.py pattern <name>` to check progress

### Q: Want to reset everything?
**A:** Fresh start:
```bash
rm error_learning.json
python3 manage_learning.py reset
# System will rebuild learning from scratch
```

---

## Key Metrics to Monitor

| Metric | What It Means | Target |
|--------|---------------|--------|
| Total Patterns Tracked | How many error types seen | 10+ = healthy |
| Patterns Promoted | Auto-fix enabled for | 5+ = good learning |
| Overall Success Rate | % of AI fixes merged | 80%+ = effective |
| Consecutive Successes | Progress on each pattern | 5 = promotion ready |

---

## Next Steps

1. ✅ Verify files are in place
2. ✅ Run `python3 manage_learning.py stats`
3. ✅ Set up GitHub webhook
4. ✅ Trigger a build with errors
5. ✅ Merge the PR created by the system
6. ✅ Monitor learning progress: `python3 manage_learning.py stats`
7. ✅ Watch for pattern promotions in build logs

---

## Documentation Reference

- **Full Details**: [LEARNING_SYSTEM.md](LEARNING_SYSTEM.md)
- **Build System**: [build_fix_v2.py](build_fix_v2.py)
- **Error Patterns**: [build_fix_v2.py#L47-L75](build_fix_v2.py)
- **Learning Engine**: [learning_classifier.py](learning_classifier.py)
- **Webhook Handler**: [github_webhook_handler.py](github_webhook_handler.py)

---

**Questions?** Refer to LEARNING_SYSTEM.md for comprehensive documentation.
