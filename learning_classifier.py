#!/usr/bin/env python3
"""
Self-Learning Error Classifier - Adaptive confidence scoring based on historical outcomes.

Features:
1. PERSISTENT LEARNING: Tracks success/failure of AI fixes per error pattern
2. DYNAMIC PROMOTION: Automatically promotes LOW-confidence patterns to HIGH-confidence after N successes
3. FEEDBACK INTEGRATION: Merges learning data when PR is merged to main branch
4. CONFIDENCE BOOST: Applies historical success rate as confidence multiplier
5. PATTERN EVOLUTION: Updates pattern matching based on real-world outcomes

Learning Flow:
1. AI generates fix for LOW-confidence error
2. If PR is merged → update learning DB with success
3. If error pattern reaches threshold (e.g., 5/5 successes) → promote to HIGH-confidence
4. Future errors use updated confidence scores
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, List

# Configuration
# Store in Git workspace (tracked files)
WORKSPACE_DIR = os.getenv('WORKSPACE', os.getcwd())
LEARNING_DB_PATH = os.getenv('LEARNING_DB_PATH', os.path.join(WORKSPACE_DIR, 'learning_db.json'))

# Ensure directory exists
os.makedirs(os.path.dirname(LEARNING_DB_PATH) if os.path.dirname(LEARNING_DB_PATH) else '.', exist_ok=True)

SUCCESS_THRESHOLD = 5  # Consecutive successes needed to promote
FAILURE_THRESHOLD = 2  # Consecutive failures to demote back to LOW
CONFIDENCE_BOOST_FACTOR = 0.05  # Each success adds 5% to base confidence (0.9 → 0.95)


class LearningDatabase:
    """Manages persistent storage of error classification outcomes."""
    
    def __init__(self, db_path: str = LEARNING_DB_PATH):
        self.db_path = db_path
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load learning database from JSON file."""
        if not os.path.exists(self.db_path):
            return {
                "metadata": {
                    "version": "1.0",
                    "created": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "total_fixes_attempted": 0,
                    "total_fixes_succeeded": 0,
                    "total_patterns_promoted": 0
                },
                "patterns": {},  # error_pattern_key -> learning stats
                "pattern_history": []  # changelog of pattern updates
            }
        
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load learning DB: {e}, creating new one")
            return self._load()  # Return fresh copy
    
    def save(self) -> bool:
        """Persist learning database to disk."""
        try:
            self.data["metadata"]["last_updated"] = datetime.now().isoformat()
            with open(self.db_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ Failed to save learning DB: {e}")
            return False
    
    def record_fix_attempt(self, error_pattern: str, category: str, success: bool, 
                          error_message: str = None, fix_attempt: str = None) -> None:
        """
        Record an attempt to fix an error pattern.
        
        Args:
            error_pattern: The regex pattern that matched this error (e.g., "NullPointerException")
            category: Error category (e.g., "business_logic", "syntax_error")
            success: Whether the fix was successful
            error_message: The actual error message for pattern refinement
            fix_attempt: What the AI tried to fix
        """
        pattern_key = f"{category}:{error_pattern}"
        
        if pattern_key not in self.data["patterns"]:
            self.data["patterns"][pattern_key] = {
                "category": category,
                "pattern": error_pattern,
                "original_confidence": None,  # Will be set on first learning
                "current_confidence": None,
                "total_attempts": 0,
                "successful_fixes": 0,
                "failed_fixes": 0,
                "success_rate": 0.0,
                "promoted_to_high": False,
                "promotion_date": None,
                "consecutive_successes": 0,
                "consecutive_failures": 0,
                "last_updated": datetime.now().isoformat(),
                "error_examples": [],
                "fix_examples": []
            }
        
        stats = self.data["patterns"][pattern_key]
        stats["total_attempts"] += 1
        self.data["metadata"]["total_fixes_attempted"] += 1
        
        if success:
            stats["successful_fixes"] += 1
            stats["consecutive_successes"] += 1
            stats["consecutive_failures"] = 0
            self.data["metadata"]["total_fixes_succeeded"] += 1
        else:
            stats["failed_fixes"] += 1
            stats["consecutive_failures"] += 1
            stats["consecutive_successes"] = 0
        
        # Update success rate
        stats["success_rate"] = stats["successful_fixes"] / stats["total_attempts"]
        stats["last_updated"] = datetime.now().isoformat()
        
        # Store example for pattern refinement
        if error_message:
            if len(stats["error_examples"]) < 5:  # Keep last 5 examples
                stats["error_examples"].append({
                    "error": error_message[:200],
                    "timestamp": datetime.now().isoformat(),
                    "success": success
                })
    
    def check_promotion(self, error_pattern: str, category: str) -> Tuple[bool, str]:
        """
        Check if a pattern should be promoted from LOW to HIGH confidence.
        
        Returns: (should_promote, reason)
        """
        pattern_key = f"{category}:{error_pattern}"
        
        if pattern_key not in self.data["patterns"]:
            return False, "Pattern not in learning database"
        
        stats = self.data["patterns"][pattern_key]
        
        # Already promoted
        if stats["promoted_to_high"]:
            return False, "Already promoted to HIGH-confidence"
        
        # Check promotion criteria
        if stats["consecutive_successes"] >= SUCCESS_THRESHOLD:
            return True, f"Reached {SUCCESS_THRESHOLD} consecutive successes ({stats['success_rate']:.0%} success rate)"
        
        return False, f"Progress: {stats['consecutive_successes']}/{SUCCESS_THRESHOLD} consecutive successes"
    
    def promote_pattern(self, error_pattern: str, category: str) -> bool:
        """
        Promote a pattern from LOW to HIGH confidence.
        
        This means the pattern will be moved to HIGH_CONFIDENCE_PATTERNS in build_fix_v2.py
        """
        pattern_key = f"{category}:{error_pattern}"
        
        if pattern_key not in self.data["patterns"]:
            return False
        
        stats = self.data["patterns"][pattern_key]
        stats["promoted_to_high"] = True
        stats["promotion_date"] = datetime.now().isoformat()
        
        self.data["pattern_history"].append({
            "action": "PROMOTED",
            "pattern_key": pattern_key,
            "category": category,
            "success_rate": stats["success_rate"],
            "consecutive_successes": stats["consecutive_successes"],
            "timestamp": datetime.now().isoformat()
        })
        
        self.data["metadata"]["total_patterns_promoted"] += 1
        
        print(f"✅ PATTERN PROMOTED: {category} - Success rate: {stats['success_rate']:.0%}")
        
        return self.save()
    
    def get_adaptive_confidence(self, error_pattern: str, category: str, 
                               base_confidence: float) -> float:
        """
        Get adaptive confidence score based on historical success.
        
        Returns confidence score boosted by success history.
        """
        pattern_key = f"{category}:{error_pattern}"
        
        if pattern_key not in self.data["patterns"]:
            return base_confidence
        
        stats = self.data["patterns"][pattern_key]
        
        # Boost confidence by success rate
        # Example: 0.1 (LOW) with 80% success → 0.1 + (0.8 * 0.05) = 0.14
        # After N successes, might jump to 0.9 (HIGH)
        success_boost = stats["success_rate"] * CONFIDENCE_BOOST_FACTOR
        
        adaptive_conf = min(base_confidence + success_boost, 1.0)  # Cap at 1.0
        
        return adaptive_conf
    
    def get_stats(self) -> dict:
        """Get learning database statistics."""
        patterns = self.data["patterns"]
        promoted = sum(1 for p in patterns.values() if p["promoted_to_high"])
        
        return {
            "total_patterns_tracked": len(patterns),
            "patterns_promoted_to_high": promoted,
            "total_fixes_attempted": self.data["metadata"]["total_fixes_attempted"],
            "total_fixes_succeeded": self.data["metadata"]["total_fixes_succeeded"],
            "overall_success_rate": (
                self.data["metadata"]["total_fixes_succeeded"] / 
                max(1, self.data["metadata"]["total_fixes_attempted"])
            ),
            "last_updated": self.data["metadata"]["last_updated"]
        }
    
    def get_pattern_stats(self, error_pattern: str, category: str) -> dict:
        """Get stats for a specific pattern."""
        pattern_key = f"{category}:{error_pattern}"
        
        if pattern_key not in self.data["patterns"]:
            return {}
        
        return self.data["patterns"][pattern_key]
    
    def get_pattern_confidence(self, category: str) -> float:
        """
        NEW: Get the confidence score for a category if it has been promoted.
        
        Args:
            category: Error category (e.g., "risky:business_logic")
        
        Returns:
            Confidence score (0.9 if promoted to HIGH, else None)
        """
        # Look through patterns for any with this category that are HIGH confidence
        for pattern_key, stats in self.data["patterns"].items():
            if pattern_key.startswith(category):
                if stats.get("promoted_to_high", False):
                    return 0.9  # HIGH confidence
        
        return None  # Not promoted yet


class AdaptiveClassifier:
    """
    Wraps the standard error classifier with learning-based confidence adjustment.
    """
    
    def __init__(self, learning_db: LearningDatabase = None):
        self.db = learning_db or LearningDatabase()
    
    def classify_with_learning(self, error_message: str, base_category: str, 
                               base_confidence: float) -> Tuple[str, float]:
        """
        Classify error with confidence boosted by learning history.
        
        Returns: (category, adaptive_confidence)
        """
        adaptive_confidence = self.db.get_adaptive_confidence(
            error_message[:100],  # Use first 100 chars as pattern key
            base_category,
            base_confidence
        )
        
        return base_category, adaptive_confidence
    
    def log_fix_outcome(self, error_message: str, category: str, success: bool) -> None:
        """
        Log the outcome of an attempted fix for learning.
        
        Should be called after PR is merged (success=True) or rejected (success=False)
        """
        self.db.record_fix_attempt(
            error_pattern=error_message[:100],
            category=category,
            success=success,
            error_message=error_message
        )
        
        # Check if pattern should be promoted
        should_promote, reason = self.db.check_promotion(error_message[:100], category)
        
        if should_promote:
            self.db.promote_pattern(error_message[:100], category)
            print(f"  📈 {reason}")
        else:
            print(f"  📊 {reason}")
        
        self.db.save()


def integrate_learning_into_classifier(base_category: str, base_confidence: float) -> Tuple[str, float]:
    """
    Integration point: Use this in build_fix_v2.py's classify_error_confidence()
    
    Example:
        category, confidence = classify_error_confidence(error_msg)
        category, adaptive_conf = integrate_learning_into_classifier(category, confidence)
    """
    classifier = AdaptiveClassifier()
    return classifier.classify_with_learning(base_category[:100], base_category, base_confidence)


def print_learning_stats():
    """Print learning database statistics."""
    db = LearningDatabase()
    stats = db.get_stats()
    
    print("\n" + "="*60)
    print("📚 LEARNING CLASSIFIER STATISTICS")
    print("="*60)
    print(f"Total Patterns Tracked:      {stats['total_patterns_tracked']}")
    print(f"Patterns Promoted to HIGH:   {stats['patterns_promoted_to_high']}")
    print(f"Total Fixes Attempted:       {stats['total_fixes_attempted']}")
    print(f"Total Fixes Successful:      {stats['total_fixes_succeeded']}")
    print(f"Overall Success Rate:        {stats['overall_success_rate']:.0%}")
    print(f"Last Updated:                {stats['last_updated']}")
    print("="*60)
    
    # Show top patterns
    db_data = db.data["patterns"]
    if db_data:
        print("\n🏆 TOP PERFORMING PATTERNS:")
        sorted_patterns = sorted(
            db_data.items(),
            key=lambda x: x[1]["success_rate"],
            reverse=True
        )[:5]
        
        for pattern_key, stats in sorted_patterns:
            status = "✅" if stats["promoted_to_high"] else "⏳"
            print(f"  {status} {pattern_key}")
            print(f"     Success: {stats['successful_fixes']}/{stats['total_attempts']} " +
                  f"({stats['success_rate']:.0%})")
            print(f"     Consecutive Successes: {stats['consecutive_successes']}/{SUCCESS_THRESHOLD}")


if __name__ == "__main__":
    print_learning_stats()
