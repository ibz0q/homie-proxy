#!/usr/bin/env python3
import os
import subprocess
import sys

# Set environment variables
os.environ['PROXY_HOST'] = 'localhost'
os.environ['PROXY_PORT'] = '8123'
os.environ['PROXY_NAME'] = 'external-only-route'
os.environ['PROXY_TOKEN'] = '0061b276-ebab-4892-8c7b-13812084f5e9'

print("Running master test script...")
print(f"Host: {os.environ['PROXY_HOST']}")
print(f"Port: {os.environ['PROXY_PORT']}")
print(f"Name: {os.environ['PROXY_NAME']}")
print(f"Token: {os.environ['PROXY_TOKEN'][:8]}...")

# Run the master test script with --list-tests first
try:
    result = subprocess.run([
        sys.executable, '/config/run_all_tests.py', '--list-tests'
    ], capture_output=True, text=True, timeout=30)
    
    print("List tests result:")
    print("STDOUT:", result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    print("Return code:", result.returncode)
    
except Exception as e:
    print(f"Error running test script: {e}") 