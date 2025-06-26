#!/usr/bin/env python3
"""
Test the CLI integration with the new services architecture.

This ensures that flask fetch-news still works after our changes.
"""

import subprocess
import sys
from pathlib import Path

def test_cli_help():
    """Test that the CLI help command works."""
    print("=== Testing CLI Help ===")
    try:
        result = subprocess.run(
            ["flask", "--help"], 
            capture_output=True, 
            text=True, 
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print("✅ Flask CLI is responsive")
            # Check if our commands are listed
            if "fetch-news" in result.stdout:
                print("✅ fetch-news command is registered")
                return True
            else:
                print("❌ fetch-news command not found in help")
                return False
        else:
            print(f"❌ Flask CLI error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_fetch_news_help():
    """Test that fetch-news command shows help without errors."""
    print("\n=== Testing fetch-news Help ===")
    try:
        result = subprocess.run(
            ["flask", "fetch-news", "--help"], 
            capture_output=True, 
            text=True, 
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            print("✅ fetch-news command loads without import errors")
            print(f"Command description: {result.stdout.split('Usage:')[0].strip()}")
            return True
        else:
            print(f"❌ fetch-news help failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run CLI integration tests."""
    print("Testing CLI integration with new services architecture...\n")
    
    tests = [
        test_cli_help,
        test_fetch_news_help
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n=== Test Results ===")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✅ CLI integration successful! Ready to build full-content service.")
    else:
        print("❌ CLI integration failed. Check errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 