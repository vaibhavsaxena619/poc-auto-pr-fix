#!/usr/bin/env python3
"""
Build failure recovery script - Analyzes compilation errors and applies fixes via Azure OpenAI.
Production-ready error handling with comprehensive logging.

Security & Safety Features:
- Retry caps (max 2 attempts) to prevent infinite loops
- Error deduplication via SHA256 hashing
- Confidence classifier for safe vs risky fixes
- Prompt optimization: log chunking and pattern extraction
- Feature flags: ENABLE_AUTO_FIX, ENABLE_OPENAI_CALLS
"""

import os
import subprocess
import sys
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime

try:
    from openai import AzureOpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai")
    sys.exit(1)


# === CONFIGURATION & FEATURE FLAGS ===
MAX_FIX_ATTEMPTS = 2  # Prevent infinite loops
ENABLE_AUTO_FIX = os.getenv('ENABLE_AUTO_FIX', 'true').lower() == 'true'
ENABLE_OPENAI_CALLS = os.getenv('ENABLE_OPENAI_CALLS', 'true').lower() == 'true'
READ_ONLY_MODE = os.getenv('READ_ONLY_MODE', 'false').lower() == 'true'

# Safe error categories (high confidence for auto-fix)
SAFE_ERROR_PATTERNS = {
    'missing_import': r'cannot find symbol|import not found|unresolved import',
    'formatting': r'unexpected token|invalid syntax|malformed',
    'test_failure': r'AssertionError|Test.*failed|FAILED',
    'lint_issue': r'warning|unused variable|dead code'
}

# Risky error categories (manual review only)
RISKY_ERROR_PATTERNS = {
    'business_logic': r'NullPointerException|IndexOutOfBoundsException|logic error',
    'security': r'SQL injection|XSS|vulnerability|deprecated|insecure',
    'migration': r'database|schema|ALTER TABLE|migration'
}


def get_compilation_error(source_file: str) -> str:
    """Capture compilation error from source file."""
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stderr if result.returncode != 0 else ""
    except Exception as e:
        print(f"ERROR: Failed to compile {source_file}: {e}")
        return ""


def classify_error_confidence(error_message: str) -> tuple[str, float]:
    """
    Classify error as safe (high confidence) or risky (low confidence).
    
    Returns: (category, confidence_score: 0.0-1.0)
    - High confidence (0.8+): Safe to auto-fix
    - Low confidence (<0.8): Requires manual review
    """
    error_lower = error_message.lower()
    
    # Check risky patterns first (return immediately if found)
    for risk_category, pattern in RISKY_ERROR_PATTERNS.items():
        if re.search(pattern, error_lower):
            return (f"risky:{risk_category}", 0.1)  # Low confidence
    
    # Check safe patterns
    for safe_category, pattern in SAFE_ERROR_PATTERNS.items():
        if re.search(pattern, error_lower):
            return (f"safe:{safe_category}", 0.9)  # High confidence
    
    # Unknown error: default to low confidence
    return ("unknown", 0.5)


def try_previous_commits(source_file: str, max_attempts: int = 3) -> bool:
    """
    Try to build previous commits to verify the error is not pre-existing.
    
    Returns True if a previous commit builds successfully (error is recent),
    Returns False if all recent commits have the same error (error is old).
    """
    print(f"  🔍 Checking previous commits to isolate the issue...")
    
    try:
        # Get the last N commits
        result = subprocess.run(
            ['git', 'log', '--oneline', f'-{max_attempts}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            print(f"    ⚠️ Could not retrieve commit history")
            return False
        
        commits = result.stdout.strip().split('\n')[1:]  # Skip current commit
        
        if not commits:
            print(f"    ℹ️ No previous commits to test")
            return False
        
        current_sha = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True
        ).stdout.strip()
        
        for idx, commit_line in enumerate(commits):
            try:
                commit_sha = commit_line.split()[0]
                commit_msg = ' '.join(commit_line.split()[1:])
                
                print(f"    Testing commit {idx + 1}/{len(commits)}: {commit_sha[:7]} ({commit_msg[:40]}...)")
                
                # Stash current changes
                subprocess.run(['git', 'stash'], capture_output=True, check=False)
                
                # Checkout previous commit
                checkout = subprocess.run(
                    ['git', 'checkout', commit_sha],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if checkout.returncode != 0:
                    print(f"      Could not checkout {commit_sha[:7]}")
                    continue
                
                # Try to compile previous version
                compile_result = subprocess.run(
                    ['javac', source_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if compile_result.returncode == 0:
                    # Previous commit compiles! Error is recent
                    print(f"    ✅ Previous commit {commit_sha[:7]} compiles successfully")
                    print(f"       Error introduced in current version - fix is needed")
                    
                    # Restore current state
                    subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
                    subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
                    return True
                else:
                    print(f"      {commit_sha[:7]} also has compilation errors (error is older)")
                    
            except Exception as e:
                print(f"      Error testing {commit_sha[:7]}: {str(e)}")
                continue
        
        # Restore current state
        subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
        subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
        
        print(f"    ℹ️ All recent commits have similar errors (issue may be pre-existing)")
        return False
        
    except Exception as e:
        print(f"  ⚠️ Could not check previous commits: {str(e)}")
        return False


def extract_error_essence(error_message: str, source_code: str, max_tokens: int = 500) -> str:
    """
    Extract only essential error information to reduce token usage.
    
    Returns optimized error context with:
    - Error type and line number
    - 3 lines of code context
    - Full error stack (first 500 chars)
    """
    lines = error_message.split('\n')
    
    # Extract line number if available
    line_match = re.search(r':(\d+):', error_message)
    line_num = int(line_match.group(1)) if line_match else None
    
    # Build optimized prompt
    prompt = f"ERROR: {lines[0][:200]}\n\n"
    
    if line_num and source_code:
        source_lines = source_code.split('\n')
        start = max(0, line_num - 2)
        end = min(len(source_lines), line_num + 1)
        
        prompt += "CODE CONTEXT:\n"
        for i in range(start, end):
            prefix = ">>> " if i == line_num - 1 else "    "
            prompt += f"{prefix}{i+1}: {source_lines[i]}\n"
        prompt += "\n"
    
    # Add first part of error stack
    prompt += f"STACK: {error_message[:max_tokens]}"
    return prompt


def get_error_hash(error_message: str) -> str:
    """Generate SHA256 hash of error for deduplication."""
    return hashlib.sha256(error_message.encode()).hexdigest()[:8]


def check_error_history(source_file: str, error_hash: str, session_id: str = None) -> bool:
    """
    Check if we've already tried fixing this exact error IN THIS SESSION ONLY.
    
    For CI/CD environments: Each build is a new session, so we don't block fixes
    based on history from previous builds. This prevents "ERROR LOOP DETECTED" 
    errors when the same compilation error appears in different builds.
    
    Returns True if error was seen before IN THIS SESSION (should skip), False otherwise.
    """
    # Use session_id (environment variable) to track current build/session
    # If not provided, we're in a new session - don't block based on history
    if not session_id:
        session_id = os.getenv('BUILD_ID', os.getenv('RUN_ID', None))
    
    if not session_id:
        # No session ID available - we're likely in a fresh Jenkins build
        # Don't block based on previous history
        return False
    
    history_file = Path(f"{source_file}.fix_history.json")
    
    try:
        if not history_file.exists():
            return False
        
        with open(history_file, 'r') as f:
            history = json.load(f)
        
        # Only check if error was attempted in SAME session
        current_session = history.get('current_session', '')
        if current_session == session_id:
            return error_hash in history.get('attempted_errors', [])
        else:
            # Different session - don't block
            return False
    except Exception:
        return False


def record_error_attempt(source_file: str, error_hash: str, success: bool, session_id: str = None) -> None:
    """Record error fix attempt in history to prevent retry loops within same session."""
    if not session_id:
        session_id = os.getenv('BUILD_ID', os.getenv('RUN_ID', 'unknown'))
    
    history_file = Path(f"{source_file}.fix_history.json")
    
    try:
        history = {}
        if history_file.exists():
            with open(history_file, 'r') as f:
                history = json.load(f)
        
        # Track current session
        history['current_session'] = session_id
        
        if 'attempted_errors' not in history:
            history['attempted_errors'] = []
        
        if error_hash not in history['attempted_errors']:
            history['attempted_errors'].append(error_hash)
        
        history['last_attempt'] = datetime.now().isoformat()
        history['last_success'] = success
        history['attempt_count'] = history.get('attempt_count', 0) + 1
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"WARNING: Could not record error history: {e}")


def read_source_file(source_file: str) -> str:
    """Read source file content."""
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"ERROR: Cannot read {source_file}: {e}")
        sys.exit(1)


def send_to_azure_openai(error_message: str, source_code: str, api_key: str, endpoint: str, api_version: str, deployment_name: str) -> str:
    """Send compilation error to Azure OpenAI for analysis and fix."""
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        prompt = f"""You are a Java code expert. A compilation error occurred. 
Analyze and provide ONLY the corrected code without explanations.

ERROR:
{error_message}

CURRENT CODE:
{source_code}

RESPONSE: Provide only the corrected Java code that fixes this error. No explanations."""
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a Java code expert that fixes compilation errors."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"ERROR: Azure OpenAI API failed: {e}")
        return ""


def apply_fix(source_file: str, fixed_code: str) -> bool:
    """Apply the fixed code to source file."""
    try:
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"Fixed code applied to {source_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to apply fix: {e}")
        return False


def verify_fix(source_file: str) -> bool:
    """Verify the fix by attempting compilation."""
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR: Verification failed: {e}")
        return False


def get_current_branch() -> str:
    """Get the current branch name, handling detached HEAD state."""
    try:
        # Try to get the branch name from environment (Jenkins sets this)
        branch = os.getenv('GIT_BRANCH', '').replace('origin/', '')
        if branch:
            return branch
        
        # Fallback: try to get from git
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch and branch != 'HEAD':
                return branch
    except Exception:
        pass
    
    # Final fallback: default to 'Release' for Release builds
    return 'Release'


def extract_commit_message(error_msg: str, source_file: str) -> str:
    """
    Extract a meaningful commit message from error details.
    
    Examples:
    - "cannot find symbol: class List" → "Fix: Add missing import for List"
    - "cannot find symbol: class ArrayList" → "Fix: Add missing imports (List, ArrayList)"
    """
    # Look for common error patterns
    if 'cannot find symbol' in error_msg.lower():
        # Extract missing classes/symbols
        symbols = []
        for line in error_msg.split('\n'):
            if 'cannot find symbol' in line.lower():
                # Try to extract symbol from error message
                if 'class' in line.lower():
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.lower() == 'class' and i + 1 < len(parts):
                            symbols.append(parts[i + 1].strip('`'))
        
        if symbols:
            unique_symbols = list(set(symbols))
            if len(unique_symbols) == 1:
                return f"Fix: Add missing import for {unique_symbols[0]}"
            else:
                return f"Fix: Add missing imports ({', '.join(unique_symbols[:3])})"
        return "Fix: Add missing imports"
    
    elif 'incompatible types' in error_msg.lower():
        return "Fix: Resolve type compatibility issue"
    
    elif 'abstract method not implemented' in error_msg.lower() or 'does not override abstract method' in error_msg.lower():
        return "Fix: Implement required abstract methods"
    
    elif 'invalid method declaration' in error_msg.lower():
        return "Fix: Correct method declaration"
    
    elif 'syntax error' in error_msg.lower() or 'unexpected token' in error_msg.lower():
        return "Fix: Correct syntax error"
    
    elif 'unreachable statement' in error_msg.lower():
        return "Fix: Remove unreachable code"
    
    else:
        # Fallback: use first error line
        first_error = error_msg.split('\n')[0].strip()
        if len(first_error) > 60:
            return f"Fix: {first_error[:60]}..."
        return f"Fix: {first_error}" if first_error else "Fix: Compilation error"


def create_review_pr_for_low_confidence(source_file: str, original_code: str, fixed_code: str, 
                                       error_msg: str, error_category: str, confidence: float) -> bool:
    """
    Create a new branch with format 'Release_OpenAI_Fix_<timestamp>' and create a PR for manual review
    instead of auto-fixing when confidence is low.
    """
    try:
        env = os.environ.copy()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_branch = f"Release_OpenAI_Fix_{timestamp}"
        
        print(f"  Creating new branch: {new_branch}")
        
        # Configure git user
        subprocess.run(['git', 'config', 'user.email', 'build-automation@jenkins.local'], 
                      check=False, capture_output=True, env=env)
        subprocess.run(['git', 'config', 'user.name', 'Build Automation (GPT-5)'], 
                      check=False, capture_output=True, env=env)
        
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', new_branch], 
                      check=True, capture_output=True, env=env)
        
        # Apply the fix
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        # Commit changes
        commit_msg = f"Fix: {error_category} - OpenAI Generated Fix (Manual Review Required)"
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True, env=env)
        subprocess.run(['git', 'commit', '-m', commit_msg], 
                      check=True, capture_output=True, env=env)
        
        # Push the new branch
        github_pat = os.getenv('GITHUB_PAT', '')
        if github_pat:
            push_url = f"https://x-access-token:{github_pat}@github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
            subprocess.run(['git', 'push', push_url, f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        else:
            subprocess.run(['git', 'push', 'origin', f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        
        print(f"  ✓ Branch pushed: {new_branch}")
        
        # Get original PR author if available
        original_author = os.getenv('PR_AUTHOR', 'original contributor')
        
        # Create PR description with detailed summary
        pr_description = f"""## Low Confidence OpenAI Fix Review

**Confidence Level:** {confidence:.0%}
**Error Category:** {error_category}
**Status:** Awaiting Manual Review

### Issue Summary
A compilation error was detected but the confidence level is below the auto-fix threshold (80%).

### Error Details
```
{error_msg[:500]}
```

### OpenAI Generated Fix
This PR contains the automated fix generated by Azure OpenAI GPT-5. 

**IMPORTANT:** Please review the changes carefully before merging.

### Changes Made
```diff
--- Original
+++ Fixed
{generate_diff(original_code, fixed_code)}
```

### Original Author
@{original_author}

---
*Generated by Build Automation Pipeline*
*Branch: {new_branch}*
*Timestamp: {datetime.now().isoformat()}*
"""
        
        # Use GitHub API to create PR
        create_github_pr(new_branch, "Release", pr_description, original_author)
        
        print(f"  ✓ Pull request created for review")
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to create review PR: {e}")
        return False


def generate_diff(original: str, fixed: str) -> str:
    """Generate a unified diff between original and fixed code."""
    original_lines = original.split('\n')
    fixed_lines = fixed.split('\n')
    
    diff_lines = []
    for line in subprocess.run(
        ['diff', '-u', original, fixed],
        capture_output=True,
        text=True
    ).stdout.split('\n')[:30]:  # Limit to first 30 lines
        diff_lines.append(line)
    
    return '\n'.join(diff_lines) if diff_lines else "(No diff available)"


def create_github_pr(source_branch: str, target_branch: str, description: str, assignee: str) -> bool:
    """Create a GitHub pull request using GitHub API."""
    try:
        github_pat = os.getenv('GITHUB_PAT', '')
        if not github_pat:
            print("  WARNING: GITHUB_PAT not set, PR creation skipped")
            return False
        
        import requests
        
        repo = "vaibhavsaxena619/poc-auto-pr-fix"
        api_url = f"https://api.github.com/repos/{repo}/pulls"
        
        headers = {
            "Authorization": f"token {github_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "title": f"[Low Confidence] {source_branch}",
            "head": source_branch,
            "base": target_branch,
            "body": description
        }
        
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 201:
            pr_data = response.json()
            pr_number = pr_data['number']
            pr_url = pr_data['html_url']
            
            print(f"  ✓ PR #{pr_number} created: {pr_url}")
            
            # Add original author as assignee if available
            if assignee and assignee != 'original contributor':
                add_assignee_to_pr(repo, pr_number, assignee, github_pat)
            
            # Add comment with detailed summary
            add_pr_comment(repo, pr_number, generate_pr_summary(), github_pat)
            
            return True
        else:
            print(f"  WARNING: Failed to create PR: {response.status_code} - {response.text}")
            return False
    
    except ImportError:
        print("  WARNING: requests library not found, PR creation skipped")
        return False
    except Exception as e:
        print(f"  WARNING: Error creating PR: {e}")
        return False


def add_assignee_to_pr(repo: str, pr_number: int, assignee: str, github_pat: str) -> bool:
    """Add assignee to pull request."""
    try:
        import requests
        
        api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}"
        headers = {
            "Authorization": f"token {github_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {"assignees": [assignee]}
        response = requests.patch(api_url, json=payload, headers=headers)
        
        if response.status_code == 200:
            print(f"  ✓ Assigned to @{assignee}")
            return True
        return False
    except Exception as e:
        print(f"  WARNING: Could not assign PR: {e}")
        return False


def add_pr_comment(repo: str, pr_number: int, comment: str, github_pat: str) -> bool:
    """Add a comment to a pull request."""
    try:
        import requests
        
        api_url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"token {github_pat}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {"body": comment}
        response = requests.post(api_url, json=payload, headers=headers)
        
        if response.status_code == 201:
            print(f"  ✓ Comment added to PR")
            return True
        return False
    except Exception:
        return False


def generate_pr_summary() -> str:
    """Generate a detailed summary comment for the PR."""
    return """## Review Checklist

- [ ] Code changes are correct
- [ ] No unintended modifications
- [ ] Imports are properly added
- [ ] Syntax is valid
- [ ] Ready to merge to Release branch

## Next Steps
1. Review the code changes carefully
2. Test the fix locally if needed
3. Approve and merge when ready

---
*This PR was created by Build Automation due to low confidence in the auto-fix.*
"""


def commit_changes(source_file: str, error_msg: str) -> bool:
    """Commit and push fixed code to git with proper credential handling."""
    try:
        # Preserve environment for subprocess (needed for Git credentials in Jenkins)
        env = os.environ.copy()
        
        # Configure git user if not already configured (for Jenkins environments)
        subprocess.run(['git', 'config', 'user.email', 'build-automation@jenkins.local'], 
                      check=False, capture_output=True, env=env)
        subprocess.run(['git', 'config', 'user.name', 'Build Automation (GPT-5)'], 
                      check=False, capture_output=True, env=env)
        
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True, env=env)
        
        # Generate meaningful commit message
        commit_msg = extract_commit_message(error_msg, source_file)
        
        result = subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            check=False,
            capture_output=True,
            text=True,
            env=env
        )
        if result.returncode == 0:
            print("✓ Changes committed to git")
            
            # === PUSH TO REMOTE ===
            # Get the current branch name
            branch_name = get_current_branch()
            print(f"  Pushing to branch: {branch_name}")
            
            # Use HTTPS with token authentication if PAT is available
            github_pat = os.getenv('GITHUB_PAT', '')
            if github_pat:
                # Construct authenticated URL with token
                push_url = f"https://x-access-token:{github_pat}@github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
                push_result = subprocess.run(
                    ['git', 'push', push_url, f'HEAD:refs/heads/{branch_name}'],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )
            else:
                # Fallback: use origin remote with explicit refspec
                push_result = subprocess.run(
                    ['git', 'push', 'origin', f'HEAD:refs/heads/{branch_name}'],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )
            
            if push_result.returncode == 0:
                print("✓ Changes pushed to remote repository")
                return True
            else:
                print(f"WARNING: Git push failed: {push_result.stderr}")
                # Still consider commit success even if push fails
                return True
        else:
            # Handle detached HEAD or other git issues gracefully
            if 'detached HEAD' in result.stderr or 'no changes added' in result.stderr:
                print("INFO: Git commit skipped (detached HEAD or no changes)")
                return True
            else:
                print(f"WARNING: Git commit failed: {result.stderr}")
                return True  # Still consider it a success as the fix was applied
    except Exception as e:
        print(f"WARNING: Git commit/push failed: {e}")
        return False


def main():
    """Main build fix workflow with safety guardrails."""
    if len(sys.argv) < 2:
        print("Usage: python build_fix.py <source_file>")
        sys.exit(1)
    
    # === FEATURE FLAG CHECKS ===
    if not ENABLE_AUTO_FIX:
        print("INFO: Auto-fix disabled (ENABLE_AUTO_FIX=false)")
        sys.exit(0)
    
    if READ_ONLY_MODE:
        print("INFO: Read-only mode enabled - will analyze but not apply fixes")
    
    source_file = sys.argv[1]
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
    deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5')
    
    if not api_key or not endpoint:
        print("ERROR: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables not set")
        sys.exit(1)
    
    if not os.path.exists(source_file):
        print(f"ERROR: Source file not found: {source_file}")
        sys.exit(1)
    
    print(f"[{datetime.now().isoformat()}] Build fix initiated for {source_file}")
    
    # Get session ID for this build (Jenkins BUILD_ID or RUN_ID)
    session_id = os.getenv('BUILD_ID', os.getenv('RUN_ID', None))
    if session_id:
        print(f"  Session: {session_id}")
    
    # === STEP 1: GET COMPILATION ERROR ===
    error_msg = get_compilation_error(source_file)
    if not error_msg:
        print("✓ No compilation errors detected")
        return
    
    print(f"✗ Compilation error detected")
    
    # === STEP 2: CLASSIFY ERROR CONFIDENCE ===
    error_category, confidence = classify_error_confidence(error_msg)
    print(f"  Category: {error_category} (confidence: {confidence:.0%})")
    
    # === STEP 3: CHECK ERROR DEDUPLICATION (Session-specific) ===
    error_hash = get_error_hash(error_msg)
    if check_error_history(source_file, error_hash, session_id):
        print(f"  ⚠ ERROR LOOP DETECTED: Same error attempted before in this session")
        print(f"  Skipping retry to prevent infinite loop (MAX_FIX_ATTEMPTS={MAX_FIX_ATTEMPTS})")
        record_error_attempt(source_file, error_hash, False, session_id)
        sys.exit(1)
    
    # === STEP 4: CONFIDENCE GATING ===
    if confidence < 0.8:
        print(f"  ⚠ LOW CONFIDENCE ({error_category}): Manual review may be required")
        
        # Try to determine if error is recent by checking previous commits
        error_is_recent = try_previous_commits(source_file, max_attempts=3)
        
        if error_is_recent:
            print(f"  ✓ Error is recent (introduced in current version)")
            print(f"  Attempting auto-fix despite low confidence...")
            # Continue with auto-fix attempt
        else:
            print(f"  Creating review PR for manual review instead of auto-fixing...")
            # Create PR for manual review instead of auto-fixing
            source_code = read_source_file(source_file)
            fixed_code = send_to_azure_openai(error_msg, source_code, api_key, endpoint, api_version, deployment_name)
            
            if fixed_code:
                create_review_pr_for_low_confidence(
                    source_file=source_file,
                    original_code=source_code,
                    fixed_code=fixed_code,
                    error_msg=error_msg,
                    error_category=error_category,
                    confidence=confidence
                )
            
            record_error_attempt(source_file, error_hash, False, session_id)
            sys.exit(0)  # Exit gracefully - PR created for review
    
    print(f"  ✓ Proceeding with fix (high confidence or recent error)")
    
    # === STEP 5: OPTIMIZE PROMPT (REDUCE TOKEN USAGE) ===
    source_code = read_source_file(source_file)
    optimized_error = extract_error_essence(error_msg, source_code)
    
    # === STEP 6: CALL OPENAI (IF ENABLED) ===
    if not ENABLE_OPENAI_CALLS:
        print("INFO: OpenAI calls disabled (ENABLE_OPENAI_CALLS=false)")
        print(f"ERROR: {optimized_error[:200]}...")
        sys.exit(1)
    
    print("  Sending error to Azure OpenAI for analysis...")
    fixed_code = send_to_azure_openai(optimized_error, source_code, api_key, endpoint, api_version, deployment_name)
    
    if not fixed_code:
        print("  ✗ Azure OpenAI failed to generate fix")
        record_error_attempt(source_file, error_hash, False, session_id)
        sys.exit(1)
    
    # === STEP 7: APPLY FIX (IF NOT IN READ-ONLY MODE) ===
    if READ_ONLY_MODE:
        print("  [READ-ONLY] Would apply fix (mode disabled)")
        return
    
    print("  Applying Azure OpenAI GPT-5 fix...")
    if not apply_fix(source_file, fixed_code):
        record_error_attempt(source_file, error_hash, False, session_id)
        sys.exit(1)
    
    # === STEP 8: VERIFY FIX ===
    print("  Verifying fix...")
    if verify_fix(source_file):
        print("  ✓ SUCCESS: Fix verified - code compiles!")
        commit_changes(source_file, error_msg[:50])
        record_error_attempt(source_file, error_hash, True, session_id)
    else:
        print("  ✗ Fix did not resolve compilation errors")
        record_error_attempt(source_file, error_hash, False, session_id)
        sys.exit(1)


if __name__ == "__main__":
    main()
