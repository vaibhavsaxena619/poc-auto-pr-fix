# Build Fix v2: Advanced Multi-Error Handling System

## Overview

A revolutionary rewrite of the build fix system addressing the two critical requirements:

1. **Handle Mixed Error Confidence Levels**: Separate high-confidence (auto-fixable) from low-confidence (manual review) errors
2. **Intelligent Commit History Walking**: Find the last good commit instead of failing when previous commits have errors

---

## Problem Statement

### Issue 1: Multiple Error Types in Single Build
**Old Behavior:**
```
5 errors detected → Try to fix ALL at once → GPT deletes code or fails → Build fails
```

**New Behavior:**
```
5 errors detected
├─ 3 HIGH-confidence (List, ArrayList, syntax) → FIX THESE
├─ 2 LOW-confidence (applyDiscount, business logic) → CREATE REVIEW PR
└─ Result: Branch created with fixes + PR tagged to original author
```

### Issue 2: Previous Commits Also Have Errors
**Old Behavior:**
```
Current commit has errors
→ Check previous commits
→ Previous commits ALSO have errors
→ FAILED - give up
```

**New Behavior:**
```
Current commit has errors
→ Search up to 10 commits back
→ Found good commit 5 commits ago (compiles cleanly)
→ Checkout that commit
→ Build succeeds from stable point
→ No wasted time creating review branches for old issues
```

---

## System Architecture

### 1. Error Classification (Multi-Error)

```python
class ErrorInfo:
    error_msg: str           # Full error message
    category: str            # "safe:missing_import" or "risky:business_logic"
    confidence: float        # 0.1 (risky) to 0.9 (safe)
    is_fixable: bool         # True if confidence >= 0.8
```

**Classification Process:**
```
Raw Error Message
    ↓
Check RISKY patterns (business_logic, security, migration)
    ↓ Found? → confidence = 0.1 (LOW)
    ↓ Not found?
    ↓
Check SAFE patterns (missing_import, formatting, syntax)
    ↓ Found? → confidence = 0.9 (HIGH)
    ↓ Not found?
    ↓
Default to 0.5 (UNKNOWN)
```

### 2. Commit History Walking

```python
find_last_good_commit(source_file, max_search=10):
    commits = git log last 10 commits
    for each commit (skip current):
        stash changes
        checkout commit
        try compile
        if COMPILES:
            return (commit_sha, True)  # Found!
        if FAILS:
            continue to next
    return (None, False)  # No good commit found
```

**Search Strategy:**
- Max 10 commits back (configurable)
- Stops at first GOOD commit (reduces iteration)
- Restores git state automatically (no pollution)
- Detailed logging of each test

### 3. Fix Decision Tree

```
Has compilation errors?
    ├─ NO → ✓ Success
    │
    └─ YES
        ├─ Parse ALL errors
        ├─ Classify by confidence
        │
        ├─ Has LOW-confidence errors?
        │   │
        │   ├─ YES
        │   │   ├─ Has HIGH-confidence errors?
        │   │   │   ├─ YES → Fix high-conf, create review branch
        │   │   │   └─ NO → Search commit history
        │   │   │           ├─ Found good commit → Build from there
        │   │   │           └─ Not found → Create review branch
        │   │   │
        │   │   └─ Tag original author
        │   │
        │   └─ NO (all HIGH-confidence)
        │       └─ Fix all errors normally
```

---

## Feature 1: Mixed Error Handling

### Scenario: 5 Errors (3 High, 2 Low)

```
Compilation error #1: cannot find symbol class List
  Category: safe:missing_import
  Confidence: 90% ← HIGH-CONFIDENCE

Compilation error #2: cannot find symbol class ArrayList
  Category: safe:missing_import
  Confidence: 90% ← HIGH-CONFIDENCE

Compilation error #3: cannot find symbol method applyDiscount
  Category: risky:business_logic
  Confidence: 10% ← LOW-CONFIDENCE

Compilation error #4: unknown error
  Category: unknown
  Confidence: 50% ← LOW-CONFIDENCE
```

### Handling Process

**Step 1: Fix High-Confidence Errors**
```java
// Apply GPT fix for missing imports only
import java.util.List;
import java.util.ArrayList;

// Keep problematic code as-is
total += applyDiscount(price);  // Still broken, but marked for review
```

**Step 2: Create Fix Branch**
- Branch name: `fix/high-confidence-errors_20260122_105530`
- Commit: "Fix: High-confidence compilation errors (manual review needed for 2 low-confidence issues)"

**Step 3: Create Review PR**
- Title: `[Auto-Fix] 2 low-confidence issues need review`
- Body:
  ```markdown
  This PR fixes 3 HIGH-CONFIDENCE compilation errors.

  ### Remaining Issues (Manual Review Required)
  Low-confidence errors that require domain knowledge or manual review:

  **Issue 1:** `risky:business_logic` (Confidence: 10%)
  ```
  cannot find symbol: method applyDiscount(Double)
  ```

  **Issue 2:** `unknown` (Confidence: 50%)
  ...

  CC: @vaibhav_saxena - Please review the remaining low-confidence issues
  ```

**Result:**
- ✅ High-confidence errors FIXED
- ⚠️ Low-confidence errors LEFT IN PLACE
- 📋 Original author NOTIFIED
- 🔗 PR CREATED for code review

---

## Feature 2: Intelligent Commit History Walking

### Scenario: Current + Previous 3 Commits All Have Errors

```
Commit 1 (Current): Has 5 errors (from 2 hours ago)
  ├─ Missing imports
  ├─ Undefined method
  └─ 3 other errors

Commit 2 (1 hour ago): Has 7 errors (from same feature)
  └─ Multiple unrelated issues

Commit 3 (30 min ago): Has 5 errors (same issues)
  └─ Didn't fully fix

Commit 4 (20 min ago): COMPILES CLEANLY ✓
  └─ Previous maintainer's stable version

Commit 5 (10 min ago): Has 1 error (new regression)
```

### Handling Process

**Step 1: Search Commit History**
```
Testing commit 1/10: abc1234 (Fix attempt 1)
  [ERROR] Has 7 compilation errors (error is older)

Testing commit 2/10: def5678 (Initial feature branch)
  [ERROR] Has 5 compilation errors (error is older)

Testing commit 3/10: ghi9012 (Stable base)
  [SUCCESS] Code compiles! ✓
```

**Step 2: Found Good Commit**
```
git checkout ghi9012
[Verified] Good commit builds successfully
→ Build continues from stable point
→ No need to create review branches
→ Error is identified as OLD (not recent)
```

**Result:**
- ✅ Found last good commit automatically
- ⚠️ Current commit marked as unstable
- 🔍 Error source identified (introduced between ghi9012 and current)
- ✅ Build succeeds from known-good state
- 📊 Developers see which commits are problematic

---

## Implementation Details

### Error Parsing

```python
def parse_all_errors(error_message: str) -> List[str]:
    """Extract all individual errors from javac output."""
    errors = []
    # javac outputs multiple "filename:linenum: error:" entries
    # Split on these markers
    for line in error_message.split('\n'):
        if re.match(r'^.*\.java:\d+:', line):  # Error line marker
            errors.append(collect_error_block(line))
    return errors
```

**Example Input (javac stderr):**
```
src/App.java:10: error: cannot find symbol
  symbol:   class List
src/App.java:18: error: cannot find symbol
  symbol:   class ArrayList
src/App.java:25: error: cannot find symbol
  symbol:   method applyDiscount(Double)
```

**Output:**
```python
[
    "src/App.java:10: error: cannot find symbol\n  symbol:   class List",
    "src/App.java:18: error: cannot find symbol\n  symbol:   class ArrayList",
    "src/App.java:25: error: cannot find symbol\n  symbol:   method applyDiscount(Double)"
]
```

### Fix Branch Creation

```python
def create_fix_branch_for_mixed_errors(...):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_branch = f"fix/high-confidence-errors_{timestamp}"
    
    # Create and checkout branch
    git checkout -b fix/high-confidence-errors_20260122_105530
    
    # Apply ONLY high-confidence fixes (GPT output)
    with open(source_file, 'w') as f:
        f.write(fixed_code_high_conf_only)
    
    # Commit with detailed message
    git commit -m "Fix: High-confidence compilation errors (manual review needed for 2 low-confidence issues)"
    
    # Push to remote
    git push origin fix/high-confidence-errors_20260122_105530
    
    # Create PR via GitHub API with:
    # - List of all low-confidence issues
    # - Confidence scores
    # - Original error messages
    # - Tag to original author
```

### Commit History Search

```python
def find_last_good_commit(source_file, max_search=10):
    current_sha = git rev-parse HEAD
    commits = git log --oneline -10
    
    for commit in commits[1:]:  # Skip current
        git stash
        git checkout {commit_sha}
        
        result = javac {source_file}
        if result.returncode == 0:
            print(f"✓ Found good commit: {commit_sha}")
            git checkout {current_sha}
            git stash pop
            return (commit_sha, True)
        else:
            print(f"✗ {commit_sha} also broken")
            continue
    
    return (None, False)
```

---

## Configuration

### Environment Variables (unchanged)
```bash
AZURE_OPENAI_API_KEY        # Azure OpenAI API key
AZURE_OPENAI_ENDPOINT       # Azure OpenAI endpoint
AZURE_OPENAI_API_VERSION    # API version (default: 2024-12-01-preview)
AZURE_OPENAI_DEPLOYMENT_NAME # Model (default: gpt-5)
GITHUB_PAT                   # GitHub token for PR creation
ENABLE_AUTO_FIX              # Feature flag (default: true)
ENABLE_OPENAI_CALLS          # API calls (default: true)
READ_ONLY_MODE               # Don't apply fixes (default: false)
```

### New Constants
```python
MAX_FIX_ATTEMPTS = 2                    # Max retry attempts
MAX_COMMIT_HISTORY_SEARCH = 10          # Commits to search back
SAFE_ERROR_PATTERNS = {...}             # High-confidence patterns
RISKY_ERROR_PATTERNS = {...}            # Low-confidence patterns
```

---

## Usage

### Option 1: Drop-in Replacement
```groovy
// In Jenkinsfile, replace:
sh 'python3 build_fix.py src/App.java'

// With:
sh 'python3 build_fix_v2.py src/App.java'
```

### Option 2: Side-by-Side Testing
```bash
# Compare outputs
python3 build_fix.py src/App.java
python3 build_fix_v2.py src/App.java
```

---

## Output Examples

### Example 1: Mixed Errors (3 High, 2 Low)

```
[2026-01-22T10:55:28.602319] Build fix initiated for src/App.java
✗ Compilation errors detected
  Found 5 error(s)
  ✓ HIGH-CONFIDENCE: safe:missing_import (90%)
  ✓ HIGH-CONFIDENCE: safe:missing_import (90%)
  ✓ HIGH-CONFIDENCE: safe:formatting (90%)
  ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
  ⚠️ LOW-CONFIDENCE: unknown (50%)

  3 low-confidence error(s) detected
  ✓ But 3 high-confidence error(s) can be fixed
  Fixing high-confidence errors only...
  Applying fix...
  
  ✓ Branch created: fix/high-confidence-errors_20260122_105530
  ✓ PR #28 created with low-confidence issues marked
```

### Example 2: Searching Commit History

```
[2026-01-22T10:55:28.602319] Build fix initiated for src/App.java
✗ Compilation errors detected
  Found 5 error(s)
  ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
  ⚠️ LOW-CONFIDENCE: risky:migration (10%)
  ⚠️ LOW-CONFIDENCE: unknown (50%)

  3 low-confidence error(s) detected
  ℹ️ Only low-confidence errors found - searching commit history...

  🔍 Searching commit history for last good commit (searching 10 commits back)...
    Current: abc1234 (Attempted fix #3)
    Testing commit 1/10: def5678 (Fix attempt 2)
      Has 5 compilation errors (error is older)
    Testing commit 2/10: ghi9012 (Initial feature)
      Has 7 compilation errors (error is older)
    Testing commit 3/10: jkl3456 (Stable base)
      ✅ Found good commit: jkl3456 - Code compiles!
  
  ✅ Found good commit: jkl3456
  Building from stable commit instead...
✓ Verified: Good commit builds successfully
```

---

## Testing Checklist

- [ ] Run test with 3 high + 2 low confidence errors
  - [ ] Verify high-confidence errors are fixed
  - [ ] Verify low-confidence errors left in place
  - [ ] Verify PR created with issues listed
  - [ ] Verify original author tagged
  
- [ ] Run test with only low-confidence errors in multiple commits
  - [ ] Verify commit history is searched
  - [ ] Verify good commit is found
  - [ ] Verify build continues from good commit
  
- [ ] Run test with only high-confidence errors
  - [ ] Verify normal auto-fix behavior
  - [ ] Verify code compiles
  - [ ] Verify changes committed and pushed
  
- [ ] Run test with no errors
  - [ ] Verify immediate success
  
- [ ] Run test with API disabled
  - [ ] Verify graceful exit

---

## Migration Path

### Phase 1: Parallel Testing
1. Keep `build_fix.py` as main script
2. Deploy `build_fix_v2.py` alongside
3. Run both on test builds to compare results

### Phase 2: Gradual Rollout
1. Switch Release builds to `build_fix_v2.py`
2. Monitor for issues
3. Adjust confidence thresholds if needed

### Phase 3: Full Deployment
1. Remove `build_fix.py` from production
2. Make `build_fix_v2.py` the default
3. Document in runbooks

---

## Known Limitations

1. **Commit History Search**: Limited to recent 10 commits (configurable)
2. **Branch Cleanup**: Old fix branches not automatically deleted
3. **PR Auto-Merge**: Manual review still required (by design)
4. **Confidence Thresholds**: Fixed at 0.8 (can be made configurable)

---

## Future Enhancements

- [ ] Configurable confidence thresholds per error type
- [ ] Automatic cleanup of old fix branches
- [ ] Machine learning-based confidence scoring
- [ ] Support for multiple file compilation
- [ ] Error categorization improvement
- [ ] Batch error fixing with error dependencies

