#!/usr/bin/env python3
"""
Test script to verify package installation and module functionality.
Run after: pip install -e .
"""

import sys
import subprocess

def test_console_script():
    """Test that the console script is installed"""
    try:
        result = subprocess.run(['homie-proxy', '--help'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Console script 'homie-proxy' installed correctly")
            return True
        else:
            print(f"❌ Console script failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("❌ Console script 'homie-proxy' not found")
        return False
    except subprocess.TimeoutExpired:
        print("❌ Console script timed out")
        return False

def test_module_import():
    """Test that the module can be imported"""
    try:
        # Test basic imports
        from homie_proxy import HomieProxyServer, create_proxy_config, create_default_config
        print("✅ Module imports successful")
        
        # Test class instantiation
        server = HomieProxyServer()
        print(f"✅ Server created with instances: {server.list_instances()}")
        
        # Test helper functions
        config = create_default_config()
        print(f"✅ Default config created with {len(config['instances'])} instances")
        
        instances = create_proxy_config({
            'test': {
                'restrict_out': 'external',
                'tokens': ['test'],
                'restrict_in_cidrs': []
            }
        })
        print(f"✅ Instance creation successful: {list(instances.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Module import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_package_structure():
    """Test that package has proper structure"""
    try:
        import homie_proxy
        
        # Check __all__ exports
        if hasattr(homie_proxy, '__all__'):
            exports = homie_proxy.__all__
            print(f"✅ Module exports defined: {exports}")
            
            # Verify all exports are available
            for export in exports:
                if hasattr(homie_proxy, export):
                    print(f"  ✅ {export} available")
                else:
                    print(f"  ❌ {export} missing")
                    return False
        else:
            print("❌ __all__ exports not defined")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Package structure test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Homie Proxy Package Installation")
    print("=" * 50)
    
    tests = [
        ("Module Import", test_module_import),
        ("Package Structure", test_package_structure),
        ("Console Script", test_console_script),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- Testing {test_name} ---")
        if test_func():
            passed += 1
        
    print("\n" + "=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Package is ready for use.")
        print("\nYou can now:")
        print("  • Use as command: homie-proxy --help")
        print("  • Import in Python: from homie_proxy import HomieProxyServer")
        print("  • Run examples: python example_module_usage.py")
    else:
        print("❌ Some tests failed. Check the output above.")
        sys.exit(1)

if __name__ == '__main__':
    main() 