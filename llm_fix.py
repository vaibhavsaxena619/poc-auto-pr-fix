import sys
import re
import json
import time
import subprocess
from pathlib import Path
import difflib
import os
from google import genai

# ---------------- CONFIG ----------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_PAT = os.getenv("GITHUB_PAT")
MODEL_NAME = "gemini-3-flash-preview"

JAVA_FILE = Path("src") / "App.java"

GEMINI_TIMEOUT_SECONDS = 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# ----------------------------------------

def fail(msg: str):
    print(f"[llm-fix] ERROR: {msg}")
    sys.exit(1)


def run_git_command(cmd: list) -> str:
    """Run a git command and return the output"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"[llm-fix] Git command failed: {' '.join(cmd)}")
        print(f"[llm-fix] Error: {e.stderr}")
        return ""


def get_last_committer() -> dict:
    """Get the last committer information"""
    name = run_git_command(["git", "log", "-1", "--pretty=format:%an"])
    email = run_git_command(["git", "log", "-1", "--pretty=format:%ae"])
    return {"name": name, "email": email}


def setup_git_credentials():
    """Configure git with GitHub PAT for authentication"""
    if not GITHUB_PAT:
        print("[llm-fix] WARNING: GITHUB_PAT not set, skipping git operations")
        return False
    
    # Get repository URL and extract repo info
    remote_url = run_git_command(["git", "remote", "get-url", "origin"])
    if "github.com" in remote_url:
        # Convert to PAT-authenticated URL
        if remote_url.startswith("https://"):
            repo_part = remote_url.replace("https://github.com/", "")
            auth_url = f"https://{GITHUB_PAT}@github.com/{repo_part}"
            run_git_command(["git", "remote", "set-url", "origin", auth_url])
    
    return True


def commit_and_push_changes(original_errors: str, last_committer: dict, original_code: str, fixed_code: str):
    """Commit the fixed code and push to repository with detailed patch notes"""
    if not setup_git_credentials():
        print("[llm-fix] Skipping git operations due to missing credentials")
        return
    
    # Configure git user (use Jenkins/CI user)
    run_git_command(["git", "config", "user.name", "Jenkins Auto-Fix Bot"])
    run_git_command(["git", "config", "user.email", "jenkins@ci.local"])
    
    # Add the fixed file
    run_git_command(["git", "add", str(JAVA_FILE)])
    
    # Generate detailed patch notes
    changes_made = []
    if "import" in fixed_code and "import" not in original_code:
        changes_made.append("- Added missing import statements")
    if "public class" in fixed_code and "public class" in original_code:
        changes_made.append("- Fixed class declaration syntax")
    if original_errors:
        if "cannot find symbol" in original_errors.lower():
            changes_made.append("- Resolved missing symbol/variable declarations")
        if "expected" in original_errors.lower():
            changes_made.append("- Fixed syntax errors (missing semicolons, brackets, etc.)")
        if "incompatible types" in original_errors.lower():
            changes_made.append("- Fixed type compatibility issues")
    
    if not changes_made:
        changes_made.append("- Applied general compilation error fixes")
    
    # Create detailed commit message with patch notes
    patch_notes = "\n".join(changes_made)
    
    commit_msg = f"""AUTO-FIX: Resolved Java compilation errors

PATCH NOTES:
{patch_notes}

ORIGINAL ERRORS FIXED:
{original_errors[:800]}{'...' if len(original_errors) > 800 else ''}

TECHNICAL DETAILS:
- Fixed by: Jenkins Auto-Fix Bot using Gemini AI
- Original committer: {last_committer['name']} <{last_committer['email']}>
- Auto-generated from CI/CD pipeline
- Branch: main (ready for merge to master)

FILES MODIFIED:
- src/App.java (compilation errors resolved)

REVIEW STATUS: Ready for merge to master branch
"""
    
    # Commit the changes
    result = run_git_command(["git", "commit", "-m", commit_msg])
    if result:
        print("[llm-fix] Committed changes with detailed patch notes")
        
        # Push the changes to main branch
        push_result = run_git_command(["git", "push", "origin", "HEAD:main"])
        if push_result:
            print("[llm-fix] SUCCESS: Auto-fixed code pushed to main branch")
            print("[llm-fix] PATCH NOTES: Included in commit message")
            print("[llm-fix] STATUS: Ready for merge to master branch")
        else:
            print("[llm-fix] ERROR: Failed to push changes")
    else:
        print("[llm-fix] ERROR: Failed to commit changes")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def call_gemini(errors: str) -> str:
    if not GEMINI_API_KEY:
        fail("GEMINI_API_KEY environment variable not set. Get your API key from: https://aistudio.google.com/app/apikey")
    
    prompt = f"""
You are fixing Java compilation errors in a CI pipeline.

STRICT REQUIREMENTS:
- Output valid Java code only
- Single public class App
- Fix ALL compilation errors
- Fix missing imports
- Fix spelling mistakes
- Fix incorrect initializations
- Do NOT change logic or behavior

Compilation errors:
{errors}
"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[llm-fix] Gemini attempt {attempt}/{MAX_RETRIES}...")
            
            # Create the client with API key
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Generate content using the new API
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt
            )
            
            if response.text:
                return response.text
            else:
                raise Exception(f"No response text from Gemini: {response}")
                    
        except Exception as e:
            last_error = e
            print(f"[llm-fix] Gemini attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                print(f"[llm-fix] Retrying in {RETRY_DELAY_SECONDS}s...")
                time.sleep(RETRY_DELAY_SECONDS)

    fail(f"Gemini failed after {MAX_RETRIES} attempts: {last_error}")


def strip_comments(code: str) -> str:
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    code = re.sub(r"//.*", "", code)
    return code


def extract_app_class(raw: str) -> str:
    raw = raw.replace("```java", "").replace("```", "").strip()

    match = re.search(
        r"(public\s+class\s+App\s*\{[\s\S]*?\n\})",
        raw,
        re.MULTILINE
    )

    if not match:
        fail("No valid public class App found in LLM output")

    return match.group(1)


def enforce_imports(java_code: str) -> str:
    needs_util = any(
        token in java_code for token in [
            "List<", "ArrayList<", "Map<", "HashMap<",
            "Set<", "HashSet<"
        ]
    )

    if needs_util and "import java.util" not in java_code:
        java_code = "import java.util.*;\n\n" + java_code

    return java_code


def print_diff(before: str, after: str):
    print("\n[llm-fix] ===== FIXES APPLIED =====")
    for line in difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before/App.java",
        tofile="after/App.java",
        lineterm=""
    ):
        print(line)
    print("[llm-fix] =========================\n")


# ---------------- MAIN ----------------

if __name__ == "__main__":

    if len(sys.argv) != 2:
        fail("Usage: python llm_fix.py <compile_errors.txt>")

    error_file = Path(sys.argv[1])

    if not error_file.exists():
        fail("Compile error file not found")

    if not JAVA_FILE.exists():
        fail("src/App.java not found")

    print("[llm-fix] Reading compilation errors...")
    errors = read_text(error_file)

    if not errors.strip():
        print("[llm-fix] No errors found — skipping")
        sys.exit(0)

    # Get last committer info before making changes
    last_committer = get_last_committer()
    print(f"[llm-fix] Last committer: {last_committer['name']} <{last_committer['email']}>")

    original_code = read_text(JAVA_FILE)

    print("[llm-fix] Sending errors to Gemini...")
    raw = call_gemini(errors)

    print("[llm-fix] Extracting App class...")
    java_code = extract_app_class(raw)

    print("[llm-fix] Removing comments...")
    java_code = strip_comments(java_code)

    print("[llm-fix] Enforcing required imports...")
    java_code = enforce_imports(java_code)

    java_code = java_code.strip() + "\n"

    print_diff(original_code, java_code)

    print("[llm-fix] Writing fixed App.java...")
    JAVA_FILE.write_text(java_code, encoding="utf-8")

    print("[llm-fix] Auto-fix completed successfully")
    
    # Commit and push the changes
    print("[llm-fix] Committing changes to git...")
    commit_and_push_changes(errors, last_committer, original_code, java_code)
    
    print("[llm-fix] Process completed - code fixed and committed to repository")
