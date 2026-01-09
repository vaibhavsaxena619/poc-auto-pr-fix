import sys
import re
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "codellama"

errors = open(sys.argv[1]).read()

prompt = f"""
Fix the Java compilation errors below.

STRICT RULES:
- Output ONLY valid Java code
- No explanations
- No markdown
- No comments
- No imports
- Single public class App
- Must compile with: javac App.java

Compilation errors:
{errors}
"""

response = requests.post(
    OLLAMA_URL,
    json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    },
    timeout=60
)

raw = response.json()["response"]

# 🔥 HARD SANITIZATION 🔥
# Remove anything before 'public class'
match = re.search(r"(public\s+class\s+App[\s\S]*)", raw)

if not match:
    print("LLM output invalid, no public class App found")
    sys.exit(1)

java_code = match.group(1)

with open("src/App.java", "w", encoding="utf-8") as f:
    f.write(java_code)

print("App.java overwritten with sanitized Java code")
