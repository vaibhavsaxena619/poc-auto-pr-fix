#!/usr/bin/env python3
"""
PR Outcome Monitor - Tracks PR merge status and updates learning database.

Features:
1. PERIODIC PR STATUS CHECKS: Monitors PRs created by auto-fix system
2. SUCCESS/FAILURE TRACKING: Determines if PR was merged without modifications
3. ROOT CAUSE LEARNING: Updates learning_db.json with outcomes
4. AUTOMATIC PROMOTION: Upgrades patterns to HIGH confidence after success threshold
5. DEMOTION ON FAILURE: Reduces confidence if pattern consistently fails

Workflow:
1. Read pr_tracking.json (list of open PRs with metadata)
2. Check GitHub API for current PR status
3. If merged without changes → mark as success
4. If closed or modified → mark as failure
5. Update learning_db.json with success/failure count
6. Promote pattern to HIGH confidence if threshold reached

PR Tracking Schema (pr_tracking.json):
{
  "prs": [
    {
      "pr_number": 42,
      "root_cause": "missing_dependency_import",
      "status": "open",
      "created_at": "2024-01-28T10:00:00",
      "error_message": "cannot find symbol",
      "branch": "fix/auto-123456",
      "base_branch": "Release"
    }
  ]
}

Learning Database Schema (learning_db.json):
{
  "root_causes": {
    "missing_dependency_import": {
      "confidence": "low",
      "success_count": 0,
      "failure_count": 0,
      "consecutive_successes": 0,
      "consecutive_failures": 0,
      "total_attempts": 0,
      "promoted_at": null,
      "last_update": "2024-01-28T10:00:00"
    }
  }
}
"""

import os
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    import sys
    sys.exit(1)


# === CONFIGURATION ===
GITHUB_PAT = os.getenv('GITHUB_PAT', '')
REPO_OWNER = os.getenv('REPO_OWNER', 'vaibhavsaxena619')
REPO_NAME = os.getenv('REPO_NAME', 'poc-auto-pr-fix')

# Persistent storage paths (outside workspace to survive builds)
LEARNING_DATA_DIR = os.getenv('LEARNING_DATA_DIR', '/var/jenkins_home/learning_data')
PR_TRACKING_PATH = os.getenv('PR_TRACKING_PATH', os.path.join(LEARNING_DATA_DIR, 'pr_tracking.json'))
LEARNING_DB_PATH = os.getenv('LEARNING_DB_PATH', os.path.join(LEARNING_DATA_DIR, 'learning_db.json'))

# Ensure directory exists
os.makedirs(LEARNING_DATA_DIR, exist_ok=True)

# Learning thresholds
SUCCESS_THRESHOLD = int(os.getenv('SUCCESS_THRESHOLD', '3'))  # Promote after 3 successes
FAILURE_THRESHOLD = int(os.getenv('FAILURE_THRESHOLD', '2'))  # Demote after 2 failures
CONSECUTIVE_SUCCESS_THRESHOLD = 3  # Consecutive successes needed for promotion

GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [pr-monitor] %(message)s',
    handlers=[
        logging.FileHandler('pr_outcome_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PRTracker:
    """Manages tracking of PRs and their outcomes."""
    
    def __init__(self, tracking_path: str = PR_TRACKING_PATH):
        """
        Initialize PR tracker.
        
        Args:
            tracking_path: Path to pr_tracking.json file
        """
        self.tracking_path = tracking_path
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load PR tracking data from disk."""
        if not os.path.exists(self.tracking_path):
            logger.info(f"Creating new PR tracking file: {self.tracking_path}")
            return {"prs": [], "metadata": {"created": datetime.now().isoformat()}}
        
        try:
            with open(self.tracking_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load PR tracking data: {e}")
            return {"prs": [], "metadata": {"created": datetime.now().isoformat()}}
    
    def save(self) -> bool:
        """Save PR tracking data to disk."""
        try:
            with open(self.tracking_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save PR tracking data: {e}")
            return False
    
    def add_pr(self, pr_number: int, root_cause: str, error_message: str = None,
               branch: str = None, base_branch: str = 'Release') -> bool:
        """
        Track a new PR.
        
        Args:
            pr_number: GitHub PR number
            root_cause: Root cause classification (e.g., "missing_dependency_import")
            error_message: Original error message
            branch: PR branch name
            base_branch: Base branch PR targets
        
        Returns:
            True if added successfully
        """
        logger.info(f"Adding PR #{pr_number} with root cause: {root_cause}")
        
        pr_entry = {
            "pr_number": pr_number,
            "root_cause": root_cause,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "error_message": error_message,
            "branch": branch,
            "base_branch": base_branch,
            "outcome": None,
            "outcome_checked_at": None,
            "merged_at": None
        }
        
        self.data["prs"].append(pr_entry)
        return self.save()
    
    def update_pr_status(self, pr_number: int, status: str, outcome: str = None,
                        merged_at: str = None) -> bool:
        """
        Update PR status.
        
        Args:
            pr_number: GitHub PR number
            status: 'open', 'merged', 'closed'
            outcome: 'success' or 'failure'
            merged_at: ISO timestamp of when PR was merged
        
        Returns:
            True if updated successfully
        """
        for pr in self.data["prs"]:
            if pr["pr_number"] == pr_number:
                pr["status"] = status
                pr["outcome"] = outcome
                pr["outcome_checked_at"] = datetime.now().isoformat()
                if merged_at:
                    pr["merged_at"] = merged_at
                
                logger.info(f"  Updated PR #{pr_number}: {status} → {outcome}")
                return self.save()
        
        logger.warning(f"  PR #{pr_number} not found in tracking data")
        return False
    
    def get_open_prs(self) -> List[Dict]:
        """Get list of open PRs."""
        return [pr for pr in self.data["prs"] if pr["status"] == "open"]
    
    def get_pr(self, pr_number: int) -> Optional[Dict]:
        """Get PR by number."""
        for pr in self.data["prs"]:
            if pr["pr_number"] == pr_number:
                return pr
        return None


class LearningDatabase:
    """Manages learning database of error patterns and their outcomes."""
    
    def __init__(self, db_path: str = LEARNING_DB_PATH):
        """
        Initialize learning database.
        
        Args:
            db_path: Path to learning_db.json file
        """
        self.db_path = db_path
        self.data = self._load()
    
    def _load(self) -> Dict:
        """Load learning database from disk."""
        if not os.path.exists(self.db_path):
            logger.info(f"Creating new learning database: {self.db_path}")
            return {
                "metadata": {
                    "version": "2.0",
                    "created": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_patterns": 0,
                    "promoted_patterns": 0,
                    "demoted_patterns": 0
                },
                "root_causes": {}
            }
        
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load learning database: {e}")
            return self._load()  # Recurse to create new DB
    
    def save(self) -> bool:
        """Save learning database to disk."""
        try:
            self.data["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.db_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save learning database: {e}")
            return False
    
    def record_outcome(self, root_cause: str, success: bool) -> bool:
        """
        Record the outcome of a PR.
        
        Args:
            root_cause: Root cause classification
            success: True if PR merged successfully, False if failed/closed
        
        Returns:
            True if recorded successfully
        """
        logger.info(f"Recording outcome for {root_cause}: {'SUCCESS' if success else 'FAILURE'}")
        
        if root_cause not in self.data["root_causes"]:
            self.data["root_causes"][root_cause] = {
                "confidence": "low",
                "success_count": 0,
                "failure_count": 0,
                "consecutive_successes": 0,
                "consecutive_failures": 0,
                "total_attempts": 0,
                "promoted_at": None,
                "last_update": datetime.now().isoformat()
            }
            self.data["metadata"]["total_patterns"] += 1
        
        pattern = self.data["root_causes"][root_cause]
        pattern["total_attempts"] += 1
        pattern["last_update"] = datetime.now().isoformat()
        
        if success:
            pattern["success_count"] += 1
            pattern["consecutive_successes"] += 1
            pattern["consecutive_failures"] = 0
            
            logger.info(f"  {root_cause}: {pattern['success_count']} successes, "
                       f"{pattern['consecutive_successes']} consecutive")
        else:
            pattern["failure_count"] += 1
            pattern["consecutive_successes"] = 0
            pattern["consecutive_failures"] += 1
            
            logger.info(f"  {root_cause}: {pattern['failure_count']} failures, "
                       f"{pattern['consecutive_failures']} consecutive")
        
        return self.save()
    
    def check_promotion(self, root_cause: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a root cause should be promoted to HIGH confidence.
        
        Args:
            root_cause: Root cause classification
        
        Returns:
            Tuple of (should_promote, reason)
        """
        if root_cause not in self.data["root_causes"]:
            return False, "Pattern not found"
        
        pattern = self.data["root_causes"][root_cause]
        
        # Check promotion criteria
        if pattern["consecutive_successes"] >= CONSECUTIVE_SUCCESS_THRESHOLD:
            return True, f"{CONSECUTIVE_SUCCESS_THRESHOLD} consecutive successes"
        
        if (pattern["success_count"] >= SUCCESS_THRESHOLD and
            pattern["success_count"] > pattern["failure_count"]):
            return True, f"{SUCCESS_THRESHOLD}+ successes with more successes than failures"
        
        return False, None
    
    def promote_pattern(self, root_cause: str) -> bool:
        """
        Promote a pattern to HIGH confidence.
        
        Args:
            root_cause: Root cause classification
        
        Returns:
            True if promoted successfully
        """
        if root_cause not in self.data["root_causes"]:
            return False
        
        pattern = self.data["root_causes"][root_cause]
        
        if pattern["confidence"] == "high":
            logger.info(f"  {root_cause} already HIGH confidence")
            return True
        
        logger.info(f"  🚀 PROMOTING {root_cause} to HIGH confidence!")
        pattern["confidence"] = "high"
        pattern["promoted_at"] = datetime.now().isoformat()
        self.data["metadata"]["promoted_patterns"] += 1
        
        return self.save()
    
    def check_demotion(self, root_cause: str) -> Tuple[bool, Optional[str]]:
        """
        Check if a pattern should be demoted from HIGH to LOW confidence.
        
        Args:
            root_cause: Root cause classification
        
        Returns:
            Tuple of (should_demote, reason)
        """
        if root_cause not in self.data["root_causes"]:
            return False, "Pattern not found"
        
        pattern = self.data["root_causes"][root_cause]
        
        if pattern["confidence"] != "high":
            return False, "Not in HIGH confidence"
        
        # Demote if consecutive failures exceed threshold
        if pattern["consecutive_failures"] >= FAILURE_THRESHOLD:
            return True, f"{FAILURE_THRESHOLD}+ consecutive failures"
        
        # Demote if more failures than successes
        if (pattern["failure_count"] > pattern["success_count"] and
            pattern["total_attempts"] >= 3):
            return True, "More failures than successes"
        
        return False, None
    
    def demote_pattern(self, root_cause: str) -> bool:
        """
        Demote a pattern from HIGH back to LOW confidence.
        
        Args:
            root_cause: Root cause classification
        
        Returns:
            True if demoted successfully
        """
        if root_cause not in self.data["root_causes"]:
            return False
        
        pattern = self.data["root_causes"][root_cause]
        
        if pattern["confidence"] == "low":
            logger.info(f"  {root_cause} already LOW confidence")
            return True
        
        logger.warning(f"  ⬇️ DEMOTING {root_cause} to LOW confidence")
        pattern["confidence"] = "low"
        pattern["consecutive_successes"] = 0
        self.data["metadata"]["demoted_patterns"] += 1
        
        return self.save()


class PROutcomeMonitor:
    """Orchestrates PR monitoring and learning updates."""
    
    def __init__(self):
        """Initialize monitor."""
        self.tracker = PRTracker()
        self.learning_db = LearningDatabase()
        self.github_headers = self._get_github_headers()
        logger.info("PR Outcome Monitor initialized")
    
    def _get_github_headers(self) -> Dict:
        """Get GitHub API headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if GITHUB_PAT:
            headers["Authorization"] = f"token {GITHUB_PAT}"
        return headers
    
    def fetch_pr_from_github(self, pr_number: int) -> Optional[Dict]:
        """
        Fetch PR details from GitHub API.
        
        Args:
            pr_number: GitHub PR number
        
        Returns:
            PR data from GitHub or None if failed
        """
        try:
            url = f"{GITHUB_API_BASE}/pulls/{pr_number}"
            response = requests.get(url, headers=self.github_headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"  GitHub API returned {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching PR from GitHub: {e}")
            return None
    
    def check_pr_commits(self, pr_number: int, branch: str) -> Tuple[bool, int]:
        """
        Check if PR has commits beyond what the LLM auto-fix created.
        
        Args:
            pr_number: GitHub PR number
            branch: PR branch name
        
        Returns:
            Tuple of (modified_by_humans, commit_count)
        """
        try:
            url = f"{GITHUB_API_BASE}/pulls/{pr_number}/commits"
            response = requests.get(url, headers=self.github_headers, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"  Could not fetch PR commits: {response.status_code}")
                return False, 0
            
            commits = response.json()
            
            # Heuristic: If more than 1 commit or last commit author is not "Build Automation"
            # then it was likely modified by humans
            is_modified = False
            
            if len(commits) > 1:
                logger.info(f"  PR has {len(commits)} commits (more than 1)")
                is_modified = True
            
            if commits:
                last_author = commits[-1].get('commit', {}).get('author', {}).get('name', '')
                if 'Build Automation' not in last_author and 'GPT' not in last_author:
                    logger.info(f"  Last commit author: {last_author}")
                    is_modified = True
            
            return is_modified, len(commits)
            
        except Exception as e:
            logger.error(f"Error checking PR commits: {e}")
            return False, 0
    
    def check_pr_status(self, pr_number: int) -> Optional[Tuple[str, bool]]:
        """
        Check the status of a PR and determine if it was a success or failure.
        
        Args:
            pr_number: GitHub PR number
        
        Returns:
            Tuple of (status, success) or None if failed to fetch
            - status: 'open', 'merged', 'closed'
            - success: True if merged without human modifications
        """
        logger.info(f"Checking status of PR #{pr_number}...")
        
        # Get tracked PR info
        tracked_pr = self.tracker.get_pr(pr_number)
        if not tracked_pr:
            logger.warning(f"  PR #{pr_number} not in tracking database")
            return None
        
        # Fetch from GitHub
        gh_pr = self.fetch_pr_from_github(pr_number)
        if not gh_pr:
            logger.warning(f"  Could not fetch PR #{pr_number} from GitHub")
            return None
        
        # Determine status
        status = gh_pr.get('state', 'unknown')  # 'open', 'closed'
        
        if status == 'merged' or gh_pr.get('merged_at'):
            # Merged - check if modified by humans
            is_modified, commit_count = self.check_pr_commits(pr_number, tracked_pr['branch'])
            
            if is_modified:
                logger.info(f"  ✓ MERGED (with human modifications) → Likely SUCCESS")
                success = True  # Human modifications usually mean they fixed additional issues
            else:
                logger.info(f"  ✓ MERGED (no modifications) → SUCCESS")
                success = True
            
            return ('merged', success)
        
        elif status == 'closed':
            logger.info(f"  ✗ CLOSED without merge → FAILURE")
            return ('closed', False)
        
        else:  # 'open'
            logger.info(f"  ℹ️ Still OPEN → no outcome yet")
            return ('open', None)
    
    def monitor_open_prs(self) -> None:
        """
        Check status of all open PRs and update outcomes in learning database.
        """
        logger.info("=" * 60)
        logger.info("PR OUTCOME MONITORING STARTED")
        logger.info("=" * 60)
        
        open_prs = self.tracker.get_open_prs()
        logger.info(f"Monitoring {len(open_prs)} open PRs...")
        
        for pr in open_prs:
            pr_number = pr["pr_number"]
            root_cause = pr["root_cause"]
            
            try:
                # Check PR status
                result = self.check_pr_status(pr_number)
                
                if result is None:
                    continue
                
                status, success = result
                
                if success is not None:  # Has a definitive outcome
                    # Update PR tracking
                    outcome = 'success' if success else 'failure'
                    self.tracker.update_pr_status(pr_number, status, outcome)
                    
                    # Record in learning database
                    self.learning_db.record_outcome(root_cause, success)
                    
                    # Check for promotion/demotion
                    should_promote, reason = self.learning_db.check_promotion(root_cause)
                    if should_promote:
                        logger.info(f"  ✅ Promotion criteria met: {reason}")
                        self.learning_db.promote_pattern(root_cause)
                    
                    should_demote, reason = self.learning_db.check_demotion(root_cause)
                    if should_demote:
                        logger.warning(f"  ⚠️ Demotion criteria met: {reason}")
                        self.learning_db.demote_pattern(root_cause)
            
            except Exception as e:
                logger.error(f"Error processing PR #{pr_number}: {e}")
        
        logger.info("=" * 60)
        logger.info("PR OUTCOME MONITORING COMPLETED")
        logger.info("=" * 60)


def main():
    """CLI entry point."""
    import sys
    
    monitor = PROutcomeMonitor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'monitor':
            monitor.monitor_open_prs()
        elif command == 'add-pr':
            if len(sys.argv) < 4:
                print("Usage: python pr_outcome_monitor.py add-pr <pr_number> <root_cause> [error_message]")
                sys.exit(1)
            
            pr_number = int(sys.argv[2])
            root_cause = sys.argv[3]
            error_message = sys.argv[4] if len(sys.argv) > 4 else None
            
            monitor.tracker.add_pr(pr_number, root_cause, error_message)
            print(f"Added PR #{pr_number} with root cause: {root_cause}")
        
        elif command == 'status':
            print(json.dumps(monitor.learning_db.data, indent=2))
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    else:
        monitor.monitor_open_prs()


if __name__ == '__main__':
    main()
