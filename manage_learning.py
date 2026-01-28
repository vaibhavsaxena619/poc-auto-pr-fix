#!/usr/bin/env python3
"""
Learning Database Manager - View, analyze, and manage the self-learning classifier.

Usage:
    python manage_learning.py stats          # Show overall statistics
    python manage_learning.py patterns       # Show all tracked patterns
    python manage_learning.py promoted       # Show promoted patterns
    python manage_learning.py pattern <name> # Show details for a specific pattern
    python manage_learning.py reset          # Reset learning database
    python manage_learning.py promote <pattern> <category>  # Manually promote pattern
"""

import sys
import json
from learning_classifier import LearningDatabase, SUCCESS_THRESHOLD
from tabulate import tabulate  # pip install tabulate

def cmd_stats():
    """Display overall learning statistics."""
    db = LearningDatabase()
    stats = db.get_stats()
    
    print("\n" + "="*70)
    print("📊 LEARNING CLASSIFIER STATISTICS")
    print("="*70)
    
    data = [
        ["Total Patterns Tracked", stats["total_patterns_tracked"]],
        ["Patterns Promoted to HIGH", stats["patterns_promoted_to_high"]],
        ["Total Fixes Attempted", stats["total_fixes_attempted"]],
        ["Total Fixes Successful", stats["total_fixes_succeeded"]],
        ["Overall Success Rate", f"{stats['overall_success_rate']:.1%}"],
        ["Last Updated", stats["last_updated"]]
    ]
    
    print(tabulate(data, headers=["Metric", "Value"], tablefmt="grid"))
    print()


def cmd_patterns():
    """Display all tracked patterns with their stats."""
    db = LearningDatabase()
    patterns = db.data["patterns"]
    
    if not patterns:
        print("No patterns tracked yet.")
        return
    
    print("\n" + "="*100)
    print("📚 ALL TRACKED PATTERNS")
    print("="*100 + "\n")
    
    data = []
    for pattern_key, stats in sorted(patterns.items()):
        promotion_status = "✅ PROMOTED" if stats["promoted_to_high"] else "⏳ Learning"
        
        data.append([
            pattern_key,
            stats["total_attempts"],
            stats["successful_fixes"],
            stats["failed_fixes"],
            f"{stats['success_rate']:.0%}",
            f"{stats['consecutive_successes']}/{SUCCESS_THRESHOLD}",
            promotion_status
        ])
    
    headers = ["Pattern", "Attempts", "Successes", "Failures", "Rate", "Progress", "Status"]
    print(tabulate(data, headers=headers, tablefmt="grid"))
    print()


def cmd_promoted():
    """Display only promoted patterns."""
    db = LearningDatabase()
    patterns = db.data["patterns"]
    
    promoted = {k: v for k, v in patterns.items() if v["promoted_to_high"]}
    
    if not promoted:
        print("\n✅ No patterns promoted yet. They will appear here after reaching success threshold.")
        return
    
    print("\n" + "="*100)
    print("✅ PROMOTED PATTERNS (Now in HIGH-CONFIDENCE)")
    print("="*100 + "\n")
    
    data = []
    for pattern_key, stats in sorted(promoted.items()):
        data.append([
            pattern_key,
            stats["total_attempts"],
            stats["successful_fixes"],
            f"{stats['success_rate']:.0%}",
            stats["promotion_date"]
        ])
    
    headers = ["Pattern", "Attempts", "Successes", "Success Rate", "Promoted Date"]
    print(tabulate(data, headers=headers, tablefmt="grid"))
    print()
    
    print(f"💡 TIP: Update HIGH_CONFIDENCE_PATTERNS in build_fix_v2.py with these patterns")
    print()


def cmd_pattern(pattern_name: str):
    """Display details for a specific pattern."""
    db = LearningDatabase()
    patterns = db.data["patterns"]
    
    # Find pattern (case-insensitive partial match)
    matching = {k: v for k, v in patterns.items() if pattern_name.lower() in k.lower()}
    
    if not matching:
        print(f"\n❌ Pattern '{pattern_name}' not found in database")
        print("\nAvailable patterns:")
        for key in patterns.keys():
            print(f"  - {key}")
        return
    
    for pattern_key, stats in matching.items():
        print("\n" + "="*70)
        print(f"📋 PATTERN DETAILS: {pattern_key}")
        print("="*70)
        
        data = [
            ["Category", stats["category"]],
            ["Original Pattern", stats["pattern"]],
            ["Total Attempts", stats["total_attempts"]],
            ["Successful Fixes", stats["successful_fixes"]],
            ["Failed Fixes", stats["failed_fixes"]],
            ["Success Rate", f"{stats['success_rate']:.1%}"],
            ["Consecutive Successes", f"{stats['consecutive_successes']}/{SUCCESS_THRESHOLD}"],
            ["Consecutive Failures", stats["consecutive_failures"]],
            ["Promoted to HIGH", "✅ Yes" if stats["promoted_to_high"] else "⏳ No"],
            ["Promotion Date", stats["promotion_date"] or "N/A"],
            ["Last Updated", stats["last_updated"]]
        ]
        
        print(tabulate(data, headers=["Attribute", "Value"], tablefmt="grid"))
        
        # Show error examples
        if stats["error_examples"]:
            print("\n📝 Recent Examples:")
            for i, example in enumerate(stats["error_examples"][-3:], 1):
                status = "✅" if example["success"] else "❌"
                print(f"  {status} Example {i}: {example['error']}")
        
        print()


def cmd_reset():
    """Reset learning database."""
    response = input("\n⚠️  Are you sure you want to reset the learning database? (yes/no): ")
    
    if response.lower() == "yes":
        import os
        db_path = "error_learning.json"
        if os.path.exists(db_path):
            os.remove(db_path)
            print("✅ Learning database reset")
        else:
            print("ℹ️ No learning database found")
    else:
        print("Cancelled")


def cmd_promote(pattern: str, category: str):
    """Manually promote a pattern to HIGH-confidence."""
    db = LearningDatabase()
    
    if db.promote_pattern(pattern, category):
        print(f"✅ Pattern promoted: {category}:{pattern}")
        print("\n💡 Next step: Add this pattern to HIGH_CONFIDENCE_PATTERNS in build_fix_v2.py")
        print(f"\nAdd to HIGH_CONFIDENCE_PATTERNS dict:")
        print(f"    '{category}': r'{pattern}',")
    else:
        print(f"❌ Failed to promote pattern")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "stats":
            cmd_stats()
        elif command == "patterns":
            cmd_patterns()
        elif command == "promoted":
            cmd_promoted()
        elif command == "pattern" and len(sys.argv) > 2:
            cmd_pattern(sys.argv[2])
        elif command == "reset":
            cmd_reset()
        elif command == "promote" and len(sys.argv) > 3:
            cmd_promote(sys.argv[2], sys.argv[3])
        else:
            print(__doc__)
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
