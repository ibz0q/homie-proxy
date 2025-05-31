#!/usr/bin/env python3
"""
Master test runner for HomieProxy integration
Runs all comprehensive tests in sequence
"""

import subprocess
import sys
import time
import os

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = os.getenv("PROXY_PORT", "8123")
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

def run_test_file(test_file):
    """Run a test file and return success status"""
    print(f"\n{'='*60}")
    print(f"RUNNING: {test_file}")
    print(f"{'='*60}")
    
    try:
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        test_path = os.path.join(script_dir, test_file)
        
        # Set up environment variables for the test
        env = os.environ.copy()
        env.update({
            "PROXY_HOST": PROXY_HOST,
            "PROXY_PORT": PROXY_PORT,
            "PROXY_NAME": PROXY_NAME,
            "PROXY_TOKEN": PROXY_TOKEN
        })
        
        # Run the test file
        result = subprocess.run([sys.executable, test_path], 
                              capture_output=False, 
                              text=True, 
                              timeout=300,  # 5 minute timeout per test
                              env=env)
        
        if result.returncode == 0:
            print(f"\n✓ {test_file} COMPLETED SUCCESSFULLY")
            return True
        else:
            print(f"\n✗ {test_file} FAILED (exit code: {result.returncode})")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n✗ {test_file} TIMED OUT")
        return False
    except FileNotFoundError:
        print(f"\n✗ {test_file} NOT FOUND")
        return False
    except Exception as e:
        print(f"\n✗ {test_file} FAILED WITH EXCEPTION: {e}")
        return False

def main():
    """Run all comprehensive tests"""
    print("=" * 60)
    print("HOMIE PROXY - COMPREHENSIVE TEST SUITE")
    print("=" * 60)
    print("This will run all available tests for the HomieProxy integration")
    print("")
    print("Current Configuration:")
    print(f"  Host: {PROXY_HOST}")
    print(f"  Port: {PROXY_PORT}")
    print(f"  Instance Name: {PROXY_NAME}")
    print(f"  Token: {PROXY_TOKEN[:8]}...{PROXY_TOKEN[-8:]}")
    print("")
    print("To override configuration, set environment variables:")
    print("  PROXY_HOST, PROXY_PORT, PROXY_NAME, PROXY_TOKEN")
    print("")
    print("Prerequisites:")
    print("- Home Assistant running with HomieProxy configured")
    print("- Internet connection for testing external services")
    print("")
    
    input("Press Enter to start tests (or Ctrl+C to cancel)...")
    
    start_time = time.time()
    
    # Define test files in order of execution
    test_files = [
        "test_http_methods.py",      # Basic HTTP methods
        "test_follow_redirects.py",  # Redirect following
        "test_websocket.py",         # WebSocket functionality
        "test_streaming_performance.py",  # Streaming and performance
    ]
    
    # Optional additional tests that might exist
    optional_tests = [
        "test_access_control.py",
        "test_tls_fix.py",
        "test_user_agent.py",
        "test_response_headers.py",
        "test_host_header.py",
        "test_concurrent_requests.py"
    ]
    
    results = {}
    
    # Run core tests
    print(f"\nRunning {len(test_files)} core tests...")
    for test_file in test_files:
        success = run_test_file(test_file)
        results[test_file] = success
        
        if not success:
            print(f"\n⚠️  Test {test_file} failed, but continuing with remaining tests...")
        
        time.sleep(2)  # Brief pause between tests
    
    # Run optional tests if they exist
    print(f"\nChecking for {len(optional_tests)} optional tests...")
    for test_file in optional_tests:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        test_path = os.path.join(script_dir, test_file)
        
        if os.path.exists(test_path):
            print(f"Found optional test: {test_file}")
            success = run_test_file(test_file)
            results[test_file] = success
            time.sleep(2)
        else:
            print(f"Optional test not found: {test_file}")
    
    # Summary
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")
    
    successful_tests = sum(1 for success in results.values() if success)
    total_tests = len(results)
    
    print(f"Total tests run: {total_tests}")
    print(f"Successful tests: {successful_tests}")
    print(f"Failed tests: {total_tests - successful_tests}")
    print(f"Total time: {total_time:.1f} seconds")
    print("")
    
    # Detailed results
    print("Detailed Results:")
    for test_file, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_file}")
    
    # Final status
    if successful_tests == total_tests:
        print(f"\n🎉 ALL TESTS PASSED! ({successful_tests}/{total_tests})")
        return 0
    else:
        print(f"\n⚠️  SOME TESTS FAILED ({successful_tests}/{total_tests} passed)")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n💥 Test suite crashed: {e}")
        sys.exit(1) 