import sys
import os
import json
import subprocess
import requests
from pathlib import Path
from google import genai

# ---------------- CONFIG ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("Gemini_API_key")
GITHUB_PAT = os.getenv("github-pat") or os.getenv("GITHUB_PAT")
MODEL_NAME = "gemini-3-flash-preview"

REPO_OWNER = "vaibhavsaxena619"
REPO_NAME = "poc-auto-pr-fix"
GITHUB_API_BASE = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"

def fail(msg: str):
    print(f"[pr-review] ERROR: {msg}")
    sys.exit(1)

def run_git_command(cmd: list) -> str:
    """Run a git command and return the output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[pr-review] Git command failed: {' '.join(cmd)}")
        print(f"[pr-review] Error: {e.stderr}")
        return ""

def get_pr_diff(base_branch: str, head_branch: str) -> str:
    """Get the diff between two branches"""
    diff = run_git_command(["git", "diff", f"origin/{base_branch}...origin/{head_branch}"])
    return diff

def call_gemini_for_review(diff_content: str, review_type: str = "code_review") -> str:
    """Call Gemini for code review or merge conflict analysis"""
    if not GEMINI_API_KEY:
        fail("GEMINI_API_KEY not set")
    
    if review_type == "code_review":
        prompt = f"""
You are conducting a thorough code review for a Pull Request.

REVIEW REQUIREMENTS:
- Analyze code quality, security, and best practices
- Check for potential bugs or issues
- Verify Java coding standards
- Look for performance improvements
- Check imports and dependencies
- Suggest improvements if needed
- Rate the code quality (Excellent/Good/Needs Improvement/Poor)

RESPONSE FORMAT:
## Code Review Summary
**Overall Rating:** [Rating]

## Findings:
### Positive Points:
- [List good practices found]

### Issues Found:
- [List issues with severity: Critical/Major/Minor]

### Recommendations:
- [List specific recommendations]

## Approval Status:
**Status:** [APPROVED/NEEDS_CHANGES/REJECTED]
**Reason:** [Brief reason]

Code changes to review:
{diff_content}
"""
    else:  # merge_conflict
        prompt = f"""
You are analyzing a merge conflict or build failure.

ANALYSIS REQUIREMENTS:
- Identify the root cause of the merge conflict
- Suggest specific resolution steps
- Check for compatibility issues
- Provide actionable fix recommendations

RESPONSE FORMAT:
## Merge Conflict Analysis

### Root Cause:
[Identify the main issue]

### Conflicting Changes:
[Describe what's conflicting]

### Resolution Steps:
1. [Step by step resolution]
2. [Include specific commands if needed]
3. [Verification steps]

### Prevention:
[How to prevent similar issues]

Conflict details:
{diff_content}
"""
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text if response.text else "No review generated"
    except Exception as e:
        return f"Failed to generate review: {str(e)}"

def post_github_comment(pr_number: int, comment: str, tag_author: str = None):
    """Post a comment on GitHub PR and optionally tag the author"""
    if not GITHUB_PAT:
        print("[pr-review] WARNING: GITHUB_PAT not set, cannot post comment")
        return False
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Add author tag if provided
    if tag_author:
        comment = f"@{tag_author}\n\n{comment}"
    
    # Add bot signature
    comment += f"\n\n---\n*🤖 Automated review by Jenkins PR Review Bot using Gemini AI*"
    
    url = f"{GITHUB_API_BASE}/issues/{pr_number}/comments"
    data = {"body": comment}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print(f"[pr-review] Successfully posted review comment on PR #{pr_number}")
            return True
        else:
            print(f"[pr-review] Failed to post comment: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[pr-review] Error posting comment: {str(e)}")
        return False

def get_pr_author(pr_number: int) -> str:
    """Get the PR author username"""
    if not GITHUB_PAT:
        return "unknown"
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"{GITHUB_API_BASE}/pulls/{pr_number}"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            pr_data = response.json()
            return pr_data["user"]["login"]
        else:
            print(f"[pr-review] Failed to get PR info: {response.status_code}")
            return "unknown"
    except Exception as e:
        print(f"[pr-review] Error getting PR author: {str(e)}")
        return "unknown"

def main():
    if len(sys.argv) < 4:
        fail("Usage: python pr_review.py <pr_number> <base_branch> <head_branch> [review_type]")
    
    pr_number = int(sys.argv[1])
    base_branch = sys.argv[2]
    head_branch = sys.argv[3]
    review_type = sys.argv[4] if len(sys.argv) > 4 else "code_review"
    
    print(f"[pr-review] Starting {review_type} for PR #{pr_number}: {head_branch} -> {base_branch}")
    
    # Get PR author
    pr_author = get_pr_author(pr_number)
    print(f"[pr-review] PR Author: {pr_author}")
    
    # Get diff content
    print("[pr-review] Fetching changes...")
    diff_content = get_pr_diff(base_branch, head_branch)
    
    if not diff_content.strip():
        comment = f"""## No Changes Detected
        
No code changes found between `{base_branch}` and `{head_branch}` branches.

**Status:** NO_CHANGES_REQUIRED
"""
        post_github_comment(pr_number, comment, pr_author)
        print("[pr-review] No changes to review")
        return
    
    # Generate review
    print(f"[pr-review] Generating {review_type} with Gemini...")
    review_content = call_gemini_for_review(diff_content, review_type)
    
    # Post review comment
    success = post_github_comment(pr_number, review_content, pr_author)
    
    if success:
        print(f"[pr-review] {review_type.title()} completed and posted to PR #{pr_number}")
    else:
        print(f"[pr-review] {review_type.title()} completed but failed to post comment")
        print("Review content:")
        print(review_content)

if __name__ == "__main__":
    main()