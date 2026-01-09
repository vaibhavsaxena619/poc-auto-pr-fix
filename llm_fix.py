import sys
import re
import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "codellama"

errors = open(sys.argv[1], encoding="utf-8").read()

prompt = f"""
Fix the Java compilation errors below.

STRICT RULES:
- Output ONLY Java code
- No markdown
- No backticks
- No explanations
- No comments
- Single public class App
- Must compile with: javac App.java

Compilation errors:
{errors}
"""

payload = json.dumps({
    "model": MODEL,
    "prompt": prompt,
    "stream": False
}).encode("utf-8")

req = urllib.request.Request(
    OLLAMA_URL,
    data=payload,
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=60) as response:
        raw = json.loads(response.read().decode("utf-8"))["response"]
except Exception as e:
    print("LLM call failed:", e)
    sys.exit(1)

# 🔥 HARD SANITIZATION PIPELINE

# 1. Remove markdown fences if present
raw = raw.replace("```java", "").replace("```", "").strip()

# 2. Extract only the App class
match = re.search(r"(public\s+class\s+App[\s\S]*\})", raw)

if not match:
    print("Invalid LLM output – no valid App class found")
    sys.exit(1)

java_code = match.group(1)

# 3. Write clean Java
with open("src/App.java", "w", encoding="utf-8") as f:
    f.write(java_code)

print("App.java overwritten with clean Java code")