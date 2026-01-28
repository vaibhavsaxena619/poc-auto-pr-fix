#!/usr/bin/env python3
"""
JSON Schema Definitions for Learning and PR Tracking System

This module documents the persistent storage schemas used by the fault detection
and self-learning system.
"""

# ============================================================================
# LEARNING DATABASE SCHEMA (learning_db.json)
# ============================================================================
LEARNING_DB_SCHEMA = {
    "description": "Tracks error patterns, confidence levels, and historical outcomes",
    "example": {
        "metadata": {
            "version": "2.0",
            "created": "2024-01-28T10:00:00",
            "last_updated": "2024-01-28T10:30:00",
            "total_patterns": 5,
            "promoted_patterns": 2,
            "demoted_patterns": 0
        },
        "root_causes": {
            "missing_dependency_import": {
                "confidence": "high",  # "low" or "high"
                "success_count": 5,
                "failure_count": 0,
                "consecutive_successes": 3,
                "consecutive_failures": 0,
                "total_attempts": 5,
                "promoted_at": "2024-01-28T10:15:00",
                "last_update": "2024-01-28T10:30:00"
            },
            "business_logic": {
                "confidence": "low",
                "success_count": 1,
                "failure_count": 2,
                "consecutive_successes": 0,
                "consecutive_failures": 1,
                "total_attempts": 3,
                "promoted_at": None,
                "last_update": "2024-01-28T10:20:00"
            }
        }
    },
    "fields": {
        "metadata": {
            "version": "Database schema version",
            "created": "ISO timestamp when DB was created",
            "last_updated": "ISO timestamp of last update",
            "total_patterns": "Number of unique error patterns tracked",
            "promoted_patterns": "Count of patterns promoted to HIGH confidence",
            "demoted_patterns": "Count of patterns demoted back to LOW confidence"
        },
        "root_causes": {
            "root_cause_key": {
                "confidence": "Current confidence level: 'low' or 'high'",
                "success_count": "Number of times this pattern was successfully fixed",
                "failure_count": "Number of times this pattern fix failed",
                "consecutive_successes": "Current consecutive successful outcomes",
                "consecutive_failures": "Current consecutive failed outcomes",
                "total_attempts": "Total number of fix attempts for this pattern",
                "promoted_at": "ISO timestamp when pattern was promoted to HIGH (null if not promoted)",
                "last_update": "ISO timestamp of last update to this pattern"
            }
        }
    },
    "promotion_criteria": {
        "automatic": "When 3+ consecutive successes are recorded",
        "threshold": "success_count >= 3 AND success_count > failure_count"
    },
    "demotion_criteria": {
        "automatic": "When 2+ consecutive failures are recorded",
        "threshold": "failure_count > success_count (with minimum 3 attempts)"
    }
}


# ============================================================================
# PR TRACKING SCHEMA (pr_tracking.json)
# ============================================================================
PR_TRACKING_SCHEMA = {
    "description": "Tracks PRs created by auto-fix system and their outcomes",
    "example": {
        "prs": [
            {
                "pr_number": 42,
                "root_cause": "missing_dependency_import",
                "status": "merged",  # "open", "merged", "closed"
                "created_at": "2024-01-28T10:00:00",
                "error_message": "cannot find symbol: class StringUtils",
                "branch": "fix/high-confidence-errors_20240128_100000",
                "base_branch": "Release",
                "outcome": "success",  # "success", "failure", None
                "outcome_checked_at": "2024-01-28T10:30:00",
                "merged_at": "2024-01-28T10:25:00"
            },
            {
                "pr_number": 41,
                "root_cause": "business_logic",
                "status": "closed",
                "created_at": "2024-01-27T15:00:00",
                "error_message": "NullPointerException at line 42",
                "branch": "fix/high-confidence-errors_20240127_150000",
                "base_branch": "Release",
                "outcome": "failure",
                "outcome_checked_at": "2024-01-27T16:00:00",
                "merged_at": None
            }
        ],
        "metadata": {
            "created": "2024-01-28T09:00:00"
        }
    },
    "fields": {
        "pr_number": "GitHub PR number",
        "root_cause": "Classification of root cause (e.g., 'missing_dependency_import')",
        "status": "Current PR status: 'open', 'merged', or 'closed'",
        "created_at": "ISO timestamp when PR was created",
        "error_message": "Original compiler error message",
        "branch": "PR branch name",
        "base_branch": "Base branch PR targets (usually 'Release')",
        "outcome": "'success' if merged, 'failure' if closed, None if still open",
        "outcome_checked_at": "ISO timestamp when outcome was last checked",
        "merged_at": "ISO timestamp when PR was merged (null if not merged)"
    }
}


# ============================================================================
# FAULTY COMMIT ANALYSIS SCHEMA (returned by fault_commit_analyzer.py)
# ============================================================================
FAULTY_COMMIT_ANALYSIS_SCHEMA = {
    "description": "Results returned from fault commit analysis",
    "example": {
        "success": True,
        "faulty_commit": "abc1234def5678",
        "author": "John Doe",
        "email": "john.doe@example.com",
        "message": "Refactor: Update dependency version\n\nUpdated spring-boot from 2.7.0 to 3.0.0",
        "verified": True,  # True if build works without this commit
        "fix_suggestion": "ROOT CAUSE: Missing import\nREASON: The new Spring Boot version requires...\nFIX: Add @SpringBootApplication annotation\nCORRECTED CODE: ...",
        "error": None
    },
    "fields": {
        "success": "Boolean indicating if analysis completed successfully",
        "faulty_commit": "SHA of the commit that introduced the error",
        "author": "Author name extracted from commit",
        "email": "Author email extracted from commit",
        "message": "Full commit message",
        "verified": "True if build succeeds without the faulty commit",
        "fix_suggestion": "AI-generated fix suggestion from LLM",
        "error": "Error message if analysis failed (null if successful)"
    }
}


# ============================================================================
# INTEGRATION GUIDE
# ============================================================================
INTEGRATION_GUIDE = """
1. FAULT COMMIT DETECTION (fault_commit_analyzer.py)
   ================================================
   
   Triggered automatically in build_fix_v2.py when compilation fails:
   
   - Runs git bisect to find the exact commit that broke the build
   - Verifies build works without the faulty commit
   - Extracts author information and commit diff
   - Sends LLM request with commit diff + compiler error
   - Optionally sends email to author with fix suggestion
   
   Enable/disable via environment variables:
   - ENABLE_FAULT_DETECTION=true|false (default: true)
   - ENABLE_EMAIL_NOTIFICATIONS=true|false (default: false)
   - SMTP_SERVER=smtp.gmail.com (default)
   - SMTP_PORT=587 (default)
   - SMTP_USER=your-email@gmail.com
   - SMTP_PASSWORD=your-app-password
   - FROM_EMAIL=noreply@company.com
   - BUILD_LOG_URL=https://jenkins.example.com/build/123

2. PR OUTCOME MONITORING (pr_outcome_monitor.py)
   ============================================
   
   Monitors PRs and updates learning database:
   
   a) Add PR to tracking:
      python pr_outcome_monitor.py add-pr 42 missing_dependency_import "error message"
   
   b) Monitor all open PRs (check GitHub API for status):
      python pr_outcome_monitor.py monitor
   
   c) Show learning database stats:
      python pr_outcome_monitor.py status
   
   Automation:
   - Run 'monitor' command periodically (e.g., every 1-2 hours via cron)
   - When PR is merged → records success and updates learning_db.json
   - When PR is closed without merge → records failure
   - If success_count reaches threshold → automatically promotes pattern to HIGH confidence
   - If failure_count increases → demotes pattern back to LOW confidence

3. SELF-LEARNING CONFIDENCE SYSTEM (learning_classifier.py + build_fix_v2.py)
   ===========================================================================
   
   Confidence classification now checks learned patterns:
   
   Before (static):
   - missing_import → always 0.9 (HIGH confidence)
   - business_logic → always 0.1 (LOW confidence)
   
   After (adaptive):
   - Check learning_db.json for this error type
   - If pattern was promoted to HIGH confidence → use 0.9
   - Else use default classifier confidence
   - Example: business_logic error promoted after 3 successes → now 0.9
   
   Integration in build_fix_v2.py (already done):
   - classify_error_confidence() checks learning_db.json
   - If root cause matches promoted pattern → returns HIGH confidence
   - Else returns default confidence
   - Automatically attempts auto-fix for promoted patterns

4. WORKFLOW: End-to-End
   ====================
   
   a) Developer pushes code with error
   b) Jenkins pipeline runs build_fix_v2.py
   c) Compilation fails → workflow triggers:
      1. Fault detection runs in background:
         - Identifies commit abc1234 introduced error
         - Sends LLM analysis with diff + error
         - Sends email to author@example.com with fix suggestion
      2. Error classification:
         - Checks if it's HIGH or LOW confidence
         - Checks learning_db.json for promoted patterns
      3. If HIGH confidence → attempts auto-fix
         - If successful → commits and creates PR
         - PR tracked in pr_tracking.json with root_cause
      4. If LOW confidence → creates review PR
         - Tags with low-confidence issues for manual review
   
   d) PR is merged (e.g., next day after manual review)
   
   e) Periodic monitoring job runs (e.g., every 2 hours):
      - pr_outcome_monitor.py checks GitHub API
      - Sees PR #42 is merged → records success
      - Updates learning_db.json: missing_dependency_import success_count++
      - If success_count reaches 3 → promotes to HIGH confidence
   
   f) Next time this error occurs:
      - classify_error_confidence() checks learning_db.json
      - Finds missing_dependency_import: confidence="high"
      - Automatically attempts auto-fix (doesn't create review PR)

5. MONITORING AND DEBUGGING
   =========================
   
   Check learning database:
   - cat learning_db.json | jq '.root_causes'
   
   Check PR tracking:
   - cat pr_tracking.json | jq '.prs'
   
   Check fault analyzer logs:
   - tail -f fault_analyzer.log
   
   Check PR monitor logs:
   - tail -f pr_outcome_monitor.log

6. CONFIGURATION CHECKLIST
   =======================
   
   Required Environment Variables:
   □ AZURE_OPENAI_API_KEY
   □ AZURE_OPENAI_ENDPOINT
   □ AZURE_OPENAI_DEPLOYMENT_NAME
   
   Optional (Fault Detection):
   □ ENABLE_FAULT_DETECTION=true
   □ ENABLE_EMAIL_NOTIFICATIONS=true
   □ SMTP_SERVER=smtp.gmail.com
   □ SMTP_PORT=587
   □ SMTP_USER=sender@example.com
   □ SMTP_PASSWORD=app-password
   □ BUILD_LOG_URL=https://jenkins.../build/...
   
   Optional (Learning):
   □ ENABLE_LEARNING=true
   □ SUCCESS_THRESHOLD=3
   □ FAILURE_THRESHOLD=2
   
   Jenkins Configuration:
   □ Install fault_commit_analyzer.py in repo
   □ Install pr_outcome_monitor.py in repo
   □ Update build_fix_v2.py (already done)
   □ Schedule pr_outcome_monitor.py as cron job (e.g., every 2 hours)
"""


if __name__ == '__main__':
    import json
    
    print("=" * 70)
    print("LEARNING DATABASE SCHEMA")
    print("=" * 70)
    print(json.dumps(LEARNING_DB_SCHEMA, indent=2))
    
    print("\n" + "=" * 70)
    print("PR TRACKING SCHEMA")
    print("=" * 70)
    print(json.dumps(PR_TRACKING_SCHEMA, indent=2))
    
    print("\n" + "=" * 70)
    print("FAULTY COMMIT ANALYSIS SCHEMA")
    print("=" * 70)
    print(json.dumps(FAULTY_COMMIT_ANALYSIS_SCHEMA, indent=2))
    
    print("\n" + "=" * 70)
    print("INTEGRATION GUIDE")
    print("=" * 70)
    print(INTEGRATION_GUIDE)
