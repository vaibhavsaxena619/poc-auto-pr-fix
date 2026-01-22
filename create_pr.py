#!/usr/bin/env python3
import os
import sys
import requests

# Get GitHub PAT from environment
github_pat = os.getenv('GITHUB_PAT')
if not github_pat:
    print("ERROR: GITHUB_PAT not set")
    sys.exit(1)

repo = "vaibhavsaxena619/poc-auto-pr-fix"
api_url = f"https://api.github.com/repos/{repo}/pulls"

pr_data = {
    "title": "Fix: Correct App.java syntax errors and improve error classification",
    "body": """## Summary
Fixes compilation errors in App.java and improves error classification in build_fix_v2.py

### Changes
1. **App.java**: Fixed brace mismatch and declared missing variable `x`
2. **build_fix_v2.py**: Added syntax error patterns to HIGH-confidence patterns
   - Pattern: `class, interface, enum, or record expected`
   - This ensures syntax errors are auto-fixed, not marked for manual review

### Testing
- ✓ App.java now compiles successfully
- ✓ Syntax errors classified as HIGH-confidence (0.9)

### Author Tag
CC: @vaibhavsaxena619 - Please review and merge if satisfied
""",
    "head": "Dev_Low",
    "base": "Release"
}

headers = {
    "Authorization": f"token {github_pat}",
    "Accept": "application/vnd.github.v3+json"
}

try:
    response = requests.post(api_url, json=pr_data, headers=headers, timeout=10)
    if response.status_code == 201:
        pr_info = response.json()
        print(f"✓ PR #{pr_info['number']} created successfully")
        print(f"  URL: {pr_info['html_url']}")
    else:
        print(f"✗ Failed to create PR: {response.status_code}")
        print(f"  Response: {response.text}")
except Exception as e:
    print(f"✗ Error creating PR: {e}")
    sys.exit(1)
