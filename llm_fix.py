import sys
import json
import urllib.request
from pathlib import Path
import re

errors = Path(sys.argv[1]).read_text()

LLM_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "codellama"

def clean(text):
    text = re.sub(r"```[a-zA-Z]*", "", text)
    return text.replace("```", "").strip()

for java_file in Path("src").glob("*.java"):
    original = java_file.read_text()

    prompt = f"""
You are fixing Java compilation errors.

Rules:
- Fix ONLY compilation errors
- You MAY remove code if required
- You MAY rewrite the file
- DO NOT add imports
- Return ONLY valid Java code
- No explanations

Java code:
{original}

Compiler errors:
{errors}
"""

    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }).encode()

    req = urllib.request.Request(
        LLM_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            response = json.loads(resp.read().decode())
            fixed_code = clean(response.get("response", ""))

            if not fixed_code:
                print("LLM returned empty response")
                sys.exit(1)

            java_file.write_text(fixed_code)
            print(f"Overwrote {java_file.name} with LLM output")

    except Exception as e:
        print(f"LLM call failed: {e}")
        sys.exit(1)
