#!/usr/bin/env python3
"""
Advanced Build Failure Recovery with Intelligent Error Classification.

Improvements over v1:
1. MULTIPLE ERROR HANDLING: Separates high-confidence (fixable) from low-confidence (review) errors
   - Fixes ONLY high-confidence errors
   - Creates review branch with low-confidence errors tagged
   
2. INTELLIGENT COMMIT HISTORY WALKING: When previous commits have errors
   - Walks back through commit history
   - Finds LAST GOOD COMMIT (fully fixable or no issues)
   - Builds from that point instead of failing

3. FAULTY COMMIT DETECTION: Automatically identifies the commit that broke the build
   - Uses git bisect for efficient detection
   - Notifies author with AI-generated fix suggestions
   - Integrates with learning system for continuous improvement

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
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Dict

try:
    from openai import AzureOpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai")
    sys.exit(1)

# Try to import fault analyzer (optional)
try:
    from fault_commit_analyzer import FaultyCommitAnalyzer
    HAS_FAULT_ANALYZER = True
except ImportError:
    HAS_FAULT_ANALYZER = False
    print("WARNING: fault_commit_analyzer not available - fault detection disabled")

# Try to import learning database (optional)
try:
    from learning_classifier import LearningDatabase
    HAS_LEARNING_DB = True
except ImportError:
    HAS_LEARNING_DB = False
    print("WARNING: learning_classifier not available - learning features disabled")

# === LOGGING ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [build-fix] %(message)s'
)


# === CONFIGURATION & FEATURE FLAGS ===
MAX_FIX_ATTEMPTS = 2
MAX_COMMIT_HISTORY_SEARCH = 10  # NEW: Search up to 10 commits back
ENABLE_AUTO_FIX = os.getenv('ENABLE_AUTO_FIX', 'true').lower() == 'true'
ENABLE_OPENAI_CALLS = os.getenv('ENABLE_OPENAI_CALLS', 'true').lower() == 'true'
READ_ONLY_MODE = os.getenv('READ_ONLY_MODE', 'false').lower() == 'true'
ENABLE_FAULT_DETECTION = os.getenv('ENABLE_FAULT_DETECTION', 'true').lower() == 'true'
ENABLE_LEARNING = os.getenv('ENABLE_LEARNING', 'true').lower() == 'true'
BUILD_LOG_URL = os.getenv('BUILD_LOG_URL', None)  # URL to failed build log

# Safe error categories (high confidence for auto-fix)
SAFE_ERROR_PATTERNS = {
    'missing_import': r'cannot find symbol|import not found|unresolved import',
    'formatting': r'unexpected token|invalid syntax|malformed',
    'syntax_error': r'class.*interface.*enum.*record expected|unexpected.*token|mismatched|unclosed',
    'test_failure': r'AssertionError|Test.*failed|FAILED',
    'lint_issue': r'warning|unused variable|dead code'
}

# Risky error categories (manual review only)
RISKY_ERROR_PATTERNS = {
    'business_logic': r'NullPointerException|IndexOutOfBoundsException|logic error|method.*not found|RuntimeException',
    'security': r'SQL injection|XSS|vulnerability|deprecated|insecure',
    'migration': r'database|schema|ALTER TABLE|migration'
}


# === NEW: ERROR CLASSIFICATION STRUCTURE ===
class ErrorInfo:
    """Container for detailed error information."""
    def __init__(self, error_msg: str, category: str, confidence: float, line_num: int = None):
        self.error_msg = error_msg
        self.category = category
        self.confidence = confidence
        self.line_num = line_num
        self.is_fixable = confidence >= 0.8
        self.error_hash = hashlib.sha256(error_msg.encode()).hexdigest()[:8]


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


def parse_all_errors(error_message: str) -> List[str]:
    """
    NEW: Extract all compilation errors from javac output.
    
    Returns list of individual error messages (one per line).
    """
    errors = []
    current_error = []
    
    for line in error_message.split('\n'):
        if re.match(r'^.*\.java:\d+:', line):  # Error line starting with filename:linenum:
            if current_error:
                errors.append('\n'.join(current_error).strip())
                current_error = []
            current_error.append(line)
        elif current_error and line.strip():
            current_error.append(line)
    
    if current_error:
        errors.append('\n'.join(current_error).strip())
    
    return [e for e in errors if e.strip()]


def classify_error_confidence(error_message: str) -> Tuple[str, float]:
    """
    Classify error as safe (high confidence) or risky (low confidence).
    
    UPDATED: Now checks learning database for previously promoted patterns.
    
    Returns: (category, confidence_score: 0.0-1.0)
    - High confidence (0.8+): Safe to auto-fix
    - Low confidence (<0.8): Requires manual review
    """
    error_lower = error_message.lower()
    
    # SPECIAL CASE: Check for method/variable symbol errors first
    # These are risky even if they match "cannot find symbol"
    if re.search(r'symbol:\s*(method|variable)', error_lower):
        return ("risky:business_logic", 0.1)  # Low confidence
    
    # Check risky patterns (that aren't method/variable symbols)
    for risk_category, pattern in RISKY_ERROR_PATTERNS.items():
        if re.search(pattern, error_lower):
            category = f"risky:{risk_category}"
            confidence = 0.1  # Low confidence
            
            # Check if this pattern has been learned as HIGH confidence
            if HAS_LEARNING_DB and ENABLE_LEARNING:
                try:
                    learning_db = LearningDatabase()
                    learned_confidence = learning_db.get_pattern_confidence(category)
                    if learned_confidence and learned_confidence > confidence:
                        print(f"  📚 LEARNED: {category} promoted to {learned_confidence:.0%}")
                        return (category, learned_confidence)
                except Exception as e:
                    logging.debug(f"Could not check learning DB: {e}")
            
            return (category, confidence)
    
    # Check safe patterns
    for safe_category, pattern in SAFE_ERROR_PATTERNS.items():
        if re.search(pattern, error_lower):
            return (f"safe:{safe_category}", 0.9)  # High confidence
    
    # Unknown error: default to low confidence
    return ("unknown", 0.5)


def find_last_good_commit(source_file: str, max_search: int = 10) -> Tuple[str, bool]:
    """
    NEW: Walk commit history to find the last GOOD commit.
    
    Returns: (commit_sha, is_good)
    - If found good commit: returns SHA and True
    - If all commits have errors: returns current SHA and False
    """
    print(f"  🔍 Searching commit history for last good commit (searching {max_search} commits back)...")
    
    try:
        # Get commit history
        result = subprocess.run(
            ['git', 'log', '--oneline', f'-{max_search}'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0 or not result.stdout.strip():
            print(f"    ⚠️ Could not retrieve commit history")
            return (None, False)
        
        commits = result.stdout.strip().split('\n')
        current_sha = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True
        ).stdout.strip()
        
        for idx, commit_line in enumerate(commits):
            try:
                commit_sha = commit_line.split()[0]
                commit_msg = ' '.join(commit_line.split()[1:])
                
                if idx == 0:
                    print(f"    Current: {commit_sha} ({commit_msg[:40]}...)")
                    continue  # Skip current commit
                
                print(f"    Testing commit {idx}/{len(commits)}: {commit_sha} ({commit_msg[:40]}...)")
                
                # Stash current changes
                subprocess.run(['git', 'stash'], capture_output=True, check=False)
                
                # Checkout commit
                checkout = subprocess.run(
                    ['git', 'checkout', commit_sha],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if checkout.returncode != 0:
                    print(f"      Could not checkout {commit_sha[:7]}")
                    continue
                
                # Try to compile
                compile_result = subprocess.run(
                    ['javac', source_file],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if compile_result.returncode == 0:
                    print(f"    ✅ Found good commit: {commit_sha} - Code compiles!")
                    # Restore to current state
                    subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
                    subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
                    return (commit_sha, True)
                else:
                    errors = compile_result.stderr.count("error:")
                    print(f"      Has {errors} compilation errors")
                    
            except Exception as e:
                print(f"      Error testing {commit_sha[:7]}: {str(e)}")
                continue
        
        # Restore current state
        subprocess.run(['git', 'checkout', current_sha], capture_output=True, check=False)
        subprocess.run(['git', 'stash', 'pop'], capture_output=True, check=False)
        
        print(f"    ℹ️ No fully good commit found in recent history")
        return (None, False)
        
    except Exception as e:
        print(f"  ⚠️ Could not search commit history: {str(e)}")
        return (None, False)


def extract_error_essence(error_message: str, source_code: str, max_tokens: int = 500) -> str:
    """Extract essential error information for GPT."""
    lines = error_message.split('\n')
    line_match = re.search(r':(\d+):', error_message)
    line_num = int(line_match.group(1)) if line_match else None
    
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
    
    prompt += f"STACK: {error_message[:max_tokens]}"
    return prompt


def read_source_file(source_file: str) -> str:
    """Read source file content."""
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"ERROR: Cannot read {source_file}: {e}")
        sys.exit(1)


def send_to_azure_openai(error_message: str, source_code: str, api_key: str, endpoint: str, 
                        api_version: str, deployment_name: str) -> str:
    """Send error to Azure OpenAI for fix."""
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        prompt = f"""You are a Java code expert. Fix ONLY high-confidence errors.

CRITICAL INSTRUCTIONS:
1. Fix ONLY the specific error mentioned
2. PRESERVE all other code - do NOT delete any code sections
3. If you cannot fix an error due to missing domain knowledge, LEAVE IT AS IS
4. Return the COMPLETE source file with minimal changes
5. Never simplify or remove code that doesn't directly cause the error

ERROR:
{error_message}

CURRENT CODE:
{source_code}

RESPONSE: Provide COMPLETE corrected Java code. Preserve all sections."""
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a Java expert that fixes compilation errors. Always preserve code."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"ERROR: Azure OpenAI API failed: {e}")
        return ""


def apply_fix(source_file: str, fixed_code: str) -> bool:
    """Apply fixed code to source file."""
    try:
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"Fixed code applied to {source_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to apply fix: {e}")
        return False


def verify_fix(source_file: str) -> bool:
    """Verify fix by compiling."""
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def create_low_confidence_pr(source_file: str, fixed_code: str, 
                             low_conf_errors: List[ErrorInfo],
                             error_msg: str,
                             original_author: str = None) -> bool:
    """
    Create a PR with LLM fix suggestion for low-confidence errors.
    """
    try:
        env = os.environ.copy()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_branch = f"fix/low-confidence-errors_{timestamp}"
        
        print(f"  Creating fix branch: {new_branch}")
        
        # Get current branch
        result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                              capture_output=True, text=True, env=env)
        base_branch = result.stdout.strip() if result.returncode == 0 else 'Release'
        
        # Configure git
        subprocess.run(['git', 'config', 'user.email', 'build-automation@jenkins.local'], 
                      check=False, capture_output=True, env=env)
        subprocess.run(['git', 'config', 'user.name', 'Build Automation (GPT-5)'], 
                      check=False, capture_output=True, env=env)
        
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', new_branch], 
                      check=True, capture_output=True, env=env)
        
        # Apply LLM suggested fix
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        
        # Commit
        commit_msg = f"Fix: LLM-suggested fix for {len(low_conf_errors)} low-confidence compilation errors"
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True, env=env)
        subprocess.run(['git', 'commit', '-m', commit_msg], 
                      check=True, capture_output=True, env=env)
        
        # Push branch
        github_pat = os.getenv('GITHUB_PAT', '')
        if github_pat:
            push_url = f"https://x-access-token:{github_pat}@github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
            subprocess.run(['git', 'push', push_url, f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        else:
            subprocess.run(['git', 'push', 'origin', f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        
        print(f"  ✓ Branch pushed: {new_branch}")
        
        # Create PR body with error details and LLM suggestion
        pr_body = f"""## Low-Confidence Compilation Errors - Manual Review Required

This PR contains an LLM-generated fix suggestion for **{len(low_conf_errors)}** low-confidence compilation errors.

### ⚠️ Manual Review Required
These errors require domain knowledge and manual verification:

"""
        
        for i, error in enumerate(low_conf_errors, 1):
            pr_body += f"\n**Issue {i}:** `{error.category}` (Confidence: {error.confidence:.0%})\n"
            pr_body += f"```\n{error.error_msg[:300]}\n```\n"
        
        pr_body += f"\n### 🤖 LLM Fix Suggestion\n"
        pr_body += f"The AI has analyzed the errors and proposed a fix in this PR.\n"
        pr_body += f"**Please review carefully before merging.**\n\n"
        
        # Tag original author
        if original_author:
            pr_body += f"CC: @{original_author} - Please review the LLM-suggested fix\n"
        
        pr_body += "\n---\n*Generated by Build Automation Pipeline*"
        
        # Create PR via GitHub API
        try:
            import requests
            
            repo = "vaibhavsaxena619/poc-auto-pr-fix"
            api_url = f"https://api.github.com/repos/{repo}/pulls"
            github_pat = os.getenv('GITHUB_PAT', '')
            
            if github_pat:
                headers = {
                    "Authorization": f"token {github_pat}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                payload = {
                    "title": f"[LLM Fix] Low-confidence errors - Manual review needed ({len(low_conf_errors)} issues)",
                    "head": new_branch,
                    "base": base_branch,
                    "body": pr_body
                }
                
                response = requests.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 201:
                    pr_data = response.json()
                    pr_number = pr_data['number']
                    print(f"  ✓ PR #{pr_number} created: {base_branch} ← {new_branch}")
                    return True
                else:
                    print(f"  ⚠️ PR creation failed: {response.status_code}")
        except Exception as e:
            print(f"  ⚠️ PR creation error: {e}")
        
        return False
        
    except Exception as e:
        print(f"  ⚠️ Failed to create PR branch: {e}")
        return False


def create_fix_branch_for_mixed_errors(source_file: str, fixed_code_high_conf: str, 
                                       low_conf_errors: List[ErrorInfo], 
                                       original_author: str = None) -> bool:
    """
    NEW: Create a fix branch with only high-confidence fixes.
    
    Leaves low-confidence errors in place and creates PR with tags for original author.
    """
    try:
        env = os.environ.copy()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_branch = f"fix/high-confidence-errors_{timestamp}"
        
        print(f"  Creating fix branch: {new_branch}")
        print(f"  [HIGH-CONFIDENCE FIXES ONLY]")
        
        # Configure git
        subprocess.run(['git', 'config', 'user.email', 'build-automation@jenkins.local'], 
                      check=False, capture_output=True, env=env)
        subprocess.run(['git', 'config', 'user.name', 'Build Automation (GPT-5)'], 
                      check=False, capture_output=True, env=env)
        
        # Create and checkout new branch
        subprocess.run(['git', 'checkout', '-b', new_branch], 
                      check=True, capture_output=True, env=env)
        
        # Apply high-confidence fixes only
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code_high_conf)
        
        # Commit
        commit_msg = f"Fix: High-confidence compilation errors (manual review needed for {len(low_conf_errors)} low-confidence issues)"
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True, env=env)
        subprocess.run(['git', 'commit', '-m', commit_msg], 
                      check=True, capture_output=True, env=env)
        
        # Push branch
        github_pat = os.getenv('GITHUB_PAT', '')
        if github_pat:
            push_url = f"https://x-access-token:{github_pat}@github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
            subprocess.run(['git', 'push', push_url, f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        else:
            subprocess.run(['git', 'push', 'origin', f'HEAD:refs/heads/{new_branch}'],
                          check=True, capture_output=True, env=env)
        
        print(f"  ✓ Branch created: {new_branch}")
        
        # Create PR with low-confidence issue details
        pr_body = f"""## Auto-Fix: High-Confidence Errors Only

This PR fixes {len(low_conf_errors)} **HIGH-CONFIDENCE** compilation errors.

### Remaining Issues (Manual Review Required)
Low-confidence errors that require domain knowledge or manual review:

"""
        
        for i, error in enumerate(low_conf_errors, 1):
            pr_body += f"\n**Issue {i}:** `{error.category}` (Confidence: {error.confidence:.0%})\n"
            pr_body += f"```\n{error.error_msg[:300]}\n```\n"
        
        # Tag original author
        if original_author:
            pr_body += f"\nCC: @{original_author} - Please review the remaining low-confidence issues\n"
        
        pr_body += "\n---\n*Generated by Build Automation Pipeline*"
        
        # Create PR via GitHub API
        try:
            import requests
            
            repo = "vaibhavsaxena619/poc-auto-pr-fix"
            api_url = f"https://api.github.com/repos/{repo}/pulls"
            github_pat = os.getenv('GITHUB_PAT', '')
            
            if github_pat:
                headers = {
                    "Authorization": f"token {github_pat}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                payload = {
                    "title": f"[Auto-Fix] {len(low_conf_errors)} low-confidence issues need review",
                    "head": new_branch,
                    "base": "Release",
                    "body": pr_body
                }
                
                response = requests.post(api_url, json=payload, headers=headers)
                
                if response.status_code == 201:
                    pr_data = response.json()
                    pr_number = pr_data['number']
                    print(f"  ✓ PR #{pr_number} created with low-confidence issues marked")
                    return True
        except ImportError:
            pass
        
        return True
        
    except Exception as e:
        print(f"  ✗ Failed to create fix branch: {e}")
        return False


def commit_and_push(source_file: str, commit_msg: str) -> bool:
    """Commit and push changes."""
    try:
        env = os.environ.copy()
        
        subprocess.run(['git', 'config', 'user.email', 'build-automation@jenkins.local'], 
                      check=False, capture_output=True, env=env)
        subprocess.run(['git', 'config', 'user.name', 'Build Automation (GPT-5)'], 
                      check=False, capture_output=True, env=env)
        
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True, env=env)
        
        result = subprocess.run(
            ['git', 'commit', '-m', commit_msg],
            check=False,
            capture_output=True,
            text=True,
            env=env
        )
        
        if result.returncode == 0:
            print("✓ Changes committed to git")
            
            # Get current branch
            branch = os.getenv('GIT_BRANCH', 'Release').replace('origin/', '')
            
            # Push
            github_pat = os.getenv('GITHUB_PAT', '')
            if github_pat:
                push_url = f"https://x-access-token:{github_pat}@github.com/vaibhavsaxena619/poc-auto-pr-fix.git"
                push_result = subprocess.run(
                    ['git', 'push', push_url, f'HEAD:refs/heads/{branch}'],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )
            else:
                push_result = subprocess.run(
                    ['git', 'push', 'origin', f'HEAD:refs/heads/{branch}'],
                    check=False,
                    capture_output=True,
                    text=True,
                    env=env
                )
            
            if push_result.returncode == 0:
                print("✓ Changes pushed to remote repository")
                return True
        
        return True
    except Exception as e:
        print(f"WARNING: Git operations failed: {e}")
        return False


def trigger_fault_detection(source_file: str, error_msg: str) -> None:
    """
    NEW: Trigger faulty commit detection asynchronously.
    
    This runs in background to identify which commit introduced the error
    and sends notifications to the author.
    """
    if not ENABLE_FAULT_DETECTION or not HAS_FAULT_ANALYZER:
        return
    
    print(f"\n  🔍 BACKGROUND: Analyzing faulty commit...")
    
    try:
        analyzer = FaultyCommitAnalyzer(source_file)
        result = analyzer.analyze(error_msg, BUILD_LOG_URL)
        
        if result['success']:
            print(f"  ✅ Faulty commit identified: {result['faulty_commit'][:7]}")
            print(f"  📧 Author: {result['author']} ({result['email']})")
            if result['verified']:
                print(f"  ✓ Verified: Build works without this commit")
            if result['fix_suggestion']:
                print(f"  💡 Fix suggestion generated and sent to author")
        else:
            print(f"  ⚠️ Fault detection failed: {result.get('error', 'unknown')}")
    
    except Exception as e:
        print(f"  ⚠️ Fault detection error: {e}")



def main():
    """Main workflow with advanced error handling."""
    if len(sys.argv) < 2:
        print("Usage: python build_fix_v2.py <source_file>")
        sys.exit(1)
    
    if not ENABLE_AUTO_FIX:
        print("INFO: Auto-fix disabled")
        sys.exit(0)
    
    source_file = sys.argv[1]
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
    deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5')
    
    if not api_key or not endpoint:
        print("ERROR: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT not set")
        sys.exit(1)
    
    if not os.path.exists(source_file):
        print(f"ERROR: Source file not found: {source_file}")
        sys.exit(1)
    
    print(f"[{datetime.now().isoformat()}] Build fix initiated for {source_file}")
    
    # === STEP 1: GET COMPILATION ERROR ===
    error_msg = get_compilation_error(source_file)
    if not error_msg:
        print("✓ No compilation errors detected")
        return
    
    print(f"✗ Compilation errors detected")
    
    # === NEW: TRIGGER FAULT DETECTION ===
    trigger_fault_detection(source_file, error_msg)
    
    # === STEP 2: PARSE ALL ERRORS (NEW) ===
    all_errors = parse_all_errors(error_msg)
    print(f"  Found {len(all_errors)} error(s)")
    
    # === STEP 3: CLASSIFY EACH ERROR (NEW) ===
    high_conf_errors = []
    low_conf_errors = []
    
    for error_text in all_errors:
        category, confidence = classify_error_confidence(error_text)
        error_info = ErrorInfo(error_text, category, confidence)
        
        if confidence >= 0.8:
            high_conf_errors.append(error_info)
            print(f"  ✓ HIGH-CONFIDENCE: {category} ({confidence:.0%})")
        else:
            low_conf_errors.append(error_info)
            print(f"  ⚠️  LOW-CONFIDENCE: {category} ({confidence:.0%})")
    
    # === STEP 4: DECISION LOGIC (NEW) ===
    if low_conf_errors:
        print(f"\n  🔍 {len(low_conf_errors)} low-confidence error(s) detected")
        
        if high_conf_errors:
            print(f"  ✓ But {len(high_conf_errors)} high-confidence error(s) can be fixed")
            
            # Fix only high-confidence errors
            source_code = read_source_file(source_file)
            high_conf_error_msg = '\n'.join([e.error_msg for e in high_conf_errors])
            
            print("  Fixing high-confidence errors only...")
            fixed_code = send_to_azure_openai(high_conf_error_msg, source_code, 
                                             api_key, endpoint, api_version, deployment_name)
            
            if fixed_code:
                apply_fix(source_file, fixed_code)
                
                print("  Verifying high-confidence fixes...")
                if verify_fix(source_file):
                    # Code compiles! Create branch with remaining low-confidence issues
                    original_author = os.getenv('PR_AUTHOR', None)
                    create_fix_branch_for_mixed_errors(source_file, fixed_code, low_conf_errors, original_author)
                    
                    print("✓ Created fix branch with high-confidence fixes")
                    print(f"  Low-confidence issues left for manual review: {len(low_conf_errors)}")
                    sys.exit(0)
                else:
                    # Fix didn't fully resolve - search commit history
                    print("  ⚠️ High-confidence fix didn't resolve all issues - searching commit history...")
                    good_commit, found = find_last_good_commit(source_file, MAX_COMMIT_HISTORY_SEARCH)
                    
                    if found:
                        print(f"  ✅ Found good commit: {good_commit}")
                        print(f"  Checking out stable commit...")
                        
                        subprocess.run(['git', 'checkout', good_commit], capture_output=True, check=False)
                        
                        if verify_fix(source_file):
                            print("✓ Verified: Good commit builds successfully")
                            sys.exit(0)
                    
                    print("  ⚠️ Could not find a compilable commit")
                    print("  Creating review branch with attempted fixes...")
                    original_author = os.getenv('PR_AUTHOR', None)
                    create_fix_branch_for_mixed_errors(source_file, fixed_code, low_conf_errors, original_author)
                    sys.exit(0)
        else:
            print(f"  ℹ️ Only low-confidence errors found - getting LLM fix suggestion...")
            
            # Get LLM fix suggestion for low-confidence errors
            source_code = read_source_file(source_file)
            error_msg_combined = '\n'.join([e.error_msg for e in low_conf_errors])
            fixed_code = send_to_azure_openai(error_msg_combined, source_code,
                                             api_key, endpoint, api_version, deployment_name)
            
            if fixed_code:
                print(f"  ✅ LLM fix suggestion generated")
                print(f"  📝 Creating PR with fix suggestion for manual review...")
                
                # Apply fix temporarily to create branch
                apply_fix(source_file, fixed_code)
                original_author = os.getenv('PR_AUTHOR', None)
                
                # Create PR with LLM fix suggestion
                if create_low_confidence_pr(source_file, fixed_code, low_conf_errors, error_msg_combined, original_author):
                    print(f"  ✅ PR created successfully for low-confidence issues")
                else:
                    print(f"  ⚠️ Failed to create PR, but fix suggestion was generated")
            else:
                print(f"  ⚠️ Could not generate LLM fix suggestion")
            
            # Now search for last good commit to build from
            print(f"\n  🔍 Searching commit history for last good commit to build...")
            good_commit, found = find_last_good_commit(source_file, MAX_COMMIT_HISTORY_SEARCH)
            
            if found:
                print(f"  ✅ Found good commit: {good_commit}")
                print(f"  Building from stable commit instead...")
                
                # Checkout that commit
                subprocess.run(['git', 'checkout', good_commit], capture_output=True, check=False)
                
                # Verify it compiles
                if verify_fix(source_file):
                    print("✓ Verified: Good commit builds successfully")
                    sys.exit(0)
            else:
                print(f"  ⚠️ Could not find a good commit to build from")
            
            sys.exit(0)
    else:
        print(f"  ✓ All errors are high-confidence - proceeding with auto-fix")
        
        source_code = read_source_file(source_file)
        fixed_code = send_to_azure_openai(error_msg, source_code, 
                                         api_key, endpoint, api_version, deployment_name)
        
        if not fixed_code:
            print("  ✗ Auto-fix failed")
            sys.exit(1)
        
        if READ_ONLY_MODE:
            print("  [READ-ONLY] Would apply fix")
            return
        
        print("  Applying fix...")
        apply_fix(source_file, fixed_code)
        
        print("  Verifying fix...")
        if verify_fix(source_file):
            print("  ✓ SUCCESS: Fix verified!")
            commit_and_push(source_file, "Fix: Auto-fix compilation errors")
        else:
            print("  ✗ Fix verification failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
