import sys
import requests
from pathlib import Path

# Read compiler errors
errors_file = Path(sys.argv[1])
errors = errors_file.read_text()

# Process all Java files in src/
for java_file in Path("src").glob("*.java"):
    code = java_file.read_text()

    prompt = f"""
You are a Java compiler assistant.
Fix ONLY compilation errors.
DO NOT change the existing logic or add new features.
Return the full corrected Java file.

Java Code:
{code}

Compiler Errors:
{errors}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "codellama",   # Or your local LLM
            "prompt": prompt,
            "stream": False
        }
    )

    fixed_code = response.json()["response"]

    # Safety check: only apply if basic checks pass
    if "class" in fixed_code and len(fixed_code) < len(code) * 1.2:
        java_file.write_text(fixed_code)
        print(f"Applied fixes to {java_file}")
    else:
        print(f"Fix for {java_file} rejected due to safety check")
