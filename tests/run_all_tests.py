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
import argparse
from typing import Dict, List, Tuple

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="HomieProxy Comprehensive Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_tests.py --host localhost --port 8123 --name external-only-route --token 0061b276-ebab-4892-8c7b-13812084f5e9
  python run_all_tests.py --host ha.local --port 8123 --concurrent
  python run_all_tests.py --sequential --name internal-only-route
        """
    )
    
    parser.add_argument("--host", default=os.getenv("PROXY_HOST", "localhost"),
                       help="Proxy host (default: localhost)")
    parser.add_argument("--port", default=os.getenv("PROXY_PORT", "8123"),
                       help="Proxy port (default: 8123)")
    parser.add_argument("--name", default=os.getenv("PROXY_NAME", "external-api-route"),
                       help="Proxy instance name (default: external-api-route)")
    parser.add_argument("--token", default=os.getenv("PROXY_TOKEN", ""),
                       help="Authentication token (auto-detected if not provided)")
    
    parser.add_argument("--concurrent", action="store_true", default=True,
                       help="Run tests concurrently (default)")
    parser.add_argument("--sequential", action="store_true", 
                       help="Run tests sequentially (slower, more detailed output)")
    
    parser.add_argument("--max-workers", type=int, default=3,
                       help="Maximum concurrent workers (default: 3)")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Timeout per test in seconds (default: 300)")
    
    parser.add_argument("--list-tests", action="store_true",
                       help="List all available tests and exit")
    parser.add_argument("--category", choices=["core", "headers", "security", "network", "methods", "cors", "redirects", "performance", "debug"],
                       help="Run only tests from specific category")
    parser.add_argument("--force", action="store_true",
                       help="Skip confirmation prompt and run tests immediately")
    
    args = parser.parse_args()
    
    # Handle mode selection
    if args.sequential:
        args.concurrent = False
    
    return args

# Configuration - can be overridden by command line arguments
args = parse_arguments()
PROXY_HOST = args.host
PROXY_PORT = args.port
PROXY_NAME = args.name
PROXY_TOKEN = args.token

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
    if PROXY_TOKEN:
        print(f"  Token: {PROXY_TOKEN[:8]}...{PROXY_TOKEN[-8:]}")
    else:
        print(f"  Token: (auto-detect from debug endpoint)")
    print("")
    print("To override configuration, use command line arguments:")
    print("  --host, --port, --name, --token")
    print("Or set environment variables: PROXY_HOST, PROXY_PORT, PROXY_NAME, PROXY_TOKEN")
    print("")
    print("Test Modes:")
    print("  --concurrent : Run tests concurrently (faster, default)")
    print("  --sequential : Run tests one by one (slower, more detailed output)")
    print("")
    print("Prerequisites:")
    print("- Home Assistant running with HomieProxy configured")
    print("- Internet connection for testing external services")
    print("")
    
    # Define test files in order of preference (concurrent safe)
    core_tests = [
        "test_http_methods.py",           # Basic HTTP methods
        "test_follow_redirects.py",       # Redirect following  
        "test_websocket.py",              # WebSocket functionality
        "test_streaming_performance.py",  # Streaming and performance
        "test_concurrent_connections.py", # Concurrent connections test
        "test_concurrent_requests.py",    # Concurrent requests test
        "test_proxy.py",                  # Core proxy functionality
    ]
    
    # Header and host tests
    header_tests = [
        "test_host_header.py",
        "test_override_host.py", 
        "test_header_logging.py",
        "test_header_logging_demo.py",
        "test_user_agent.py",
        "test_blank_ua.py",
        "test_response_headers.py",
    ]
    
    # TLS and security tests
    security_tests = [
        "test_tls_all.py",
        "test_tls_fix.py", 
        "test_tls_cert_info.py",
        "simple_tls_test.py",
    ]
    
    # Access control and networking tests
    network_tests = [
        "test_access_control.py",
        "test_cloudflare_dns.py",
        "test_dns_override.py",
    ]
    
    # POST/PUT/PATCH method tests
    method_tests = [
        "test_post_methods.py",
    ]
    
    # CORS and options tests  
    cors_tests = [
        "test_options_cors.py",
        "cors_test.py",
    ]
    
    # Redirect tests
    redirect_tests = [
        "test_redirect_simple.py",
    ]
    
    # Performance and streaming tests
    performance_tests = [
        "test_real_video.py",
    ]
    
    # Simple/debug tests
    debug_tests = [
        "test_simple.py",
        "test_simple_debug.py", 
        "test_debug_simple.py",
        "debug_headers.py",
    ]
    
    # Combine all test categories
    all_test_categories = [
        ("Core Functionality", "core", core_tests),
        ("Headers & Host", "headers", header_tests), 
        ("TLS & Security", "security", security_tests),
        ("Network & Access Control", "network", network_tests),
        ("HTTP Methods", "methods", method_tests),
        ("CORS & Options", "cors", cors_tests),
        ("Redirects", "redirects", redirect_tests),
        ("Performance", "performance", performance_tests),
        ("Debug & Simple", "debug", debug_tests),
    ]
    
    # Find existing test files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    existing_tests = []
    
    print("Scanning for available tests...")
    
    # Add tests from all categories that exist
    for category_name, category_key, test_files in all_test_categories:
        category_found = []
        for test_file in test_files:
            test_path = os.path.join(script_dir, test_file)
            if os.path.exists(test_path):
                category_found.append(test_file)
                # Only add to existing_tests if no category filter or matches filter
                if not args.category or args.category == category_key:
                    existing_tests.append(test_file)
        
        if category_found:
            filtered_info = f" (filtered)" if args.category and args.category != category_key else ""
            print(f"  {category_name}: {len(category_found)} tests found{filtered_info}")
    
    # Check for any test files that weren't categorized
    all_files = [f for f in os.listdir(script_dir) if f.startswith('test_') and f.endswith('.py')]
    all_files.extend([f for f in os.listdir(script_dir) if f.endswith('_test.py')])
    all_files.extend(['cors_test.py', 'debug_headers.py', 'simple_tls_test.py'])  # Non-standard naming
    
    categorized_files = []
    for _, _, test_files in all_test_categories:
        categorized_files.extend(test_files)
    
    uncategorized = [f for f in all_files if f not in categorized_files and f != 'run_all_tests.py']
    if uncategorized:
        print(f"\nUncategorized test files found: {uncategorized}")
        for test_file in uncategorized:
            test_path = os.path.join(script_dir, test_file)
            if os.path.exists(test_path):
                if not args.category:  # Only add uncategorized if no category filter
                    existing_tests.append(test_file)
                print(f"  Added uncategorized test: {test_file}")
    
    # Handle --list-tests option
    if args.list_tests:
        print(f"\nAll available tests ({len(existing_tests)} total):")
        for i, test_file in enumerate(existing_tests, 1):
            print(f"  {i:2d}. {test_file}")
        return 0
    
    print(f"\nTotal tests found: {len(existing_tests)}")
    if args.category:
        print(f"Category filter: {args.category}")
    print(f"Tests to run: {', '.join(existing_tests[:5])}{'...' if len(existing_tests) > 5 else ''}")
    
    if not existing_tests:
        print("No tests found to run!")
        return 1
    
    mode_str = "concurrent" if args.concurrent else "sequential"
    print(f"Running in {mode_str} mode...")
    
    if not PROXY_TOKEN:
        print("\n⚠️  No token provided - will attempt auto-detection from debug endpoint")
    
    if not args.force:
        input("Press Enter to start tests (or Ctrl+C to cancel)...")
    
    start_time = time.time()
    
    # Run tests
    if args.concurrent:
        results = run_tests_concurrent(existing_tests, max_workers=args.max_workers)
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