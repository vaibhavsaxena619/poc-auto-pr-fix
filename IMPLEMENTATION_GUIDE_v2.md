# COMPREHENSIVE IMPLEMENTATION GUIDE
## Enhanced CI/CD System with Fault Detection & Self-Learning

**Date:** January 28, 2026  
**Status:** PRODUCTION-READY  
**Version:** 2.0

---

## TABLE OF CONTENTS
1. [Overview](#overview)
2. [New Components](#new-components)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Usage Examples](#usage-examples)
6. [Integration Points](#integration-points)
7. [Troubleshooting](#troubleshooting)
8. [Monitoring & Metrics](#monitoring--metrics)

---

## OVERVIEW

This enhancement adds two critical capabilities to the existing CI/CD system:

### **TASK 1: Faulty Commit Detection + Author Notification**
When a build fails, the system automatically:
- Uses git bisect to identify the exact commit that introduced the error
- Verifies the build works without that commit
- Extracts author information and commit details
- Sends LLM-generated fix suggestion to author via email

### **TASK 2: Self-Learning Confidence System**
The system learns from PR outcomes and automatically:
- Tracks which error patterns are successfully fixed by LLM
- Promotes patterns to HIGH confidence after 3+ successes
- Demotes patterns back to LOW confidence if they fail repeatedly
- Uses learned patterns for smarter auto-fix decisions in future builds

---

## NEW COMPONENTS

### 1. `fault_commit_analyzer.py` (410 lines)
**Purpose:** Identifies faulty commits and generates fix suggestions

**Key Classes:**
- `FaultyCommitAnalyzer`: Main orchestrator
  - `find_last_good_commit()` - Searches history for compilable commit
  - `run_git_bisect()` - Binary search to find exact faulty commit
  - `verify_build_without_commit()` - Confirms build works without it
  - `extract_author_info()` - Gets commit author and email
  - `extract_commit_diff()` - Gets the changes in faulty commit
  - `generate_fix_suggestion_with_llm()` - Sends to LLM for analysis
  - `send_email_to_author()` - Notifies author with fix suggestion
  - `analyze()` - Main workflow orchestration

**Features:**
- ✅ Git bisect with safety cap (50 attempts max)
- ✅ Comprehensive logging (fault_analyzer.log)
- ✅ Email notifications (configurable via SMTP variables)
- ✅ LLM integration for root cause analysis
- ✅ Production-ready error handling
- ✅ Type hints and docstrings

**Output:** JSON with analysis results and fix suggestion

### 2. `pr_outcome_monitor.py` (480 lines)
**Purpose:** Tracks PR outcomes and updates learning database

**Key Classes:**
- `PRTracker` - Manages pr_tracking.json
  - `add_pr()` - Register new PR with root cause
  - `update_pr_status()` - Update PR status and outcome
  - `get_open_prs()` - List all open PRs

- `LearningDatabase` - Manages learning_db.json
  - `record_outcome()` - Record success/failure
  - `check_promotion()` - Check if pattern meets promotion criteria
  - `promote_pattern()` - Upgrade to HIGH confidence
  - `check_demotion()` - Check if pattern should be demoted
  - `demote_pattern()` - Downgrade to LOW confidence

- `PROutcomeMonitor` - Main orchestrator
  - `fetch_pr_from_github()` - Get PR details via GitHub API
  - `check_pr_commits()` - Detect human modifications
  - `check_pr_status()` - Determine success/failure
  - `monitor_open_prs()` - Main monitoring workflow

**Features:**
- ✅ GitHub API integration (with PAT auth)
- ✅ Automatic promotion/demotion logic
- ✅ PR commit analysis (detect human modifications)
- ✅ Comprehensive logging (pr_outcome_monitor.log)
- ✅ CLI interface for manual operations
- ✅ Type hints and docstrings

**Promotion Criteria:**
- 3 consecutive successes → promote to HIGH
- success_count ≥ 3 AND success_count > failure_count

**Demotion Criteria:**
- 2+ consecutive failures → demote to LOW
- failure_count > success_count (with min 3 attempts)

### 3. Updated `build_fix_v2.py`
**Changes:**
- Added imports for fault_commit_analyzer and learning_classifier
- New environment variables: ENABLE_FAULT_DETECTION, ENABLE_LEARNING, BUILD_LOG_URL
- Updated `classify_error_confidence()` to check learning_db.json
- New `trigger_fault_detection()` function called when compilation fails
- Integrated automatic pattern promotion/demotion

### 4. Updated `learning_classifier.py`
**Changes:**
- Added `get_pattern_confidence()` method
- Returns confidence score for promoted patterns
- Now used by build_fix_v2.py for adaptive confidence

### 5. `schema_definitions.py` (NEW)
**Purpose:** Documents persistent storage schemas and integration guide

**Contains:**
- JSON schema for learning_db.json
- JSON schema for pr_tracking.json
- Faulty commit analysis schema
- End-to-end integration guide

---

## INSTALLATION

### Prerequisites
```bash
# Ensure all Python dependencies are installed
pip install openai requests python-dotenv

# Git must be available
git --version

# For email notifications (optional)
# Enable "Less secure app access" for Gmail
# Or use app-specific password for other providers
```

### File Deployment
```bash
# Copy new files to repository
cp fault_commit_analyzer.py /path/to/repo/
cp pr_outcome_monitor.py /path/to/repo/
cp schema_definitions.py /path/to/repo/

# Update existing files
# - build_fix_v2.py (already updated)
# - learning_classifier.py (already updated)

# Create initial JSON files (will auto-create if missing)
# - learning_db.json
# - pr_tracking.json
```

### Permission Setup
```bash
# Make scripts executable
chmod +x fault_commit_analyzer.py
chmod +x pr_outcome_monitor.py

# Ensure git repository is properly configured
git config user.email "automation@jenkins.local"
git config user.name "Build Automation"
```

---

## CONFIGURATION

### Required Environment Variables
```bash
# Azure OpenAI (required)
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_ENDPOINT="https://your-instance.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT_NAME="gpt-5"
export AZURE_OPENAI_API_VERSION="2024-12-01-preview"

# GitHub (required for PR tracking)
export GITHUB_PAT="ghp_xxxxxxxxxxxxxxxxxxxx"
export REPO_OWNER="vaibhavsaxena619"
export REPO_NAME="poc-auto-pr-fix"

# Feature flags (optional)
export ENABLE_AUTO_FIX="true"
export ENABLE_FAULT_DETECTION="true"
export ENABLE_LEARNING="true"
export ENABLE_EMAIL_NOTIFICATIONS="false"  # Set to true to enable
```

### Optional: Email Notifications
```bash
# For Gmail with app-specific password
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@gmail.com"
export SMTP_PASSWORD="your-app-specific-password"
export FROM_EMAIL="noreply@company.com"

# For Office 365
export SMTP_SERVER="smtp.office365.com"
export SMTP_PORT="587"
export SMTP_USER="your-email@company.com"
export SMTP_PASSWORD="your-password"

# Build log URL (optional)
export BUILD_LOG_URL="https://jenkins.example.com/job/Build/123"
```

### Optional: Learning System Thresholds
```bash
# Promotion/demotion settings
export SUCCESS_THRESHOLD="3"      # Promote after this many successes
export FAILURE_THRESHOLD="2"      # Demote after this many failures
export CONSECUTIVE_SUCCESS_THRESHOLD="3"  # Consecutive successes needed
```

### Jenkins Pipeline Configuration
```groovy
pipeline {
    environment {
        AZURE_OPENAI_API_KEY = credentials('azure-openai-key')
        AZURE_OPENAI_ENDPOINT = credentials('azure-openai-endpoint')
        GITHUB_PAT = credentials('github-pat')
        SMTP_USER = credentials('smtp-user')
        SMTP_PASSWORD = credentials('smtp-password')
        ENABLE_FAULT_DETECTION = 'true'
        ENABLE_LEARNING = 'true'
    }
    
    stages {
        stage('Build') {
            steps {
                sh 'python build_fix_v2.py src/App.java'
            }
        }
        
        stage('Monitor PRs') {
            // Run periodically (e.g., every 2 hours)
            when {
                // Cron trigger or manual
            }
            steps {
                sh 'python pr_outcome_monitor.py monitor'
            }
        }
    }
}
```

### Cron Job Setup (for periodic monitoring)
```bash
# /etc/cron.d/pr-monitor
# Run every 2 hours
0 */2 * * * cd /path/to/repo && /usr/bin/python3 pr_outcome_monitor.py monitor >> /var/log/pr-monitor.log 2>&1

# Or using systemd timer
# /etc/systemd/system/pr-monitor.service
[Unit]
Description=PR Outcome Monitor
After=network.target

[Service]
Type=oneshot
WorkingDirectory=/path/to/repo
ExecStart=/usr/bin/python3 pr_outcome_monitor.py monitor

# /etc/systemd/system/pr-monitor.timer
[Unit]
Description=PR Outcome Monitor Timer
Requires=pr-monitor.service

[Timer]
OnBootSec=5min
OnUnitActiveSec=2h
Persistent=true

[Install]
WantedBy=timers.target

# Enable and start
systemctl enable pr-monitor.timer
systemctl start pr-monitor.timer
```

---

## USAGE EXAMPLES

### Example 1: Running Build Fix with Fault Detection
```bash
# Normal workflow (triggered by Jenkins)
python build_fix_v2.py src/App.java

# Output:
# [2024-01-28T10:00:00] Build fix initiated for src/App.java
# ✗ Compilation errors detected
# 🔍 BACKGROUND: Analyzing faulty commit...
# ✅ Faulty commit identified: abc1234d
# 📧 Author: John Doe (john.doe@example.com)
# ✓ Verified: Build works without this commit
# 💡 Fix suggestion generated and sent to author
```

### Example 2: Manual Fault Analysis
```bash
# Direct invocation for testing
python fault_commit_analyzer.py src/App.java https://jenkins.../build/123

# Output (JSON):
# {
#   "success": true,
#   "faulty_commit": "abc1234def5678",
#   "author": "John Doe",
#   "email": "john.doe@example.com",
#   "message": "Refactor: Update dependency\n\n...",
#   "verified": true,
#   "fix_suggestion": "ROOT CAUSE: Missing import...",
#   "error": null
# }
```

### Example 3: Adding PR to Tracking
```bash
# Register a new PR created by auto-fix
python pr_outcome_monitor.py add-pr 42 missing_dependency_import "cannot find symbol"

# Output:
# [2024-01-28T10:15:00] Adding PR #42 with root cause: missing_dependency_import
```

### Example 4: Monitoring Open PRs
```bash
# Run periodic monitoring (typically via cron or CI/CD scheduler)
python pr_outcome_monitor.py monitor

# Output:
# ============================================================
# PR OUTCOME MONITORING STARTED
# ============================================================
# Monitoring 3 open PRs...
# Checking status of PR #42...
#   ✓ MERGED (no modifications) → SUCCESS
#   Updated PR #42: merged → success
#   Recording outcome for missing_dependency_import: SUCCESS
#   missing_dependency_import: 3 successes, 3 consecutive
#   ✅ Promotion criteria met: 3 consecutive successes
#   🚀 PROMOTING missing_dependency_import to HIGH confidence!
# ============================================================
```

### Example 5: Checking Learning Database Stats
```bash
# View current learning database status
python pr_outcome_monitor.py status

# Output:
# {
#   "metadata": {
#     "version": "2.0",
#     "total_patterns": 5,
#     "promoted_patterns": 2,
#     ...
#   },
#   "root_causes": {
#     "missing_dependency_import": {
#       "confidence": "high",
#       "success_count": 5,
#       "failure_count": 0,
#       ...
#     },
#     ...
#   }
# }

# Or view with jq
cat learning_db.json | jq '.root_causes | to_entries | sort_by(.value.success_count) | reverse'
```

---

## INTEGRATION POINTS

### 1. Build Pipeline Integration
```
Jenkins Pipeline
    ↓
build_fix_v2.py
    ├─ Compile code
    ├─ [NEW] Trigger fault_commit_analyzer.py (async)
    │   ├─ Git bisect
    │   ├─ Author extraction
    │   ├─ LLM analysis
    │   └─ Email notification
    ├─ Classify errors (with learning_db.json)
    ├─ Auto-fix if HIGH confidence
    └─ Create PR
```

### 2. PR Monitoring Pipeline
```
Cron Job (every 2 hours)
    ↓
pr_outcome_monitor.py
    ├─ Get open PRs from pr_tracking.json
    ├─ Check GitHub API for status
    ├─ Update pr_tracking.json
    ├─ Update learning_db.json
    ├─ Check promotion/demotion criteria
    └─ Notify on promotion/demotion
```

### 3. Learning Database Usage
```
Next Build Failure
    ↓
build_fix_v2.py::classify_error_confidence()
    ├─ Check learning_db.json
    ├─ If pattern promoted to HIGH
    │   └─ Attempt auto-fix
    └─ Else use default confidence
```

---

## TROUBLESHOOTING

### Issue: "fault_commit_analyzer not available"
**Cause:** Module not in Python path or import error

**Solution:**
```bash
# Check file exists
ls -la fault_commit_analyzer.py

# Add to PYTHONPATH
export PYTHONPATH=/path/to/repo:$PYTHONPATH

# Test import
python -c "from fault_commit_analyzer import FaultyCommitAnalyzer; print('OK')"
```

### Issue: Git bisect hangs or takes too long
**Cause:** Large repository or compilation takes time

**Solution:**
```bash
# Set timeout
export GIT_BISECT_TIMEOUT="120"  # 2 minutes per compilation

# Manually reset bisect if stuck
git bisect reset

# Check max bisect attempts in fault_commit_analyzer.py
MAX_BISECT_ATTEMPTS = 50  # Reduce if needed
```

### Issue: Email notifications not sending
**Cause:** SMTP configuration incorrect

**Solution:**
```bash
# Test SMTP credentials
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('user@gmail.com', 'password')
print('✓ SMTP connection successful')
server.quit()
"

# Check firewall
telnet smtp.gmail.com 587

# Gmail users: Enable 2FA and create app-specific password
# https://myaccount.google.com/apppasswords
```

### Issue: GitHub API rate limiting
**Cause:** Too many API calls

**Solution:**
```bash
# Use GitHub PAT for higher limits
export GITHUB_PAT="ghp_xxxxxxxxxxxxxxxxxxxx"

# Check current rate limit
curl -H "Authorization: token $GITHUB_PAT" \
  https://api.github.com/rate_limit

# Reduce monitoring frequency (default: 2 hours)
```

### Issue: Learning database not promoting patterns
**Cause:** Promotion criteria not met

**Solution:**
```bash
# Check current stats
python pr_outcome_monitor.py status | jq '.root_causes'

# Manually check a pattern
cat learning_db.json | jq '.root_causes["missing_dependency_import"]'

# Verify monitoring is running
ps aux | grep pr_outcome_monitor

# Check logs
tail -20 pr_outcome_monitor.log
```

---

## MONITORING & METRICS

### Key Metrics to Track

#### Build Success Rate
```bash
# By error category
cat learning_db.json | jq '.root_causes[] | {confidence, success_rate}'

# Overall
python -c "import learning_classifier as lc; db = lc.LearningDatabase(); print(db.get_stats())"
```

#### Faulty Commits Detected
```bash
# Count entries in log
grep "Faulty commit found" fault_analyzer.log | wc -l

# Time spent on fault detection
grep "ANALYSIS COMPLETED" fault_analyzer.log
```

#### Pattern Promotion Events
```bash
# Promoted patterns
grep "PROMOTING" pr_outcome_monitor.log

# When promoted
grep "PROMOTED" learning_db.json | jq '.root_causes[] | select(.promoted_at != null)'
```

#### PR Monitoring Health
```bash
# Open PRs being monitored
cat pr_tracking.json | jq '.prs[] | select(.status == "open") | .pr_number'

# Recent outcomes
grep "outcome" pr_outcome_monitor.log | tail -10

# Monitoring success rate
grep "Monitoring" pr_outcome_monitor.log | grep "COMPLETED"
```

### Setting Up Dashboards

#### Prometheus Metrics (optional)
```python
# Export metrics format
from prometheus_client import CollectorRegistry, Gauge

registry = CollectorRegistry()
promoted_patterns = Gauge('promoted_patterns_total', 'Patterns promoted to HIGH', registry=registry)
pr_success_rate = Gauge('pr_success_rate', 'Overall PR merge success rate', registry=registry)

# Update and expose
promoted_patterns.set(db.data["metadata"]["promoted_patterns"])
pr_success_rate.set(success_rate)
```

#### CloudWatch Logs (AWS)
```bash
# Send logs to CloudWatch
aws logs put-log-events \
  --log-group-name /build-automation/fault-analyzer \
  --log-stream-name build-001 \
  --log-events file://fault_analyzer.log
```

---

## BEST PRACTICES

1. **Run Monitoring Regularly**
   - Monitor at least every 2-4 hours
   - More frequent checks for high-volume repositories

2. **Email Notifications**
   - Keep enabled for critical builds
   - Disable for development/testing environments
   - Use group emails for team notifications

3. **Learning Thresholds**
   - DEFAULT: Promote after 3 successes
   - CONSERVATIVE: Increase to 5-7 for mission-critical systems
   - AGGRESSIVE: Decrease to 2 for experimental systems

4. **Git Bisect Safety**
   - Monitor bisect timeout (default: 50 attempts)
   - Increase for large codebases with slow builds
   - Add health checks between bisect steps

5. **Logging & Auditing**
   - Keep logs for at least 30 days
   - Archive learning_db.json regularly
   - Review promoted patterns weekly

6. **Testing**
   - Test fault detection with intentional commits
   - Verify email notifications before production
   - Validate learning promotion with manual PRs

---

## PRODUCTION CHECKLIST

- [ ] All environment variables configured
- [ ] fault_commit_analyzer.py deployed and tested
- [ ] pr_outcome_monitor.py deployed and tested
- [ ] build_fix_v2.py updated and tested
- [ ] learning_classifier.py updated and tested
- [ ] Cron job for monitoring configured and running
- [ ] Email notifications tested (if enabled)
- [ ] GitHub API PAT configured and working
- [ ] Logs being collected and archived
- [ ] Dashboard/metrics setup complete
- [ ] Team trained on new system
- [ ] Rollback plan documented
- [ ] High-confidence patterns validated
- [ ] Learning database initialized
- [ ] PR tracking database initialized

---

## SUPPORT & TROUBLESHOOTING

For issues, check:
1. fault_analyzer.log - Fault detection logs
2. pr_outcome_monitor.log - PR monitoring logs
3. learning_db.json - Current learning state
4. pr_tracking.json - Tracked PRs
5. GitHub Actions/Jenkins logs - Integration logs

For feature requests or bugs:
- Update schema_definitions.py with new patterns
- Test new patterns before promotion
- Document changes in this guide

---

**Last Updated:** January 28, 2026  
**Maintained By:** Build Automation Team
