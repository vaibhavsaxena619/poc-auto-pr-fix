# Build Fix v2: Migration & Deployment Guide

## Quick Summary

**New System:** Advanced multi-error handling with intelligent commit history walking

**Key Improvements:**
1. Handle mixed error types (high + low confidence) separately
2. Fix only auto-fixable errors; tag low-confidence errors for review
3. Search commit history to find good commits instead of failing
4. Original author tagged and notified of low-confidence issues

---

## Deployment Steps

### Phase 1: Side-by-Side Testing (Recommended)

#### Step 1a: Deploy New Script
```bash
# New file is already created: build_fix_v2.py
# Keep both scripts in repository for A/B testing
git log --oneline | grep "build_fix_v2"
# Confirm: 4318f58 FEATURE: Advanced multi-error handling...
```

#### Step 1b: Test Release Build with v2
```groovy
// In Jenkinsfile, temporarily update the Release stage to use v2:
sh 'python3 build_fix_v2.py src/App.java'

// Keep original as fallback:
sh 'python3 build_fix.py src/App.java'
```

#### Step 1c: Run Test Build
- Trigger Release build manually
- Monitor output for new features:
  - "Found X error(s)" → Multiple error detection
  - "HIGH-CONFIDENCE" → Error classification
  - "Searching commit history" → Commit history walking
  - "PR #X created with low-confidence issues marked" → Review branch creation

#### Step 1d: Compare Results
```bash
# Check if:
- [ ] High-confidence errors fixed
- [ ] Low-confidence errors left in place  
- [ ] Review branch created (if mixed errors)
- [ ] Original author tagged (if review needed)
- [ ] Commit history searched (if only low-confidence)
```

---

### Phase 2: Full Replacement

#### Step 2a: Update Jenkinsfile
```groovy
// BEFORE (Release stage):
sh 'python3 build_fix.py src/App.java'

// AFTER (Release stage):
sh 'python3 build_fix_v2.py src/App.java'
```

#### Step 2b: Test on Staging
```bash
# Trigger 3 Release builds with:
# 1. Only high-confidence errors
# 2. Only low-confidence errors  
# 3. Mixed errors

# Verify each passes appropriate stage
```

#### Step 2c: Remove Old Script
```bash
# Once v2 is stable (after 1-2 weeks):
git rm build_fix.py
git commit -m "BREAKING: Remove old build_fix.py - v2 is now default"
```

---

## Testing Scenarios

### Scenario 1: Mixed Errors (High + Low)

**Test Code (src/App.java):**
```java
// Missing imports (HIGH confidence)
List<String> list = new ArrayList<>();

// Missing method (LOW confidence)  
applyDiscount(100.0);

// Unknown business logic (LOW confidence)
calculateTotal(prices);
```

**Expected Behavior:**
```
✗ Compilation errors detected
  Found 3 error(s)
  ✓ HIGH-CONFIDENCE: safe:missing_import (90%)
  ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
  ⚠️ LOW-CONFIDENCE: unknown (50%)

Creating fix branch...
✓ Branch created: fix/high-confidence-errors_20260122_110000
✓ PR #28 created with low-confidence issues marked
```

**Verification:**
- [ ] Imports are added to fixed code
- [ ] applyDiscount() call left as-is (not deleted)
- [ ] calculateTotal() call left as-is
- [ ] PR body lists 2 low-confidence issues
- [ ] Original author tagged in PR

### Scenario 2: Only Low-Confidence Errors

**Test Code (src/App.java):**
```java
// Only unfixable/risky errors
applyDiscount(price);    // Method not found
calculateROI(data);      // Unknown calculation
```

**Expected Behavior (with no good commits available):**
```
⚠️ Only low-confidence errors found
  Searching commit history...
  ℹ️ No good commit found in recent history
  Creating review branch...
```

**Expected Behavior (with good commit found):**
```
⚠️ Only low-confidence errors found
  Searching commit history...
  ✅ Found good commit: abc1234
  Building from stable commit instead...
✓ Verified: Good commit builds successfully
```

**Verification:**
- [ ] If good commit exists: Build succeeds from that commit
- [ ] If no good commit: Review branch created with issues listed

### Scenario 3: Only High-Confidence Errors

**Test Code (src/App.java):**
```java
// Only fixable errors
List<String> list = new ArrayList<>();  // Missing import
String str = "test; // Syntax error
```

**Expected Behavior:**
```
✓ All errors are high-confidence - proceeding with auto-fix
Applying fix...
Verifying fix...
✓ SUCCESS: Fix verified!
✓ Changes committed and pushed
```

**Verification:**
- [ ] Code compiles cleanly after fix
- [ ] Imports added properly
- [ ] Syntax errors corrected
- [ ] Changes committed to Release branch
- [ ] No review branch created

---

## Configuration Changes

### New Environment Variables
None - v2 uses same variables as v1:
```bash
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
GITHUB_PAT
# ... same as before
```

### New Constants (if customization needed)
```python
MAX_COMMIT_HISTORY_SEARCH = 10  # Change to search more/fewer commits
                                # Default: 10 (sufficient for most cases)
```

### Confidence Threshold (if customization needed)
```python
# In classify_error_confidence():
HIGH_CONFIDENCE = 0.8  # Change if needed
LOW_CONFIDENCE = 0.2

# Default values in ErrorInfo:
if confidence >= 0.8:
    is_fixable = True  # HIGH - auto-fix
else:
    is_fixable = False # LOW - manual review
```

---

## Rollback Plan

If v2 causes issues:

### Quick Rollback
```bash
# Revert Jenkinsfile to use v1
git revert <commit_hash>

# Rebuild Release pipeline
# Everything reverts to previous behavior
```

### Parallel Fallback
```groovy
// In Jenkinsfile - run both and compare
try {
    sh 'python3 build_fix_v2.py src/App.java'
} catch {
    echo "v2 failed, falling back to v1..."
    sh 'python3 build_fix.py src/App.java'
}
```

---

## Monitoring & Metrics

### Key Metrics to Track

```
Per Build:
- Number of errors detected
- High-confidence vs low-confidence split
- Review branches created (count)
- Commits searched in history
- Good commit found (yes/no)
- Auto-fix success rate

Weekly:
- Average errors per build
- Review branch merge rate
- Commit history search depth needed
- v2 success rate vs v1 baseline
```

### Log Locations
```
Jenkins Console Output:
- Each build shows detailed v2 output
- Search for:
  * "Found X error(s)"
  * "HIGH-CONFIDENCE" / "LOW-CONFIDENCE"
  * "Searching commit history"
  * "Branch created"
  * "PR #X created"
```

---

## Troubleshooting

### Issue: "PR creation failed"
**Cause:** GITHUB_PAT not set or invalid
**Solution:**
```bash
# Verify GITHUB_PAT is set in Jenkins credentials
# Check GitHub token hasn't expired (30 days)
# Regenerate if needed at: https://github.com/settings/tokens
```

### Issue: "Commit history search taking too long"
**Cause:** Many commits to check with slow git operations
**Solution:**
```python
# Reduce search depth in build_fix_v2.py:
find_last_good_commit(source_file, max_search=5)  # Default was 10
```

### Issue: "Fix branch created but PR not created"
**Cause:** requests library not installed
**Solution:**
```bash
pip3 install requests
# Or in Jenkinsfile:
sh 'pip3 install openai requests --quiet --break-system-packages'
```

### Issue: "Low-confidence errors wrongly classified"
**Cause:** Pattern matching doesn't match error message format
**Solution:**
Update RISKY_ERROR_PATTERNS in build_fix_v2.py:
```python
RISKY_ERROR_PATTERNS = {
    'custom_pattern': r'your|pattern|here',
    # ... add new patterns as needed
}
```

---

## Success Criteria

Build Fix v2 is considered successful if:

1. **Functionality**
   - [ ] Handles mixed high/low confidence errors correctly
   - [ ] Fixes high-confidence, leaves low-confidence untouched
   - [ ] Creates review branches with proper tagging
   - [ ] Searches commit history without errors
   - [ ] Finds good commits when available

2. **Performance**
   - [ ] No increase in build time (target: < 5 min total)
   - [ ] Commit history search completes in < 30 seconds
   - [ ] PR creation completes in < 10 seconds

3. **Quality**
   - [ ] No code is silently deleted
   - [ ] All code changes are intentional
   - [ ] Original authors are notified
   - [ ] Manual review is enabled for risky changes

4. **Stability**
   - [ ] No regressions vs v1 behavior
   - [ ] Handles edge cases gracefully
   - [ ] Meaningful error messages
   - [ ] No infinite loops or hangs

---

## Documentation Updates

Once v2 is deployed, update:

1. **Jenkinsfile comments**
   ```groovy
   // Release - Auto-Fix (if needed)
   // Uses Azure OpenAI GPT-5 with advanced multi-error handling
   // v2 features: mixed confidence, commit history walking
   ```

2. **README.md**
   - Add note about v2 features
   - Link to BUILD_FIX_V2_DOCUMENTATION.md

3. **Runbooks**
   - Add troubleshooting section
   - Document new behavior for ops

4. **Team Training**
   - Explain what "low-confidence" means
   - Show how to review marked issues
   - Document new PR tagging format

---

## Timeline

**Recommended Rollout:**
```
Day 1:  Deploy v2 alongside v1 (commit 4318f58)
Day 2:  Test with mixed error scenarios
Day 3:  Test with commit history walking
Day 4:  A/B testing with sample builds
Day 5-7: Monitor for issues
Week 2: Full switch to v2
Week 3: Remove old build_fix.py
```

---

## Support & Questions

For issues or questions:

1. Check [BUILD_FIX_V2_DOCUMENTATION.md](BUILD_FIX_V2_DOCUMENTATION.md) for detailed specs
2. Review test scenarios above
3. Check Jenkins console output for v2 logs
4. Examine git commit messages for context

---

## Revision History

**v2.0 - Advanced Multi-Error Handling** (Commit: 4318f58)
- Multiple error classification
- High-confidence fix, low-confidence review
- Intelligent commit history walking
- PR creation with issue tagging

**v1.0 - Single Error Handling** (Earlier)
- Basic error detection
- GPT auto-fix for first error
- Simple confidence gating
- Low-confidence PR creation

