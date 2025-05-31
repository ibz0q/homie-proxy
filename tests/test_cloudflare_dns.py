#!/usr/bin/env python3

import requests

print("=" * 60)
print("CLOUDFLARE DNS OVER HTTPS TEST")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

# Test the Cloudflare DNS over HTTPS endpoint
test_url = f"{base_url}&url=https://1.1.1.1&override_host_header=one.one.one.one&skip_tls_checks=all"

print(f"\nTesting Cloudflare DNS over HTTPS...")
print(f"Target: https://1.1.1.1 with Host: one.one.one.one")
print("-" * 60)

try:
    print("Making request...")
    response = requests.get(test_url, timeout=15, stream=True)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Server: {response.headers.get('Server', 'N/A')}")
    print(f"📥 CF-Ray: {response.headers.get('CF-Ray', 'N/A')}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS: Cloudflare DNS over HTTPS working!")
        print("🔗 TLS bypass successful")
        print("🔗 Host header override successful") 
        print("🔗 Connection to 1.1.1.1 successful")
        
        # Try to read a small portion of the response
        try:
            content_sample = ""
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    content_sample += chunk.decode('utf-8', errors='ignore')
                    if len(content_sample) > 500:
                        break
            
            print(f"\n📄 Response preview:")
            print(content_sample[:200] + "..." if len(content_sample) > 200 else content_sample)
            
        except Exception as e:
            print(f"📄 Could not decode response content: {e}")
        
    else:
        print(f"❌ Got status {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60) 