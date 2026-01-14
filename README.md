# Java CI/CD Automation with Gemini AI

Enterprise-grade Jenkins pipeline with automated code review and build error recovery powered by Google Gemini AI.

## Project Overview

This project implements a production-ready CI/CD automation system for Java applications with:
- **PR Code Review:** Automated AI-powered code analysis for pull requests to master
- **Master Build Recovery:** Automatic error detection and repair using Gemini AI
- **Branch-Specific Workflows:** Tailored pipelines for main, master, and feature branches
- **GitHub Integration:** Seamless PR commenting and commit operations

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                       │
│                  poc-auto-pr-fix (master)                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─ PR Created (PR Branch → master)
                       │   └─→ Jenkins Webhook Triggered
                       │       └─→ Code Review Stage
                       │           ├─ Fetch PR diff
                       │           ├─ Send to Gemini AI
                       │           └─ Post review comment + author tag
                       │
                       ├─ Push to main Branch
                       │   └─→ Jenkins Build Triggered
                       │       └─→ Main Branch Build
                       │           ├─ Compile only (no auto-fix)
                       │           └─ Fail if errors (push nothing)
                       │
                       └─ Push to master Branch
                           └─→ Jenkins Build Triggered
                               └─→ Master Branch Build
                                   ├─ Compile Java code
                                   │   └─ On Failure → Gemini Error Analysis
                                   │       ├─ Analyze error + source
                                   │       ├─ Apply fixes
                                   │       └─ Retry compilation
                                   ├─ Create JAR file
                                   ├─ Run tests
                                   └─ Archive artifacts
```

## Workflow Stages

### 1. Pull Request Code Review (Master PRs Only)

**Trigger:** PR created with master as target branch  
**Condition:** `changeRequest() && env.CHANGE_TARGET == 'master'`

**Process:**
1. Jenkins webhook detects PR
2. Fetches code diff between branches
3. Sends diff to Gemini AI for analysis
4. Posts comprehensive review comment with:
   - Files changed count
   - Lines added/deleted
   - Architecture assessment
   - Author mention (@username)

**Scripts:** `pr_review.py`  
**Credentials:** `GEMINI_API_KEY_CREDENTIAL`, `GITHUB_PAT_CREDENTIAL`

### 2. Main Branch Build

**Trigger:** Commits to main branch  
**Condition:** `branch('main')`

**Process:**
1. Checkout code
2. Compile Java source
3. Fail if compilation errors (no auto-fix)
4. No push back to repository

**Purpose:** Simple build verification without automated changes

### 3. Master Branch Production Build

**Trigger:** Commits to master branch (non-PR)  
**Condition:** `branch('master') && !changeRequest()`

**Process:**

#### Stage A: Compilation
```
Compile Java -> Success? 
  ├─ YES -> Continue to JAR creation
  └─ NO -> Error Recovery
       ├─ Capture error message
       ├─ Send to Gemini AI
       ├─ Apply fixes automatically
       ├─ Retry compilation
       └─ Success? -> Continue or fail build
```

#### Stage B: JAR Creation
```
javac -d build/classes src/App.java
jar cfe build/App.jar App build/classes/*.class
```

#### Stage C: Testing
```
java -cp build/classes App
```

#### Stage D: Artifact Archival
```
Archive: build/App.jar, build/classes/
Available for download in Jenkins
```

**Scripts:** `build_fix.py` (for error recovery)  
**Credentials:** `GEMINI_API_KEY_CREDENTIAL`, `GITHUB_PAT_CREDENTIAL`

### 4. Feature Branch Build

**Trigger:** Commits to branches other than main/master  
**Condition:** `not(branch('main') || branch('master'))`

**Process:**
1. Checkout code
2. Compile Java
3. Fail if errors (no recovery)

## Quick Start

For a **5-minute setup**, see [docs/QUICKSTART.md](docs/QUICKSTART.md)

## Setup Instructions

### Prerequisites
- Jenkins with GitHub plugin configured
- Java compiler (javac) installed
- Python 3.8+
- Git installed

### 1. Install Dependencies

```bash
pip install google-genai requests
```

### 2. Configure Jenkins Credentials

**Important:** Keep `JENKINS_CREDENTIALS.md` in your local environment only (in .gitignore).

To set up credentials:
1. Create Gemini API key at https://aistudio.google.com/app/apikey
2. Create GitHub PAT at https://github.com/settings/tokens (scopes: `repo`, `workflow`)
3. In Jenkins:
   - Add credential with ID: `GEMINI_API_KEY_CREDENTIAL` (secret text)
   - Add credential with ID: `GITHUB_PAT_CREDENTIAL` (username + password)

### 3. Configure GitHub Webhook

In GitHub repository Settings → Webhooks:

**Payload URL:** `http://jenkins-server:8080/github-webhook/`  
**Events:** Push events + Pull request events  
**Content type:** application/json

### 4. Create Jenkins Multibranch Pipeline

1. Jenkins → New Item → Multibranch Pipeline
2. Name: `poc-auto-pr-fix`
3. Branch Sources → GitHub
   - Repository: `vaibhavsaxena619/poc-auto-pr-fix`
   - Credentials: Select GitHub PAT credential
4. Build Configuration
   - Mode: by Jenkinsfile
   - Script path: `Jenkinsfile`
5. Save

### 5. Test the Pipeline

**Test PR Review:**
```bash
git checkout -b feature/test-pr
git push origin feature/test-pr
# Create PR to master in GitHub
```

**Test Master Build:**
```bash
git push origin master
```

## File Structure

```
.
├── Jenkinsfile                 # Jenkins pipeline definition
├── pr_review.py               # GitHub PR code review script
├── build_fix.py               # Master build error recovery
├── llm_fix.py                 # Auto-fix for errors (reference)
├── README.md                  # This file
├── .gitignore                 # Git ignore patterns
├── src/
│   └── App.java               # Sample Java application
├── build/                      # Build artifacts (local only, not in git)
│   ├── classes/               # Compiled .class files
│   └── App.jar               # Packaged JAR
└── docs/                       # Documentation (in git)
    ├── QUICKSTART.md          # 5-minute setup guide
    └── TROUBLESHOOTING.md     # Issue resolution

LOCAL ONLY (in .gitignore):
├── JENKINS_CREDENTIALS.md     # Credential setup (sensitive)
├── PRODUCTION_READINESS.md    # Verification checklist
├── REFACTORING_SUMMARY.md     # Historical changes
└── build/                      # Build artifacts
```

## Environment Variables

The pipeline automatically injects these via credentials:

```groovy
GEMINI_API_KEY      # Gemini API authentication
GITHUB_USERNAME     # GitHub account username
GITHUB_PAT          # GitHub personal access token
BRANCH_NAME         # Current git branch
CHANGE_ID           # PR number (if PR)
CHANGE_TARGET       # PR target branch (if PR)
CHANGE_BRANCH       # PR source branch (if PR)
CHANGE_AUTHOR       # PR author (if PR)
```

## Scripts Documentation

### pr_review.py
**Purpose:** Analyzes pull requests and posts code reviews to GitHub

**Usage:**
```bash
python pr_review.py <pr_number> <target_branch> <source_branch>
```

**Requires:**
- `GEMINI_API_KEY` environment variable
- `GITHUB_PAT` environment variable
- `REPO_OWNER` and `REPO_NAME` environment variables (or defaults to hardcoded)

**Output:** Posts comment on GitHub PR with:
- Code review analysis
- Files changed summary
- Author mention

### build_fix.py
**Purpose:** Analyzes compilation errors and applies Gemini-suggested fixes

**Usage:**
```bash
python build_fix.py <source_file>
```

**Example:**
```bash
GEMINI_API_KEY=your_key python build_fix.py src/App.java
```

**Process:**
1. Attempts to compile source file
2. Captures error message
3. Sends error to Gemini AI
4. Applies suggested fix
5. Retries compilation
6. Commits changes if successful

**Requires:**
- `GEMINI_API_KEY` environment variable
- Git repository initialized

## Troubleshooting

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues:
- Credentials errors
- API failures
- Git operations failing
- Build step timeouts

## Security Considerations

1. **Credential Rotation:** Rotate Gemini API keys quarterly
2. **GitHub PAT Scopes:** Use minimal required scopes (`repo`, `workflow`)
3. **API Rate Limiting:** Gemini has rate limits; monitor API usage
4. **Code Review:** Human review recommended before merging PRs
5. **Logs:** Build logs may contain sensitive info; restrict access

## Performance Tuning

**Code Review Speed:**
- Default timeout: 30 seconds
- Gemini model: gemini-1.5-flash (fast variant)

**Build Time:**
- Compilation: 2-5 seconds per file
- JAR creation: 1 second
- Tests: 2-3 seconds

**Error Recovery:**
- Gemini analysis: 5-10 seconds
- Auto-fix application: 1 second
- Retry compilation: 2-5 seconds

## API Rate Limits

**Gemini API:**
- Free tier: 15 requests/minute, 500,000 requests/day
- Paid tier: Higher limits based on plan

**GitHub API:**
- Authenticated: 5,000 requests/hour
- Per PR: 10-20 requests (typical)

## Monitoring and Alerts

**Jenkins Setup:**
- Configure email notifications for failures
- Monitor build history in Jenkins UI
- Check logs for error details

**GitHub:**
- PR comments indicate review status
- Check commit messages for auto-fixes

## Known Limitations

1. **Java Only:** Currently configured for Java projects
2. **Single File Focus:** Works best with single Java file projects
3. **No Parallel Builds:** Sequential master builds for consistency
4. **GitHub Only:** Designed for GitHub repositories

## References

- [Gemini AI API Documentation](https://ai.google.dev/tutorials)
- [GitHub API Reference](https://docs.github.com/en/rest)
- [Jenkins Documentation](https://www.jenkins.io/doc/)
- [Java Compiler Documentation](https://docs.oracle.com/javase/8/docs/technotes/tools/windows/javac.html)

## License

This project is provided as-is for CI/CD automation purposes.

## Support

For issues or questions:
1. Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Review Jenkins build logs
3. For credential setup: See `JENKINS_CREDENTIALS.md` in your local environment
4. Check GitHub webhook delivery logs
/ /   e 2 e   t e s t  
 