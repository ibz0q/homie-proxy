#!/usr/bin/env python3
"""
Simple Test Runner for Reverse Proxy
Runs all test scripts and provides a summary (no psutil dependency)
"""

import os
import subprocess
import sys
import time
from datetime import datetime

def find_test_files():
    """Find all Python test files in the tests directory"""
    test_files = []
    tests_dir = "tests"
    
    if os.path.exists(tests_dir):
        for file in os.listdir(tests_dir):
            if file.endswith('.py') and (file.startswith('test_') or file.endswith('_test.py')):
                test_files.append(os.path.join(tests_dir, file))
    
    # Sort tests by priority (put core functionality tests first)
    priority_tests = [
        'test_host_header.py',
        'test_header_logging.py', 
        'test_tls_all.py',
        'test_cache_debug.py',
        'test_streaming.py'
    ]
    
    sorted_tests = []
    for priority_test in priority_tests:
        full_path = os.path.join(tests_dir, priority_test)
        if full_path in test_files:
            sorted_tests.append(full_path)
            test_files.remove(full_path)
    
    # Add remaining tests
    sorted_tests.extend(sorted(test_files))
    
    return sorted_tests

def check_server_running():
    """Check if the proxy server is running"""
    try:
        import requests
        response = requests.get("http://localhost:8080/default?token=test", timeout=2)
        return True
    except:
        return False

def run_test(test_file):
    """Run a single test file and analyze results"""
    test_name = os.path.basename(test_file)
    print(f"\n{'='*60}")
    print(f"🧪 Running: {test_name}")
    print('='*60)
    
    start_time = time.time()
    
    try:
        # Run the test
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=True, text=True, timeout=60)
        
        duration = time.time() - start_time
        output = result.stdout
        error_output = result.stderr
        return_code = result.returncode
        
        # Print test output
        if output:
            print(output)
        if error_output:
            print("STDERR:", error_output)
        
        # Analyze output for success/failure indicators
        success_indicators = ['✅', 'SUCCESS', 'PASSED', 'completed!', 'working correctly']
        failure_indicators = ['❌', 'ERROR', 'FAILED', 'failed:', 'Error:']
        
        success_count = sum(output.count(indicator) for indicator in success_indicators)
        failure_count = sum(output.count(indicator) for indicator in failure_indicators)
        
        # Determine status
        if return_code != 0:
            status = "FAILED"
        elif failure_count > success_count:
            status = "FAILED"  
        elif success_count > 0:
            status = "PASSED"
        else:
            status = "UNCLEAR"
        
        print(f"\n📊 Test Result: {status} ({duration:.2f}s)")
        
        return {
            'name': test_name,
            'status': status,
            'duration': duration,
            'return_code': return_code,
            'success_count': success_count,
            'failure_count': failure_count
        }
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print(f"⏰ Test timed out after 60 seconds")
        return {
            'name': test_name,
            'status': 'TIMEOUT',
            'duration': duration,
            'return_code': -1,
            'success_count': 0,
            'failure_count': 1
        }
    except Exception as e:
        duration = time.time() - start_time
        print(f"💥 Test execution failed: {e}")
        return {
            'name': test_name,
            'status': 'ERROR',
            'duration': duration,
            'return_code': -1,
            'success_count': 0,
            'failure_count': 1
        }

def print_summary(results):
    """Print test summary"""
    print("\n" + "="*80)
    print("📋 TEST SUMMARY REPORT")
    print("="*80)
    
    if not results:
        print("❌ No tests were executed")
        return
    
    # Count results by status
    passed = [r for r in results if r['status'] == 'PASSED']
    failed = [r for r in results if r['status'] == 'FAILED']
    errors = [r for r in results if r['status'] == 'ERROR']
    timeouts = [r for r in results if r['status'] == 'TIMEOUT']
    unclear = [r for r in results if r['status'] == 'UNCLEAR']
    
    total = len(results)
    total_duration = sum(r['duration'] for r in results)
    
    print(f"📊 Total Tests: {total}")
    print(f"✅ Passed: {len(passed)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"💥 Errors: {len(errors)}")
    print(f"⏰ Timeouts: {len(timeouts)}")
    print(f"❓ Unclear: {len(unclear)}")
    print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
    print(f"📅 Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Detailed results
    print(f"\n{'='*50}")
    print("📋 DETAILED RESULTS")
    print("="*50)
    
    for result in results:
        status_emoji = {
            'PASSED': '✅',
            'FAILED': '❌', 
            'ERROR': '💥',
            'TIMEOUT': '⏰',
            'UNCLEAR': '❓'
        }
        
        emoji = status_emoji.get(result['status'], '❓')
        print(f"{emoji} {result['name']:<30} {result['status']:<8} ({result['duration']:.2f}s)")
    
    # Failed tests
    failed_tests = [r for r in results if r['status'] in ['FAILED', 'ERROR', 'TIMEOUT']]
    if failed_tests:
        print(f"\n{'='*50}")
        print("❌ FAILED TESTS")
        print("="*50)
        for result in failed_tests:
            print(f"🔍 {result['name']}: {result['status']} (Return code: {result['return_code']})")
    
    # Success rate
    success_rate = (len(passed) / total * 100) if total > 0 else 0
    print(f"\n📈 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 Great job! Most tests are passing!")
    elif success_rate >= 60:
        print("👍 Good progress, but some tests need attention.")
    else:
        print("⚠️  Many tests are failing - check the proxy server and test environment.")

def main():
    print("🧪 Simple Reverse Proxy Test Runner")
    print("="*80)
    
    # Check if server is running
    if not check_server_running():
        print("❌ Proxy server is not running!")
        print("💡 Please start the server first: py reverse_proxy.py")
        print("   Then run this test script in another terminal.")
        return
    
    print("✅ Proxy server is running")
    
    # Find test files
    test_files = find_test_files()
    if not test_files:
        print("❌ No test files found in tests/ directory")
        return
    
    print(f"📁 Found {len(test_files)} test files")
    for test_file in test_files:
        print(f"  - {os.path.basename(test_file)}")
    
    # Run tests
    results = []
    for test_file in test_files:
        result = run_test(test_file)
        results.append(result)
        time.sleep(1)  # Brief pause between tests
    
    # Print summary
    print_summary(results)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Test run interrupted by user")
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1) 