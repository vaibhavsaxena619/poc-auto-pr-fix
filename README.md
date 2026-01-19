# Java CI/CD Automation with Azure OpenAI GPT-5

Enterprise-grade Jenkins pipeline with automated code review and build error recovery powered by Microsoft Azure OpenAI GPT-5.

## Project Overview

This project implements a production-ready CI/CD automation system for Java applications with:
- **Dev_Poc_V1 Branch:** Development branch with no automatic builds (push-only workflow)
- **Pull Requests:** Automated AI-powered code review without compilation using Azure OpenAI GPT-5
- **Release Branch:** Manual trigger builds with automatic error detection and repair
- **GitHub Integration:** Seamless PR commenting with code quality suggestions

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   GitHub Repository                         │
│            poc-auto-pr-fix (Dev_Poc_V1 + Release)           │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
    PUSH TO         PULL REQUEST   RELEASE TRIGGER
    Dev_Poc_V1        TO RELEASE   (Manual Build)
        │              │              │
        │ No Build     │ Code Review  │ Full Build
        │ No Tests     │ No Build     │ Auto-Fix
        │              │ No Compile   │ Tests
        ▼              ▼              ▼
    Code Sync    AI Analysis    Production
                 + Comment       Release
```

## Branch Strategy

### 1. Dev_Poc_V1 (Development Branch)
**Purpose:** Primary development branch  
**Workflow:** Push-only, no builds  
**Trigger:** Manual push  
**Actions:** Code gets synced to remote without any validation  

```
Developer Push → Dev_Poc_V1 → Remote Updated ✓
                  (No Build)
```

### 2. Pull Requests
**Purpose:** Code review before Release  
**Trigger:** PR created against Release branch  
**Workflow:** AI code review without compilation  
**Actions:**
- Analyzes code changes using Azure OpenAI GPT-5
- Posts review comment with:
  - Possible mistakes
  - Improvement suggestions
  - Code quality recommendations
  - Best practices violations

```
Dev_Poc_V1 → Create PR to Release
             │
             ▼
         Fetch Changes
             │
             ▼
    Send to Azure OpenAI GPT-5
             │
             ▼
    Post Review Comment on PR
```

### 3. Release Branch (Production Builds)
**Purpose:** Production release builds  
**Trigger:** Manual trigger on Release branch  
**Workflow:** Build with automatic error recovery  
**Actions:**
1. **Compile:** Attempt Java compilation
2. **Auto-Fix:** If compilation fails, invoke Azure OpenAI GPT-5
   - Analyze compilation error
   - Apply fixes to source code
   - Retry compilation
3. **Verify:** Confirm auto-fix resolved issues
4. **Package:** Create JAR file and run tests
5. **Report:** Post build summary to associated PR (if exists)

```
Manual Trigger on Release
       │
       ▼
   Compile (javac)
       │
    ├─ SUCCESS ─→ JAR + Tests ─→ Archive ✓
    │
    └─ FAILURE ─→ GPT-5 Analysis ─→ Auto-Fix
                      │
                      ▼
                  Recompile
                      │
                   ├─ SUCCESS ─→ JAR + Tests ✓
                   │
                   └─ FAILURE ─→ Build Failed ✗
```

## Jenkins Pipeline Configuration

### Environment Variables
```groovy
ENABLE_AUTO_FIX = true          // Enable LLM auto-fix on Release builds
ENABLE_OPENAI_CALLS = true      // Enable Azure OpenAI API calls
READ_ONLY_MODE = false          // Disable read-only mode for real fixes
```

### Credentials Required
- `AZURE_OPENAI_API_KEY`: Azure OpenAI API authentication key
- `AZURE_OPENAI_ENDPOINT`: Azure OpenAI endpoint URL
- `GITHUB_PAT`: GitHub Personal Access Token for PR operations

## Detailed Workflow Examples

### Example 1: Dev_Poc_V1 Push (No Build)
```bash
$ git checkout Dev_Poc_V1
$ git add src/App.java
$ git commit -m "Add new feature"
$ git push origin Dev_Poc_V1

Jenkins Output:
✓ Dev_Poc_V1 branch detected
⊘ No automatic builds on Dev_Poc_V1
ℹ To trigger builds, create a PR to Release
```

### Example 2: Pull Request with Code Review
```bash
$ git checkout -b feature-xyz origin/Dev_Poc_V1
$ # Make code changes
$ git push origin feature-xyz
$ # Create PR: feature-xyz → Release on GitHub

Jenkins Output:
PR #42 to Release detected
Analyzing code changes without compilation...
[Fetching PR changes]
[Sending to Azure OpenAI GPT-5]
[Analyzing code quality]
✓ Code review completed for PR #42
Comment posted with:
  - Possible mistakes and improvements
  - Code quality suggestions
  - Best practices recommendations
```

**PR Comment Posted:**
```
## Code Review - PR #42

### Issues Found
1. Missing null check on line 15
2. Unused import on line 3
3. Potential NullPointerException in getUserData()

### Suggestions
- Add input validation for user IDs
- Consider using Optional<> instead of null checks
- Extract method complexity > 15 lines

### Best Practices
✓ Good exception handling
⚠ Consider logging levels
✗ Missing JavaDoc on public methods
```

### Example 3: Release Build with Auto-Fix
```bash
$ git checkout Release
$ # Jenkins UI: Manually trigger build for Release branch

Jenkins Output:
Release Branch: Building production release...
[1] Compile: Attempting Java compilation...
✗ Compilation failed - Attempting GPT-5 auto-fix...

[2] Auto-Fix: Invoking Azure OpenAI GPT-5...
[Analyzing compilation error: "cannot find symbol: variable userId"]
[Generating fix suggestion...]
[Applying fix to src/App.java]
✓ Auto-fix completed

[3] Verify: Recompiling after fix...
✓ Compilation successful - compilation now passes

[4] Package: Creating JAR file...
✓ JAR created successfully

[5] Test: Running tests...
✓ Tests passed

[6] Archive: Saving build artifacts...
✓ Build artifacts archived

========================================
SUCCESS: Release build completed
Artifacts: build/App.jar, build/classes/
========================================
```

**PR Summary Posted (if PR exists):**
```
## 🔧 Release Build Summary

**Timestamp:** 2024-01-19T14:32:45.123456

### Build Status
- **Initial Compilation:** ✗ Failed
- **Auto-Fix Applied:** ✓ Yes
- **Fix Verification:** ✓ Passed

### Artifacts Generated
- JAR file: `build/App.jar`
- Compiled classes: `build/classes/`

### Issue Fixed
Error: `cannot find symbol: variable userId`
Fix: Added proper variable initialization in line 42
```

## Security & Safety Features

### Confidence-Based Gating
- Only high-confidence errors (≥80%) are auto-fixed
- Low-confidence errors require manual review
- Prevents unsafe automatic changes

### Error Deduplication
- SHA256-based hash tracking
- Prevents infinite fix loops
- Maintains error history in `.fix_history.json`

### Retry Caps
- Maximum 2 fix attempts per build
- Prevents resource exhaustion
- Clear failure after max attempts

### Feature Flags
```bash
# Enable/disable auto-fix
export ENABLE_AUTO_FIX=true/false

# Control Azure OpenAI API calls
export ENABLE_OPENAI_CALLS=true/false

# Test mode without commits/pushes
export READ_ONLY_MODE=true/false
```

### Prompt Optimization
- Extracts error essence (reduces tokens by 99.2%)
- Sends ~200 tokens instead of 25,000+
- Reduces API costs and response time

## Setup Instructions

### Prerequisites
- Java 8+ (for compilation)
- Python 3.7+ (for automation scripts)
- Jenkins with Git plugin
- GitHub repository with webhook access

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git
   cd poc-auto-pr-fix
   ```

2. **Configure Jenkins Credentials**
   ```
   Manage Jenkins → Manage Credentials → Global
   
   Add Credentials:
   - AZURE_OPENAI_API_KEY (Secret text)
   - AZURE_OPENAI_ENDPOINT (Secret text)
   - GITHUB_PAT (Username/Password or Secret text)
   ```

3. **Create Jenkinsfile Pipeline Job**
   ```
   New Item → Multibranch Pipeline
   
   Configuration:
   - Display Name: poc-auto-pr-fix
   - Branch Sources: GitHub
   - Repository: vaibhavsaxena619/poc-auto-pr-fix
   - Behaviors: Discover branches, Discover PRs
   - Script Path: Jenkinsfile
   ```

4. **Add GitHub Webhook**
   ```
   GitHub Repository Settings → Webhooks
   
   Payload URL: https://your-jenkins-url/github-webhook/
   Content type: application/json
   Events: Push, Pull requests
   Active: ✓
   ```

5. **Install Python Dependencies**
   ```bash
   pip3 install openai requests --break-system-packages
   ```

## API Credentials Configuration

### Azure OpenAI Setup
1. Create Azure account at https://azure.microsoft.com/
2. Create OpenAI resource in Azure Portal
3. Get API Key and Endpoint from resource settings
4. Store in Jenkins credentials as noted above

### GitHub PAT Setup
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Create new fine-grained token with:
   - Permissions: `pull_requests:read`, `issues:write`
   - Repository access: Select poc-auto-pr-fix
3. Store in Jenkins credentials

## File Structure

```
poc-auto-pr-fix/
├── Jenkinsfile              # Jenkins pipeline definition
├── build_fix.py             # Auto-fix script for compilation errors
├── pr_review.py             # PR code review script
├── llm_fix.py               # LLM utilities (Azure OpenAI integration)
├── src/
│   └── App.java             # Sample Java application
├── build/                   # Build output directory
│   ├── classes/
│   └── App.jar
├── README.md                # This file
├── SECURITY.md              # Security guidelines
├── LOCAL_SETUP.md           # Local development setup
└── .fix_history.json        # Error deduplication history
```

## Scripts Description

### build_fix.py
Automatically fixes compilation errors in Java code using Azure OpenAI GPT-5.

**Usage:**
```bash
python3 build_fix.py <source_file>
```

**Features:**
- Detects compilation errors
- Classifies error confidence level
- Sends error to Azure OpenAI
- Applies fixes to source code
- Tracks error history to prevent loops

### pr_review.py
Performs automated code review on pull requests using Azure OpenAI GPT-5.

**Usage:**
```bash
python3 pr_review.py <pr_number> <target_branch> <source_branch>
```

**Features:**
- Fetches PR diff from GitHub
- Analyzes code quality
- Identifies potential issues
- Posts review comment with suggestions

### llm_fix.py
Core LLM integration module for Azure OpenAI communication.

**Features:**
- Azure OpenAI API client initialization
- Prompt engineering and optimization
- Token usage tracking
- Error handling and retries

## Monitoring & Logging

### Build Logs
- All pipeline logs available in Jenkins UI
- Detailed error messages for debugging
- Build artifacts stored in `build/` directory

### Error History
- Tracked in `.fix_history.json`
- Prevents duplicate fixes
- Helps identify recurring issues

### GitHub Comments
- Code review comments posted automatically
- Build summaries available in PR
- Full audit trail in GitHub history

## Troubleshooting

### Issue: "cannot find symbol: API key"
**Solution:** Verify AZURE_OPENAI_API_KEY credential is set in Jenkins

### Issue: "GitHub API 401 Unauthorized"
**Solution:** Regenerate GitHub PAT with correct permissions

### Issue: Auto-fix not being applied
**Solution:** 
- Check ENABLE_AUTO_FIX environment variable is `true`
- Verify error confidence level is ≥80%
- Check error history hasn't exceeded max retries

### Issue: Python module not found (openai)
**Solution:** Run in Jenkins shell step:
```bash
pip3 install openai requests --quiet --break-system-packages
```

## Performance Metrics

- **Code Review Time:** ~2-5 seconds per PR
- **Auto-Fix Time:** ~3-8 seconds per error
- **API Cost:** ~$0.01 per review, ~$0.02 per fix
- **Token Usage:** ~200 tokens per request (optimized)

## Best Practices

1. **Dev_Poc_V1 Usage:** Use for daily development without build constraints
2. **PR Process:** Always create PR to Release for code review
3. **Release Builds:** Trigger manually only when ready for production
4. **Auto-Fix Review:** Always review auto-fix changes in code review
5. **Error Handling:** Check build logs for error details before re-triggering

## Contributing

1. Clone and create feature branch from Dev_Poc_V1
2. Make code changes
3. Push to Dev_Poc_V1 (no build validation)
4. Create PR to Release for automated code review
5. Address review comments
6. Merge after PR approval

## License

MIT License - See LICENSE file for details

## Support

- **Issues:** GitHub Issues page
- **Documentation:** SECURITY.md, LOCAL_SETUP.md
- **Contact:** vaibhavsaxena619@example.com

---

**Last Updated:** January 19, 2024  
**Version:** 2.0 (Dev_Poc_V1 + Release Branch Strategy)  
**Status:** Production Ready ✓
