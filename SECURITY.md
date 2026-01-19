# Security & Safety Guidelines

This document outlines critical security considerations and safety features for the AI-powered Java CI/CD pipeline.

---

## 🔐 **1. API Key Management**

### Best Practices

**DO:**
- ✅ Store API keys in **Docker secrets** or **Jenkins credentials vault**
- ✅ Use environment variables with **restricted access**
- ✅ Rotate API keys periodically (every 90 days)
- ✅ Audit API key usage in logs

**DON'T:**
- ❌ Commit API keys to git
- ❌ Log full API keys in build output
- ❌ Share API keys across teams
- ❌ Use the same key for dev/staging/prod

### Jenkins Configuration

```groovy
// Correct: Use Jenkins credentials
withCredentials([
    string(credentialsId: 'AZURE_OPENAI_API_KEY', variable: 'AZURE_OPENAI_API_KEY'),
    string(credentialsId: 'AZURE_OPENAI_ENDPOINT', variable: 'AZURE_OPENAI_ENDPOINT')
]) {
    // Jenkins automatically masks these in logs
}

// Wrong: Hardcoding keys
AZURE_OPENAI_API_KEY = "sk-1234..." // ❌ SECURITY RISK
```

### Docker Secrets Setup

```bash
# Create Docker secrets (not committed to git)
echo "your-api-key" | docker secret create AZURE_OPENAI_API_KEY -
echo "your-endpoint" | docker secret create AZURE_OPENAI_ENDPOINT -

# Reference in docker-compose or swarm
# Services will have /run/secrets/AZURE_OPENAI_API_KEY available
```

---

## 👤 **2. GitHub Fine-Grained PAT (Personal Access Token)**

### Least Privilege Principle

Create a **read-only token** for code review PRs:

```
Repository Permissions:
✓ Contents: Read-only
✓ Pull Requests: Read & write comments
✗ Admin: None
✗ Workflow: None

Account Permissions:
✗ All
```

**Token Scope:**
```
Single repository: poc-auto-pr-fix
Expiration: 30 days (rotate frequently)
```

### Jenkins Credential Setup

```groovy
// Use fine-grained PAT, not personal access token
withCredentials([
    usernamePassword(
        credentialsId: 'GITHUB_PAT',
        usernameVariable: 'GITHUB_USERNAME',
        passwordVariable: 'GITHUB_PAT'
    )
]) {
    // Token is masked in logs
}
```

### What NOT to Do

- ❌ Use `repo` scope (allows everything)
- ❌ Use personal access tokens (classic)
- ❌ Use tokens without expiration
- ❌ Share tokens across projects

---

## 🚨 **3. Automatic Fix Guardrails**

### Confidence Classifier

Not all errors are safe to auto-fix. The pipeline uses a **confidence scoring system**:

**HIGH CONFIDENCE (≥ 80%) - AUTO-FIX ENABLED:**
```python
✓ Missing imports
  Pattern: "cannot find symbol", "import not found"
  
✓ Formatting issues
  Pattern: "unexpected token", "invalid syntax"
  
✓ Test failures
  Pattern: "AssertionError", "Test failed"
  
✓ Lint issues
  Pattern: "unused variable", "dead code"
```

**LOW CONFIDENCE (< 80%) - MANUAL REVIEW REQUIRED:**
```python
✗ Business logic errors
  Pattern: "NullPointerException", "IndexOutOfBoundsException"
  → Can mask real bugs, needs manual review
  
✗ Security vulnerabilities
  Pattern: "SQL injection", "XSS", "deprecated"
  → Never auto-fix security issues
  
✗ Database migrations
  Pattern: "ALTER TABLE", "schema changes"
  → Can cause data loss, requires DBA review
```

### Example: Low Confidence Error

```java
// This error will NOT be auto-fixed
Exception in thread "main" java.lang.NullPointerException
  at App.processUser(App.java:42)
```

Output:
```
✗ Compilation error detected
  Category: risky:business_logic (confidence: 10%)
  ⚠ LOW CONFIDENCE: Manual review required
  Aborting auto-fix (requires confidence >= 80%)
```

---

## 🔄 **4. Infinite Loop Prevention**

### Retry Caps

```python
MAX_FIX_ATTEMPTS = 2  # Maximum retry attempts per build
```

**How it works:**

1. **First error:** Generate fix, apply, verify
2. **Verification fails:** Generate new fix (attempt 2)
3. **Still fails:** ABORT (prevent endless loop)

### Error Deduplication

```python
# Generate hash of error message
error_hash = hashlib.sha256(error_message.encode()).hexdigest()[:8]

# Check if we've tried this exact error before
if check_error_history(source_file, error_hash):
    print("ERROR LOOP DETECTED: Same error attempted before")
    sys.exit(1)  # Stop immediately
```

**History file:** `.src/App.java.fix_history.json`
```json
{
  "attempted_errors": ["a1b2c3d4", "e5f6g7h8"],
  "last_attempt": "2026-01-19T14:11:36.652382",
  "last_success": false,
  "attempt_count": 3
}
```

---

## 🎯 **5. Feature Flags**

Control pipeline behavior without code changes:

### Configuration

Set these in Jenkins **Build Parameters** or **environment**:

```groovy
environment {
    // Enable/disable auto-fix completely
    ENABLE_AUTO_FIX = "true"  // Default: enabled
    
    // Enable/disable OpenAI API calls (for testing)
    ENABLE_OPENAI_CALLS = "true"  // Default: enabled
    
    // Dry-run mode (analyze but don't apply fixes)
    READ_ONLY_MODE = "false"  // Default: disabled
}
```

### Use Cases

**1. Development Testing (Read-Only Mode)**
```bash
# Jenkins will analyze errors but NOT apply fixes
ENABLE_AUTO_FIX=false
READ_ONLY_MODE=true
```

Output:
```
✗ Compilation error detected
  Category: safe:missing_import (confidence: 90%)
  [READ-ONLY] Would apply fix (mode disabled)
```

**2. Disable OpenAI Calls (Cost Control)**
```bash
# Analyze confidence but skip OpenAI
ENABLE_OPENAI_CALLS=false
```

**3. Production Hotfix (Full Auto-Fix)**
```bash
ENABLE_AUTO_FIX=true
ENABLE_OPENAI_CALLS=true
READ_ONLY_MODE=false
```

---

## 📊 **6. Token Usage Optimization**

### Problem: Prompt Leakage

Large build logs waste tokens and expose sensitive info:
```
Error size: 100KB build log → 25,000+ tokens
Cost: ~$0.75 per build (expensive!)
```

### Solution: Error Essence Extraction

Only send critical information:

```python
extract_error_essence(error_message, source_code, max_tokens=500)
```

**What gets sent:**
```
ERROR: src/App.java:8: error: cannot find symbol
        List<String> users = new ArrayList<>();
        ^

CODE CONTEXT:
>>>  8: List<String> users = new ArrayList<>();
     9: System.out.println(users);
    10: }

STACK: (first 500 chars of error)
```

**NOT sent:**
- ✗ Full build output (100KB+)
- ✗ Maven/Gradle logs
- ✗ System environment variables
- ✗ Credentials or API keys

**Token savings:**
- Before: ~25,000 tokens → ~$0.75
- After: ~200 tokens → ~$0.006 (99.2% reduction!)

---

## 🛡️ **7. Read-Only Mode for PRs**

### Scenario: Code Review Only PRs

Some PRs should get feedback WITHOUT auto-applying fixes:

```bash
# For PR reviews (risky feature branch)
READ_ONLY_MODE=true
ENABLE_AUTO_FIX=false
```

**Behavior:**
1. ✓ Analyzes code quality
2. ✓ Posts code review comments
3. ✓ Suggests fixes (but doesn't apply)
4. ✗ Does NOT commit changes

**Output:**
```
PR #10 Code Review Analysis:
- Missing imports detected
- Unused variables in line 15
- Recommended: Add java.util.* import

[No changes applied - READ_ONLY_MODE enabled]
```

---

## 📝 **8. Audit Logging**

### What Gets Logged

```
[2026-01-19T14:11:36] Build fix initiated for src/App.java
  Category: safe:missing_import (confidence: 90%)
  Decision: HIGH CONFIDENCE - Safe to auto-fix
  Action: Sending to Azure OpenAI for analysis...
  Result: SUCCESS - Fix verified, code compiles
  Commit: abc123def
```

### What Should NOT Get Logged

- ❌ Full API key
- ❌ Source code (only file path)
- ❌ Error stack traces (only first 100 chars)
- ❌ GitHub token

### Access Logs

```bash
# Jenkins logs are visible to:
✓ Build admin
✓ Project developers
✗ Anyone with repo access (logs masked)
```

---

## 🚀 **9. Deployment Checklist**

Before using in production, verify:

- [ ] API keys stored in Jenkins credentials vault
- [ ] GitHub PAT is fine-grained with 30-day expiration
- [ ] `MAX_FIX_ATTEMPTS = 2` (prevents loops)
- [ ] Confidence threshold is 0.8 (80%)
- [ ] Feature flags documented for your team
- [ ] Error deduplication enabled (hash checking)
- [ ] Prompt optimization enabled (token savings)
- [ ] Read-only mode tested on a non-critical branch
- [ ] Build logs reviewed for credential leakage
- [ ] Error patterns match your codebase

---

## ❓ **10. Frequently Asked Questions**

**Q: Is it safe to auto-fix business logic errors?**
A: No. The confidence classifier rejects them. Manual review required.

**Q: What happens if AI generates a wrong fix?**
A: The build verifies the fix by recompiling. If it fails, auto-fix is rejected.

**Q: Can I auto-fix database migrations?**
A: Not recommended. Marked as risky and requires manual review (low confidence).

**Q: How much does this cost?**
A: ~$0.006 per error fix (with prompt optimization). ~100 fixes = $0.60.

**Q: What if OpenAI is down?**
A: `ENABLE_OPENAI_CALLS=false` allows builds to continue without AI assistance.

**Q: Can I disable auto-fix for a single PR?**
A: Yes, set `ENABLE_AUTO_FIX=false` on the branch or use environment variable override.

---

## 🔗 **Related Documentation**

- [README.md](README.md) - Project overview
- [LOCAL_SETUP.md](LOCAL_SETUP.md) - Environment setup
- [JENKINS_CREDENTIALS.md](JENKINS_CREDENTIALS.md) - Credential configuration
