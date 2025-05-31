#!/usr/bin/env python3
"""
Simple test script to verify module functionality
"""

try:
    from homie_proxy import HomieProxyServer, create_proxy_config, create_default_config
    print("✅ Module import successful")
    
    # Test 1: Create server with default config
    server = HomieProxyServer()
    print(f"✅ Default instances created: {server.list_instances()}")
    
    # Test 2: Add instance programmatically
    server.add_instance('test_api', {
        'restrict_out': 'external',
        'tokens': ['test-token-123'],
        'restrict_in_cidrs': []
    })
    print(f"✅ Added instance, total: {server.list_instances()}")
    
    # Test 3: Get instance config
    config = server.get_instance_config('test_api')
    print(f"✅ Instance config retrieved: {config}")
    
    # Test 4: Test helper functions
    default_config = create_default_config()
    print(f"✅ Default config created with {len(default_config['instances'])} instances")
    
    # Test 5: Create instances from dict
    test_config = {
        'web_scraper': {
            'restrict_out': 'external',
            'tokens': ['scraper-key'],
            'restrict_in_cidrs': []
        }
    }
    instances = create_proxy_config(test_config)
    print(f"✅ Created instances from dict: {list(instances.keys())}")
    
    print("\n🎉 All module tests passed!")
    
except Exception as e:
    print(f"❌ Module test failed: {e}")
    import traceback
    traceback.print_exc() 