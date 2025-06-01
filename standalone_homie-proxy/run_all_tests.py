#!/usr/bin/env python3
"""
Master Test Runner for Homie Proxy
Runs all test files and provides a comprehensive test report.
"""

import subprocess
import sys
import os
import time
import argparse
from datetime import datetime

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run all Homie Proxy tests')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
parser.add_argument('--host', default='localhost',
                   help='Proxy server host (default: localhost)')
args = parser.parse_args()

print("=" * 80)
print("HOMIE PROXY - MASTER TEST RUNNER")
print("=" * 80)
print(f"Testing proxy at {args.host}:{args.port}")
print(f"Test started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Set environment variables for all tests
os.environ['PROXY_PORT'] = str(args.port)
os.environ['PROXY_HOST'] = args.host

# Test files to run (in order of importance)
test_files = [
    # Core functionality tests
    {
        'file': 'tests/test_simple.py',
        'name': 'Basic Functionality',
        'description': 'Tests basic GET requests and Host header fixes'
    },
    {
        'file': 'tests/test_proxy.py', 
        'name': 'Comprehensive Proxy Tests',
        'description': 'Full test suite including caching, headers, methods'
    },
    {
        'file': 'tests/test_access_control.py',
        'name': 'Access Control Tests',
        'description': 'Tests client IP restrictions and target URL access modes'
    },
    {
        'file': 'tests/test_tls_fix.py',
        'name': 'TLS Bypass & Fixes',
        'description': 'Tests TLS bypass and host header functionality'
    },
    {
        'file': 'tests/test_host_header.py',
        'name': 'Host Header Management', 
        'description': 'Tests Host header correction for different scenarios'
    },
    {
        'file': 'tests/test_override_host.py',
        'name': 'Host Header Override',
        'description': 'Tests manual host header override functionality'
    },
    
    # Feature-specific tests
    {
        'file': 'tests/test_user_agent.py',
        'name': 'User-Agent Handling',
        'description': 'Tests User-Agent preservation and modification'
    },
    {
        'file': 'tests/test_blank_ua.py',
        'name': 'Blank User-Agent',
        'description': 'Tests blank User-Agent default behavior'
    },
    {
        'file': 'tests/test_response_header.py',
        'name': 'Response Headers',
        'description': 'Tests custom response headers and CORS'
    },
    {
        'file': 'tests/test_header_logging.py',
        'name': 'Header Logging',
        'description': 'Tests request header logging functionality'
    },
    {
        'file': 'tests/cors_test.py',
        'name': 'CORS Headers',
        'description': 'Tests CORS header functionality'
    },
    
    # Advanced features
    {
        'file': 'tests/test_concurrent_requests.py',
        'name': 'Concurrent Requests',
        'description': 'Tests multi-threading and concurrent request handling'
    },
    {
        'file': 'tests/test_real_video.py',
        'name': 'Video Streaming',
        'description': 'Tests large file streaming and video handling'
    },
    {
        'file': 'tests/test_tls_all.py',
        'name': 'TLS Skip All',
        'description': 'Tests skip_tls_checks=ALL functionality'
    },
    {
        'file': 'tests/test_tls_cert_info.py',
        'name': 'TLS Certificate Logging',
        'description': 'Tests TLS certificate information logging'
    },
    {
        'file': 'tests/simple_tls_test.py',
        'name': 'TLS Certificate Inspector',
        'description': 'Standalone TLS certificate inspection tool'
    },
    {
        'file': 'tests/test_dns_override.py',
        'name': 'DNS Override',
        'description': 'Tests custom DNS server functionality'
    },
    {
        'file': 'tests/test_cloudflare_dns.py',
        'name': 'Cloudflare DNS Test',
        'description': 'Tests DNS resolution with Cloudflare servers'
    },
    {
        'file': 'tests/test_redirect_simple.py',
        'name': 'Redirect Following',
        'description': 'Tests redirect following functionality'
    },
    
    # Debug and diagnostic tests
    {
        'file': 'tests/test_simple_debug.py',
        'name': 'Debug Tests',
        'description': 'Diagnostic tests for debugging'
    },
    {
        'file': 'tests/test_debug_simple.py',
        'name': 'Simple Debug Test',
        'description': 'Simple diagnostic test for basic debugging'
    },
    {
        'file': 'tests/test_header_logging_demo.py',
        'name': 'Header Logging Demo',
        'description': 'Demonstrates header logging capabilities'
    },
    {
        'file': 'tests/debug_headers.py',
        'name': 'Header Debug Utility',
        'description': 'Debug utility for header inspection and testing'
    },
    {
        'file': 'tests/run_tests.py',
        'name': 'Legacy Test Runner',
        'description': 'Original test runner (legacy)'
    }
]

# Results tracking
results = []
total_tests = len(test_files)
passed_tests = 0
failed_tests = 0
skipped_tests = 0

def run_test(test_info):
    """Run a single test file and return results"""
    test_file = test_info['file']
    test_name = test_info['name']
    test_desc = test_info['description']
    
    print(f"🧪 Running: {test_name}")
    print(f"   File: {test_file}")
    print(f"   Description: {test_desc}")
    
    if not os.path.exists(test_file):
        print(f"   ⚠️  SKIPPED: File not found")
        return {'status': 'SKIPPED', 'reason': 'File not found'}
    
    try:
        start_time = time.time()
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=True, text=True, timeout=60)
        end_time = time.time()
        
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"   ✅ PASSED ({duration:.1f}s)")
            return {'status': 'PASSED', 'duration': duration, 'output': result.stdout}
        else:
            print(f"   ❌ FAILED ({duration:.1f}s)")
            print(f"   Error: {result.stderr[:200]}...")
            return {'status': 'FAILED', 'duration': duration, 'error': result.stderr, 'output': result.stdout}
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ TIMEOUT (60s)")
        return {'status': 'TIMEOUT', 'reason': 'Test exceeded 60 second timeout'}
    except Exception as e:
        print(f"   💥 ERROR: {e}")
        return {'status': 'ERROR', 'reason': str(e)}

# Run all tests
print("Starting test execution...")
print("-" * 60)

for i, test_info in enumerate(test_files, 1):
    print(f"\n[{i}/{total_tests}] ", end="")
    
    result = run_test(test_info)
    result.update(test_info)
    results.append(result)
    
    if result['status'] == 'PASSED':
        passed_tests += 1
    elif result['status'] == 'FAILED':
        failed_tests += 1
    elif result['status'] in ['SKIPPED', 'TIMEOUT', 'ERROR']:
        skipped_tests += 1
    
    # Small delay between tests
    time.sleep(0.5)

# Print final summary
print("\n" + "=" * 80)
print("TEST EXECUTION COMPLETE")
print("=" * 80)

print(f"\n📊 SUMMARY:")
print(f"   Total Tests:   {total_tests}")
print(f"   ✅ Passed:     {passed_tests}")
print(f"   ❌ Failed:     {failed_tests}")
print(f"   ⚠️  Skipped:    {skipped_tests}")

success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
print(f"   🎯 Success Rate: {success_rate:.1f}%")

# Detailed results
print(f"\n📋 DETAILED RESULTS:")
print("-" * 60)

for result in results:
    status_icon = {
        'PASSED': '✅',
        'FAILED': '❌', 
        'SKIPPED': '⚠️',
        'TIMEOUT': '⏰',
        'ERROR': '💥'
    }.get(result['status'], '❓')
    
    duration_str = f"({result.get('duration', 0):.1f}s)" if 'duration' in result else ""
    print(f"{status_icon} {result['name']} {duration_str}")
    
    if result['status'] == 'FAILED' and 'error' in result:
        # Show first line of error
        error_lines = result['error'].strip().split('\n')
        if error_lines:
            print(f"    Error: {error_lines[0]}")

# Final status
print(f"\n🏁 Test run completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if failed_tests == 0:
    print("🎉 All tests passed successfully!")
    exit_code = 0
else:
    print(f"⚠️  {failed_tests} test(s) failed. Check logs above for details.")
    exit_code = 1

print("=" * 80)
sys.exit(exit_code) 