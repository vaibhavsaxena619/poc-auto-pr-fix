import sys
import requests
from pathlib import Path

errors = Path(sys.argv[1]).read_text()

for file in Path(".").glob("*.java"):
    code = file.read_text()

    prompt = f"""
Fix Java compilation errors only.
Do NOT change logic.
Do NOT add features.

Java Code:
{code}

Compiler Errors:
{errors}

Return FULL corrected file only.
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "codellama",
            "prompt": prompt,
            "stream": False
        }
    )

    fixed = response.json()["response"]

    # Safety guard
    if "import" in fixed and len(fixed) < len(code) * 1.2:
        file.write_text(fixed)
