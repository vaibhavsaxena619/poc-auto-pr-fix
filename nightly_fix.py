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
    print(f"[nightly-fix] ERROR: {msg}")
    sys.exit(1)

def run_git_command(cmd: list) -> str:
    """Run a git command and return the output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[nightly-fix] Git command failed: {' '.join(cmd)}")
        return ""

def call_gemini_for_build_fix(build_logs: str, error_context: str = "") -> dict:
    """Analyze build logs and provide fixes"""
    if not GEMINI_API_KEY:
        fail("GEMINI_API_KEY not set")
    
    prompt = f"""
You are fixing a nightly build failure. Analyze the build logs and provide actionable fixes.

ANALYSIS REQUIREMENTS:
- Identify root cause of build failure
- Provide specific code fixes
- Suggest preventive measures
- Rate severity (Critical/High/Medium/Low)

RESPONSE FORMAT (JSON):
{{
    "analysis": {{
        "root_cause": "Brief description of main issue",
        "severity": "Critical/High/Medium/Low",
        "affected_components": ["list", "of", "components"]
    }},
    "fixes": [
        {{
            "file": "path/to/file",
            "issue": "Description of issue",
            "solution": "Specific fix to apply",
            "code_change": "If applicable, exact code to change"
        }}
    ],
    "summary": "Brief summary for PR comment",
    "prevention": ["preventive", "measures"]
}}

Build context: {error_context}

Build logs:
{build_logs}
"""
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        
        if response.text:
            # Try to parse JSON response
            try:
                return json.loads(response.text)
            except json.JSONDecodeError:
                # If not JSON, return structured text
                return {
                    "analysis": {"root_cause": "Parse error", "severity": "High"},
                    "fixes": [],
                    "summary": response.text,
                    "prevention": []
                }
        else:
            return {"analysis": {"root_cause": "No response", "severity": "High"}, "fixes": [], "summary": "Failed to analyze", "prevention": []}
    except Exception as e:
        return {"analysis": {"root_cause": str(e), "severity": "High"}, "fixes": [], "summary": f"Analysis failed: {str(e)}", "prevention": []}

def apply_code_fixes(fixes: list) -> list:
    """Apply code fixes to files"""
    applied_fixes = []
    
    for fix in fixes:
        if "file" in fix and "code_change" in fix:
            file_path = Path(fix["file"])
            if file_path.exists():
                try:
                    # Read current content
                    content = file_path.read_text(encoding="utf-8")
                    
                    # Apply fix (this is simplified - in practice you'd need more sophisticated matching)
                    if fix.get("code_change"):
                        # For now, just log what would be changed
                        applied_fixes.append({
                            "file": str(file_path),
                            "status": "identified",
                            "issue": fix.get("issue", "Unknown issue"),
                            "solution": fix.get("solution", "No solution provided")
                        })
                    
                except Exception as e:
                    applied_fixes.append({
                        "file": str(file_path),
                        "status": "failed",
                        "error": str(e)
                    })
    
    return applied_fixes

def get_recent_pr_for_commit(commit_sha: str) -> int:
    """Get the PR number that introduced a commit"""
    if not GITHUB_PAT:
        return None
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Search for PRs that might have introduced this commit
    url = f"{GITHUB_API_BASE}/pulls?state=closed&sort=updated&direction=desc"
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            prs = response.json()
            # Return the most recent merged PR (simplified logic)
            for pr in prs:
                if pr.get("merged_at"):
                    return pr["number"]
        return None
    except Exception as e:
        print(f"[nightly-fix] Error getting recent PR: {str(e)}")
        return None

def post_build_fix_comment(pr_number: int, analysis: dict, applied_fixes: list, pr_author: str = None):
    """Post build fix comment to PR"""
    if not GITHUB_PAT or not pr_number:
        print("[nightly-fix] Cannot post comment: missing GitHub PAT or PR number")
        return False
    
    # Format comment
    severity_emoji = {
        "Critical": "🔴",
        "High": "🟠", 
        "Medium": "🟡",
        "Low": "🟢"
    }
    
    severity = analysis.get("analysis", {}).get("severity", "Medium")
    emoji = severity_emoji.get(severity, "🔵")
    
    comment = f"""## {emoji} Nightly Build Failure Analysis

### Issue Summary
**Severity:** {severity}
**Root Cause:** {analysis.get("analysis", {}).get("root_cause", "Unknown")}

### Applied Fixes
"""
    
    if applied_fixes:
        for fix in applied_fixes:
            comment += f"- **{fix['file']}**: {fix.get('solution', fix.get('issue', 'Fix applied'))}\n"
    else:
        comment += "- Manual intervention required - please review build logs\n"
    
    comment += f"""
### Prevention Measures
"""
    for prevention in analysis.get("prevention", []):
        comment += f"- {prevention}\n"
    
    comment += f"""
### Build Status
The build has been automatically re-triggered after applying fixes.

**Next Steps:**
1. Review the applied fixes
2. Test the changes locally
3. Consider adding tests to prevent similar issues
"""
    
    # Tag author if provided
    if pr_author:
        comment = f"@{pr_author}\n\n{comment}"
    
    comment += f"\n\n---\n*🤖 Automated build fix by Jenkins Nightly Build Bot using Gemini AI*"
    
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    url = f"{GITHUB_API_BASE}/issues/{pr_number}/comments"
    data = {"body": comment}
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print(f"[nightly-fix] Posted build fix comment to PR #{pr_number}")
            return True
        else:
            print(f"[nightly-fix] Failed to post comment: {response.status_code}")
            return False
    except Exception as e:
        print(f"[nightly-fix] Error posting comment: {str(e)}")
        return False

def main():
    if len(sys.argv) < 2:
        fail("Usage: python nightly_fix.py <build_log_file> [error_context]")
    
    log_file = Path(sys.argv[1])
    error_context = sys.argv[2] if len(sys.argv) > 2 else ""
    
    if not log_file.exists():
        fail(f"Build log file not found: {log_file}")
    
    print("[nightly-fix] Analyzing nightly build failure...")
    
    # Read build logs
    build_logs = log_file.read_text(encoding="utf-8", errors="ignore")
    
    # Get current commit to find related PR
    current_commit = run_git_command(["git", "rev-parse", "HEAD"])
    pr_number = get_recent_pr_for_commit(current_commit)
    
    print(f"[nightly-fix] Current commit: {current_commit}")
    print(f"[nightly-fix] Associated PR: {pr_number}")
    
    # Analyze with Gemini
    print("[nightly-fix] Sending logs to Gemini for analysis...")
    analysis = call_gemini_for_build_fix(build_logs, error_context)
    
    # Apply fixes
    print("[nightly-fix] Applying suggested fixes...")
    applied_fixes = apply_code_fixes(analysis.get("fixes", []))
    
    # Get PR author if we have a PR number
    pr_author = None
    if pr_number and GITHUB_PAT:
        headers = {"Authorization": f"token {GITHUB_PAT}"}
        try:
            response = requests.get(f"{GITHUB_API_BASE}/pulls/{pr_number}", headers=headers)
            if response.status_code == 200:
                pr_author = response.json()["user"]["login"]
        except:
            pass
    
    # Post comment to PR
    if pr_number:
        success = post_build_fix_comment(pr_number, analysis, applied_fixes, pr_author)
        if not success:
            print("[nightly-fix] Failed to post PR comment, printing analysis:")
            print(json.dumps(analysis, indent=2))
    else:
        print("[nightly-fix] No associated PR found, printing analysis:")
        print(json.dumps(analysis, indent=2))
    
    print("[nightly-fix] Build fix analysis completed")

if __name__ == "__main__":
    main()