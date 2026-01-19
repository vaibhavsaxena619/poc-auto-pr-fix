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

---

## 🌐 **11. Multi-Language Support**

The pipeline now supports automatic error fixing for **6 programming languages**:

### Supported Languages

| Language | File Extension | Checker | Safe Errors | Risky Errors |
|----------|---|---|---|---|
| **Java** | `.java` | `javac` | Missing imports, syntax, tests | Business logic, security, migrations |
| **JavaScript** | `.js` | `eslint` | Syntax, imports, type errors, tests | Async logic, XSS, code execution |
| **CSS** | `.css` | `stylelint` | Syntax, selectors, properties | Specificity conflicts, performance |
| **Shell** | `.sh` | `bash -n` | Syntax, undefined vars, quotes | Injection, file ops, permissions |
| **Smarty** | `.tpl`, `.smarty` | Framework | Syntax, undefined vars, tags | XSS injection, PHP execution |
| **XSLT** | `.xsl`, `.xslt` | `xmllint` | Syntax, XPath, namespaces | XXE injection, recursion |

### Language-Specific Security Concerns

#### 🔴 **Java**
```
❌ Avoid auto-fixing:
- SQL injection (use parameterized queries)
- XXE vulnerabilities  
- Weak cryptography (MD5, SHA1)
- Deserialization attacks
- Hardcoded credentials
```

#### 🟡 **JavaScript**
```
❌ Avoid auto-fixing:
- Command injection (child_process.exec)
- eval() and Function() constructor
- innerHTML assignments (XSS)
- Prototype pollution
- Hardcoded secrets
- Dependency vulnerabilities
```

#### 🔵 **CSS**
```
⚠️ Watch for:
- expression() (IE vulnerability)
- Behavior property (IE vulnerability)  
- Data URLs with JavaScript
- font-face with untrusted sources
- Content property injection

Note: CSS errors are mostly styling, low security risk
```

#### 🟢 **Shell**
```
🚨 HIGHEST RISK - Extra caution required:
- Shell injection via unquoted variables
- Command substitution injection ($(...), backticks)
- Hardcoded credentials and API keys
- Unsafe file operations (rm -rf, dd)
- Running with elevated privileges
- Unsafe curl/wget with passwords
- eval() and exec() usage
- Insecure /tmp handling
```

#### 🟠 **Smarty**
```
❌ Avoid auto-fixing:
- XSS via unescaped variables (always use |escape)
- {php} tags (full PHP execution risk)
- {eval} tags (dynamic code execution)
- Unsanitized includes
- Template injection
- Hardcoded database credentials
```

#### 🔴 **XSLT**
```
❌ Avoid auto-fixing:
- XXE injection (XML External Entity)
- Billion laughs DoS (quadratic blowup)
- disable-output-escaping="yes" enabling injection
- Recursive templates (infinite loops)
- Unvalidated entity references
- Sensitive data in output
```

### Language Auto-Fix Confidence Levels

**HIGH CONFIDENCE (≥80%) - Auto-fix enabled:**
- **Java:** Missing imports, formatting, test failures
- **JavaScript:** Syntax errors, undefined variables, type errors
- **CSS:** Property syntax, selector format
- **Shell:** Variable expansion, quote balancing
- **Smarty:** Tag syntax, variable definition
- **XSLT:** XPath expressions, namespace issues

**LOW CONFIDENCE (<80%) - Manual review required:**
- **Java:** Logic errors, security issues, migrations
- **JavaScript:** Async/await, injection attacks, prototype pollution
- **CSS:** Specificity conflicts, complex selectors
- **Shell:** Command injection, privilege escalation, file operations
- **Smarty:** XSS, template injection, code execution
- **XSLT:** XXE, recursion, output escaping

### Example: Language Detection & Auto-Fix

```bash
# Java file - auto-fix missing import
$ python3 build_fix.py src/App.java
[...] Build fix initiated for src/App.java (java)
✗ Error detected
  Category: safe:missing_import (confidence: 90%)
✓ HIGH CONFIDENCE: Safe to auto-fix
  Sending error to Azure OpenAI for analysis...
  ✓ SUCCESS: Fix verified!

# Shell script - reject risky command injection error
$ python3 build_fix.py deploy.sh
[...] Build fix initiated for deploy.sh (shell)
✗ Error detected
  Category: risky:injection (confidence: 10%)
⚠ LOW CONFIDENCE: Manual review required
  Aborting auto-fix (requires confidence >= 80%)

# CSS file - auto-fix property syntax
$ python3 build_fix.py styles.css
[...] Build fix initiated for styles.css (css)
✗ Error detected
  Category: safe:property_error (confidence: 90%)
✓ HIGH CONFIDENCE: Safe to auto-fix
```

### Feature Flag Control by Language

```groovy
environment {
    // Global control
    ENABLE_AUTO_FIX = "true"
    
    // Language-specific overrides (future enhancement)
    ENABLE_JAVA_FIX = "true"
    ENABLE_SHELL_FIX = "false"  // Disable for shell (high risk)
    ENABLE_JAVASCRIPT_FIX = "true"
}
```

### Security Best Practices by Language

**For Shell Scripts (⚠️ Highest Risk):**
```bash
# DO: Quote all variables
"${variable}" ✓
rm -rf "${directory}"

# DON'T: Unquoted expansion
$variable ✗
rm -rf $directory
```

**For JavaScript:**
```javascript
// DO: Use parameterized queries
db.query('SELECT * FROM users WHERE id = ?', [userId])

// DON'T: String concatenation
db.query('SELECT * FROM users WHERE id = ' + userId)
```

**For Smarty Templates:**
```smarty
<!-- DO: Always escape user output -->
{$user_input|escape:'html'}

<!-- DON'T: Unescaped output -->
{$user_input}
```

**For XSLT:**
```xml
<!-- DO: Disable external entities -->
<!DOCTYPE stylesheet [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>

<!-- Use disable-output-escaping carefully -->
<xsl:value-of select="..." disable-output-escaping="no"/>
```
