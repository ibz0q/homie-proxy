#!/usr/bin/env python3
"""
Comprehensive Test Runner for Reverse Proxy
Runs all test scripts and provides a detailed summary
"""

import os
import subprocess
import sys
import time
import json
from datetime import datetime
import signal
import psutil

class TestRunner:
    def __init__(self):
        self.tests_dir = "tests"
        self.results = []
        self.server_process = None
        self.server_port = 8080
        
    def find_test_files(self):
        """Find all Python test files in the tests directory"""
        test_files = []
        if os.path.exists(self.tests_dir):
            for file in os.listdir(self.tests_dir):
                if file.endswith('.py') and (file.startswith('test_') or file.endswith('_test.py')):
                    test_files.append(os.path.join(self.tests_dir, file))
        
        # Sort tests by priority (put core functionality tests first)
        priority_order = [
            'test_host_header.py',
            'test_header_logging.py', 
            'test_tls_all.py',
            'test_cache_debug.py',
            'test_streaming.py',
            'test_real_video.py',
            'test_response_headers.py',
            'test_user_agent.py'
        ]
        
        sorted_tests = []
        for priority_test in priority_order:
            full_path = os.path.join(self.tests_dir, priority_test)
            if full_path in test_files:
                sorted_tests.append(full_path)
                test_files.remove(full_path)
        
        # Add remaining tests
        sorted_tests.extend(sorted(test_files))
        
        return sorted_tests
    
    def check_server_running(self):
        """Check if the proxy server is running"""
        try:
            import requests
            response = requests.get(f"http://localhost:{self.server_port}/default?token=test", timeout=2)
            return True
        except:
            return False
    
    def start_server(self):
        """Start the proxy server in background"""
        print("🚀 Starting reverse proxy server...")
        
        # Kill any existing server processes
        self.stop_existing_servers()
        
        try:
            # Start the server as a background process
            self.server_process = subprocess.Popen([
                sys.executable, "reverse_proxy.py",
                "--host", "0.0.0.0",
                "--port", str(self.server_port)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait a moment for server to start
            time.sleep(3)
            
            # Check if server is responding
            if self.check_server_running():
                print(f"✅ Server started successfully on port {self.server_port}")
                return True
            else:
                print("❌ Server failed to start or not responding")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start server: {e}")
            return False
    
    def stop_existing_servers(self):
        """Stop any existing Python processes running the proxy server"""
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if (cmdline and 'python' in cmdline[0].lower() and 
                        any('reverse_proxy.py' in arg for arg in cmdline)):
                        print(f"🛑 Stopping existing server process (PID: {proc.info['pid']})")
                        proc.kill()
                        proc.wait(timeout=5)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                    pass
        except ImportError:
            # psutil not available, try basic approach
            try:
                if os.name == 'nt':  # Windows
                    subprocess.run(['taskkill', '/F', '/IM', 'python.exe'], 
                                 capture_output=True, check=False)
                else:  # Unix/Linux
                    subprocess.run(['pkill', '-f', 'reverse_proxy.py'], 
                                 capture_output=True, check=False)
            except:
                pass
        
        time.sleep(2)  # Wait for processes to stop
    
    def stop_server(self):
        """Stop the proxy server"""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("🛑 Server stopped")
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                print("🛑 Server force killed")
            except:
                pass
    
    def run_test(self, test_file):
        """Run a single test file and capture results"""
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
            
            # Analyze the output to determine if test passed
            output = result.stdout
            error_output = result.stderr
            return_code = result.returncode
            
            # Check for common success/failure indicators
            success_indicators = ['✅', 'SUCCESS', 'PASSED', 'completed!', 'working correctly']
            failure_indicators = ['❌', 'ERROR', 'FAILED', 'failed:', 'Error:']
            
            success_count = sum(output.count(indicator) for indicator in success_indicators)
            failure_count = sum(output.count(indicator) for indicator in failure_indicators)
            
            # Determine overall status
            if return_code != 0:
                status = "FAILED"
            elif failure_count > success_count:
                status = "FAILED"  
            elif success_count > 0:
                status = "PASSED"
            else:
                status = "UNCLEAR"
            
            # Print test output
            if output:
                print(output)
            if error_output:
                print("STDERR:", error_output)
            
            # Store results
            test_result = {
                'name': test_name,
                'status': status,
                'duration': duration,
                'return_code': return_code,
                'success_count': success_count,
                'failure_count': failure_count,
                'output_preview': output[:200] + "..." if len(output) > 200 else output
            }
            
            self.results.append(test_result)
            
            print(f"\n📊 Test Result: {status} ({duration:.2f}s)")
            return test_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"⏰ Test timed out after 60 seconds")
            test_result = {
                'name': test_name,
                'status': 'TIMEOUT',
                'duration': duration,
                'return_code': -1,
                'success_count': 0,
                'failure_count': 1,
                'output_preview': 'Test timed out'
            }
            self.results.append(test_result)
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"💥 Test execution failed: {e}")
            test_result = {
                'name': test_name,
                'status': 'ERROR',
                'duration': duration,
                'return_code': -1,
                'success_count': 0,
                'failure_count': 1,
                'output_preview': str(e)
            }
            self.results.append(test_result)
            return test_result
    
    def print_summary(self):
        """Print a comprehensive test summary"""
        print("\n" + "="*80)
        print("📋 TEST SUMMARY REPORT")
        print("="*80)
        
        if not self.results:
            print("❌ No tests were executed")
            return
        
        # Count results by status
        passed = [r for r in self.results if r['status'] == 'PASSED']
        failed = [r for r in self.results if r['status'] == 'FAILED']
        errors = [r for r in self.results if r['status'] == 'ERROR']
        timeouts = [r for r in self.results if r['status'] == 'TIMEOUT']
        unclear = [r for r in self.results if r['status'] == 'UNCLEAR']
        
        total = len(self.results)
        total_duration = sum(r['duration'] for r in self.results)
        
        print(f"📊 Total Tests: {total}")
        print(f"✅ Passed: {len(passed)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"💥 Errors: {len(errors)}")
        print(f"⏰ Timeouts: {len(timeouts)}")
        print(f"❓ Unclear: {len(unclear)}")
        print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
        print(f"📅 Run Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Detailed results
        print(f"\n{'='*80}")
        print("📋 DETAILED RESULTS")
        print("="*80)
        
        for result in self.results:
            status_emoji = {
                'PASSED': '✅',
                'FAILED': '❌', 
                'ERROR': '💥',
                'TIMEOUT': '⏰',
                'UNCLEAR': '❓'
            }
            
            emoji = status_emoji.get(result['status'], '❓')
            print(f"{emoji} {result['name']:<35} {result['status']:<8} ({result['duration']:.2f}s)")
            
            if result['status'] in ['FAILED', 'ERROR']:
                print(f"   💬 {result['output_preview']}")
        
        # Failed tests details
        if failed or errors or timeouts:
            print(f"\n{'='*80}")
            print("❌ FAILED TESTS DETAILS")
            print("="*80)
            
            for result in failed + errors + timeouts:
                print(f"\n🔍 {result['name']}:")
                print(f"   Status: {result['status']}")
                print(f"   Return Code: {result['return_code']}")
                print(f"   Duration: {result['duration']:.2f}s")
                if result['success_count'] > 0:
                    print(f"   Success Indicators: {result['success_count']}")
                if result['failure_count'] > 0:
                    print(f"   Failure Indicators: {result['failure_count']}")
        
        # Success rate
        success_rate = (len(passed) / total * 100) if total > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Great job! Most tests are passing!")
        elif success_rate >= 60:
            print("👍 Good progress, but some tests need attention.")
        else:
            print("⚠️  Many tests are failing - check the proxy server and test environment.")
    
    def save_results(self):
        """Save test results to a JSON file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"test_results_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'total_tests': len(self.results),
                    'passed': len([r for r in self.results if r['status'] == 'PASSED']),
                    'failed': len([r for r in self.results if r['status'] == 'FAILED']),
                    'errors': len([r for r in self.results if r['status'] == 'ERROR']),
                    'results': self.results
                }, f, indent=2)
            
            print(f"💾 Test results saved to: {filename}")
        except Exception as e:
            print(f"⚠️  Could not save results: {e}")
    
    def run_all_tests(self):
        """Run all tests with server management"""
        print("🧪 Reverse Proxy Test Runner")
        print("="*80)
        
        # Find test files
        test_files = self.find_test_files()
        if not test_files:
            print("❌ No test files found in tests/ directory")
            return
        
        print(f"📁 Found {len(test_files)} test files")
        for test_file in test_files:
            print(f"  - {os.path.basename(test_file)}")
        
        # Start server
        if not self.start_server():
            print("❌ Cannot start server - tests cannot run")
            return
        
        try:
            # Run tests
            for test_file in test_files:
                self.run_test(test_file)
                time.sleep(1)  # Brief pause between tests
            
            # Print summary
            self.print_summary()
            self.save_results()
            
        finally:
            # Always stop server
            self.stop_server()

if __name__ == "__main__":
    runner = TestRunner()
    
    try:
        runner.run_all_tests()
    except KeyboardInterrupt:
        print("\n⚠️  Test run interrupted by user")
        runner.stop_server()
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        runner.stop_server()
        sys.exit(1) 