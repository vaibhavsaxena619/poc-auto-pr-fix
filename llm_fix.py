import sys
import re
import json
import urllib.request
import urllib.error
import time
from pathlib import Path
import difflib
import os

# ---------------- CONFIG ----------------

# Get your API key from: https://aistudio.google.com/app/apikey
# For Jenkins: Use credentials with ID "Gemini API key"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("Gemini_API_key")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

JAVA_FILE = Path("src") / "App.java"

GEMINI_TIMEOUT_SECONDS = 60
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5

# ----------------------------------------

def fail(msg: str):
    print(f"[llm-fix] ERROR: {msg}")
    sys.exit(1)


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

    payload = json.dumps({
        "contents": [{
            "parts": [{
                "text": prompt
            }]
        }],
        "generationConfig": {
            "temperature": 0.0,
            "topP": 0.1,
            "maxOutputTokens": 8192
        }
    }).encode("utf-8")

    url_with_key = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    req = urllib.request.Request(
        url_with_key,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[llm-fix] Gemini attempt {attempt}/{MAX_RETRIES}...")
            with urllib.request.urlopen(req, timeout=GEMINI_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    raise Exception(f"No response from Gemini: {data}")
                    
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
