#!/usr/bin/env python3
"""
URL Safety Checker for CSOH Chat Resources

Validates URLs before adding them to chat-resources.html by checking:
- URL format and structure
- Suspicious patterns (phishing indicators)
- Optional: Google Safe Browsing API / VirusTotal API
- Domain reputation

Usage:
    python3 tools/check_url_safety.py <url>
    python3 tools/check_url_safety.py --batch urls.txt
    python3 tools/check_url_safety.py --interactive
"""

import sys
import re
from urllib.parse import urlparse
import json
from typing import Dict, List, Tuple

# Suspicious patterns that might indicate malicious URLs
SUSPICIOUS_PATTERNS = [
    r'bit\.ly|goo\.gl|tinyurl\.com|ow\.ly|t\.co',  # URL shorteners (not inherently bad, but risky)
    r'@',  # @ symbol in URL (phishing technique)
    r'\.tk$|\.ml$|\.ga$|\.cf$|\.gq$',  # Free/suspicious TLDs
    r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # Raw IP addresses
    r'paypal|amazon|microsoft|google|apple.*login',  # Potential phishing
    r'secure.*account|verify.*account|suspended.*account',  # Common phishing phrases
    r'exe$|\.scr$|\.bat$|\.cmd$|\.vbs$',  # Executable files in URL
    r'-{10,}',  # Excessive dashes (obfuscation technique)
]

# Known malicious or spam domains (add to this list as needed)
BLOCKLIST = [
    'malicious-example.com',
    'spam-domain.tk',
    # Add known bad domains here
]

# Whitelist of trusted domains (won't trigger warnings)
WHITELIST = [
    'github.com',
    'youtube.com',
    'wiz.io',
    'aws.amazon.com',
    'docs.aws.amazon.com',
    'owasp.org',
    'cisa.gov',
    'nist.gov',
    'csoh.org',
    'microsoft.com',
    'google.com',
    'cloudflare.com',
    'wikipedia.org',
]


class URLSafetyChecker:
    def __init__(self):
        self.warnings = []
        self.errors = []
        
    def check_url(self, url: str) -> Dict:
        """
        Check a URL for safety issues.
        Returns dict with 'safe', 'warnings', 'errors', 'details'
        """
        self.warnings = []
        self.errors = []
        
        # Basic validation
        if not url or not isinstance(url, str):
            self.errors.append("Invalid URL: empty or not a string")
            return self._result(False)
            
        url = url.strip()
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            self.errors.append(f"Failed to parse URL: {e}")
            return self._result(False)
            
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            self.errors.append(f"Invalid scheme: {parsed.scheme} (only http/https allowed)")
            return self._result(False)
        
        if parsed.scheme == 'http':
            self.warnings.append("Uses HTTP (not HTTPS) - may be insecure")
            
        # Check domain
        domain = parsed.netloc.lower()
        if not domain:
            self.errors.append("No domain found in URL")
            return self._result(False)
            
        # Check against blocklist
        for blocked in BLOCKLIST:
            if blocked in domain:
                self.errors.append(f"Domain '{domain}' is on blocklist")
                return self._result(False)
        
        # Check if whitelisted (skip pattern checks)
        is_whitelisted = any(whitelist in domain for whitelist in WHITELIST)
        
        if not is_whitelisted:
            # Check suspicious patterns
            for pattern in SUSPICIOUS_PATTERNS:
                if re.search(pattern, url, re.IGNORECASE):
                    self.warnings.append(f"Suspicious pattern detected: {pattern}")
            
            # Check domain length (very long domains can be suspicious)
            if len(domain) > 50:
                self.warnings.append(f"Unusually long domain: {len(domain)} characters")
            
            # Check for excessive subdomains
            parts = domain.split('.')
            if len(parts) > 5:
                self.warnings.append(f"Excessive subdomains: {len(parts)} levels")
        
        # No critical errors
        return self._result(True)
    
    def _result(self, safe: bool) -> Dict:
        return {
            'safe': safe and len(self.errors) == 0,
            'warnings': self.warnings,
            'errors': self.errors,
            'suspicious': len(self.warnings) > 0,
        }
    
    def check_batch(self, urls: List[str]) -> List[Tuple[str, Dict]]:
        """Check multiple URLs and return results"""
        results = []
        for url in urls:
            result = self.check_url(url)
            results.append((url, result))
        return results


def print_result(url: str, result: Dict, verbose: bool = True):
    """Pretty print check result"""
    status = "✅ SAFE" if result['safe'] else "❌ UNSAFE"
    if result['suspicious'] and result['safe']:
        status = "⚠️  SUSPICIOUS (but not blocked)"
    
    print(f"\n{status}: {url}")
    
    if result['errors']:
        print("  ERRORS:")
        for error in result['errors']:
            print(f"    • {error}")
    
    if result['warnings'] and verbose:
        print("  WARNINGS:")
        for warning in result['warnings']:
            print(f"    • {warning}")


def interactive_mode():
    """Interactive mode for checking URLs"""
    print("=" * 60)
    print("CSOH URL Safety Checker - Interactive Mode")
    print("=" * 60)
    print("Enter URLs to check (one per line)")
    print("Type 'quit' or press Ctrl+C to exit")
    print("=" * 60)
    
    checker = URLSafetyChecker()
    
    try:
        while True:
            url = input("\nURL: ").strip()
            if url.lower() in ['quit', 'exit', 'q']:
                break
            if not url:
                continue
                
            result = checker.check_url(url)
            print_result(url, result)
            
            if not result['safe']:
                print("\n⛔ This URL should NOT be added to chat-resources.html")
            elif result['suspicious']:
                print("\n⚠️  Review this URL carefully before adding")
            else:
                print("\n✅ This URL appears safe to add")
                
    except KeyboardInterrupt:
        print("\n\nExiting...")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Single URL:    python3 tools/check_url_safety.py <url>")
        print("  Batch file:    python3 tools/check_url_safety.py --batch urls.txt")
        print("  Interactive:   python3 tools/check_url_safety.py --interactive")
        sys.exit(1)
    
    checker = URLSafetyChecker()
    
    # Interactive mode
    if sys.argv[1] == '--interactive':
        interactive_mode()
        return
    
    # Batch mode
    if sys.argv[1] == '--batch':
        if len(sys.argv) < 3:
            print("Error: --batch requires a filename")
            sys.exit(1)
        
        filename = sys.argv[2]
        try:
            with open(filename, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
            sys.exit(1)
        
        results = checker.check_batch(urls)
        
        safe_count = sum(1 for _, r in results if r['safe'])
        unsafe_count = sum(1 for _, r in results if not r['safe'])
        suspicious_count = sum(1 for _, r in results if r['suspicious'] and r['safe'])
        
        print(f"\n{'=' * 60}")
        print(f"Checked {len(urls)} URLs")
        print(f"  ✅ Safe: {safe_count}")
        print(f"  ⚠️  Suspicious: {suspicious_count}")
        print(f"  ❌ Unsafe: {unsafe_count}")
        print(f"{'=' * 60}\n")
        
        for url, result in results:
            print_result(url, result, verbose=False)
        
        if unsafe_count > 0:
            print(f"\n⛔ {unsafe_count} URL(s) should NOT be added")
            sys.exit(1)
        
    # Single URL mode
    else:
        url = sys.argv[1]
        result = checker.check_url(url)
        print_result(url, result)
        
        if not result['safe']:
            print("\n⛔ This URL should NOT be added to chat-resources.html")
            sys.exit(1)
        elif result['suspicious']:
            print("\n⚠️  Review this URL carefully before adding")
        else:
            print("\n✅ This URL appears safe to add")


if __name__ == '__main__':
    main()
