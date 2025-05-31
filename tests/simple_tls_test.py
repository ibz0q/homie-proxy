#!/usr/bin/env python3

import ssl
import socket
import sys

def test_tls_logging(hostname, port=443):
    """Test the TLS certificate logging function directly"""
    try:
        print(f"🔒 TLS Certificate Info for {hostname}:{port}")
        print("-" * 50)
        
        # Create SSL context for certificate inspection
        context = ssl.create_default_context()
        
        # Connect and get certificate
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                cipher = ssock.cipher()
                version = ssock.version()
                
                if cert:
                    # Basic certificate info
                    subject = dict(x[0] for x in cert.get('subject', []))
                    issuer = dict(x[0] for x in cert.get('issuer', []))
                    
                    print(f"📋 Subject: {subject.get('commonName', 'N/A')}")
                    print(f"🏢 Organization: {subject.get('organizationName', 'N/A')}")
                    print(f"🌍 Country: {subject.get('countryName', 'N/A')}")
                    print(f"📋 Issuer: {issuer.get('commonName', 'N/A')}")
                    print(f"🏢 Issuer Org: {issuer.get('organizationName', 'N/A')}")
                    
                    # Validity dates
                    not_before = cert.get('notBefore', 'N/A')
                    not_after = cert.get('notAfter', 'N/A')
                    print(f"📅 Valid From: {not_before}")
                    print(f"📅 Valid Until: {not_after}")
                    
                    # Subject Alternative Names
                    san_list = []
                    for ext in cert.get('subjectAltName', []):
                        if ext[0] == 'DNS':
                            san_list.append(ext[1])
                    if san_list:
                        print(f"🌐 Alt Names: {', '.join(san_list[:5])}{'...' if len(san_list) > 5 else ''}")
                    
                    # Serial number and fingerprint
                    serial = cert.get('serialNumber', 'N/A')
                    print(f"🔢 Serial: {serial}")
                    
                    # Certificate version
                    version_num = cert.get('version', 'N/A')
                    print(f"📋 Version: {version_num}")
                
                # TLS connection info
                print(f"🔐 TLS Version: {version}")
                if cipher:
                    print(f"🔐 Cipher Suite: {cipher[0]}")
                    print(f"🔐 TLS Protocol: {cipher[1]}")
                    print(f"🔐 Key Bits: {cipher[2]}")
                
                print("-" * 50)
                
    except Exception as e:
        print(f"❌ TLS Certificate inspection failed for {hostname}:{port}")
        print(f"   Error: {e}")
        print("-" * 50)

if __name__ == "__main__":
    print("=" * 60)
    print("TLS CERTIFICATE INSPECTOR - STANDALONE TEST")
    print("=" * 60)
    
    # Test sites
    test_sites = [
        ("httpbin.org", 443),
        ("github.com", 443),
        ("google.com", 443),
    ]
    
    for hostname, port in test_sites:
        print(f"\n🧪 Testing {hostname}:{port}")
        test_tls_logging(hostname, port)
    
    print("✅ TLS certificate inspection test completed!") 