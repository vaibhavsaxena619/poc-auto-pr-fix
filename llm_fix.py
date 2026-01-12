import sys
import re
import json
import time
from pathlib import Path
import difflib
import os
from google import generativeai as genai

# ---------------- CONFIG ----------------

# Get your API key from: https://aistudio.google.com/app/apikey
# For Jenkins: Use credentials with ID "Gemini API key"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("Gemini_API_key")
MODEL_NAME = "gemini-1.5-flash"

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
    
    # Configure the API key
    genai.configure(api_key=GEMINI_API_KEY)
    
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

    # Configure generation parameters
    generation_config = {
        "temperature": 0.0,
        "top_p": 0.1,
        "max_output_tokens": 8192,
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[llm-fix] Gemini attempt {attempt}/{MAX_RETRIES}...")
            
            # Create the model
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                generation_config=generation_config
            )
            
            # Generate content
            response = model.generate_content(prompt)
            
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
