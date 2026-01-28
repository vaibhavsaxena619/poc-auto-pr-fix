#!/usr/bin/env python3
"""
GitHub Webhook Handler - Detects PR merges and provides learning feedback.

This webhook processes GitHub events to:
1. Detect when auto-fix PRs are merged (success)
2. Detect when PRs are closed without merge (failure)
3. Update learning database with outcomes
4. Suggest pattern promotions

Setup:
1. Add webhook to GitHub repo: Settings → Webhooks
2. Payload URL: https://your-jenkins-server/github-webhook/
3. Content type: application/json
4. Events: Pull request events
"""

import os
import json
import sys
from datetime import datetime
from typing import Dict, Optional
from learning_classifier import LearningDatabase


class PROutcomeTracker:
    """Tracks PR outcomes (merged/closed) for learning feedback."""
    
    def __init__(self):
        self.db = LearningDatabase()
    
    def process_github_webhook(self, webhook_payload: dict) -> Dict:
        """
        Process GitHub webhook payload for PR events.
        
        Detects:
        - PR merged (merged=true, action=closed) → SUCCESS
        - PR closed without merge (merged=false, action=closed) → FAILURE
        """
        
        event_action = webhook_payload.get("action", "").lower()
        
        # Only process pull_request events
        if webhook_payload.get("pull_request") is None:
            return {"status": "ignored", "reason": "Not a pull request event"}
        
        pr = webhook_payload["pull_request"]
        pr_number = pr["number"]
        pr_title = pr["title"]
        is_merged = pr.get("merged", False)
        
        # Only process when PR is closed
        if event_action != "closed":
            return {"status": "ignored", "reason": f"Action '{event_action}' not 'closed'"}
        
        # Check if this is an auto-fix PR (created by our bot)
        pr_author = pr["user"]["login"]
        is_auto_fix_pr = (
            "[Auto-Fix]" in pr_title or 
            "[auto-fix]" in pr_title or
            pr_author == "build-automation@jenkins.local" or
            "Build Automation" in pr.get("user", {}).get("name", "")
        )
        
        if not is_auto_fix_pr:
            return {
                "status": "ignored",
                "reason": f"Not an auto-fix PR (author: {pr_author})"
            }
        
        # Process outcome
        if is_merged:
            return self._process_success(pr_number, pr_title, pr)
        else:
            return self._process_failure(pr_number, pr_title, pr)
    
    def _process_success(self, pr_number: int, pr_title: str, pr: dict) -> Dict:
        """Process successful PR merge."""
        
        print(f"\n✅ AUTO-FIX PR #{pr_number} MERGED - Recording as SUCCESS")
        print(f"   Title: {pr_title}")
        
        # Extract error info from PR title and body
        low_conf_count = self._extract_low_confidence_count(pr_title)
        error_patterns = self._extract_error_patterns(pr.get("body", ""))
        
        success_data = {
            "pr_number": pr_number,
            "pr_title": pr_title,
            "merged": True,
            "timestamp": datetime.now().isoformat(),
            "low_confidence_issues": low_conf_count,
            "error_patterns": error_patterns
        }
        
        # Record each error pattern as successful
        for pattern_info in error_patterns:
            category = pattern_info.get("category", "unknown")
            pattern = pattern_info.get("pattern", "")
            
            self.db.record_fix_attempt(
                error_pattern=pattern,
                category=category,
                success=True,
                error_message=pattern_info.get("error_msg", "")
            )
            
            # Check for promotion
            should_promote, reason = self.db.check_promotion(pattern, category)
            if should_promote:
                print(f"  📈 PROMOTING: {category}:{pattern}")
                print(f"     Reason: {reason}")
                self.db.promote_pattern(pattern, category)
        
        self.db.save()
        
        return {
            "status": "success",
            "pr_number": pr_number,
            "patterns_recorded": len(error_patterns),
            "data": success_data
        }
    
    def _process_failure(self, pr_number: int, pr_title: str, pr: dict) -> Dict:
        """Process failed PR (closed without merge)."""
        
        print(f"\n❌ AUTO-FIX PR #{pr_number} CLOSED - Recording as FAILURE")
        print(f"   Title: {pr_title}")
        
        # Extract error patterns
        error_patterns = self._extract_error_patterns(pr.get("body", ""))
        
        failure_data = {
            "pr_number": pr_number,
            "pr_title": pr_title,
            "merged": False,
            "timestamp": datetime.now().isoformat(),
            "error_patterns": error_patterns
        }
        
        # Record each error pattern as failed
        for pattern_info in error_patterns:
            category = pattern_info.get("category", "unknown")
            pattern = pattern_info.get("pattern", "")
            
            self.db.record_fix_attempt(
                error_pattern=pattern,
                category=category,
                success=False,
                error_message=pattern_info.get("error_msg", "")
            )
        
        self.db.save()
        
        return {
            "status": "failure",
            "pr_number": pr_number,
            "patterns_recorded": len(error_patterns),
            "data": failure_data
        }
    
    def _extract_low_confidence_count(self, pr_title: str) -> int:
        """Extract count of low-confidence issues from PR title."""
        import re
        match = re.search(r'(\d+)\s+low-confidence', pr_title, re.IGNORECASE)
        return int(match.group(1)) if match else 0
    
    def _extract_error_patterns(self, pr_body: str) -> list:
        """
        Extract error patterns from PR body.
        
        Expected format from create_fix_branch_for_mixed_errors():
        Issue 1: `low:business_logic` (Confidence: 10%)
        ```
        error message
        ```
        """
        import re
        
        patterns = []
        
        # Match: **Issue N:** `category` (Confidence: X%)
        issue_pattern = r'\*\*Issue\s+\d+:\*\*\s+`([^`]+)`\s+\(Confidence:\s+([\d.]+)%\)'
        
        for match in re.finditer(issue_pattern, pr_body):
            category_full = match.group(1)  # e.g., "low:business_logic"
            confidence = float(match.group(2)) / 100
            
            # Parse category
            if ":" in category_full:
                level, category = category_full.split(":", 1)
            else:
                level = "unknown"
                category = category_full
            
            patterns.append({
                "category": category,
                "level": level,
                "confidence": confidence,
                "pattern": category_full,
                "error_msg": ""
            })
        
        return patterns


def handle_webhook_request(request_body: str) -> Dict:
    """
    Main webhook handler - called by Jenkins/webhook server.
    
    Args:
        request_body: Raw JSON body from GitHub webhook
    
    Returns:
        Response dict with status and details
    """
    try:
        payload = json.loads(request_body)
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Invalid JSON: {e}"}
    
    tracker = PROutcomeTracker()
    result = tracker.process_github_webhook(payload)
    
    print(f"\n📊 Webhook Processing Result: {json.dumps(result, indent=2)}")
    
    return result


# === For testing locally ===
if __name__ == "__main__":
    # Example test webhook payload
    test_payload = {
        "action": "closed",
        "pull_request": {
            "number": 42,
            "title": "[Auto-Fix] 2 low-confidence issues need review",
            "merged": True,
            "user": {
                "login": "github-bot",
                "name": "Build Automation"
            },
            "body": """## Auto-Fix: High-Confidence Errors Only

This PR fixes 2 **HIGH-CONFIDENCE** compilation errors.

### Remaining Issues (Manual Review Required)

**Issue 1:** `low:business_logic` (Confidence: 10%)
```
NullPointerException at line 42
```

**Issue 2:** `low:security` (Confidence: 10%)
```
Potential SQL injection detected
```

CC: @developer-name - Please review the remaining low-confidence issues
"""
        }
    }
    
    print("🧪 Testing webhook handler with sample payload...")
    result = handle_webhook_request(json.dumps(test_payload))
    print(f"\nResult: {json.dumps(result, indent=2)}")
