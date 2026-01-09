import sys
import json
import urllib.request
from pathlib import Path

errors_file = Path(sys.argv[1])
errors = errors_file.read_text()

LLM_URL = "http://localhost:11434/api/generate"
MODEL = "codellama"

for java_file in Path("src").glob("*.java"):
    original_code = java_file.read_text()

    prompt = f"""
You are a Java compiler assistant.

Rules:
- Fix ONLY compilation errors
- DO NOT add new logic or features
- ONLY add imports, fix syntax, or method signatures
- Return the FULL corrected Java file
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
            fixed_code = response.get("response", "")

            # Safety guard
            if "class" in fixed_code and len(fixed_code) <= len(original_code) * 1.2:
                java_file.write_text(fixed_code)
                print(f"Applied fixes to {java_file.name}")
            else:
                print(f"Rejected unsafe fix for {java_file.name}")

    except Exception as e:
        print(f"LLM call failed: {e}")
        sys.exit(1)
