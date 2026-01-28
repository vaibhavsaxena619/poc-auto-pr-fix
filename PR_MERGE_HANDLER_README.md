# PR Merge Handler - Automated Learning System

## Overview

The PR Merge Handler automatically updates the learning confidence system when low-confidence fix PRs are merged to the Release branch. This replaces the need for a cron job and provides real-time learning updates based on PR outcomes.

## How It Works

### 1. **Low-Confidence Fix PR Creation**
When the build system detects only low-confidence errors:
- Generates LLM fix
- Creates branch: `fix/low-confidence-fix_<timestamp>`
- Creates PR with:
  - Detailed error analysis
  - Review checklist
  - **Hidden metadata** in PR body for tracking

### 2. **PR Merge Detection**
When a low-confidence fix PR is merged:
- Jenkins detects merge commit on Release branch
- Extracts PR number from merge commit message
- Triggers `pr_merge_handler.py`

### 3. **Learning System Update**
The merge handler:
- Fetches PR details from GitHub API
- Extracts root cause metadata from PR body
- Updates learning database:
  - **Merged PR** = Success → increment success count
  - **Closed PR** = Failure → increment failure count
- Automatically promotes/demotes patterns based on criteria

## PR Metadata Format

Low-confidence fix PRs contain hidden metadata in the body:

```html
<!-- LEARNING_METADATA: {"root_causes": ["risky:business_logic"], "error_count": 2, "source_file": "src/App.java"} -->
```

This metadata is extracted when the PR is merged to update the learning system.

## Integration with Jenkins

### Automatic Trigger (Recommended)

The Jenkinsfile includes a stage that automatically detects PR merges:

```groovy
stage('PR Merged - Update Learning') {
    when {
        branch 'Release'
        expression { 
            def commitMsg = sh(script: "git log -1 --pretty=%s", returnStdout: true).trim()
            return commitMsg.contains('Merge pull request') && 
                   (commitMsg.contains('low-confidence-fix') || 
                    commitMsg.contains('REQUIRES REVIEW'))
        }
    }
    steps {
        // Extracts PR number and triggers pr_merge_handler.py
    }
}
```

**When it triggers:**
- On Release branch
- After a merge commit
- For low-confidence fix PRs only

### Manual Trigger

You can also manually process a PR:

```bash
# Process a merged PR
python pr_merge_handler.py --pr-number 44 --action merged

# Process a closed (rejected) PR
python pr_merge_handler.py --pr-number 45 --action closed
```

## Promotion/Demotion Criteria

### Promotion to HIGH Confidence
A pattern is promoted when:
- `consecutive_successes >= 3`
- `success_count > failure_count`

**Effect:** Future errors matching this pattern will be auto-fixed with high confidence

### Demotion to LOW Confidence
A pattern is demoted when:
- `consecutive_failures >= 2`, OR
- `failure_count > success_count`

**Effect:** Future errors matching this pattern will require manual review

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_PAT` | Yes | GitHub Personal Access Token |
| `REPO_OWNER` | No | Default: `vaibhavsaxena619` |
| `REPO_NAME` | No | Default: `poc-auto-pr-fix` |

## Logging

All operations are logged to:
- **File:** `pr_merge_handler.log`
- **Console:** Real-time output

Log includes:
- PR merge/close events
- Metadata extraction
- Learning database updates
- Promotion/demotion events

## Example Workflow

### Scenario: Low-Confidence Error Detected

1. **Build Failure** - App.java has 2 low-confidence errors
   ```
   ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
   ⚠️ LOW-CONFIDENCE: risky:business_logic (10%)
   ```

2. **LLM Fix Generated** - System calls GPT-5 to generate fix

3. **PR Created** - `fix/low-confidence-fix_20260128_113555`
   - Title: "🔧 Low-Confidence Fix: 2 Issue(s) - REQUIRES REVIEW"
   - Body contains hidden metadata
   - Assigned to original author

4. **Manual Review** - Developer reviews PR:
   - Option A: Merge → Success outcome
   - Option B: Close → Failure outcome

5. **Learning Update** (Automatic)
   - Jenkins detects merge on Release
   - Extracts metadata from PR
   - Updates learning database:
     ```
     risky:business_logic: success_count += 1
     consecutive_successes = 1
     ```

6. **Future Behavior**
   - After 3 consecutive successes → Promoted to HIGH confidence
   - Next time same pattern appears → Auto-fixed without PR

## File Structure

```
GitAutomationTesting/
├── pr_merge_handler.py          # Main handler (NEW)
├── pr_outcome_monitor.py        # Learning database manager (EXISTING)
├── build_fix_v2.py              # Build fix with metadata injection (UPDATED)
├── Jenkinsfile                  # CI/CD with merge detection (UPDATED)
├── learning_db.json             # Learning database
├── pr_tracking.json             # PR tracking database
└── pr_merge_handler.log         # Handler logs (NEW)
```

## Comparison: Cron Job vs PR Merge Handler

| Aspect | Cron Job | PR Merge Handler |
|--------|----------|------------------|
| **Trigger** | Time-based (every 2 hours) | Event-based (PR merge) |
| **Latency** | Up to 2 hours delay | Immediate (real-time) |
| **Accuracy** | Checks all open PRs | Processes specific merged PR |
| **Efficiency** | Continuous polling | Event-driven |
| **Setup** | Requires cron configuration | Integrated in Jenkins |
| **Best For** | Monitoring multiple PRs | Single PR processing |

## Troubleshooting

### PR Not Processed

**Problem:** PR merged but learning system not updated

**Solutions:**
1. Check Jenkins logs for merge detection stage
2. Verify PR title contains "REQUIRES REVIEW" or "Low-Confidence"
3. Check if metadata is present in PR body
4. Manually trigger: `python pr_merge_handler.py --pr-number <num> --action merged`

### No Metadata Found

**Problem:** `⚠️ No learning metadata found in PR body`

**Cause:** PR was not created by the automated system or metadata was removed

**Solution:** Only PRs created by `build_fix_v2.py` contain metadata. Manual PRs won't have it.

### GitHub API Errors

**Problem:** `✗ Failed to fetch PR: 401`

**Solution:** Check `GITHUB_PAT` environment variable is set and valid

## Future Enhancements

Potential improvements:
- Webhook endpoint for direct GitHub integration
- Support for multiple repositories
- Machine learning for pattern similarity
- Dashboard for learning metrics
- Email notifications for promotions/demotions

## Support

For issues or questions:
1. Check logs: `pr_merge_handler.log`
2. Review Jenkins console output
3. Verify environment variables
4. Test with manual trigger first
