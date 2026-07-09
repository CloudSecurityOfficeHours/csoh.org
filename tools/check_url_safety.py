#!/usr/bin/env python3
"""
URL Safety Checker for CSOH Chat Resources

Validates URLs before adding them to chat-resources.html by checking:
- URL format and structure
- Suspicious patterns (phishing indicators)
- Redirect resolution (follows redirects to check final destination)
- Domain reputation

Usage:
    python3 tools/check_url_safety.py <url>
    python3 tools/check_url_safety.py --batch urls.txt
    python3 tools/check_url_safety.py --interactive
    python3 tools/check_url_safety.py --no-resolve <url>
"""

import sys
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from typing import Dict, List, Optional, Tuple

# Suspicious patterns that might indicate malicious URLs
SUSPICIOUS_PATTERNS = [
    r'@',  # @ symbol in URL (phishing technique)
    r'\.tk$|\.ml$|\.ga$|\.cf$|\.gq$',  # Free/suspicious TLDs
    r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}',  # Raw IP addresses
    r'paypal|amazon|microsoft|google|apple.*login',  # Potential phishing
    r'secure.*account|verify.*account|suspended.*account',  # Common phishing phrases
    r'\.exe$|\.scr$|\.bat$|\.cmd$|\.vbs$',  # Executable files in URL
    r'-{10,}',  # Excessive dashes (obfuscation technique)
]

# Domains known to be URL shorteners/redirectors - checked by exact domain match
SHORTENER_DOMAINS = [
    'bit.ly', 'goo.gl', 'tinyurl.com', 'ow.ly', 't.co',
    'is.gd', 'buff.ly', 'rebrand.ly', 'cutt.ly', 'shorturl.at',
]

# Known malicious or spam domains (add to this list as needed)
BLOCKLIST = [
    'malicious-example.com',
    'spam-domain.tk',
    # Bot-detection redirect trap - legitimate sites 302 to this when they
    # see a non-browser User-Agent. Never a real destination.
    'survey-smiles.com',
]

# Whitelist of trusted domains (won't trigger warnings, skip redirect resolution)
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


def is_shortener_domain(url: str) -> bool:
    """Check if the URL's domain is a known URL shortener."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain == sd or domain.endswith('.' + sd) for sd in SHORTENER_DOMAINS)
    except Exception:
        return False


def resolve_url(url: str, timeout: int = 5) -> Tuple[str, Optional[str]]:
    """Follow redirects and return (final_url, error_or_none).

    Uses HEAD first; falls back to GET if HEAD gets 405 Method Not Allowed.

    SECURITY: only http/https schemes are accepted. urllib.request.urlopen
    will happily handle file://, ftp://, gopher://, etc., which would let a
    malicious URL in HTML trigger SSRF / local-file-read on the CI runner
    (and potentially leak content into a PR comment via the safety report).
    Reject anything that isn't a real web URL before issuing any request.
    """
    try:
        scheme = urlparse(url).scheme.lower()
    except Exception:
        return url, "unparseable URL"
    if scheme not in {"http", "https"}:
        return url, f"unsupported scheme: {scheme or '(none)'}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                final = resp.url
                if final and final != url:
                    return final, None
                return url, None
        except urllib.error.HTTPError as e:
            if method == "HEAD" and (e.code == 405 or e.code >= 400):
                continue  # HEAD is unreliable on many hosts; try GET
            # 308 Permanent Redirect - follow it via the Location header
            if e.code == 308:
                location = e.headers.get("Location")
                if location:
                    return location, None
            return url, f"HTTP {e.code}"
        except Exception as e:
            return url, str(e)
    return url, None


def resolve_urls_concurrent(
    urls: List[str],
    max_workers: int = 10,
    timeout: int = 5,
    skip_domains: Optional[List[str]] = None,
) -> Dict[str, Tuple[str, Optional[str]]]:
    """Resolve multiple URLs concurrently, returning {original: (resolved, error)}.

    URLs whose domain is in skip_domains are returned unchanged without
    making HTTP requests.
    """
    if skip_domains is None:
        skip_domains = WHITELIST

    results: Dict[str, Tuple[str, Optional[str]]] = {}
    to_resolve: List[str] = []

    for url in urls:
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            results[url] = (url, None)
            continue

        if any(wd in domain for wd in skip_domains):
            results[url] = (url, None)
        else:
            to_resolve.append(url)

    if not to_resolve:
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(resolve_url, url, timeout): url
            for url in to_resolve
        }
        for future in as_completed(future_to_url):
            original = future_to_url[future]
            try:
                resolved, error = future.result()
                results[original] = (resolved, error)
            except Exception as e:
                results[original] = (original, str(e))

    return results


class URLSafetyChecker:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def check_url(self, url: str, resolved_url: Optional[str] = None,
                  resolve_error: Optional[str] = None) -> Dict:
        """
        Check a URL for safety issues.

        If resolved_url is provided, pattern/blocklist checks run against the
        resolved URL.  Cross-domain redirects are flagged as warnings.
        """
        self.warnings = []
        self.errors = []

        # Basic validation
        if not url or not isinstance(url, str):
            self.errors.append("Invalid URL: empty or not a string")
            return self._result(False, url, resolved_url)

        url = url.strip()

        # Determine which URL to check for patterns
        check_target = resolved_url if resolved_url and resolved_url != url else url

        # Flag cross-domain redirects
        if resolved_url and resolved_url != url:
            try:
                orig_domain = urlparse(url).netloc.lower()
                resolved_domain = urlparse(resolved_url).netloc.lower()
                if orig_domain != resolved_domain:
                    self.warnings.append(
                        f"Redirects to different domain: {orig_domain} -> {resolved_domain}"
                    )
            except Exception:
                pass

        # Note resolution failures (warning, not error - graceful fallback)
        if resolve_error:
            self.warnings.append(f"Could not resolve URL: {resolve_error}")

        # Parse the target URL
        try:
            parsed = urlparse(check_target)
        except Exception as e:
            self.errors.append(f"Failed to parse URL: {e}")
            return self._result(False, url, resolved_url)

        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            self.errors.append(f"Invalid scheme: {parsed.scheme} (only http/https allowed)")
            return self._result(False, url, resolved_url)

        if parsed.scheme == 'http':
            self.warnings.append("Uses HTTP (not HTTPS) - may be insecure")

        # Check domain
        domain = parsed.netloc.lower()
        if not domain:
            self.errors.append("No domain found in URL")
            return self._result(False, url, resolved_url)

        # Check against blocklist
        for blocked in BLOCKLIST:
            if blocked in domain:
                self.errors.append(f"Domain '{domain}' is on blocklist")
                return self._result(False, url, resolved_url)

        # Check if whitelisted (skip pattern checks)
        is_whitelisted = any(whitelist in domain for whitelist in WHITELIST)

        if not is_whitelisted:
            # Check if it's a URL shortener (exact domain match)
            if is_shortener_domain(check_target):
                self.warnings.append(f"URL shortener domain: {domain}")

            # Check suspicious patterns
            for pattern in SUSPICIOUS_PATTERNS:
                if re.search(pattern, check_target, re.IGNORECASE):
                    self.warnings.append(f"Suspicious pattern detected: {pattern}")

            # Check domain length (very long domains can be suspicious)
            if len(domain) > 50:
                self.warnings.append(f"Unusually long domain: {len(domain)} characters")

            # Check for excessive subdomains
            parts = domain.split('.')
            if len(parts) > 5:
                self.warnings.append(f"Excessive subdomains: {len(parts)} levels")

        # No critical errors
        return self._result(True, url, resolved_url)

    def _result(self, safe: bool, original_url: Optional[str] = None,
                resolved_url: Optional[str] = None) -> Dict:
        redirected = (resolved_url is not None and original_url is not None
                      and resolved_url != original_url)
        return {
            'safe': safe and len(self.errors) == 0,
            'warnings': self.warnings,
            'errors': self.errors,
            'suspicious': len(self.warnings) > 0,
            'redirected': redirected,
            'resolved_url': resolved_url if redirected else None,
        }

    def check_batch(self, urls: List[str], resolve: bool = True) -> List[Tuple[str, Dict]]:
        """Check multiple URLs, optionally resolving redirects first."""
        results = []

        if resolve:
            unique_urls = list(dict.fromkeys(urls))
            resolution_map = resolve_urls_concurrent(unique_urls)

            for url in urls:
                resolved, error = resolution_map.get(url, (url, None))
                result = self.check_url(url, resolved_url=resolved, resolve_error=error)
                results.append((url, result))
        else:
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

    if result.get('redirected') and result.get('resolved_url'):
        print(f"  -> Resolved to: {result['resolved_url']}")

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

            resolved, error = resolve_url(url)
            result = checker.check_url(url, resolved_url=resolved, resolve_error=error)
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
        print("  No resolution: python3 tools/check_url_safety.py --no-resolve <url>")
        sys.exit(1)

    resolve = '--no-resolve' not in sys.argv
    args = [a for a in sys.argv[1:] if a != '--no-resolve']

    checker = URLSafetyChecker()

    # Interactive mode
    if args[0] == '--interactive':
        interactive_mode()
        return

    # Batch mode
    if args[0] == '--batch':
        if len(args) < 2:
            print("Error: --batch requires a filename")
            sys.exit(1)

        filename = args[1]
        try:
            with open(filename, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
            sys.exit(1)

        results = checker.check_batch(urls, resolve=resolve)

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
        url = args[0]
        if resolve:
            resolved, error = resolve_url(url)
        else:
            resolved, error = url, None
        result = checker.check_url(url, resolved_url=resolved, resolve_error=error)
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
