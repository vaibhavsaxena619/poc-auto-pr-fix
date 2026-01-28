#!/usr/bin/env python3
"""
QUICK START GUIDE - Fault Detection & Self-Learning System

Run this script to:
1. Validate all components are installed
2. Initialize learning databases
3. Test configuration
4. Show example workflows
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime


def print_section(title):
    """Print formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_file_exists(filepath):
    """Check if required file exists."""
    exists = Path(filepath).exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {filepath}")
    return exists


def check_import(module_name):
    """Check if Python module can be imported."""
    try:
        __import__(module_name)
        print(f"  ✓ {module_name}")
        return True
    except ImportError:
        print(f"  ✗ {module_name}")
        return False


def check_env_var(var_name, required=False):
    """Check if environment variable is set."""
    value = os.getenv(var_name)
    if value:
        masked = value[:10] + "..." if len(value) > 10 else value
        print(f"  ✓ {var_name}={masked}")
        return True
    else:
        status = "✗ REQUIRED" if required else "⚠️ OPTIONAL"
        print(f"  {status}: {var_name}")
        return not required


def check_command(cmd):
    """Check if command is available."""
    import subprocess
    try:
        subprocess.run([cmd, '--version'], capture_output=True, check=True, timeout=5)
        print(f"  ✓ {cmd}")
        return True
    except:
        print(f"  ✗ {cmd}")
        return False


def init_learning_db():
    """Initialize learning database if not exists."""
    learning_db_path = 'learning_db.json'
    
    if Path(learning_db_path).exists():
        print(f"  ✓ {learning_db_path} already exists")
        return True
    
    db = {
        "metadata": {
            "version": "2.0",
            "created": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "total_patterns": 0,
            "promoted_patterns": 0,
            "demoted_patterns": 0
        },
        "root_causes": {}
    }
    
    try:
        with open(learning_db_path, 'w') as f:
            json.dump(db, f, indent=2)
        print(f"  ✓ Created {learning_db_path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to create {learning_db_path}: {e}")
        return False


def init_pr_tracking():
    """Initialize PR tracking database if not exists."""
    pr_tracking_path = 'pr_tracking.json'
    
    if Path(pr_tracking_path).exists():
        print(f"  ✓ {pr_tracking_path} already exists")
        return True
    
    db = {
        "prs": [],
        "metadata": {
            "created": datetime.now().isoformat()
        }
    }
    
    try:
        with open(pr_tracking_path, 'w') as f:
            json.dump(db, f, indent=2)
        print(f"  ✓ Created {pr_tracking_path}")
        return True
    except Exception as e:
        print(f"  ✗ Failed to create {pr_tracking_path}: {e}")
        return False


def main():
    """Run validation and initialization."""
    
    print_section("QUICK START - SYSTEM VALIDATION")
    
    all_good = True
    
    # 1. Check files
    print_section("1. REQUIRED FILES")
    required_files = [
        'build_fix_v2.py',
        'fault_commit_analyzer.py',
        'pr_outcome_monitor.py',
        'learning_classifier.py',
        'schema_definitions.py'
    ]
    
    for f in required_files:
        if not check_file_exists(f):
            all_good = False
    
    # 2. Check Python dependencies
    print_section("2. PYTHON DEPENDENCIES")
    required_modules = [
        'openai',
        'requests',
        'subprocess',
        'json',
        'logging',
        'smtplib'
    ]
    
    for mod in required_modules:
        if not check_import(mod):
            all_good = False
    
    # 3. Check system commands
    print_section("3. SYSTEM COMMANDS")
    required_commands = [
        'git',
        'javac'
    ]
    
    for cmd in required_commands:
        if not check_command(cmd):
            all_good = False
    
    # 4. Check required environment variables
    print_section("4. REQUIRED ENVIRONMENT VARIABLES")
    required_vars = [
        'AZURE_OPENAI_API_KEY',
        'AZURE_OPENAI_ENDPOINT',
        'GITHUB_PAT'
    ]
    
    for var in required_vars:
        if not check_env_var(var, required=True):
            all_good = False
    
    # 5. Check optional environment variables
    print_section("5. OPTIONAL ENVIRONMENT VARIABLES")
    optional_vars = [
        'ENABLE_FAULT_DETECTION',
        'ENABLE_LEARNING',
        'ENABLE_EMAIL_NOTIFICATIONS',
        'SMTP_SERVER',
        'BUILD_LOG_URL'
    ]
    
    for var in optional_vars:
        check_env_var(var, required=False)
    
    # 6. Initialize databases
    print_section("6. INITIALIZE DATABASES")
    
    if not init_learning_db():
        all_good = False
    
    if not init_pr_tracking():
        all_good = False
    
    # 7. Show example commands
    print_section("7. EXAMPLE COMMANDS")
    
    print("""
  # Run build fix with fault detection
  python build_fix_v2.py src/App.java
  
  # Check learning database
  cat learning_db.json | jq '.root_causes'
  
  # Monitor open PRs
  python pr_outcome_monitor.py monitor
  
  # Add PR to tracking
  python pr_outcome_monitor.py add-pr 42 missing_dependency_import "error message"
  
  # View learning statistics
  python learning_classifier.py
  
  # View schema definitions
  python schema_definitions.py
    """)
    
    # 8. Final status
    print_section("VALIDATION SUMMARY")
    
    if all_good:
        print("""
  ✅ ALL CHECKS PASSED
  
  Next steps:
  1. Set remaining OPTIONAL environment variables as needed
  2. Configure cron job for pr_outcome_monitor.py (every 2 hours)
  3. Deploy to Jenkins/CI pipeline
  4. Test with sample build failure
  5. Monitor logs: tail -f fault_analyzer.log pr_outcome_monitor.log
        """)
        return 0
    else:
        print("""
  ⚠️ SOME CHECKS FAILED
  
  Please fix the issues above:
  1. Ensure all required files are in current directory
  2. Install missing Python packages: pip install -r requirements.txt
  3. Set all required environment variables
  4. Ensure git and javac are available in PATH
  
  Then run this script again.
        """)
        return 1


if __name__ == '__main__':
    sys.exit(main())
