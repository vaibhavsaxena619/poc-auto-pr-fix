# Local Environment Setup

Production-ready setup guide for Java CI/CD Automation with Azure OpenAI GPT-5.

## Prerequisites

- **Java:** Version 8 or higher
- **Python:** Version 3.7 or higher  
- **Git:** Latest version
- **Jenkins:** 2.300+
- **Azure Subscription:** For OpenAI API access
- **GitHub Account:** With repository access

## Step 1: Install Python Dependencies

```bash
# Using pip (recommended)
pip install -U openai requests

# Or with specific version
pip install openai==1.3.0 requests==2.31.0

# For Windows with system packages
pip install openai requests --break-system-packages
```

## Step 2: Configure Azure OpenAI Credentials

### Get Your Credentials

1. **Sign in to Azure Portal:** https://portal.azure.com
2. **Create OpenAI Resource:**
   - Click "Create a resource"
   - Search "OpenAI"
   - Click "Create"
3. **Get API Key:**
   - Go to resource → Keys and endpoints
   - Copy key 1 or key 2
   - Copy endpoint URL
4. **Get API Version:** Use `2024-12-01-preview` (latest)

### Set Environment Variables

**Windows PowerShell:**
```powershell
$env:AZURE_OPENAI_API_KEY = "your-api-key-here"
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_VERSION = "2024-12-01-preview"
$env:AZURE_OPENAI_DEPLOYMENT_NAME = "gpt-5"
```

**Windows CMD:**
```cmd
set AZURE_OPENAI_API_KEY=your-api-key-here
set AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
set AZURE_OPENAI_API_VERSION=2024-12-01-preview
set AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5
```

**Linux/macOS:**
```bash
export AZURE_OPENAI_API_KEY="your-api-key-here"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_VERSION="2024-12-01-preview"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5"
```

**Permanent Setup (.bashrc or .zshrc):**
```bash
echo 'export AZURE_OPENAI_API_KEY="your-api-key"' >> ~/.bashrc
echo 'export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"' >> ~/.bashrc
source ~/.bashrc
```

## Step 3: Configure GitHub PAT

### Create Fine-Grained Personal Access Token

1. **GitHub Settings:** https://github.com/settings/tokens?type=beta
2. **Click "Generate new token"**
3. **Configure:**
   - **Token name:** `Jenkins-CI-CD-Automation`
   - **Expiration:** 90 days (recommended)
   - **Repository access:** Select `poc-auto-pr-fix`
   - **Permissions:**
     - `pull_requests`: Read and write
     - `issues`: Read and write
     - `contents`: Read
4. **Copy token and store securely**

### Store in Environment Variables

**Windows PowerShell:**
```powershell
$env:GITHUB_PAT = "github_pat_XXXXX..."
$env:REPO_OWNER = "vaibhavsaxena619"
$env:REPO_NAME = "poc-auto-pr-fix"
```

**Linux/macOS:**
```bash
export GITHUB_PAT="github_pat_XXXXX..."
export REPO_OWNER="vaibhavsaxena619"
export REPO_NAME="poc-auto-pr-fix"
```

## Step 4: Clone Repository

```bash
git clone https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git
cd poc-auto-pr-fix
```

## Step 5: Test Local Setup

### Verify Python Installation

```bash
python3 --version
pip list | grep openai
```

### Test Credentials

```bash
python3 build_fix_v2.py src/App.java
```

**Expected Output:**
```
[2026-01-22T12:34:56.789] Build fix initiated for src/App.java
✗ Compilation errors detected
  Found 4 error(s)
  ✓ HIGH-CONFIDENCE: safe:missing_import (90%)
  ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
  ...
```

## Step 6: Jenkins Configuration

### Create Jenkins Credentials

1. **Jenkins URL:** Navigate to `http://your-jenkins:8080`
2. **Manage Jenkins → Manage Credentials → Global**
3. **Add "Secret text" credential:**
   - **ID:** `AZURE_OPENAI_API_KEY`
   - **Secret:** Your Azure OpenAI API key
4. **Add "Secret text" credential:**
   - **ID:** `AZURE_OPENAI_ENDPOINT`
   - **Secret:** Your Azure OpenAI endpoint
5. **Add "Username with password" credential:**
   - **ID:** `github-pat`
   - **Username:** `vaibhavsaxena619`
   - **Password:** Your GitHub PAT

### Create Multibranch Pipeline Job

1. **New Item → Multibranch Pipeline**
2. **Configuration:**
   - **Display name:** `poc-java-pr-workflow`
   - **Branch Sources → GitHub:**
     - **Repository HTTPS URL:** `https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git`
     - **Credentials:** `github-pat`
   - **Discover branches:** `All branches`
   - **Discover pull requests from:**
     - Origin: `PRs merged to target branch`
     - Forks: `PRs from forks`
   - **Script path:** `Jenkinsfile`

3. **Save and Jenkins will automatically scan branches**

### Configure GitHub Webhook

1. **GitHub Repo → Settings → Webhooks**
2. **Add webhook:**
   - **Payload URL:** `http://your-jenkins:8080/github-webhook/`
   - **Content type:** `application/json`
   - **Events:** `Push events`, `Pull request events`
   - **Active:** ✓ Check

## Step 7: Enable Pipeline Features

### Set Build Environment Variables

In Jenkins job configuration:

**Build Environment:**
- Check "Use secret text(s) or files"
- Add bindings:
  - **Secret text:** `AZURE_OPENAI_API_KEY` → Credential: `AZURE_OPENAI_API_KEY`
  - **Secret text:** `AZURE_OPENAI_ENDPOINT` → Credential: `AZURE_OPENAI_ENDPOINT`
  - **Username and password:** Credential: `github-pat`

### Pipeline Parameters (Optional)

Add to Jenkinsfile for flexibility:

```groovy
parameters {
    booleanParam(name: 'ENABLE_AUTO_FIX', defaultValue: true, description: 'Enable GPT auto-fix')
    booleanParam(name: 'ENABLE_OPENAI_CALLS', defaultValue: true, description: 'Enable Azure OpenAI calls')
}
```

## Step 8: Verify Setup

### Local Test

```bash
# Test compilation error handling
python3 build_fix_v2.py src/App.java
```

### Jenkins Test

1. **Manual Trigger:** Jenkins UI → `poc-java-pr-workflow` → Release → "Build Now"
2. **Automatic Trigger:** Create PR from Dev_Poc_V1 to Release
3. **Observe Console Output:**
   ```
   ✓ Compile: Attempt Java compilation
   ✓ Error Detection: Parse errors
   ✓ Classification: Split HIGH/LOW
   ✓ Auto-Fix: Apply fixes
   ✓ Verify: Confirm compilation
   ✓ Success: Build completes
   ```

## File Structure

```
poc-auto-pr-fix/
├── README.md                 # Main documentation
├── LOCAL_SETUP.md           # This file
├── Jenkinsfile              # Pipeline definition
├── build_fix_v2.py          # Auto-fix engine (PRODUCTION)
├── src/App.java             # Sample Java application
├── .env.example             # Example environment variables
├── .gitignore               # Git ignore rules
├── build/                   # Build artifacts (local only)
│   ├── classes/
│   └── App.jar
└── docs/                    # Additional documentation
```

## Environment Variables Summary

| Variable | Required | Example |
|---|---|---|
| AZURE_OPENAI_API_KEY | ✓ | `sk-...` |
| AZURE_OPENAI_ENDPOINT | ✓ | `https://....openai.azure.com/` |
| AZURE_OPENAI_API_VERSION | ✓ | `2024-12-01-preview` |
| AZURE_OPENAI_DEPLOYMENT_NAME | ✓ | `gpt-5` |
| GITHUB_PAT | ✓ | `github_pat_...` |
| REPO_OWNER | ✓ | `vaibhavsaxena619` |
| REPO_NAME | ✓ | `poc-auto-pr-fix` |
| ENABLE_AUTO_FIX | ✗ | `true` |
| ENABLE_OPENAI_CALLS | ✗ | `true` |
| READ_ONLY_MODE | ✗ | `false` |

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'openai'"

**Solution:**
```bash
pip install openai --upgrade
# Or for system packages:
pip install openai --break-system-packages
```

### Issue: "401 Unauthorized" from Azure OpenAI

**Check:**
1. Is API key correct? (No extra spaces)
2. Is endpoint correct? (Has trailing `/`)
3. Does API key have correct permissions?
4. Is resource region correct?

**Solution:**
```bash
# Re-verify credentials from Azure Portal
# Copy API key and endpoint again carefully
# Set environment variables and test
```

### Issue: "GitHub API 401 Unauthorized"

**Check:**
1. Is GitHub PAT correct and not expired?
2. Does PAT have `pull_requests` and `issues` permissions?
3. Is repository access correct?

**Solution:**
```bash
# Generate new GitHub PAT with correct permissions
# Update Jenkins credentials
# Re-trigger build
```

### Issue: "Build fails at auto-fix stage"

**Check:**
1. Are environment variables set?
   ```bash
   echo $AZURE_OPENAI_API_KEY
   echo $GITHUB_PAT
   ```
2. Can Python import openai?
   ```bash
   python3 -c "from openai import AzureOpenAI; print('OK')"
   ```
3. Are credentials correct in Jenkins?

### Issue: PR not being created

**Check:**
1. Is GitHub PAT valid? Check expiration date
2. Does token have repo write permissions?
3. Are GitHub credentials in Jenkins?
4. Check Jenkins logs for API errors

## Production Deployment Checklist

- [ ] Java 8+ installed and in PATH
- [ ] Python 3.7+ installed
- [ ] openai and requests packages installed
- [ ] Azure OpenAI credentials obtained and stored
- [ ] GitHub PAT created with correct permissions
- [ ] Repository cloned locally
- [ ] Jenkins installed and running
- [ ] Jenkins credentials configured
- [ ] Multibranch pipeline job created
- [ ] GitHub webhook configured
- [ ] Local test: `python3 build_fix_v2.py src/App.java` works
- [ ] Jenkins test: Release build completes successfully
- [ ] PR test: Create PR and verify code review

## Security Best Practices

✅ **DO:**
- Store credentials in Jenkins only (never in code)
- Use GitHub PAT with minimal permissions
- Rotate credentials every 90 days
- Use HTTPS for Jenkins and API calls
- Enable Jenkins API token instead of username/password

❌ **DON'T:**
- Commit credentials to Git
- Use generic GitHub tokens (use fine-grained)
- Store passwords in environment variables permanently
- Share Jenkins credentials between users
- Enable public build logs with credentials

## Support & Debugging

### Enable Debug Logging

**In Jenkinsfile:**
```groovy
sh '''
    export DEBUG=1
    python3 build_fix_v2.py src/App.java
'''
```

### Check Build Logs

```bash
# Jenkins UI: Click "Console Output" on build
# Or local file:
tail -f $JENKINS_HOME/jobs/poc-java-pr-workflow/builds/lastBuild/log
```

### Test Python Script Directly

```bash
# Set debug mode
export DEBUG=1
python3 -u build_fix_v2.py src/App.java 2>&1 | tee debug.log
```

## Next Steps

1. ✅ Complete setup steps above
2. ✅ Run local test: `python3 build_fix_v2.py src/App.java`
3. ✅ Push to Dev_Poc_V1: `git push origin Dev_Poc_V1`
4. ✅ Create PR to Release in GitHub
5. ✅ Trigger Release build in Jenkins
6. ✅ Verify output and PR creation
7. ✅ Review build logs and PR comments

## References

- [README.md](README.md) - Project overview
- [Azure OpenAI Documentation](https://learn.microsoft.com/en-us/azure/ai-services/openai/)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [Jenkins Documentation](https://www.jenkins.io/doc/)

---

**Status:** ✅ Production Ready  
**Last Updated:** January 22, 2026
