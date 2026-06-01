#!/usr/bin/env python3
"""
Interactive CTF Submission Tool for CSOH.org

Adds a new CTF challenge card to ctfs.html with:
- Interactive prompts for all required information
- Automatic URL safety validation
- HTML generation matching the ctfs.html card format
- Optional preview image generation
- Git branch creation and commit

Usage:
    python3 tools/submit_ctf.py
"""

import sys
import re
import subprocess
from pathlib import Path
from check_url_safety import URLSafetyChecker

# Section IDs in ctfs.html - each maps to a section heading on the page
SECTIONS = {
    '1': ('wiz-standalone', 'Wiz Standalone Challenges (always-available)'),
    '2': ('aws-ctfs', 'AWS CTFs'),
    '3': ('azure-ctfs', 'Azure CTFs'),
    '4': ('gcp-ctfs', 'GCP CTFs'),
    '5': ('kubernetes-ctfs', 'Kubernetes CTFs'),
    '6': ('multi-cloud-ctfs', 'Multi-Cloud CTFs'),
    '7': ('specialty-ctfs', 'AI, Secrets, and CI/CD CTFs'),
}

# Tags grouped for selection
CLOUD_TAGS = ['AWS', 'Azure', 'GCP', 'Kubernetes', 'Multi-Cloud']
FOCUS_TAGS = [
    'IAM', 'Containers', 'Serverless', 'Recon', 'Incident Response',
    'Reverse Engineering', 'IaC', 'Secrets Management', 'CI/CD', 'AI/ML',
    'Cloud Security',
]

def print_header(text):
    print(f"\n{'='*70}\n  {text}\n{'='*70}\n")

def print_section(text):
    print(f"\n{'-'*70}\n  {text}\n{'-'*70}\n")

def get_input(prompt, required=True):
    while True:
        value = input(f"{prompt}: ").strip()
        if not value and required:
            print("❌ This field is required.\n")
            continue
        return value

def select_from_list(prompt, options):
    print(f"\n{prompt}")
    for key, (_, label) in options.items():
        print(f"  {key}. {label}")
    while True:
        sel = input("\n  Your selection: ").strip()
        if sel in options:
            return options[sel]
        print(f"  ❌ Invalid selection. Choose from {', '.join(options.keys())}\n")

def select_tags():
    """Interactive tag selection - CTF-tuned."""
    print("\n📋 Select relevant tags (CTF tag is added automatically)\n")
    print("  Cloud / Platform:")
    for i, t in enumerate(CLOUD_TAGS, 1):
        print(f"    {i}. {t}")
    print("\n  Focus Area:")
    for i, t in enumerate(FOCUS_TAGS, len(CLOUD_TAGS) + 1):
        print(f"    {i}. {t}")

    all_tags = CLOUD_TAGS + FOCUS_TAGS
    print("\n  Enter tag numbers separated by commas (e.g., 1,7). Recommended: 1-3.")
    while True:
        sel = input("  Your selection: ").strip()
        if not sel:
            print("  ❌ Please select at least one tag.\n")
            continue
        try:
            idxs = [int(s.strip()) - 1 for s in sel.split(',')]
            chosen = [all_tags[i] for i in idxs if 0 <= i < len(all_tags)]
            if chosen:
                # CTF tag is always first
                return ['CTF'] + chosen
            print("  ❌ No valid tags selected.\n")
        except (ValueError, IndexError):
            print("  ❌ Invalid input. Use numbers separated by commas.\n")

def validate_url(url):
    if not url.startswith(('http://', 'https://')):
        return False, {'errors': ['URL must start with http:// or https://']}
    checker = URLSafetyChecker()
    result = checker.check_url(url)
    return result['safe'], result

def generate_image_filename(url):
    """Match generate_preview.py's filename convention."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    path = parsed.path.strip('/').replace('/', '-')
    filename = f"{domain}-{path}" if path else domain
    filename = filename.lower()
    filename = ''.join(c if c.isalnum() or c in ['-', '_'] else '-' for c in filename)
    return filename[:100] + '.jpg'

def create_ctf_card_html(name, url, description, tags, tooltip):
    """Generate the card HTML matching ctfs.html card format."""
    # CTF tag first (with special ctf class), other tags plain
    tag_html_parts = []
    for t in tags:
        if t == 'CTF':
            tag_html_parts.append('<span class="tag ctf">CTF</span>')
        elif t == 'AI/ML':
            tag_html_parts.append('<span class="tag ai-security">AI/ML</span>')
        else:
            tag_html_parts.append(f'<span class="tag">{t}</span>')
    tags_html = '\n                            '.join(tag_html_parts)

    escaped_tooltip = tooltip.replace('&', '&amp;').replace('"', '&quot;') if tooltip else ''
    tooltip_attr = f'\n                        data-tooltip="{escaped_tooltip}"' if tooltip else ''

    img_filename = generate_image_filename(url)

    return f'''<a href="{url}" class="card-link" target="_blank" rel="noopener noreferrer">
                    <div class="resource-card"{tooltip_attr}>
                        <img src="img/previews/{img_filename}" alt="{name} preview" class="resource-preview" loading="lazy" decoding="async" onerror="this.style.display='none'">
                        <h3>{name}</h3>
                        <p>{description}</p>
                        <div class="resource-tags">
                            {tags_html}
                        </div>
                    </div>
                </a>'''

def insert_card_into_section(html_content, section_id, card_html):
    """Insert a new card before the closing </div> of the section's resource-grid."""
    # Locate the section by id
    section_start_pattern = rf'<section[^>]+id="{re.escape(section_id)}"[^>]*>'
    section_match = re.search(section_start_pattern, html_content)
    if not section_match:
        return None, f'Section id "{section_id}" not found in ctfs.html'

    section_start = section_match.start()
    # Find the closing </section>
    section_end_match = re.search(r'</section>', html_content[section_start:])
    if not section_end_match:
        return None, 'Closing </section> not found'
    section_end = section_start + section_end_match.start()

    section_html = html_content[section_start:section_end]
    # Find the last </a> (last card in the resource-grid) inside the section
    last_a = section_html.rfind('</a>')
    if last_a == -1:
        return None, 'No existing card found in section - cannot determine insertion point'

    insertion_point = section_start + last_a + len('</a>')
    new_html = (html_content[:insertion_point]
                + card_html
                + html_content[insertion_point:])
    return new_html, None

def git_command(args, capture_output=True):
    try:
        result = subprocess.run(['git'] + args, capture_output=capture_output,
                                text=True, check=True)
        return True, result.stdout.strip() if capture_output else ''
    except subprocess.CalledProcessError as e:
        return False, e.stderr if capture_output else str(e)

def check_git_status():
    success, output = git_command(['status', '--porcelain'])
    if not success:
        return False, 'Not in a git repository'
    if output:
        return False, 'Working directory has uncommitted changes. Commit or stash first.'
    return True, ''

def create_branch_and_commit(name):
    branch = 'add-ctf-' + re.sub(r'[^a-z0-9]+', '-', name.lower())[:40]
    print(f"\n📝 Creating git branch: {branch}")
    success, out = git_command(['checkout', '-b', branch])
    if not success:
        return False, f"Failed to create branch: {out}"
    success, out = git_command(['add', 'ctfs.html'])
    if not success:
        return False, f"Failed to stage: {out}"
    success, out = git_command(['commit', '-m', f'Add {name} to CTFs'])
    if not success:
        return False, f"Failed to commit: {out}"
    return True, branch

def main():
    print_header("🎯 CSOH CTF Submission Tool")
    print("Adds a new CTF challenge card to ctfs.html.\n")

    # Git pre-check
    ok, msg = check_git_status()
    if not ok:
        print(f"❌ {msg}")
        return 1
    print("✅ Git repository is clean\n")

    # Step 1: Name
    print_section("Step 1: CTF Name")
    name = get_input("CTF name (e.g., 'flAWS', 'EntraGoat')")

    # Step 2: URL + safety check
    print_section("Step 2: URL")
    while True:
        url = get_input("Challenge URL (must start with http:// or https://)")
        print("\n🔒 Validating URL...")
        safe, result = validate_url(url)
        if not safe or result.get('errors'):
            print("❌ URL validation failed:")
            for e in result.get('errors', []):
                print(f"   • {e}")
            if input("\nTry a different URL? (y/n): ").strip().lower() != 'y':
                print("\n⛔ Cannot proceed with unsafe URL.")
                return 1
            continue
        if result.get('warnings'):
            print("⚠️  Warnings:")
            for w in result['warnings']:
                print(f"   • {w}")
            if input("\nProceed anyway? (y/n): ").strip().lower() != 'y':
                continue
        print("✅ URL is safe")
        break

    # Step 3: Description
    print_section("Step 3: Short Description")
    print("1 sentence shown below the title. Example: 'AWS IAM privilege escalation - 31 attack paths via Terraform.'")
    description = get_input("Description")

    # Step 4: Tooltip (extended)
    print_section("Step 4: Tooltip Description (Optional)")
    print("2-3 sentences shown on hover. What's unique, who benefits, prerequisites.")
    print("(Press Enter to skip.)")
    tooltip = get_input("Tooltip", required=False)

    # Step 5: Section
    print_section("Step 5: Section Placement")
    section_id, section_label = select_from_list("Which section should this CTF go in?", SECTIONS)

    # Step 6: Tags
    print_section("Step 6: Tags")
    tags = select_tags()

    # Review
    print_section("📋 Review")
    print(f"Name:        {name}")
    print(f"URL:         {url}")
    print(f"Section:     {section_label}")
    print(f"Tags:        {', '.join(tags)}")
    print(f"Description: {description}")
    print(f"Tooltip:     {tooltip if tooltip else '(none)'}")
    if input("\n✅ Looks correct? (y/n): ").strip().lower() != 'y':
        print("\n⛔ Cancelled.")
        return 0

    # Optional preview generation
    if input("\n🖼️  Generate preview image locally? (y/n, default=y): ").strip().lower() in ('', 'y', 'yes'):
        print_section("🖼️  Generating Preview")
        print("This may take 10-30 seconds...")
        try:
            sys.path.insert(0, str(Path(__file__).parent))
            from generate_preview import generate_preview
            ok, path, msg = generate_preview(url)
            print(f"{'✅' if ok else '⚠️ '} {msg}")
            if ok:
                print(f"   Preview: {path}")
            else:
                print("   Preview will be auto-generated by GitHub Actions.")
        except Exception as e:
            print(f"⚠️  Preview generation skipped: {e}")
            print("   Preview will be auto-generated by GitHub Actions.")
    else:
        print("\n⏭️  Skipping local preview generation.")

    # Generate HTML + insert
    print_section("Generating HTML")
    card_html = create_ctf_card_html(name, url, description, tags, tooltip)
    print("Generated card:\n")
    print(card_html)

    workspace_root = Path(__file__).parent.parent
    ctfs_file = workspace_root / 'ctfs.html'
    if not ctfs_file.exists():
        print(f"\n❌ ctfs.html not found at {ctfs_file}")
        return 1

    content = ctfs_file.read_text(encoding='utf-8')
    new_content, err = insert_card_into_section(content, section_id, card_html)
    if err:
        print(f"\n❌ {err}")
        print("\nYou can paste the card manually at the end of the relevant section.")
        return 1

    ctfs_file.write_text(new_content, encoding='utf-8')
    print(f"\n✅ Updated {ctfs_file.name}")

    # Git branch + commit
    print_section("Creating Git Branch")
    ok, branch = create_branch_and_commit(name)
    if not ok:
        print(f"❌ {branch}")
        print("You'll need to commit manually.")
        return 1
    print(f"✅ Committed on branch: {branch}")

    print_section("Next Steps")
    print(f"1. Push:\n   git push origin {branch}")
    print("2. Open a PR:")
    print("   https://github.com/CloudSecurityOfficeHours/csoh.org/pulls")

    if input("\nPush now? (y/n): ").strip().lower() == 'y':
        ok, out = git_command(['push', '-u', 'origin', branch])
        if ok:
            print(f"✅ Pushed.\n\n   https://github.com/CloudSecurityOfficeHours/csoh.org/compare/{branch}?expand=1")
        else:
            print(f"❌ Push failed: {out}")

    print_header("✨ Submission Complete - thanks!")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Cancelled by user")
        sys.exit(1)
