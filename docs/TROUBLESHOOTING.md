# Jenkins PR Automation Troubleshooting Guide

## Issue: Jenkins not triggering automatically on PR creation

### Step 1: Verify Jenkins Job Configuration

**Create Multibranch Pipeline Job (Not Regular Pipeline!):**

1. **Jenkins → New Item**
   - Item name: `poc-java-pr-workflow`  
   - Type: **Multibranch Pipeline** (NOT Pipeline!)
   - Click OK

2. **Configure Branch Sources:**
   ```
   Branch Sources → Add source → GitHub
   - Repository HTTPS URL: https://github.com/vaibhavsaxena619/poc-auto-pr-fix.git
   - Credentials: github-pat (your GitHub PAT)
   ```

3. **Configure Behaviors (CRITICAL):**
   ```
   Behaviors → Add:
   ✅ Discover branches
   ✅ Discover pull requests from origin
      - Strategy: "Merging the pull request with the current target branch revision"
   ✅ Discover pull requests from forks  
      - Strategy: "Merging the pull request with the current target branch revision"
      - Trust: "From users with Admin or Write permission"
   ```

4. **Property Strategy:**
   ```
   ✅ All branches get the same properties
   ```

5. **Build Configuration:**
   ```
   Mode: by Jenkinsfile
   Script Path: Jenkinsfile
   ```

6. **Scan Repository Triggers:**
   ```
   ✅ Periodically if not otherwise run
   Interval: 1 minute (for testing, change to 15 minutes later)
   ```

### Step 2: Verify GitHub Webhook Configuration

1. **Go to GitHub Repository:**
   - https://github.com/vaibhavsaxena619/poc-auto-pr-fix
   - Settings → Webhooks

2. **Add Webhook:**
   ```
   Payload URL: http://YOUR_JENKINS_IP:8080/github-webhook/
   Content Type: application/json
   SSL verification: Disable SSL verification (if using HTTP)
   
   Events:
   ✅ Pull requests
   ✅ Pushes  
   ✅ Pull request reviews
   ✅ Pull request review comments
   
   Active: ✅
   ```

### Step 3: Test Manual Scan

1. **In Jenkins Job:**
   - Click "Scan Repository Now"
   - Check console output for errors

2. **Expected Output:**
   ```
   Checking branch main
   Checking pull requests
   Found pull request #X: feature-branch -> master
   ```

### Step 4: Create Test PR

1. **Create a test branch:**
   ```bash
   git checkout -b test-jenkins-pr
   echo "// Test change for Jenkins PR" >> src/App.java
   git add .
   git commit -m "Test: Jenkins PR automation"
   git push origin test-jenkins-pr
   ```

2. **Create PR on GitHub:**
   - test-jenkins-pr → master
   - Title: "Test Jenkins PR Automation"

3. **Check Jenkins:**
   - Should automatically detect PR within 1-2 minutes
   - Look for new branch in multibranch job

### Step 5: Debug Common Issues

**A. No PR Detection:**
```bash
# Check Jenkins logs:
1. Jenkins → Manage → System Log
2. Look for GitHub webhook entries
3. Check multibranch scan logs
```

**B. Webhook Not Received:**
```bash
# In GitHub:
1. Settings → Webhooks → Your webhook
2. Click "Recent Deliveries"  
3. Check response codes (should be 200)
4. If 404/500 errors, check Jenkins URL
```

**C. Missing Environment Variables:**
```bash
# In Jenkinsfile, add debug stage:
stage('Debug') {
    steps {
        script {
            echo "All Environment Variables:"
            bat 'set'  // Windows
            // sh 'env'  // Linux
        }
    }
}
```

**D. Credentials Issues:**
```bash
# Check GitHub PAT permissions:
✅ repo (Full control of private repositories)
✅ admin:repo_hook (Admin access to repository hooks)  
✅ read:org (Read org and team membership)
```

### Step 6: Verify Plugins

**Required Jenkins Plugins:**
```
1. GitHub Branch Source Plugin
2. Pipeline: Multibranch Plugin  
3. GitHub Integration Plugin
4. Generic Webhook Trigger Plugin (optional)
```

**Install via:**
- Jenkins → Manage → Plugin Manager → Available

### Step 7: Test Command

**Run in Jenkins workspace or locally:**
```bash
# Windows:
test_jenkins_pr.bat

# Linux/Mac:  
./test_jenkins_pr.sh
```

### Step 8: Expected Workflow After Fix

1. **Create PR:** `main` → `master`
2. **Jenkins detects:** Within 1-2 minutes  
3. **Build starts:** Multibranch job shows new PR branch
4. **PR Review runs:** Gemini analyzes code, posts comments
5. **Status visible:** In GitHub PR checks section

### Quick Fix Checklist:

- [ ] Job type is **Multibranch Pipeline** (not Pipeline)
- [ ] "Discover pull requests from origin" behavior enabled
- [ ] GitHub webhook URL correct with `/github-webhook/`  
- [ ] GitHub PAT has `repo` and `admin:repo_hook` permissions
- [ ] Webhook events include "Pull requests"
- [ ] Jenkins can reach GitHub (firewall/network check)
- [ ] No proxy issues blocking webhook delivery

Run through these steps and let me know which specific step is failing!