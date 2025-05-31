#!/usr/bin/env python3
"""
Test Runner for Homie Proxy
Runs all tests with configurable port settings
"""

import subprocess
import sys
import argparse
import os
import time
import requests

def test_proxy_connection(port):
    """Test if proxy is running on the specified port"""
    try:
        response = requests.get(f"http://localhost:{port}/nonexistent", timeout=2)
        return True  # Any response means proxy is running
    except requests.exceptions.ConnectionError:
        return False
    except:
        return True  # Other errors likely mean proxy is running

def run_test(test_file, port):
    """Run a single test file with the specified port"""
    print(f"\n{'='*60}")
    print(f"Running: {test_file}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run([
            sys.executable, f"tests/{test_file}", 
            "--port", str(port)
        ], timeout=30, capture_output=False)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {test_file} took too long")
        return False
    except Exception as e:
        print(f"ERROR running {test_file}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run homie proxy tests')
    parser.add_argument('--port', type=int, 
                       default=int(os.environ.get('PROXY_PORT', 8080)),
                       help='Proxy server port (default: 8080, or PROXY_PORT env var)')
    parser.add_argument('--test', type=str,
                       help='Run specific test file (without .py extension)')
    parser.add_argument('--skip-connection-check', action='store_true',
                       help='Skip checking if proxy is running')
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("HOMIE PROXY TEST RUNNER")
    print("=" * 80)
    print(f"Target proxy: localhost:{args.port}")
    
    # Check if proxy is running
    if not args.skip_connection_check:
        print(f"\nChecking if proxy is running on port {args.port}...")
        if not test_proxy_connection(args.port):
            print(f"❌ ERROR: No proxy found on localhost:{args.port}")
            print(f"Start the proxy server first:")
            print(f"  python homie_proxy.py --port {args.port}")
            sys.exit(1)
        print("✅ Proxy server detected")
    
    # Define test files that support --port argument
    test_files = [
        "test_simple.py",
        "test_blank_ua.py", 
        "test_concurrent_requests.py",
        "test_tls_all.py",
        "cors_test.py",
        "test_host_header.py",
        # Add more as they get updated...
    ]
    
    # If specific test requested, run only that
    if args.test:
        test_file = f"{args.test}.py"
        if test_file in test_files:
            success = run_test(test_file, args.port)
            sys.exit(0 if success else 1)
        else:
            print(f"❌ Test '{args.test}' not found or not yet updated for port configuration")
            print(f"Available tests: {', '.join([t.replace('.py', '') for t in test_files])}")
            sys.exit(1)
    
    # Run all tests
    print(f"\nRunning {len(test_files)} tests...")
    
    results = {}
    for test_file in test_files:
        success = run_test(test_file, args.port)
        results[test_file] = success
    
    # Summary
    print(f"\n{'='*80}")
    print("TEST RESULTS SUMMARY")
    print(f"{'='*80}")
    
    passed = 0
    failed = 0
    
    for test_file, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_file}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {len(results)} tests, {passed} passed, {failed} failed")
    
    if failed > 0:
        print(f"\n❌ {failed} test(s) failed")
        sys.exit(1)
    else:
        print(f"\n✅ All tests passed!")
        sys.exit(0)

if __name__ == '__main__':
    main() 