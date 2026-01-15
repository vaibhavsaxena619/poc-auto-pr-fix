# Quick Start Guide

## 5-Minute Setup

### Step 1: Create Jenkins Credentials (3 minutes)

**In Jenkins UI:**

1. Go to `Manage Jenkins` → `Manage Credentials` → `System`
2. Click "Add Credentials"
   - **Kind:** Secret text
   - **Secret:** [Paste your Gemini API key from https://aistudio.google.com/app/apikey]
   - **ID:** `GEMINI_API_KEY_CREDENTIAL`
   - **Save**

3. Click "Add Credentials" again
   - **Kind:** Username with password
   - **Username:** [Your GitHub username]
   - **Password:** [Your GitHub PAT from https://github.com/settings/tokens]
   - **ID:** `GITHUB_PAT_CREDENTIAL`
   - **Save**

✅ **Done** - Credentials configured

---

### Step 2: Create GitHub Webhook (2 minutes)

**In GitHub Repository:**

1. Go to `Settings` → `Webhooks` → `Add webhook`
2. **Payload URL:** `http://your-jenkins-server:8080/github-webhook/`
3. **Content type:** `application/json`
4. **Which events would you like to trigger this webhook?**
   - Select "Let me select individual events"
   - ✅ Push events
   - ✅ Pull requests
5. **Save**

✅ **Done** - Webhook configured

---

### Step 3: Test the Pipeline (Verify it works)

**Test 1 - Main Branch:**
```bash
git push origin main
# Check Jenkins: Should compile successfully
```

**Test 2 - PR Code Review:**
```bash
git checkout -b feature/test-pr
echo "// test comment" >> src/App.java
git add . && git commit -m "Test PR"
git push origin feature/test-pr
# Go to GitHub, create PR to master
# Jenkins will post a code review comment
```

✅ **Done** - Pipeline is working!

---

## Key Files to Know

| File | Purpose | When to Read |
|------|---------|--------------|
| [README.md](README.md) | Full documentation | Before deploying |
| [JENKINS_CREDENTIALS.md](JENKINS_CREDENTIALS.md) | Credential setup guide | During setup |
| [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) | What changed | For details |
| [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) | Verification checklist | Post-deployment |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Problem solving | When issues arise |
| [Jenkinsfile](Jenkinsfile) | Pipeline definition | For technical details |

---

## What Happens Now?

### When you push to **main**:
```
main branch push
    └─→ Jenkins webhook triggered
        └─→ Compiles Java code
            ├─ Success: Build passes
            └─ Failure: Build fails (no auto-fix)
```

### When you create a **PR to master**:
```
PR created (target: master)
    └─→ Jenkins webhook triggered
        └─→ Gemini AI analyzes your code
            └─→ Posts review comment with:
                - Code analysis
                - Suggestions
                - Author mention (@yourname)
```

### When you push to **master**:
```
master branch push
    └─→ Jenkins webhook triggered
        └─→ Compiles Java code
            ├─ Success: Continue
            │   ├─ Creates JAR
            │   ├─ Runs tests
            │   └─ Archives artifacts
            └─ Failure: Gemini error recovery
                ├─ Analyzes error
                ├─ Applies fix
                ├─ Commits fix
                └─ Retries compilation
```

---

## Common Commands

```bash
# View pipeline status
git log --oneline

# Create a feature branch
git checkout -b feature/my-feature

# Push your changes
git push origin feature/my-feature

# Create PR on GitHub
# (Then Jenkins automatically reviews it)

# Sync with latest
git pull origin main

# Check Jenkins build logs
# Jenkins UI → Project → Build number → Console Output
```

---

## Troubleshooting Quick Links

**Credentials not working?**
→ [JENKINS_CREDENTIALS.md](JENKINS_CREDENTIALS.md) - Credential setup section

**Code review not posting?**
→ [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - PR Comments Not Posting

**Build keeps failing?**
→ [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - Build Failures

**Need full details?**
→ [README.md](README.md) - Complete documentation

---

## Next Steps

1. ✅ Set up credentials (done above)
2. ✅ Create webhook (done above)
3. ✅ Test the pipeline (done above)
4. → **Production ready!** Push your code and let Jenkins handle it

---

## Support

- **Documentation:** [README.md](README.md)
- **Credential Setup:** [JENKINS_CREDENTIALS.md](JENKINS_CREDENTIALS.md)
- **Issues:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- **Verification:** [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)

---

**Status:** ✅ Ready to use!
