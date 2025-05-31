#!/usr/bin/env python3
"""
Example Usage of Homie Proxy as a Module

This script demonstrates various ways to use the homie proxy server
as an importable Python module in your own applications.
"""

import threading
import time
import requests
from homie_proxy import HomieProxyServer, ProxyInstance, create_proxy_config

def example_1_file_based():
    """Example 1: Using existing configuration file"""
    print("=== Example 1: File-based Configuration ===")
    
    # Create server with existing config file
    server = HomieProxyServer('proxy_config.json')
    
    # List configured instances
    print(f"Configured instances: {server.list_instances()}")
    
    # Get configuration for specific instance
    config = server.get_instance_config('default')
    print(f"Default instance config: {config}")

def example_2_programmatic():
    """Example 2: Programmatic configuration"""
    print("\n=== Example 2: Programmatic Configuration ===")
    
    # Create server without any config file
    server = HomieProxyServer()
    
    # Add instances programmatically
    server.add_instance('api_proxy', {
        'restrict_out': 'external',
        'tokens': ['my-api-key-123'],
        'restrict_in_cidrs': ['192.168.1.0/24', '10.0.0.0/8']
    })
    
    server.add_instance('internal_dev', {
        'restrict_out': 'internal',
        'tokens': [],  # No authentication required
        'restrict_in_cidrs': []
    })
    
    server.add_instance('restricted_service', {
        'restrict_out': 'both',
        'restrict_out_cidrs': ['8.8.8.0/24', '1.1.1.0/24'],
        'tokens': ['service-token'],
        'restrict_in_cidrs': []
    })
    
    print(f"Created instances: {server.list_instances()}")
    
    # Modify instances
    server.remove_instance('internal_dev')
    print(f"After removal: {server.list_instances()}")

def example_3_prebuilt_instances():
    """Example 3: Using pre-built instance configurations"""
    print("\n=== Example 3: Pre-built Instance Configuration ===")
    
    # Create instances using helper function
    instances_config = {
        'web_scraper': {
            'restrict_out': 'external',
            'tokens': ['scraper-token-456'],
            'restrict_in_cidrs': []
        },
        'api_gateway': {
            'restrict_out': 'both',
            'restrict_out_cidrs': ['192.168.0.0/16', '10.0.0.0/8'],
            'tokens': ['gateway-key'],
            'restrict_in_cidrs': ['172.16.0.0/12']
        }
    }
    
    instances = create_proxy_config(instances_config)
    server = HomieProxyServer(instances=instances)
    
    print(f"Pre-built instances: {server.list_instances()}")

def example_4_embedded_server():
    """Example 4: Running proxy server in a thread"""
    print("\n=== Example 4: Embedded Server in Thread ===")
    
    # Create a simple proxy server
    server = HomieProxyServer()
    server.add_instance('test', {
        'restrict_out': 'both',
        'tokens': ['test-token'],
        'restrict_in_cidrs': []
    })
    
    # Run server in background thread
    def run_server():
        try:
            server.run(host='localhost', port=8081)
        except Exception as e:
            print(f"Server error: {e}")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(2)
    
    # Test the proxy
    try:
        response = requests.get(
            'http://localhost:8081/test',
            params={
                'url': 'https://httpbin.org/get',
                'token': 'test-token'
            },
            timeout=5
        )
        print(f"Proxy test successful: {response.status_code}")
        result = response.json()
        print(f"Response origin: {result.get('origin', 'unknown')}")
    except Exception as e:
        print(f"Proxy test failed: {e}")
    
    print("Server running in background thread...")

def example_5_custom_app_integration():
    """Example 5: Integration with custom application"""
    print("\n=== Example 5: Custom Application Integration ===")
    
    class MyApplication:
        def __init__(self):
            self.proxy_server = None
            self.setup_proxy()
        
        def setup_proxy(self):
            """Setup proxy for the application"""
            self.proxy_server = HomieProxyServer()
            
            # Configure proxy instances based on app needs
            self.proxy_server.add_instance('user_requests', {
                'restrict_out': 'external',
                'tokens': ['user-session-token'],
                'restrict_in_cidrs': []
            })
            
            self.proxy_server.add_instance('admin_requests', {
                'restrict_out': 'both',
                'tokens': ['admin-token-xyz'],
                'restrict_in_cidrs': ['192.168.1.0/24']  # Admin network only
            })
        
        def start_proxy(self, port=8082):
            """Start the integrated proxy server"""
            if self.proxy_server:
                print(f"Starting application proxy on port {port}")
                print(f"Available endpoints: {self.proxy_server.list_instances()}")
                # In real app, you'd run this in a separate thread
                # self.proxy_server.run(host='localhost', port=port)
        
        def get_proxy_stats(self):
            """Get proxy configuration stats"""
            if self.proxy_server:
                return {
                    'instances': self.proxy_server.list_instances(),
                    'instance_configs': {
                        name: self.proxy_server.get_instance_config(name)
                        for name in self.proxy_server.list_instances()
                    }
                }
            return {}
    
    # Create and use the application
    app = MyApplication()
    stats = app.get_proxy_stats()
    print(f"Application proxy stats: {stats}")

if __name__ == '__main__':
    print("Homie Proxy Module Usage Examples")
    print("=" * 50)
    
    # Run all examples
    try:
        example_1_file_based()
        example_2_programmatic()
        example_3_prebuilt_instances()
        example_4_embedded_server()
        example_5_custom_app_integration()
        
        print("\n" + "=" * 50)
        print("All examples completed successfully!")
        print("The embedded server (Example 4) is still running in the background.")
        print("You can test it with:")
        print("curl 'http://localhost:8081/test?url=https://httpbin.org/get&token=test-token'")
        
        # Keep the embedded server running for testing
        input("\nPress Enter to exit and stop the embedded server...")
        
    except Exception as e:
        print(f"Example error: {e}")
        import traceback
        traceback.print_exc() 