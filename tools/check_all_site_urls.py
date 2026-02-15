#!/usr/bin/env python3
"""
Check all URLs across all HTML files on the site for safety.
"""

import re
import os
from pathlib import Path
from check_url_safety import URLSafetyChecker

def extract_urls_from_html(file_path):
    """Extract all URLs from an HTML file."""
    urls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Find all href attributes
            href_pattern = r'<a[^>]+href=["\'](https?://[^"\']+)["\']'
            urls.extend(re.findall(href_pattern, content))
            
            # Find all src attributes (images, scripts, iframes, etc.)
            src_pattern = r'<(?:img|script|iframe|source|video|audio)[^>]+src=["\'](https?://[^"\']+)["\']'
            urls.extend(re.findall(src_pattern, content))
            
            # Find any other http/https URLs that might be in content
            # (but not in comments or script blocks)
            url_pattern = r'https?://[^\s<>"\']+[^\s<>"\'.,;:!?)]'
            urls.extend(re.findall(url_pattern, content))
            
    except Exception as e:
        print(f"  ⚠️  Error reading {file_path}: {e}")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls

def main():
    # Find all HTML files
    workspace_root = Path(__file__).parent.parent
    html_files = sorted(workspace_root.glob('*.html'))
    
    print("=" * 80)
    print("COMPREHENSIVE SITE-WIDE URL SAFETY CHECK")
    print("=" * 80)
    print()
    
    checker = URLSafetyChecker()
    
    all_results = {
        'safe': [],
        'suspicious': [],
        'unsafe': []
    }
    
    file_results = {}
    
    # Check each HTML file
    for html_file in html_files:
        print(f"📄 Checking: {html_file.name}")
        urls = extract_urls_from_html(html_file)
        
        if not urls:
            print(f"   No URLs found\n")
            continue
        
        print(f"   Found {len(urls)} URL(s)")
        
        file_safe = []
        file_suspicious = []
        file_unsafe = []
        
        for url in urls:
            result = checker.check_url(url)
            
            if not result['safe']:
                # Unsafe - has errors
                file_unsafe.append((url, result))
                all_results['unsafe'].append((html_file.name, url, result))
            elif result['suspicious']:
                # Safe but suspicious - has warnings
                file_suspicious.append((url, result))
                all_results['suspicious'].append((html_file.name, url, result))
            else:
                # Safe - no issues
                file_safe.append((url, result))
                all_results['safe'].append((html_file.name, url, result))
        
        file_results[html_file.name] = {
            'safe': file_safe,
            'suspicious': file_suspicious,
            'unsafe': file_unsafe,
            'total': len(urls)
        }
        
        print(f"   ✅ Safe: {len(file_safe)}")
        if file_suspicious:
            print(f"   ⚠️  Suspicious: {len(file_suspicious)}")
        if file_unsafe:
            print(f"   ❌ Unsafe: {len(file_unsafe)}")
        print()
    
    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    total_urls = len(all_results['safe']) + len(all_results['suspicious']) + len(all_results['unsafe'])
    
    print(f"Total HTML files scanned: {len(html_files)}")
    print(f"Total URLs checked: {total_urls}")
    print()
    print(f"  ✅ Safe:        {len(all_results['safe'])} ({len(all_results['safe'])/total_urls*100:.1f}%)")
    print(f"  ⚠️  Suspicious:  {len(all_results['suspicious'])} ({len(all_results['suspicious'])/total_urls*100:.1f}%)")
    print(f"  ❌ Unsafe:      {len(all_results['unsafe'])} ({len(all_results['unsafe'])/total_urls*100:.1f}%)")
    print()
    
    # Detailed results by file
    if any(file_results[f]['suspicious'] or file_results[f]['unsafe'] for f in file_results):
        print("=" * 80)
        print("DETAILED RESULTS BY FILE")
        print("=" * 80)
        print()
        
        for filename in sorted(file_results.keys()):
            results = file_results[filename]
            
            if results['suspicious'] or results['unsafe']:
                print(f"📄 {filename}")
                print(f"   Total URLs: {results['total']}")
                print()
                
                if results['unsafe']:
                    print("   ❌ UNSAFE URLs:")
                    for url, result in results['unsafe']:
                        print(f"      • {url}")
                        for reason in result['errors']:
                            print(f"        - {reason}")
                    print()
                
                if results['suspicious']:
                    print("   ⚠️  SUSPICIOUS URLs:")
                    for url, result in results['suspicious']:
                        print(f"      • {url}")
                        for reason in result['warnings']:
                            print(f"        - {reason}")
                    print()
    
    # Print all suspicious URLs summary
    if all_results['suspicious']:
        print("=" * 80)
        print(f"⚠️  SUSPICIOUS URLS ({len(all_results['suspicious'])})")
        print("=" * 80)
        print()
        for filename, url, result in all_results['suspicious']:
            print(f"📄 {filename}")
            print(f"   {url}")
            for reason in result['warnings']:
                print(f"   - {reason}")
            print()
    
    # Print all unsafe URLs summary
    if all_results['unsafe']:
        print("=" * 80)
        print(f"❌ UNSAFE URLS ({len(all_results['unsafe'])})")
        print("=" * 80)
        print()
        for filename, url, result in all_results['unsafe']:
            print(f"📄 {filename}")
            print(f"   {url}")
            for reason in result['errors']:
                print(f"   - {reason}")
            print()
    
    print("=" * 80)
    
    # Exit with error code if unsafe URLs found
    if all_results['unsafe']:
        print("\n❌ FAILED: Unsafe URLs detected")
        return 1
    
    print("\n✅ PASSED: No unsafe URLs detected")
    return 0

if __name__ == '__main__':
    exit(main())
