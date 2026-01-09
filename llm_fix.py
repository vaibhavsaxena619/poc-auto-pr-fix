import sys
import json
import urllib.request
from pathlib import Path

errors = Path(sys.argv[1]).read_text()

LLM_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "deepseek-coder"

for java_file in Path("src").glob("*.java"):
    original_code = java_file.read_text()

    prompt = f"""
You are a Java compiler assistant.

Rules:
- Fix ONLY compilation errors
- DO NOT change logic
- Prefer adding missing imports
- If possible, return ONLY the import statements
- Otherwise return the FULL corrected Java file
- No explanations

Java Code:
{original_code}

Compiler Errors:
{errors}
"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        LLM_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response = json.loads(resp.read().decode("utf-8"))
            fix = response.get("response", "").strip()

            # CASE 1: Import-only fix (SAFE)
            if fix.startswith("import ") and "class" in original_code:
                updated = fix + "\n\n" + original_code
                java_file.write_text(updated)
                print(f"Applied import-only fix to {java_file.name}")

            # CASE 2: Full-file fix (SAFE)
            elif "class" in fix and len(fix) <= len(original_code) * 1.3:
                java_file.write_text(fix)
                print(f"Applied full fix to {java_file.name}")

            else:
                print(f"Rejected unsafe fix for {java_file.name}")

    except Exception as e:
        print(f"LLM call failed: {e}")
        sys.exit(1)
