#!/usr/bin/env python3
"""
Extract and check all URLs from chat-resources.html
"""
import re
import sys
sys.path.insert(0, 'tools')
from check_url_safety import URLSafetyChecker

# Read chat-resources.html
with open('chat-resources.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all URLs from <a href="..." class="card-link">
pattern = r'<a href="([^"]+)" class="card-link"'
urls = re.findall(pattern, content)

print(f"Found {len(urls)} URLs in chat-resources.html\n")
print("Running safety checks...\n")
print("=" * 70)

checker = URLSafetyChecker()
results = checker.check_batch(urls)

# Categorize results
safe = []
suspicious = []
unsafe = []

for url, result in results:
    if not result['safe']:
        unsafe.append((url, result))
    elif result['suspicious']:
        suspicious.append((url, result))
    else:
        safe.append((url, result))

# Print summary
print(f"\n{'=' * 70}")
print(f"SUMMARY")
print(f"{'=' * 70}")
print(f"Total URLs checked: {len(urls)}")
print(f"  ✅ Safe:        {len(safe)}")
print(f"  ⚠️  Suspicious:  {len(suspicious)}")
print(f"  ❌ Unsafe:      {len(unsafe)}")
print(f"{'=' * 70}\n")

# Show unsafe URLs
if unsafe:
    print(f"\n❌ UNSAFE URLS ({len(unsafe)}):")
    print("=" * 70)
    for url, result in unsafe:
        print(f"\n🚫 {url}")
        for error in result['errors']:
            print(f"   ERROR: {error}")

# Show suspicious URLs
if suspicious:
    print(f"\n⚠️  SUSPICIOUS URLS ({len(suspicious)}):")
    print("=" * 70)
    for url, result in suspicious:
        print(f"\n⚠️  {url}")
        for warning in result['warnings']:
            print(f"   • {warning}")

# Show count of safe URLs (don't list them all)
if safe:
    print(f"\n✅ SAFE URLS: {len(safe)} (not listed)")

# Exit with error if any unsafe URLs found
if unsafe:
    print(f"\n{'=' * 70}")
    print(f"⛔ ACTION REQUIRED: {len(unsafe)} unsafe URL(s) found!")
    print("=" * 70)
    sys.exit(1)

if suspicious:
    print(f"\n{'=' * 70}")
    print(f"⚠️  REVIEW RECOMMENDED: {len(suspicious)} suspicious URL(s) found")
    print("=" * 70)

print("\n✅ All URLs passed safety checks (some may need review)")
