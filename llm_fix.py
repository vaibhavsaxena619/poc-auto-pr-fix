import sys
import re
import json
import urllib.request
import urllib.error
from pathlib import Path

# ---------------- CONFIG ----------------

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "deepseek-coder:latest"

JAVA_FILE = Path("src") / "App.java"

# ----------------------------------------

def fail(msg: str):
    print(f"[llm-fix] ERROR: {msg}")
    sys.exit(1)


def read_errors(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        fail(f"Failed to read error file: {e}")


def call_ollama(errors: str) -> str:
    prompt = f"""
You are fixing Java compilation errors in a CI pipeline.

STRICT RULES (MANDATORY):
- Output ONLY valid Java source code
- No markdown
- No backticks
- No explanations
- No comments
- Single public class App
- File must compile with: javac App.java
- Do NOT add new logic
- Do NOT change behavior
- Only fix compilation issues (imports, syntax, signatures)

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
    except urllib.error.URLError as e:
        fail(f"Ollama not reachable: {e}")
    except Exception as e:
        fail(f"Ollama call failed: {e}")


def sanitize_java(raw: str) -> str:
    if not raw:
        fail("Empty response from LLM")

    # Remove hallucinated markdown
    raw = raw.replace("```java", "").replace("```", "").strip()

    # Extract ONLY the App class
    match = re.search(
        r"(public\s+class\s+App\s*\{[\s\S]*?\n\})",
        raw,
        re.MULTILINE
    )

    if not match:
        fail("LLM output does not contain a valid public class App")

    java_code = match.group(1).strip()

    # Final safety check
    if "public class App" not in java_code:
        fail("Sanitized output missing public class App")

    return java_code + "\n"


def write_java(code: str):
    try:
        JAVA_FILE.write_text(code, encoding="utf-8")
    except Exception as e:
        fail(f"Failed to write App.java: {e}")


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
        print("[llm-fix] No errors found — skipping LLM call")
        sys.exit(0)

    print("[llm-fix] Sending errors to DeepSeek-Coder...")
    raw_response = call_ollama(errors)

    print("[llm-fix] Sanitizing LLM output...")
    fixed_java = sanitize_java(raw_response)

    print("[llm-fix] Writing fixed App.java...")
    write_java(fixed_java)

    print("[llm-fix] App.java overwritten successfully")
