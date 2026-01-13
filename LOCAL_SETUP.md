# Local Environment Setup

This file documents the local-only setup needed for this project.

## Local-Only Files (Not in Git)

Keep these files in your local environment only. They are listed in `.gitignore`:

### 1. JENKINS_CREDENTIALS.md
- Contains sensitive credential setup information
- Do NOT push to GitHub
- Refers to Jenkins credential IDs and API keys
- Keep locally for reference during Jenkins configuration

### 2. REFACTORING_SUMMARY.md
- Historical documentation of refactoring process
- Local reference for development team
- Not needed in production repository

### 3. PRODUCTION_READINESS.md
- Verification checklist from initial refactoring
- Local reference for validation history
- Can be regenerated if needed

### 4. build/ Directory
- Compilation output and artifacts
- Gitignore prevents tracking
- Safe to delete and regenerate

## Setup Your Local Environment

### 1. Install Python Dependencies
```bash
pip install google-genai requests
```

### 2. Set Environment Variables (for testing locally)
```bash
# Windows PowerShell
$env:GEMINI_API_KEY = "your-gemini-api-key"
$env:GITHUB_PAT = "your-github-pat"
$env:REPO_OWNER = "vaibhavsaxena619"
$env:REPO_NAME = "poc-auto-pr-fix"

# Or in Windows CMD
set GEMINI_API_KEY=your-gemini-api-key
set GITHUB_PAT=your-github-pat
```

### 3. Create Local Credentials File (Optional)
For easier management, create a `.env` file (not tracked by git):
```
GEMINI_API_KEY=your-api-key
GITHUB_PAT=your-token
REPO_OWNER=vaibhavsaxena619
REPO_NAME=poc-auto-pr-fix
```

Then load with:
```bash
# In Python scripts, use python-dotenv
from dotenv import load_dotenv
load_dotenv()
```

### 4. Configure Jenkins (Production)
See `JENKINS_CREDENTIALS.md` for:
- Creating Jenkins credentials
- Setting credential IDs
- Configuring GitHub webhook

## Directory Structure After Setup

```
GitAutomationTesting/
├── .gitignore                          # Ignore local files
├── README.md                            # Main documentation
├── Jenkinsfile                          # Pipeline definition
├── pr_review.py                        # PR review script
├── build_fix.py                        # Error recovery
├── llm_fix.py                          # Reference script
├── src/
│   └── App.java
├── docs/
│   ├── QUICKSTART.md                   # 5-minute setup
│   └── TROUBLESHOOTING.md              # Issue resolution
├── build/                              # Generated locally, not in git
│   ├── classes/
│   └── App.jar
├── JENKINS_CREDENTIALS.md              # Local only (sensitive)
├── PRODUCTION_READINESS.md             # Local only (reference)
└── REFACTORING_SUMMARY.md              # Local only (reference)
```

## Git Best Practices

### Pull Fresh Copy
```bash
git clone https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git
cd poc-auto-pr-fix
```

### Create Your Local Files
```bash
# These will NOT be tracked by git
cp JENKINS_CREDENTIALS.md.template JENKINS_CREDENTIALS.md  # If available
# Or keep from your local environment
```

### Never Accidentally Commit Local Files
```bash
# Check what would be committed
git status

# Files in .gitignore should NOT appear
# If they do, they were already tracked before .gitignore was added
# (already handled by git rm --cached)
```

### Update Git If Needed
```bash
# If local files still appear in git status
git rm --cached <filename>
git commit -m "Remove file from tracking"
```

## Jenkins Configuration File

To share Jenkins configuration safely, create a `setup-jenkins.sh` or `setup-jenkins.bat`:

```groovy
// Jenkins Configuration as Code (not in repository)
credentials {
  string {
    id = 'GEMINI_API_KEY_CREDENTIAL'
    secret = '${GEMINI_API_KEY}'
    description = 'Gemini API Key'
  }
  usernamePassword {
    id = 'GITHUB_PAT_CREDENTIAL'
    username = '${GITHUB_USERNAME}'
    password = '${GITHUB_PAT}'
    description = 'GitHub PAT'
  }
}
```

Store this locally, apply manually, or use Jenkins Configuration as Code plugin.

## Team Onboarding

When new team members join:

1. **Clone Repository**
   ```bash
   git clone <repo-url>
   cd poc-auto-pr-fix
   ```

2. **Read Setup Instructions**
   ```bash
   cat docs/QUICKSTART.md
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt  # When created
   ```

4. **Configure Locally**
   - Get credentials from Jenkins admin (never in git)
   - Set environment variables
   - Test with `python pr_review.py` (optional)

5. **Start Using Pipeline**
   - Push to branches
   - Jenkins automatically handles the rest

## Troubleshooting Local Setup

### "Module not found" Error
```bash
pip install google-genai requests --upgrade
```

### "Credential not found" in Jenkins
- Verify credentials exist in Jenkins UI
- Check credential IDs match (GEMINI_API_KEY_CREDENTIAL, GITHUB_PAT_CREDENTIAL)
- See `JENKINS_CREDENTIALS.md`

### Need to Test Scripts Locally
```bash
# Set environment variables first
set GEMINI_API_KEY=test-key
python pr_review.py 123 master feature-branch
```

---

**Remember:** Git tracks code only. Local configuration stays local. This is the proper production pattern!
