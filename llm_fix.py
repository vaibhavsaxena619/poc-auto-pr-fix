import sys
import re
import json
import urllib.request
import urllib.error
from pathlib import Path
import difflib

# ---------------- CONFIG ----------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-coder:latest"

JAVA_FILE = Path("src") / "App.java"

# ----------------------------------------

def fail(msg: str):
    print(f"[llm-fix] ERROR: {msg}")
    sys.exit(1)


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def read_errors(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        fail(f"Failed to read error file: {e}")


def call_ollama(errors: str) -> str:
    prompt = f"""
You are fixing Java compilation errors in a CI pipeline.

MANDATORY RULES (ABSOLUTE):
- Output ONLY valid Java source code
- NO markdown, NO backticks
- NO comments (// or /* */)
- NO explanations
- Single public class App
- Must compile with: javac App.java
- Do NOT change logic or behavior
- Fix ONLY compilation errors

YOU MUST:
1. Resolve ALL "cannot find symbol" errors
2. Add ALL required imports explicitly
3. Fix spelling mistakes in class, variable, or type names
4. Fix incorrect initializations
5. Ensure all types used are fully resolvable

If any collection type is used, ensure java.util imports exist.

Compilation errors:
{errors}
"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.1
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "")
    except Exception as e:
        fail(f"Ollama call failed: {e}")


def sanitize_java(raw: str) -> str:
    if not raw.strip():
        fail("Empty LLM output")

    # Strip markdown
    raw = raw.replace("```java", "").replace("```", "").strip()

    # HARD FAIL if comments exist
    if "//" in raw or "/*" in raw:
        fail("LLM output contains comments – rejected")

    # Extract ONLY App class
    match = re.search(
        r"(public\s+class\s+App\s*\{[\s\S]*?\n\})",
        raw,
        re.MULTILINE
    )

    if not match:
        fail("No valid public class App found")

    java_code = match.group(1).strip()

    # Enforce import safety
    if "List<" in java_code or "ArrayList<" in java_code:
        if "import java.util" not in java_code:
            java_code = "import java.util.*;\n\n" + java_code

    return java_code + "\n"


def print_diff(before: str, after: str):
    print("\n[llm-fix] ===== CODE DIFF =====")
    for line in difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile="before/App.java",
        tofile="after/App.java",
        lineterm=""
    ):
        print(line)
    print("[llm-fix] =====================\n")


# ---------------- MAIN ----------------

if __name__ == "__main__":

    if len(sys.argv) != 2:
        fail("Usage: python llm_fix.py <compile_errors.txt>")

    error_file = sys.argv[1]

    if not Path(error_file).exists():
        fail("Compile error file not found")

    if not JAVA_FILE.exists():
        fail("src/App.java not found")

    print("[llm-fix] Reading compilation errors...")
    errors = read_errors(error_file)

    if not errors.strip():
        print("[llm-fix] No errors detected, skipping")
        sys.exit(0)

    original_code = read_file(JAVA_FILE)

    print("[llm-fix] Sending errors to DeepSeek-Coder...")
    raw_response = call_ollama(errors)

    print("[llm-fix] Sanitizing LLM output...")
    fixed_code = sanitize_java(raw_response)

    print_diff(original_code, fixed_code)

    print("[llm-fix] Writing fixed App.java...")
    JAVA_FILE.write_text(fixed_code, encoding="utf-8")

    print("[llm-fix] Auto-fix completed successfully")
