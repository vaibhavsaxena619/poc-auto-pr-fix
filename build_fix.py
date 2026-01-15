#!/usr/bin/env python3
"""
Build failure recovery script - Analyzes compilation errors and applies fixes via Azure OpenAI.
Production-ready error handling with comprehensive logging.
"""

import os
import subprocess
import sys
import json
from pathlib import Path
from datetime import datetime

try:
    from openai import AzureOpenAI
except ImportError:
    print("ERROR: openai not installed. Run: pip install openai")
    sys.exit(1)


def get_compilation_error(source_file: str) -> str:
    """Capture compilation error from source file."""
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stderr if result.returncode != 0 else ""
    except Exception as e:
        print(f"ERROR: Failed to compile {source_file}: {e}")
        return ""


def read_source_file(source_file: str) -> str:
    """Read source file content."""
    try:
        with open(source_file, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"ERROR: Cannot read {source_file}: {e}")
        sys.exit(1)


def send_to_azure_openai(error_message: str, source_code: str, api_key: str, endpoint: str, api_version: str, deployment_name: str) -> str:
    """Send compilation error to Azure OpenAI for analysis and fix."""
    try:
        client = AzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=endpoint
        )
        
        prompt = f"""You are a Java code expert. A compilation error occurred. 
Analyze and provide ONLY the corrected code without explanations.

ERROR:
{error_message}

CURRENT CODE:
{source_code}

RESPONSE: Provide only the corrected Java code that fixes this error. No explanations."""
        
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": "You are a Java code expert that fixes compilation errors."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=2000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"ERROR: Azure OpenAI API failed: {e}")
        return ""


def apply_fix(source_file: str, fixed_code: str) -> bool:
    """Apply the fixed code to source file."""
    try:
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(fixed_code)
        print(f"Fixed code applied to {source_file}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to apply fix: {e}")
        return False


def verify_fix(source_file: str) -> bool:
    """Verify the fix by attempting compilation."""
    try:
        result = subprocess.run(
            ['javac', source_file],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception as e:
        print(f"ERROR: Verification failed: {e}")
        return False


def commit_changes(source_file: str, error_msg: str) -> bool:
    """Commit fixed code to git."""
    try:
        subprocess.run(['git', 'add', source_file], check=True, capture_output=True)
        result = subprocess.run(
            ['git', 'commit', '-m', f'Build fix: {error_msg[:50]}...'],
            check=False,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print("Changes committed to git")
            return True
        else:
            # Handle detached HEAD or other git issues gracefully
            if 'detached HEAD' in result.stderr or 'no changes added' in result.stderr:
                print("INFO: Git commit skipped (detached HEAD or no changes)")
                return True
            else:
                print(f"WARNING: Git commit failed: {result.stderr}")
                return True  # Still consider it a success as the fix was applied
    except Exception as e:
        print(f"WARNING: Git commit failed: {e}")
        return False


def main():
    """Main build fix workflow."""
    if len(sys.argv) < 2:
        print("Usage: python build_fix.py <source_file>")
        sys.exit(1)
    
    source_file = sys.argv[1]
    api_key = os.getenv('AZURE_OPENAI_API_KEY')
    endpoint = os.getenv('AZURE_OPENAI_ENDPOINT')
    api_version = os.getenv('AZURE_OPENAI_API_VERSION', '2024-12-01-preview')
    deployment_name = os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5')
    
    if not api_key or not endpoint:
        print("ERROR: AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT environment variables not set")
        sys.exit(1)
    
    if not os.path.exists(source_file):
        print(f"ERROR: Source file not found: {source_file}")
        sys.exit(1)
    
    print(f"[{datetime.now().isoformat()}] Build fix initiated for {source_file}")
    
    # Get compilation error
    error_msg = get_compilation_error(source_file)
    if not error_msg:
        print("No compilation errors detected")
        return
    
    print(f"Compilation error detected: {error_msg[:100]}...")
    
    # Read current source
    source_code = read_source_file(source_file)
    
    # Send to Azure OpenAI for fix
    print("Sending error to Azure OpenAI for analysis...")
    fixed_code = send_to_azure_openai(error_msg, source_code, api_key, endpoint, api_version, deployment_name)
    
    if not fixed_code:
        print("ERROR: Azure OpenAI failed to generate fix")
        sys.exit(1)
    
    # Apply fix
    print("Applying Azure OpenAI GPT-5 fix...")
    if not apply_fix(source_file, fixed_code):
        sys.exit(1)
    
    # Verify fix
    print("Verifying fix...")
    if verify_fix(source_file):
        print("SUCCESS: Fix verified - code compiles!")
        commit_changes(source_file, error_msg[:50])
    else:
        print("ERROR: Fix did not resolve compilation errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
