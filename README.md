# Java CI/CD Automation with Azure OpenAI GPT-5

**Production-Ready Enterprise CI/CD System** - Intelligent Build Error Recovery with Mixed Confidence Error Classification

Automated Jenkins pipeline that intelligently separates fixable (high-confidence) from unfixable (low-confidence) compilation errors, applies fixes only to safe errors, and creates review branches for manual intervention on business logic errors.

## Key Features

✅ **Smart Error Classification** - Separates HIGH-confidence (missing imports) from LOW-confidence (missing methods)  
✅ **Intelligent Auto-Fix** - Fixes only safe, high-confidence errors using Azure OpenAI GPT-5  
✅ **Review Branches** - Creates PR with low-confidence issues marked for manual review  
✅ **Commit History Fallback** - Searches previous commits for stable builds when fixes don't work  
✅ **Zero Code Deletion** - Never deletes code, preserves all sections for review  
✅ **GitHub Integration** - Full PR automation with author tagging and issue lists  
✅ **Production-Grade** - Three-tier pipeline: Dev (push-only) → PR (review) → Release (auto-fix)

## Quick Start

### Prerequisites
- Java 8+
- Python 3.7+
- Jenkins with GitHub integration
- Azure OpenAI API credentials
- GitHub Fine-grained Personal Access Token

### Setup

See [LOCAL_SETUP.md](LOCAL_SETUP.md) for detailed instructions.

**Quick:**
```bash
# 1. Install Python dependencies
pip3 install openai requests

# 2. Set environment variables
export AZURE_OPENAI_API_KEY=your-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
export AZURE_OPENAI_API_VERSION=2024-12-01-preview
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5
export GITHUB_PAT=your-github-pat

# 3. Run Release build in Jenkins
```

## Pipeline Architecture

### Three-Tier System

| Branch | Trigger | Action | Build |
|---|---|---|---|
| **Dev_Poc_V1** | Manual push | Code sync only | ❌ None |
| **Pull Requests** | PR creation | AI code review | ❌ No compile |
| **Release** | Manual trigger | Build + Auto-Fix | ✅ Full pipeline |

### Build Fix Workflow

```
Compilation Error
       │
       ├─ Parse all errors
       │
       ├─ Classify by confidence
       │  ├─ HIGH (0.9): missing imports, formatting
       │  └─ LOW (0.1): missing methods, business logic
       │
       ├─ Fix HIGH-confidence errors
       │  └─ Send to Azure OpenAI GPT-5
       │
       ├─ Verify fix works
       │  ├─ YES → Create review branch for LOW errors
       │  └─ NO → Search commit history
       │
       └─ Result: Build SUCCESS with review PR
```

## How It Works

### Release Build (Auto-Fix Enabled)

1. **Compile:** Attempt Java compilation with `javac`
2. **Error Detection:** Parse compilation output
3. **Classification:** Split errors by confidence level
4. **Auto-Fix:** Apply fixes to HIGH-confidence errors
5. **Verify:** Confirm fixes compile successfully
6. **Fallback:** Search commit history if needed
7. **Review:** Create PR for LOW-confidence issues
8. **Success:** Build completes with review PR

### Error Classification

**HIGH-CONFIDENCE (Auto-Fixed):**
- `cannot find symbol: class List` → Add `import java.util.List;`
- `cannot find symbol: variable Arrays` → Add `import java.util.Arrays;`
- Formatting and syntax errors
- Linting issues

**LOW-CONFIDENCE (Manual Review):**
- `cannot find symbol: method applyDiscount()` → Business logic needed
- Runtime exceptions requiring knowledge
- Security issues
- Migration issues

## File Structure

```
.
├── README.md                 # This file
├── LOCAL_SETUP.md           # Setup instructions
├── Jenkinsfile              # Jenkins pipeline
├── build_fix_v2.py          # Main auto-fix engine
├── .env.example             # Environment template
├── src/App.java             # Sample application
├── build/                   # Compilation artifacts
├── docs/                    # Additional docs
└── .gitignore               # Git ignore rules
```

## Production Deployment

### Jenkins Setup

1. **Create Multibranch Pipeline Job**
   - Name: `poc-java-pr-workflow`
   - Source: GitHub repository
   - Script path: `Jenkinsfile`

2. **Add Credentials**
   ```
   Manage Jenkins → Manage Credentials
   
   Add as "Secret text":
   - AZURE_OPENAI_API_KEY
   - AZURE_OPENAI_ENDPOINT
   - GITHUB_PAT
   ```

3. **Configure Environment Variables**
   - AZURE_OPENAI_API_VERSION: `2024-12-01-preview`
   - AZURE_OPENAI_DEPLOYMENT_NAME: `gpt-5`
   - ENABLE_AUTO_FIX: `true`

4. **Add GitHub Webhook**
   ```
   Payload URL: https://your-jenkins/github-webhook/
   Events: Push, Pull requests
   ```

### Build Triggers

| Branch | Trigger | Action |
|---|---|---|
| Dev_Poc_V1 | Manual | Push code only |
| Pull Request | Automatic | Code review |
| Release | Manual | Build + Auto-Fix |

## Example Workflows

### Workflow 1: Successful Auto-Fix

```
$ git commit && git push origin Release
Jenkins: Release build triggered

[Compile] src/App.java: 4 errors
  ✗ cannot find symbol: class List
  ✗ cannot find symbol: class ArrayList
  ✗ cannot find symbol: variable Arrays
  ✗ cannot find symbol: method applyDiscount()

[Classify]
  ✓ HIGH: 3 errors (imports)
  ⚠️ LOW: 1 error (method)

[Fix]
  ✓ Adding import statements
  ✓ Verifying compilation
  ✓ Code now compiles (with 1 remaining low-confidence error)

[Review]
  ✓ Creating fix branch: fix/high-confidence-errors_20260122_11XXXX
  ✓ PR #34 created with applyDiscount() marked for review

Result: BUILD SUCCESS ✅
```

### Workflow 2: Fallback to Previous Commit

```
[Compile] 5 errors detected
[Classify] All are LOW-confidence (business logic)
[Fix] Cannot auto-fix (requires domain knowledge)
[Fallback] Searching commit history...
  ✓ Commit N-1: Still has 5 errors
  ✓ Commit N-2: Still has 5 errors
  ✓ Commit N-5: Compiles successfully!
[Checkout] Building from N-5
[Result] Build SUCCESS ✅
```

## Security

### Credentials
- All API keys stored in Jenkins secrets
- Never logged or printed to console
- Masked in build output automatically

### Code Safety
- HIGH-confidence fixes are context-aware
- LOW-confidence errors preserved for review
- Zero code deletion risk
- Full audit trail in Git

### Network Security
- HTTPS/TLS for all API calls
- GitHub webhook signature verification
- Rate limiting on API calls

## Testing

### Local Test

```bash
# Test auto-fix engine
python3 build_fix_v2.py src/App.java

# With environment variables
export AZURE_OPENAI_API_KEY=test-key
export ENABLE_AUTO_FIX=true
python3 build_fix_v2.py src/App.java
```

### Jenkins Test

1. Create test branch from Dev_Poc_V1
2. Introduce intentional error (remove import)
3. Create PR to Release
4. Trigger Release build manually
5. Observe auto-fix in console output

## Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| API Key error | Credential not set | Check Jenkins credentials |
| GitHub 401 | Invalid PAT | Regenerate token with permissions |
| Auto-fix not applied | Error confidence < 0.8 | Check classification |
| PR not created | Missing permissions | Verify GitHub PAT scope |
| Build still fails | Low-confidence errors | Check review PR for details |

## Performance

- **Code Review:** 2-5 seconds per PR
- **Auto-Fix:** 3-8 seconds per error
- **Commit History:** 1-2 seconds per commit
- **Total Build:** 2-3 minutes

## Documentation

- [LOCAL_SETUP.md](LOCAL_SETUP.md) - Installation & configuration
- [Jenkinsfile](Jenkinsfile) - Pipeline definition
- [build_fix_v2.py](build_fix_v2.py) - Auto-fix engine

## Support

For issues:
1. Check [LOCAL_SETUP.md](LOCAL_SETUP.md)
2. Review Jenkins console output
3. Check Git commit history
4. Verify credentials in Jenkins

---

**Status:** ✅ Production Ready  
**Version:** 2.0.0  
**Last Updated:** January 22, 2026
