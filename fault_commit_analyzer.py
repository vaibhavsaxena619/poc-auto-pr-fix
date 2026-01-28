#!/usr/bin/env python3
"""
Faulty Commit Analyzer - Detects the commit that introduced a compilation error.

Features:
1. AUTOMATED GIT BISECT: Binary search to find the exact faulty commit
2. ISOLATED BUILD VERIFICATION: Confirms build works without the faulty commit
3. ROOT CAUSE EXTRACTION: Analyzes commit diff + compiler error with LLM
4. AUTHOR NOTIFICATION: Sends email with fix suggestion to commit author
5. PRODUCTION-READY LOGGING: Detailed audit trail of all operations

Workflow:
1. Detect faulty commit between last good and current HEAD
2. Verify build without faulty commit
3. Extract author info from commit
4. Generate AI-assisted fix suggestion
5. Send email notification with details and fix suggestion
"""

import os
import subprocess
import sys
import json
import smtplib
import logging
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    from openai import AzureOpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai")
    sys.exit(1)


# === CONFIGURATION ===
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER)
NOTIFY_BISECT_RESULTS = os.getenv('NOTIFY_BISECT_RESULTS', 'true').lower() == 'true'
ENABLE_EMAIL_NOTIFICATIONS = os.getenv('ENABLE_EMAIL_NOTIFICATIONS', 'false').lower() == 'true'
MAX_BISECT_ATTEMPTS = 50  # Safety cap for git bisect

AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
AZURE_OPENAI_API_VERSION = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5')

# === LOGGING SETUP ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [fault-analyzer] %(message)s',
    handlers=[
        logging.FileHandler('fault_analyzer.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class FaultyCommitAnalyzer:
    """Orchestrates faulty commit detection and fix suggestion workflow."""
    
    def __init__(self, source_file: str, start_commit: str = None, end_commit: str = 'HEAD'):
        """
        Initialize analyzer.
        
        Args:
            source_file: Path to Java source file being compiled
            start_commit: Starting commit for bisect (if None, searches history)
            end_commit: Ending commit (default: current HEAD)
        """
        self.source_file = source_file
        self.start_commit = start_commit
        self.end_commit = end_commit
        self.faulty_commit = None
        self.faulty_commit_author = None
        self.faulty_commit_email = None
        self.faulty_commit_message = None
        self.faulty_commit_diff = None
        
        logger.info(f"Analyzer initialized for {source_file}")
    
    def find_last_good_commit(self) -> Optional[str]:
        """
        Find the most recent commit where the source file compiles successfully.
        
        Returns:
            Commit SHA of last good commit, or None if not found
        """
        logger.info("🔍 Searching for last good commit...")
        
        try:
            # Get commit history
            result = subprocess.run(
                ['git', 'log', '--oneline', '-20'],
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            
            commits = result.stdout.strip().split('\n')
            current_sha = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            ).stdout.strip()
            
            for idx, commit_line in enumerate(commits):
                try:
                    commit_sha = commit_line.split()[0]
                    
                    if idx == 0:
                        logger.info(f"  Current: {commit_sha[:7]} - skipping")
                        continue
                    
                    logger.info(f"  Testing {commit_sha[:7]}...")
                    
                    # Save current state
                    subprocess.run(['git', 'stash'], capture_output=True, check=False)
                    
                    # Checkout commit
                    checkout = subprocess.run(
                        ['git', 'checkout', commit_sha],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if checkout.returncode != 0:
                        logger.debug(f"    Could not checkout {commit_sha[:7]}")
                        continue
                    
                    # Try to compile
                    compile_result = subprocess.run(
                        ['javac', self.source_file],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if compile_result.returncode == 0:
                        logger.info(f"  ✅ Found good commit: {commit_sha[:7]}")
                        # Restore to current state
                        subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
                        subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
                        return commit_sha
                    else:
                        logger.debug(f"    Has compilation errors")
                
                except Exception as e:
                    logger.debug(f"    Error testing {commit_sha[:7]}: {e}")
                    continue
            
            # Restore current state
            subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
            subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
            
            logger.warning("  No good commit found in recent history")
            return None
            
        except Exception as e:
            logger.error(f"Error searching commit history: {e}")
            return None
    
    def run_git_bisect(self, good_commit: str, bad_commit: str) -> Optional[str]:
        """
        Use git bisect to find the exact commit that introduced the error.
        
        Args:
            good_commit: SHA of last known good commit
            bad_commit: SHA of failing commit (usually HEAD)
        
        Returns:
            SHA of the faulty commit, or None if bisect failed
        """
        logger.info(f"🔄 Running git bisect between {good_commit[:7]} and {bad_commit[:7]}...")
        
        try:
            # Start bisect
            subprocess.run(['git', 'bisect', 'reset'], capture_output=True, check=False)
            subprocess.run(['git', 'bisect', 'start'], capture_output=True, check=True)
            subprocess.run(['git', 'bisect', 'bad', bad_commit], capture_output=True, check=True)
            subprocess.run(['git', 'bisect', 'good', good_commit], capture_output=True, check=True)
            
            attempt = 0
            while attempt < MAX_BISECT_ATTEMPTS:
                attempt += 1
                
                # Try to compile at current bisect point
                compile_result = subprocess.run(
                    ['javac', self.source_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                current_sha = subprocess.run(
                    ['git', 'rev-parse', 'HEAD'],
                    capture_output=True,
                    text=True,
                    check=True
                ).stdout.strip()
                
                if compile_result.returncode == 0:
                    logger.debug(f"  Bisect attempt {attempt}: {current_sha[:7]} compiles ✓")
                    subprocess.run(['git', 'bisect', 'good'], capture_output=True, check=True)
                else:
                    logger.debug(f"  Bisect attempt {attempt}: {current_sha[:7]} fails ✗")
                    subprocess.run(['git', 'bisect', 'bad'], capture_output=True, check=True)
                
                # Check if bisect is done
                result = subprocess.run(
                    ['git', 'bisect', 'log'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Get current bisect status
                status_result = subprocess.run(
                    ['git', 'log', '--oneline', '-1'],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # Try to determine if we've found the faulty commit
                if 'first bad commit' in result.stdout or attempt >= MAX_BISECT_ATTEMPTS - 1:
                    faulty_sha = subprocess.run(
                        ['git', 'rev-parse', 'HEAD'],
                        capture_output=True,
                        text=True,
                        check=True
                    ).stdout.strip()
                    
                    logger.info(f"  ✅ Faulty commit found: {faulty_sha[:7]}")
                    
                    # Clean up bisect
                    subprocess.run(['git', 'bisect', 'reset'], capture_output=True, check=False)
                    
                    return faulty_sha
            
            # Clean up
            subprocess.run(['git', 'bisect', 'reset'], capture_output=True, check=False)
            return None
            
        except Exception as e:
            logger.error(f"Git bisect failed: {e}")
            subprocess.run(['git', 'bisect', 'reset'], capture_output=True, check=False)
            return None
    
    def verify_build_without_commit(self, faulty_commit: str) -> bool:
        """
        Verify that the build succeeds without the faulty commit.
        
        Creates temporary branch from parent of faulty commit and builds there.
        
        Args:
            faulty_commit: SHA of the faulty commit
        
        Returns:
            True if build succeeds without the commit, False otherwise
        """
        logger.info(f"🔨 Verifying build without faulty commit {faulty_commit[:7]}...")
        
        try:
            # Get current state
            current_sha = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True
            ).stdout.strip()
            
            # Get parent of faulty commit
            parent_result = subprocess.run(
                ['git', 'rev-parse', f'{faulty_commit}^'],
                capture_output=True,
                text=True,
                check=True
            )
            parent_sha = parent_result.stdout.strip()
            
            # Stash current changes
            subprocess.run(['git', 'stash'], capture_output=True, check=False)
            
            try:
                # Checkout parent
                subprocess.run(
                    ['git', 'checkout', parent_sha],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=10
                )
                
                # Try to compile
                compile_result = subprocess.run(
                    ['javac', self.source_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                success = compile_result.returncode == 0
                
                if success:
                    logger.info(f"  ✅ Build succeeds without faulty commit!")
                else:
                    logger.warning(f"  ⚠️ Build still fails without faulty commit")
                
                return success
                
            finally:
                # Restore current state
                subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
                subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
                
        except Exception as e:
            logger.error(f"Error verifying build: {e}")
            return False
    
    def extract_author_info(self, commit_sha: str) -> bool:
        """
        Extract author information from commit.
        
        Args:
            commit_sha: SHA of the commit
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"📧 Extracting author info from commit {commit_sha[:7]}...")
        
        try:
            # Extract author and email
            result = subprocess.run(
                ['git', 'show', '-s', '--format=%an <%ae>', commit_sha],
                capture_output=True,
                text=True,
                check=True
            )
            
            author_line = result.stdout.strip()
            # Parse "Name <email>" format
            if '<' in author_line and '>' in author_line:
                self.faulty_commit_author = author_line.split('<')[0].strip()
                self.faulty_commit_email = author_line.split('<')[1].split('>')[0].strip()
            else:
                self.faulty_commit_author = author_line
                self.faulty_commit_email = None
            
            # Extract commit message
            msg_result = subprocess.run(
                ['git', 'show', '-s', '--format=%B', commit_sha],
                capture_output=True,
                text=True,
                check=True
            )
            self.faulty_commit_message = msg_result.stdout.strip()
            
            logger.info(f"  Author: {self.faulty_commit_author}")
            logger.info(f"  Email: {self.faulty_commit_email}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error extracting author info: {e}")
            return False
    
    def extract_commit_diff(self, commit_sha: str) -> bool:
        """
        Extract the diff of the faulty commit.
        
        Args:
            commit_sha: SHA of the commit
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"📄 Extracting commit diff...")
        
        try:
            result = subprocess.run(
                ['git', 'show', commit_sha],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            self.faulty_commit_diff = result.stdout
            logger.info(f"  Diff size: {len(self.faulty_commit_diff)} bytes")
            
            return True
            
        except Exception as e:
            logger.error(f"Error extracting diff: {e}")
            return False
    
    def generate_fix_suggestion_with_llm(self, compiler_error: str) -> Optional[str]:
        """
        Send commit diff + compiler error to LLM for root cause analysis and fix suggestion.
        
        Args:
            compiler_error: The compiler error message
        
        Returns:
            LLM-generated fix suggestion, or None if failed
        """
        logger.info("🤖 Generating fix suggestion with LLM...")
        
        if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
            logger.error("Azure OpenAI credentials not configured")
            return None
        
        try:
            client = AzureOpenAI(
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_OPENAI_API_VERSION,
                azure_endpoint=AZURE_OPENAI_ENDPOINT
            )
            
            # Truncate diff and error if too large
            diff_truncated = self.faulty_commit_diff[:2000] if self.faulty_commit_diff else ""
            error_truncated = compiler_error[:1000] if compiler_error else ""
            
            prompt = f"""You are a Java expert analyzing a faulty commit.

COMMIT MESSAGE:
{self.faulty_commit_message}

COMMIT DIFF (first 2000 chars):
{diff_truncated}

COMPILER ERROR:
{error_truncated}

TASK:
1. Explain the ROOT CAUSE of the compilation error
2. Suggest a MINIMAL FIX (just the essential change needed)
3. Explain why the original code failed
4. Provide the corrected code snippet

Format your response as:
ROOT CAUSE: [brief explanation]
REASON: [why it failed]
FIX: [the minimal change needed]
CORRECTED CODE:
[code snippet]"""
            
            response = client.chat.completions.create(
                model=AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a Java expert. Analyze compilation errors and suggest minimal, safe fixes."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_completion_tokens=1000,
                temperature=0.5
            )
            
            suggestion = response.choices[0].message.content.strip()
            logger.info("  ✅ LLM generated fix suggestion")
            
            return suggestion
            
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return None
    
    def send_email_to_author(self, compiler_error: str, build_log_url: str = None,
                            fix_suggestion: str = None) -> bool:
        """
        Send email notification to commit author.
        
        Args:
            compiler_error: The compiler error message
            build_log_url: URL to the failed build log
            fix_suggestion: AI-generated fix suggestion
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not ENABLE_EMAIL_NOTIFICATIONS:
            logger.info("📧 Email notifications disabled")
            return False
        
        if not self.faulty_commit_email:
            logger.warning("📧 No email address available for author")
            return False
        
        logger.info(f"📧 Sending email to {self.faulty_commit_email}...")
        
        try:
            # Create email
            msg = MIMEMultipart()
            msg['From'] = FROM_EMAIL
            msg['To'] = self.faulty_commit_email
            msg['Subject'] = f"⚠️ Compilation Error in Commit {self.faulty_commit[:7]}"
            
            # Build email body
            body = f"""Hi {self.faulty_commit_author},

Your commit {self.faulty_commit[:7]} has introduced a compilation error in the build pipeline.

--- COMMIT DETAILS ---
Commit: {self.faulty_commit}
Message: {self.faulty_commit_message}

--- ERROR SUMMARY ---
{compiler_error[:500]}

--- ROOT CAUSE ANALYSIS & FIX SUGGESTION ---
{fix_suggestion if fix_suggestion else 'No fix suggestion available'}

--- BUILD LOG ---
{build_log_url if build_log_url else 'Build log URL not available'}

--- ACTION REQUIRED ---
Please review the error and fix suggestion above. If you need help, please refer to the build log.

Best regards,
Build Automation Pipeline"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            if SMTP_USER and SMTP_PASSWORD:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                    server.starttls()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.send_message(msg)
                
                logger.info(f"  ✅ Email sent to {self.faulty_commit_email}")
                return True
            else:
                logger.warning("  SMTP credentials not configured, skipping email send")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def analyze(self, compiler_error: str, build_log_url: str = None) -> Dict:
        """
        Execute full analysis workflow.
        
        Args:
            compiler_error: The compiler error message
            build_log_url: Optional URL to build log
        
        Returns:
            Dictionary with analysis results
        """
        logger.info("=" * 60)
        logger.info("FAULTY COMMIT ANALYSIS WORKFLOW STARTED")
        logger.info("=" * 60)
        
        result = {
            'success': False,
            'faulty_commit': None,
            'author': None,
            'email': None,
            'message': None,
            'verified': False,
            'fix_suggestion': None,
            'error': None
        }
        
        try:
            # Step 1: Find last good commit
            good_commit = self.find_last_good_commit()
            if not good_commit:
                result['error'] = 'Could not find a good commit in history'
                logger.warning(result['error'])
                return result
            
            # Step 2: Run git bisect
            faulty_commit = self.run_git_bisect(good_commit, self.end_commit)
            if not faulty_commit:
                result['error'] = 'Git bisect failed to identify faulty commit'
                logger.error(result['error'])
                return result
            
            self.faulty_commit = faulty_commit
            
            # Step 3: Verify build without faulty commit
            verified = self.verify_build_without_commit(faulty_commit)
            result['verified'] = verified
            
            if not verified:
                logger.warning("Build still fails without faulty commit - may not be the root cause")
            
            # Step 4: Extract author info
            if not self.extract_author_info(faulty_commit):
                logger.warning("Could not extract author info")
            else:
                result['author'] = self.faulty_commit_author
                result['email'] = self.faulty_commit_email
                result['message'] = self.faulty_commit_message
            
            # Step 5: Extract commit diff
            self.extract_commit_diff(faulty_commit)
            
            # Step 6: Generate fix suggestion
            fix_suggestion = self.generate_fix_suggestion_with_llm(compiler_error)
            result['fix_suggestion'] = fix_suggestion
            
            # Step 7: Send email
            self.send_email_to_author(compiler_error, build_log_url, fix_suggestion)
            
            result['success'] = True
            result['faulty_commit'] = faulty_commit
            
            logger.info("=" * 60)
            logger.info("ANALYSIS COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            result['error'] = str(e)
        
        return result


def main():
    """CLI entry point for fault commit analyzer."""
    if len(sys.argv) < 2:
        print("Usage: python fault_commit_analyzer.py <source_file> [build_log_url]")
        sys.exit(1)
    
    source_file = sys.argv[1]
    build_log_url = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(source_file):
        logger.error(f"Source file not found: {source_file}")
        sys.exit(1)
    
    # Get compilation error
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        compiler_error = result.stderr if result.returncode != 0 else ""
        
        if not compiler_error:
            logger.info("No compilation error detected")
            sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to compile source file: {e}")
        sys.exit(1)
    
    # Run analysis
    analyzer = FaultyCommitAnalyzer(source_file)
    result = analyzer.analyze(compiler_error, build_log_url)
    
    # Output result as JSON
    print(json.dumps(result, indent=2))
    
    sys.exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
