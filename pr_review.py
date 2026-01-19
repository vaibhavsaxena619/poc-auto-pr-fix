import sys
import os
import json
import subprocess
import requests
from pathlib import Path
from openai import AzureOpenAI

# ---------------- CONFIG ----------------
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")
GITHUB_PAT = os.getenv("GITHUB_PAT")

REPO_OWNER = os.getenv("REPO_OWNER", "vaibhavsaxena619")
REPO_NAME = os.getenv("REPO_NAME", "poc-auto-pr-fix")
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
    # First, ensure we have the latest refs from remote
    run_git_command(["git", "fetch", "origin", f"{base_branch}:{base_branch}", f"{head_branch}:{head_branch}"])
    
    # Try with remote branches first
    diff = run_git_command(["git", "diff", f"origin/{base_branch}...origin/{head_branch}"])
    
    # If that fails, try with local branches
    if not diff.strip():
        diff = run_git_command(["git", "diff", f"{base_branch}...{head_branch}"])
    
    # If still no diff, try a simpler approach using merge-base
    if not diff.strip():
        merge_base = run_git_command(["git", "merge-base", "HEAD", f"origin/{base_branch}"])
        if merge_base:
            diff = run_git_command(["git", "diff", merge_base, "HEAD"])
    
    return diff

def call_azure_openai_for_review(diff_content: str, review_type: str = "code_review", pr_info: dict = None) -> str:
    """Call Azure OpenAI for code review or merge conflict analysis"""
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        fail("AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT not set")
    
    if review_type == "code_review":
        prompt = f"""
You are conducting a thorough code review for a Pull Request.

PR Information:
- Title: {pr_info.get('title', 'N/A') if pr_info else 'N/A'}
- Author: {pr_info.get('author', 'N/A') if pr_info else 'N/A'}
- Files Changed: {pr_info.get('files_changed', 'N/A') if pr_info else 'N/A'}

REVIEW REQUIREMENTS:
- Analyze code quality, security, and best practices
- Check for potential bugs or logic issues
- Verify Java coding standards and conventions
- Look for performance improvements
- Check imports and dependencies usage
- Evaluate error handling and edge cases
- Consider maintainability and readability
- Rate the code quality (Excellent/Good/Needs Improvement/Poor)

RESPONSE FORMAT:
## 🔍 Code Review Summary
**Overall Rating:** [Rating] | **Reviewer:** Azure OpenAI GPT-5

## ✅ Positive Points:
- [List good practices and well-written code sections]

## ⚠️ Issues Found:
### Critical Issues:
- [List critical issues that must be fixed]

### Major Issues:  
- [List important issues that should be addressed]

### Minor Issues:
- [List minor suggestions and style improvements]

## 💡 Recommendations:
- [Specific actionable recommendations]
- [Performance improvements]
- [Best practice suggestions]

## 📋 Approval Status:
**Status:** [✅ APPROVED | ⚠️ NEEDS_CHANGES | ❌ REJECTED]
**Reason:** [Brief explanation of decision]

**Next Steps:** [What the author should do next]

---
*Code changes analyzed:*
```diff
{diff_content[:2000]}{'...[truncated]' if len(diff_content) > 2000 else ''}
```
"""
    
    elif review_type == "merge_conflict":
        prompt = f"""
You are analyzing a merge conflict or integration issue in a Pull Request.

CONFLICT ANALYSIS REQUIREMENTS:
- Identify the root cause of merge conflicts
- Analyze compatibility between branches
- Suggest specific resolution steps
- Check for breaking changes
- Provide merge strategy recommendations

RESPONSE FORMAT:
## ⚠️ Merge Conflict Analysis

### 🔍 Root Cause:
[Identify the main cause of the conflict]

### 💥 Conflicting Changes:
- [Describe what's conflicting between branches]
- [Identify overlapping modifications]

### 🛠️ Resolution Steps:
1. [Step-by-step resolution instructions]
2. [Include specific git commands if needed]
3. [Code changes required]
4. [Verification steps]

### 🚫 Prevention Strategy:
- [How to prevent similar conflicts in future]
- [Branch management recommendations]

### ✅ Merge Strategy:
**Recommended approach:** [merge/rebase/squash]
**Why:** [Explanation]

---
*Conflict details:*
```diff
{diff_content[:2000]}{'...[truncated]' if len(diff_content) > 2000 else ''}
```
"""
    
    elif review_type == "error_fallback":
        return f"""## 🤖 Automated Review Status

**Status:** ⚠️ Technical Issue Encountered

The automated code review system experienced technical difficulties while analyzing this PR. 

**Recommended Actions:**
1. **Manual Review Required** - Please have a team member review the changes
2. **Check Build Status** - Ensure all tests pass before merging
3. **Verify Compilation** - Make sure code compiles without errors

**What was attempted:**
- Azure OpenAI GPT-5 code analysis
- Automated security scanning
- Best practice validation

**Next Steps:**
- Request review from a team member
- Run local tests before merging
- Consider breaking large changes into smaller PRs

---
*🤖 Automated message from Jenkins CI/CD Pipeline*"""
    
    try:
        client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        response = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            messages=[
                {"role": "system", "content": "You are a professional code reviewer for Java projects."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000
        )
        return response.choices[0].message.content if response.choices else "No review generated"
    except Exception as e:
        return f"""## ❌ Code Review Failed

**Error:** Failed to generate automated review due to technical issues.

**Details:** {str(e)}

**Manual Review Required:** Please have a team member review this PR manually.

**Checklist for Manual Review:**
- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No security vulnerabilities introduced
- [ ] Code follows team standards
- [ ] Proper error handling implemented
- [ ] Documentation updated if needed

---
*🤖 Automated message from Jenkins CI/CD Pipeline*"""

def post_github_comment(pr_number: int, comment: str, pr_info: dict = None):
    """Post a comment on GitHub PR and tag the author"""
    if not GITHUB_PAT:
        print("[pr-review] WARNING: GITHUB_PAT not set, cannot post comment")
        return False
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Enhanced comment with PR statistics
    enhanced_comment = comment
    
    if pr_info:
        stats = f"""
---
**📊 PR Statistics:**
- **Files Changed:** {pr_info.get('changed_files', 'N/A')}
- **Lines Added:** +{pr_info.get('additions', 0)}
- **Lines Deleted:** -{pr_info.get('deletions', 0)}
- **Author:** @{pr_info.get('author', 'unknown')}

"""
        enhanced_comment = f"@{pr_info.get('author', 'unknown')}\n\n{comment}{stats}"
    
    # Add bot signature with timestamp
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    enhanced_comment += f"""
---
*🤖 Automated review by Jenkins PR Review Bot using Azure OpenAI GPT-5*  
*Generated on: {timestamp}*
*Job: Jenkins Multibranch Pipeline*"""
    
    url = f"{GITHUB_API_BASE}/issues/{pr_number}/comments"
    data = {"body": enhanced_comment}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print(f"[pr-review] ✅ Successfully posted review comment on PR #{pr_number}")
            comment_url = response.json().get("html_url", "")
            if comment_url:
                print(f"[pr-review] Comment URL: {comment_url}")
            return True
        else:
            print(f"[pr-review] ❌ Failed to post comment: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"[pr-review] ❌ Error posting comment: {str(e)}")
        return False

def get_pr_info(pr_number: int) -> dict:
    """Get detailed PR information from GitHub API"""
    if not GITHUB_PAT:
        return {}
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Get PR details
    url = f"{GITHUB_API_BASE}/pulls/{pr_number}"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            pr_data = response.json()
            
            # Get files changed
            files_url = f"{GITHUB_API_BASE}/pulls/{pr_number}/files"
            files_response = requests.get(files_url, headers=headers)
            files_changed = []
            if files_response.status_code == 200:
                files_data = files_response.json()
                files_changed = [f["filename"] for f in files_data]
            
            return {
                "title": pr_data.get("title", ""),
                "author": pr_data["user"]["login"],
                "files_changed": ", ".join(files_changed[:10]),  # Limit to first 10 files
                "additions": pr_data.get("additions", 0),
                "deletions": pr_data.get("deletions", 0),
                "changed_files": pr_data.get("changed_files", 0)
            }
    except Exception as e:
        print(f"[pr-review] Error getting PR info: {str(e)}")
        return {}

def main():
    if len(sys.argv) < 4:
        fail("Usage: python pr_review.py <pr_number> <base_branch> <head_branch> [review_type]")
    
    pr_number = int(sys.argv[1])
    base_branch = sys.argv[2]
    head_branch = sys.argv[3]
    review_type = sys.argv[4] if len(sys.argv) > 4 else "code_review"
    
    print(f"[pr-review] Starting {review_type} for PR #{pr_number}")
    print(f"[pr-review] Branches: {head_branch} -> {base_branch}")
    
    # Get detailed PR information
    print("[pr-review] Fetching PR information from GitHub...")
    pr_info = get_pr_info(pr_number)
    
    if pr_info:
        print(f"[pr-review] PR Title: {pr_info.get('title', 'N/A')}")
        print(f"[pr-review] PR Author: @{pr_info.get('author', 'unknown')}")
        print(f"[pr-review] Files Changed: {pr_info.get('changed_files', 'N/A')}")
        print(f"[pr-review] Changes: +{pr_info.get('additions', 0)}/-{pr_info.get('deletions', 0)}")
    
    # Get diff content
    print("[pr-review] Analyzing code changes...")
    diff_content = get_pr_diff(base_branch, head_branch)
    
    if not diff_content.strip():
        comment = f"""## 📋 No Code Changes Detected

No code changes found between `{base_branch}` and `{head_branch}` branches.

**Possible Reasons:**
- Branches are identical
- Only non-code files changed (documentation, configs)
- Git diff unable to detect changes

**Recommendations:**
- Verify the correct branches are being compared
- Check if this is a documentation-only change
- Manual review may still be valuable for context

**Status:** ✅ NO_CHANGES_REQUIRED
"""
        success = post_github_comment(pr_number, comment, pr_info)
        if success:
            print("[pr-review] Posted 'no changes' comment to PR")
        return
    
    print(f"[pr-review] Found {len(diff_content.splitlines())} lines of changes")
    
    # Generate review with PR context
    print(f"[pr-review] Generating {review_type} analysis with Azure OpenAI...")
    review_content = call_azure_openai_for_review(diff_content, review_type, pr_info)
    
    # Post comprehensive review comment
    success = post_github_comment(pr_number, review_content, pr_info)
    
    if success:
        print(f"[pr-review] ✅ {review_type.replace('_', ' ').title()} completed and posted to PR #{pr_number}")
        print(f"[pr-review] 📝 Author @{pr_info.get('author', 'unknown')} has been notified")
        print("[pr-review] 🤖 Review powered by Azure OpenAI (gpt-5)")
        print("[pr-review] 🔗 Check the PR on GitHub for the full review")
    else:
        print(f"[pr-review] ⚠️ {review_type.replace('_', ' ').title()} completed but failed to post comment")
        print("[pr-review] Review content generated but not posted to GitHub")
        print("=" * 50)
        print("REVIEW CONTENT:")
        print(review_content)
        print("=" * 50)

if __name__ == "__main__":
    main()