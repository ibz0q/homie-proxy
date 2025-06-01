#!/usr/bin/env python3
"""
Master test runner for HomieProxy integration
Runs all comprehensive tests with optional concurrency for speed
"""

import subprocess
import sys
import time
import os
import concurrent.futures
import threading
from typing import Dict, List, Tuple

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = os.getenv("PROXY_PORT", "8123")
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

def run_test_file(test_file: str, capture_output: bool = True) -> Tuple[str, bool, str, float]:
    """Run a test file and return (test_file, success, output, duration)"""
    start_time = time.time()
    
    if not capture_output:
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
                              capture_output=capture_output, 
                              text=True, 
                              timeout=300,  # 5 minute timeout per test
                              env=env)
        
        duration = time.time() - start_time
        output = result.stdout + result.stderr if capture_output else ""
        
        if result.returncode == 0:
            if not capture_output:
                print(f"\n✓ {test_file} COMPLETED SUCCESSFULLY")
            return test_file, True, output, duration
        else:
            if not capture_output:
                print(f"\n✗ {test_file} FAILED (exit code: {result.returncode})")
            return test_file, False, output, duration
            
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        if not capture_output:
            print(f"\n✗ {test_file} TIMED OUT")
        return test_file, False, "TIMEOUT", duration
    except FileNotFoundError:
        duration = time.time() - start_time
        if not capture_output:
            print(f"\n✗ {test_file} NOT FOUND")
        return test_file, False, "FILE NOT FOUND", duration
    except Exception as e:
        duration = time.time() - start_time
        if not capture_output:
            print(f"\n✗ {test_file} FAILED WITH EXCEPTION: {e}")
        return test_file, False, str(e), duration

def run_tests_concurrent(test_files: List[str], max_workers: int = 3) -> Dict[str, Tuple[bool, str, float]]:
    """Run tests concurrently and return results"""
    print(f"\n🚀 Running {len(test_files)} tests concurrently (max {max_workers} workers)...")
    
    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tests
        future_to_test = {
            executor.submit(run_test_file, test_file, True): test_file 
            for test_file in test_files
        }
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_test):
            test_file = future_to_test[future]
            try:
                _, success, output, duration = future.result()
                results[test_file] = (success, output, duration)
                
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"  {status}: {test_file} ({duration:.1f}s)")
                
            except Exception as exc:
                print(f'  ✗ FAIL: {test_file} generated an exception: {exc}')
                results[test_file] = (False, str(exc), 0.0)
    
    return results

def run_tests_sequential(test_files: List[str]) -> Dict[str, Tuple[bool, str, float]]:
    """Run tests sequentially (original behavior)"""
    print(f"\n📝 Running {len(test_files)} tests sequentially...")
    
    results = {}
    
    for test_file in test_files:
        _, success, output, duration = run_test_file(test_file, False)
        results[test_file] = (success, output, duration)
        
        if not success:
            print(f"\n⚠️  Test {test_file} failed, but continuing with remaining tests...")
        
        time.sleep(1)  # Brief pause between tests
    
    return results

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
    print("Test Modes:")
    print("  --concurrent : Run tests concurrently (faster, default)")
    print("  --sequential : Run tests one by one (slower, more detailed output)")
    print("")
    print("Prerequisites:")
    print("- Home Assistant running with HomieProxy configured")
    print("- Internet connection for testing external services")
    print("")
    
    # Check for command line arguments
    concurrent_mode = True
    if len(sys.argv) > 1:
        if "--sequential" in sys.argv:
            concurrent_mode = False
        elif "--concurrent" in sys.argv:
            concurrent_mode = True
    
    mode_str = "concurrent" if concurrent_mode else "sequential"
    print(f"Running in {mode_str} mode...")
    
    input("Press Enter to start tests (or Ctrl+C to cancel)...")
    
    start_time = time.time()
    
    # Define test files in order of preference (concurrent safe)
    test_files = [
        "test_http_methods.py",           # Basic HTTP methods
        "test_follow_redirects.py",       # Redirect following
        "test_websocket.py",              # WebSocket functionality
        "test_streaming_performance.py",  # Streaming and performance
        "test_concurrent_connections.py", # New concurrent connections test
    ]
    
    # Optional additional tests that might exist
    optional_tests = [
        "test_access_control.py",
        "test_tls_fix.py",
        "test_user_agent.py",
        "test_response_header.py",
        "test_host_header.py",
    ]
    
    # Find existing test files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    existing_tests = []
    
    # Add core tests that exist
    for test_file in test_files:
        test_path = os.path.join(script_dir, test_file)
        if os.path.exists(test_path):
            existing_tests.append(test_file)
        else:
            print(f"Core test not found: {test_file}")
    
    # Add optional tests that exist
    for test_file in optional_tests:
        test_path = os.path.join(script_dir, test_file)
        if os.path.exists(test_path):
            print(f"Found optional test: {test_file}")
            existing_tests.append(test_file)
    
    # Run tests
    if concurrent_mode:
        results = run_tests_concurrent(existing_tests, max_workers=3)
    else:
        results = run_tests_sequential(existing_tests)
    
    # Summary
    end_time = time.time()
    total_time = end_time - start_time
    
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")
    
    successful_tests = sum(1 for success, _, _ in results.values() if success)
    total_tests = len(results)
    
    print(f"Total tests run: {total_tests}")
    print(f"Successful tests: {successful_tests}")
    print(f"Failed tests: {total_tests - successful_tests}")
    print(f"Total time: {total_time:.1f} seconds")
    print(f"Mode: {mode_str}")
    print("")
    
    # Detailed results
    print("Detailed Results:")
    for test_file, (success, output, duration) in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_file} ({duration:.1f}s)")
        
        # Show error output for failed tests
        if not success and output and output not in ["TIMEOUT", "FILE NOT FOUND"]:
            # Show last few lines of error output
            error_lines = output.split('\n')[-5:]
            for line in error_lines:
                if line.strip():
                    print(f"    {line}")
    
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