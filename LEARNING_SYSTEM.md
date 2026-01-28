# Self-Learning Error Classification System

## Overview

This system implements adaptive error classification that **learns from real-world outcomes**. When AI-generated fixes for LOW-confidence errors are successful (PR merged), the system automatically improves confidence scoring for similar errors in future builds.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Build Error Occurs                       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│            classify_error_confidence()                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Standard Classification (HIGH/LOW/UNKNOWN)           │   │
│  │ + Learning Boost (if historical success)             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
            HIGH-CONFIDENCE    LOW/UNKNOWN-CONFIDENCE
            (Auto-fix)         (Create PR)
                    │                 │
                    ▼                 ▼
            ┌─────────────┐    ┌─────────────┐
            │Build & Push │    │Create PR    │
            └──────┬──────┘    └──────┬──────┘
                   │                  │
                   │                  ▼
                   │          GitHub PR Created
                   │          (with error details)
                   │                  │
                   │                  ▼
                   │        [Developer Reviews & Merges?]
                   │                  │
                   └──────────┬───────┘
                              ▼
                 GitHub Webhook Event Fired
                 (github_webhook_handler.py)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
                 MERGED            CLOSED (not merged)
                (SUCCESS)          (FAILURE)
                    │                   │
                    ▼                   ▼
        Record Success in DB    Record Failure in DB
        Check for Promotion      Update Confidence
                    │                   │
                    ▼                   ▼
        5 Consecutive Successes?
                    │
                    YES
                    │
                    ▼
        AUTO-PROMOTE to HIGH-CONFIDENCE
        (Update pattern scoring)
```

## How It Works

### 1. **Standard Classification**
Errors are classified based on regex patterns:
- **HIGH-CONFIDENCE (0.9)**: Safe patterns (syntax errors, imports, formatting)
- **LOW-CONFIDENCE (0.1)**: Risky patterns (NullPointerException, security issues)
- **UNKNOWN (0.5)**: Unrecognized patterns

### 2. **Learning Boost**
If a pattern has historical success rate, confidence is boosted:
```
Adaptive Confidence = Base Confidence + (Success Rate × Boost Factor)

Example:
- NullPointerException (BASE: LOW = 0.1)
- Success Rate: 80% (8/10 fixes merged successfully)
- Boost: 0.8 × 0.05 = 0.04
- Result: 0.1 + 0.04 = 0.14 (still LOW, but boosted)

After 5 consecutive successes:
- Pattern PROMOTED to HIGH-CONFIDENCE (0.9)
```

### 3. **PR Creation with Metadata**
For LOW-confidence errors, a PR is created with detailed error information:
```markdown
## Auto-Fix: High-Confidence Errors Only

### Remaining Issues (Manual Review Required)

**Issue 1:** `low:business_logic` (Confidence: 10%)
```
NullPointerException detected
```

CC: @developer - Please review
```

### 4. **Webhook Feedback Loop**
When PR is merged or closed, webhook fires:
```python
Event: Pull Request Closed
- Check: is_merged?
  - YES → Record SUCCESS for all patterns in PR
  - NO → Record FAILURE for all patterns in PR

Result: Learning database updated with outcome
```

### 5. **Pattern Promotion**
When a pattern reaches success threshold:
```
Pattern: NullPointerException
- Total attempts: 5
- Successful: 5
- Consecutive successes: 5/5 ✅
→ PROMOTED to HIGH-CONFIDENCE

Next time this error appears → auto-fixed immediately!
```

## Files

### Core Files

#### `learning_classifier.py`
Implements the self-learning mechanism:
- `LearningDatabase`: Persistent storage of learning outcomes
- `AdaptiveClassifier`: Confidence scoring with learning boost
- Pattern tracking and promotion logic

**Key Classes:**
```python
class LearningDatabase:
    record_fix_attempt()      # Log success/failure
    check_promotion()         # Check if pattern qualifies for promotion
    promote_pattern()         # Promote to HIGH-confidence
    get_adaptive_confidence() # Get boosted confidence score

class AdaptiveClassifier:
    classify_with_learning()  # Classification with learning boost
    log_fix_outcome()         # Record PR merge/close outcomes
```

#### `github_webhook_handler.py`
Processes GitHub webhook events to record outcomes:
- `PROutcomeTracker`: Detects merged vs closed PRs
- Extracts error patterns from PR body
- Records success/failure in learning database
- Triggers pattern promotion checks

**Setup:**
1. GitHub Repo Settings → Webhooks
2. Add webhook:
   - Payload URL: `https://your-jenkins-server/github-webhook/`
   - Content type: `application/json`
   - Events: Pull requests
3. Secret: Set to `GITHUB_WEBHOOK_SECRET` (recommended)

#### `manage_learning.py`
Command-line tool to view and manage learning database:
```bash
python manage_learning.py stats          # Overall statistics
python manage_learning.py patterns       # All tracked patterns
python manage_learning.py promoted       # Only promoted patterns
python manage_learning.py pattern <name> # Details for specific pattern
python manage_learning.py reset          # Reset learning database
```

### Modified Files

#### `build_fix_v2.py`
Integration points:
- Import learning classifier
- `classify_error_confidence()` now calls `apply_learning_boost()`
- Confidence scores reflect historical success

### Data Storage

#### `error_learning.json`
Persistent learning database:
```json
{
  "metadata": {
    "version": "1.0",
    "created": "2026-01-23T...",
    "total_fixes_attempted": 42,
    "total_fixes_succeeded": 38,
    "total_patterns_promoted": 3
  },
  "patterns": {
    "business_logic:NullPointerException": {
      "category": "business_logic",
      "pattern": "NullPointerException",
      "total_attempts": 5,
      "successful_fixes": 5,
      "failed_fixes": 0,
      "success_rate": 1.0,
      "promoted_to_high": true,
      "promotion_date": "2026-01-20T...",
      "consecutive_successes": 5,
      "error_examples": [...]
    }
  },
  "pattern_history": [
    {
      "action": "PROMOTED",
      "pattern_key": "business_logic:NullPointerException",
      "timestamp": "2026-01-20T..."
    }
  ]
}
```

## Configuration

### Tuning Parameters

In `learning_classifier.py`:
```python
SUCCESS_THRESHOLD = 5      # Successes needed to promote (default: 5)
FAILURE_THRESHOLD = 2      # Failures to consider demotion (not yet implemented)
CONFIDENCE_BOOST_FACTOR = 0.05  # Boost per success rate point (default: 5%)
```

### Feature Flags

In `build_fix_v2.py`:
```python
ENABLE_AUTO_FIX = os.getenv('ENABLE_AUTO_FIX', 'true')
ENABLE_OPENAI_CALLS = os.getenv('ENABLE_OPENAI_CALLS', 'true')
READ_ONLY_MODE = os.getenv('READ_ONLY_MODE', 'false')
```

Add to `Jenkinsfile`:
```groovy
environment {
    ENABLE_AUTO_FIX = 'true'
    ENABLE_OPENAI_CALLS = 'true'
    // Learning is automatic once error_learning.json exists
}
```

## Workflow Example

### Scenario 1: NEW Error Pattern (HIGH → AUTO-FIX)

1. **Build fails** with: `class expected` error
2. **Classification**: Matches `HIGH_CONFIDENCE_PATTERNS['syntax_error']` → confidence: 0.9
3. **Action**: AUTO-FIX applied, code compiled, pushed directly
4. **Result**: ✅ Merged to main branch

### Scenario 2: RISKY Error Pattern (LOW → PR → PROMOTE)

1. **Build fails** with: `NullPointerException` error
2. **Classification**: Matches `LOW_CONFIDENCE_PATTERNS['business_logic']` → confidence: 0.1
3. **Action**: PR created with error details, developer reviews
4. **PR Merged**: ✅ Webhook fires
5. **Learning DB**: Records SUCCESS for this pattern
6. **Progress**: consecutive_successes = 1/5

**Repeat steps 1-5 four more times...**

7. **After 5th success**: 
   - Check promotion: 5 consecutive successes ✅
   - **PROMOTION**: Pattern moved to HIGH-CONFIDENCE
   - Print: `📈 PATTERN PROMOTED: business_logic - Success rate: 100%`

8. **6th occurrence** of same error:
   - Classification: Still `LOW` by pattern, but learning boost applied
   - Confidence: 0.1 + (1.0 × 0.05) = 0.15 ✅ Slightly boosted
   - **Note**: After manual promotion, would jump to 0.9

### Scenario 3: UNKNOWN Error Pattern (LEARNING IN ACTION)

1. **Build fails** with unrecognized error
2. **Classification**: No pattern match → confidence: 0.5 (UNKNOWN)
3. **Action**: PR created for manual review
4. **Outcomes tracked**:
   - Success: Builds confidence for future similar errors
   - Failure: Maintains caution, doesn't promote

## Usage Guide

### For CI/CD Engineers

#### View Learning Statistics
```bash
# Jenkins Execute Shell
python3 manage_learning.py stats
```

#### Monitor Pattern Promotion
```bash
# Add to Jenkins dashboard
python3 manage_learning.py promoted
```

#### Reset Learning (Fresh Start)
```bash
python3 manage_learning.py reset
```

### For Developers

#### Understanding PR with Learning
PR description now includes:
- Error category and confidence level
- Success rate if pattern has history
- "This error was successfully fixed X times before"

#### Interpreting Confidence Scores
- **✅ 0.9+ (HIGH)**: Auto-fixed, safe to merge
- **⏳ 0.1-0.4 (LOW)**: Review PR, needs domain knowledge
- **❓ 0.5 (UNKNOWN)**: First time seeing error, manual review needed

### For DevOps

#### Set Up Webhook
```bash
# 1. In GitHub Repo Settings
# Settings → Webhooks → Add webhook
# Payload URL: https://jenkins.example.com/github-webhook/
# Content type: application/json
# Events: Pull requests

# 2. In Jenkins
# Configure webhook secret in credentials
# Map to: github_webhook_handler.py endpoint
```

#### Monitor Learning Database Growth
```bash
# Track learning metrics
watch -n 60 'python3 manage_learning.py stats'

# Archive weekly
cp error_learning.json backup/error_learning.json.$(date +%Y%m%d)
```

## Metrics & Monitoring

### Key Metrics

- **Overall Success Rate**: % of AI fixes that were merged
- **Patterns Promoted**: How many patterns reached HIGH-confidence
- **Learning Progress**: Consecutive successes for each pattern
- **Confidence Boost Average**: Average confidence improvement from learning

### Example Dashboard Output

```
📊 LEARNING CLASSIFIER STATISTICS
┌──────────────────────────────────┬─────────┐
│ Total Patterns Tracked           │    12   │
│ Patterns Promoted to HIGH        │     3   │
│ Total Fixes Attempted            │    47   │
│ Total Fixes Successful           │    42   │
│ Overall Success Rate             │  89.4%  │
└──────────────────────────────────┴─────────┘

📚 TOP PERFORMING PATTERNS
  ✅ business_logic:NullPointerException
     Success: 5/5 (100%)
     Consecutive Successes: 5/5
     
  ⏳ security:SQL_injection
     Success: 3/5 (60%)
     Consecutive Successes: 3/5
     
  ⏳ formatting:line_too_long
     Success: 2/4 (50%)
     Consecutive Successes: 2/5
```

## Future Enhancements

1. **Demotion Logic**: Demote patterns back to LOW if failure rate exceeds threshold
2. **Pattern Refinement**: Automatically update regex patterns based on error examples
3. **ML-based Confidence**: Use neural networks to predict fix success likelihood
4. **Seasonal Learning**: Account for seasonal patterns in error types
5. **Team-specific Learning**: Different confidence scores per team/project
6. **A/B Testing**: Compare auto-fix vs manual-review outcomes

## Troubleshooting

### Learning not working?

1. Check if `error_learning.json` exists
2. Verify webhook is configured in GitHub
3. Check Jenkins logs: `python3 manage_learning.py stats`
4. Reset and restart: `python3 manage_learning.py reset`

### Pattern not promoting?

1. Check consecutive_successes: `python3 manage_learning.py pattern <name>`
2. Ensure PRs are being merged (webhook triggers on merge)
3. Verify GitHub webhook secret matches

### Confidence not boosting?

1. Confirm learning_classifier imported successfully
2. Check error_learning.json not corrupted
3. Verify AdaptiveClassifier is enabled in build_fix_v2.py

## References

- [GitHub Webhooks Documentation](https://docs.github.com/en/developers/webhooks-and-events/webhooks)
- [PR Review Flow](./pr_review.py)
- [Build Fix System](./build_fix_v2.py)
