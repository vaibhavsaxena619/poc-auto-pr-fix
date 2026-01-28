#!/usr/bin/env python3
"""
PR Merge Event Handler - Triggers Learning System on PR Merge

This module handles GitHub webhook events for PR merges and automatically
updates the learning confidence system when low-confidence fix PRs are merged.

Instead of a cron job, this provides real-time learning updates based on PR outcomes.

Usage:
    # As webhook endpoint (Flask/FastAPI)
    from pr_merge_handler import handle_pr_merge_event
    
    @app.post("/webhook/github")
    def github_webhook(request):
        handle_pr_merge_event(request.json)
    
    # Manual trigger via CLI
    python pr_merge_handler.py --pr-number 44 --action merged

Features:
- Detects PR merge events from GitHub webhooks
- Extracts root cause metadata from PR body
- Updates learning database with success/failure outcomes
- Supports both merged (success) and closed (failure) events
- Comprehensive logging for audit trail
"""

import os
import sys
import json
import re
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from pr_outcome_monitor import PRTracker, LearningDatabase
except ImportError:
    print("ERROR: pr_outcome_monitor not found. Ensure it's in the same directory.")
    sys.exit(1)

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [pr-merge-handler] %(message)s',
    handlers=[
        logging.FileHandler('pr_merge_handler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class PRMergeHandler:
    """Handles PR merge events and updates learning database."""
    
    def __init__(self):
        """Initialize the PR merge handler."""
        self.github_token = os.getenv('GITHUB_PAT', '')
        self.repo_owner = os.getenv('REPO_OWNER', 'vaibhavsaxena619')
        self.repo_name = os.getenv('REPO_NAME', 'poc-auto-pr-fix')
        
        if not self.github_token:
            logger.warning("GITHUB_PAT not set - some features may not work")
        
        self.pr_tracker = PRTracker()
        self.learning_db = LearningDatabase()
        
        logger.info("PR Merge Handler initialized")
    
    def extract_learning_metadata(self, pr_body: str) -> Optional[Dict]:
        """
        Extract learning metadata from PR body.
        
        Args:
            pr_body: The PR body text
            
        Returns:
            Dictionary with root_causes, error_count, source_file or None
        """
        try:
            # Look for hidden HTML comment with metadata
            pattern = r'<!-- LEARNING_METADATA: ({.*?}) -->'
            match = re.search(pattern, pr_body, re.DOTALL)
            
            if match:
                metadata_json = match.group(1)
                metadata = json.loads(metadata_json)
                logger.info(f"  ✅ Extracted metadata: {len(metadata.get('root_causes', []))} root cause(s)")
                return metadata
            else:
                logger.warning("  ⚠️ No learning metadata found in PR body")
                return None
                
        except Exception as e:
            logger.error(f"  ✗ Failed to extract metadata: {e}")
            return None
    
    def fetch_pr_details(self, pr_number: int) -> Optional[Dict]:
        """
        Fetch PR details from GitHub API.
        
        Args:
            pr_number: The PR number
            
        Returns:
            PR details dictionary or None
        """
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls/{pr_number}"
            headers = {
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"  ✗ Failed to fetch PR: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"  ✗ Error fetching PR: {e}")
            return None
    
    def handle_pr_merged(self, pr_number: int, pr_data: Dict) -> bool:
        """
        Handle a merged PR event.
        
        Args:
            pr_number: The PR number
            pr_data: PR data from GitHub API
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"🔀 Processing merged PR #{pr_number}")
            
            # Extract metadata from PR body
            pr_body = pr_data.get('body', '')
            metadata = self.extract_learning_metadata(pr_body)
            
            if not metadata:
                logger.warning("  ⚠️ No metadata found - cannot update learning DB")
                return False
            
            root_causes = metadata.get('root_causes', [])
            
            if not root_causes:
                logger.warning("  ⚠️ No root causes in metadata")
                return False
            
            # Update learning database with SUCCESS
            logger.info(f"  📚 Updating learning DB with {len(root_causes)} successful pattern(s)")
            
            for root_cause in root_causes:
                self.learning_db.record_outcome(root_cause, success=True)
                
                # Check if pattern should be promoted
                promoted = self.learning_db.check_promotion(root_cause)
                if promoted:
                    logger.info(f"  ⬆️ PROMOTED: {root_cause} to HIGH confidence")
            
            # Update PR tracker
            merged_at = pr_data.get('merged_at', datetime.now().isoformat())
            
            # Try to get from tracker first
            existing_pr = self.pr_tracker.get_pr(pr_number)
            if existing_pr:
                self.pr_tracker.update_pr_status(
                    pr_number,
                    status='merged',
                    outcome='success',
                    merged_at=merged_at
                )
                logger.info(f"  ✅ Updated PR tracker for #{pr_number}")
            else:
                # Add new entry
                branch = pr_data.get('head', {}).get('ref', '')
                base_branch = pr_data.get('base', {}).get('ref', 'Release')
                
                for root_cause in root_causes:
                    self.pr_tracker.add_pr(
                        pr_number,
                        root_cause,
                        f"Low-confidence fix for {root_cause}",
                        branch,
                        base_branch
                    )
                
                self.pr_tracker.update_pr_status(
                    pr_number,
                    status='merged',
                    outcome='success',
                    merged_at=merged_at
                )
                logger.info(f"  ✅ Added PR #{pr_number} to tracker")
            
            logger.info(f"✅ Successfully processed merged PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error handling merged PR: {e}", exc_info=True)
            return False
    
    def handle_pr_closed(self, pr_number: int, pr_data: Dict) -> bool:
        """
        Handle a closed (not merged) PR event.
        
        Args:
            pr_number: The PR number
            pr_data: PR data from GitHub API
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"❌ Processing closed (not merged) PR #{pr_number}")
            
            # Extract metadata from PR body
            pr_body = pr_data.get('body', '')
            metadata = self.extract_learning_metadata(pr_body)
            
            if not metadata:
                logger.warning("  ⚠️ No metadata found - cannot update learning DB")
                return False
            
            root_causes = metadata.get('root_causes', [])
            
            if not root_causes:
                logger.warning("  ⚠️ No root causes in metadata")
                return False
            
            # Update learning database with FAILURE
            logger.info(f"  📚 Updating learning DB with {len(root_causes)} failed pattern(s)")
            
            for root_cause in root_causes:
                self.learning_db.record_outcome(root_cause, success=False)
                
                # Check if pattern should be demoted
                demoted = self.learning_db.check_demotion(root_cause)
                if demoted:
                    logger.info(f"  ⬇️ DEMOTED: {root_cause} to LOW confidence")
            
            # Update PR tracker
            closed_at = pr_data.get('closed_at', datetime.now().isoformat())
            
            existing_pr = self.pr_tracker.get_pr(pr_number)
            if existing_pr:
                self.pr_tracker.update_pr_status(
                    pr_number,
                    status='closed',
                    outcome='failure',
                    merged_at=closed_at
                )
                logger.info(f"  ✅ Updated PR tracker for #{pr_number}")
            
            logger.info(f"✅ Successfully processed closed PR #{pr_number}")
            return True
            
        except Exception as e:
            logger.error(f"✗ Error handling closed PR: {e}", exc_info=True)
            return False
    
    def handle_webhook_event(self, payload: Dict) -> bool:
        """
        Handle GitHub webhook event.
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            True if processed successfully, False otherwise
        """
        try:
            action = payload.get('action')
            pr_data = payload.get('pull_request', {})
            pr_number = pr_data.get('number')
            
            if not pr_number:
                logger.warning("No PR number in webhook payload")
                return False
            
            logger.info("="*60)
            logger.info(f"GitHub Webhook Event: {action} for PR #{pr_number}")
            logger.info("="*60)
            
            # Check if PR title indicates it's a low-confidence fix
            pr_title = pr_data.get('title', '')
            if 'REQUIRES REVIEW' not in pr_title and 'Low-Confidence' not in pr_title:
                logger.info(f"  ℹ️ PR #{pr_number} is not a low-confidence fix - ignoring")
                return True
            
            if action == 'closed':
                # Check if merged or just closed
                if pr_data.get('merged', False):
                    return self.handle_pr_merged(pr_number, pr_data)
                else:
                    return self.handle_pr_closed(pr_number, pr_data)
            else:
                logger.info(f"  ℹ️ Action '{action}' not relevant for learning - ignoring")
                return True
                
        except Exception as e:
            logger.error(f"✗ Error handling webhook event: {e}", exc_info=True)
            return False
    
    def handle_pr_by_number(self, pr_number: int, action: str) -> bool:
        """
        Manually handle a PR by number.
        
        Args:
            pr_number: The PR number
            action: 'merged' or 'closed'
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("="*60)
            logger.info(f"Manual PR Processing: {action} for PR #{pr_number}")
            logger.info("="*60)
            
            # Fetch PR details
            pr_data = self.fetch_pr_details(pr_number)
            
            if not pr_data:
                logger.error(f"  ✗ Could not fetch PR #{pr_number}")
                return False
            
            # Check if it's a low-confidence fix PR
            pr_title = pr_data.get('title', '')
            if 'REQUIRES REVIEW' not in pr_title and 'Low-Confidence' not in pr_title:
                logger.warning(f"  ⚠️ PR #{pr_number} is not a low-confidence fix")
                # Continue anyway for manual processing
            
            if action == 'merged':
                return self.handle_pr_merged(pr_number, pr_data)
            elif action == 'closed':
                return self.handle_pr_closed(pr_number, pr_data)
            else:
                logger.error(f"  ✗ Unknown action: {action}")
                return False
                
        except Exception as e:
            logger.error(f"✗ Error processing PR: {e}", exc_info=True)
            return False


def main():
    """CLI interface for manual PR processing."""
    parser = argparse.ArgumentParser(
        description='Process PR merge/close events for learning system'
    )
    parser.add_argument(
        '--pr-number',
        type=int,
        required=True,
        help='PR number to process'
    )
    parser.add_argument(
        '--action',
        choices=['merged', 'closed'],
        required=True,
        help='Action to process (merged or closed)'
    )
    
    args = parser.parse_args()
    
    handler = PRMergeHandler()
    success = handler.handle_pr_by_number(args.pr_number, args.action)
    
    if success:
        print(f"\n✅ Successfully processed PR #{args.pr_number} as {args.action}")
        sys.exit(0)
    else:
        print(f"\n✗ Failed to process PR #{args.pr_number}")
        sys.exit(1)


if __name__ == "__main__":
    main()
