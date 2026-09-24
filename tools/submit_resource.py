#!/usr/bin/env python3
"""
Interactive Resource Submission Tool for CSOH.org

This script helps contributors add new resources to the site with:
- Interactive prompts for all required information
- Automatic URL safety validation
- HTML generation
- Git branch creation and commit
- GitHub PR creation (optional)

Usage:
    python3 tools/submit_resource.py
"""

import sys
import re
import html
import subprocess
from pathlib import Path
from check_url_safety import URLSafetyChecker
from sync_counts import CATEGORY_META

REPO = Path(__file__).resolve().parent.parent

# Categories come from sync_counts.CATEGORY_META, the same table that builds
# the hub and every category page's ItemList. Reading the shared table means
# a new category page needs no edit here.
CATEGORIES = {
    str(i): (cid, name)
    for i, (cid, (name, _desc)) in enumerate(CATEGORY_META.items(), start=1)
}

# The coloured lead tag each category page puts first on its cards, as
# (css class, label). A category missing here still works; its cards just
# lead with the plain tags the contributor picked.
CATEGORY_LEAD_TAG = {
    'ctf-challenges': ('ctf', 'CTF'),
    'labs-training': ('lab', 'Labs &amp; Training'),
    'security-tools': ('tool', 'Tool'),
    'certifications': ('certification', 'Certification'),
    'ai-security': ('ai-security', 'AI Security'),
    'job-search': ('job', 'Job Board'),
    'newsletters': ('newsletter', 'Newsletter'),
}

# Available tags
AVAILABLE_TAGS = [
    'AWS', 'Azure', 'GCP', 'Kubernetes', 'Multi-Cloud',
    'CTF', 'Labs & Training', 'Tool', 'Certification', 'Job Search', 'Newsletter',
    'Vulnerability Testing', 'Penetration Testing', 'Cloud Scanning',
    'Secrets Management', 'Compliance', 'AI Security', 'IAM', 'DevSecOps',
    'NEW 2026', 'Free', 'Paid', 'Open Source'
]

def print_header(text):
    """Print a formatted header."""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}\n")

def print_section(text):
    """Print a formatted section."""
    print(f"\n{'─'*70}")
    print(f"  {text}")
    print(f"{'─'*70}\n")

def validate_url(url):
    """Validate a URL and return safety check results."""
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"

    checker = URLSafetyChecker()
    result = checker.check_url(url)

    return result['safe'], result

def get_input(prompt, required=True, validator=None):
    """Get input with optional validation."""
    while True:
        value = input(f"{prompt}: ").strip()

        if not value and required:
            print("❌ This field is required. Please try again.\n")
            continue

        if not value and not required:
            return value

        if validator:
            valid, message = validator(value)
            if not valid:
                print(f"❌ {message}\n")
                continue

        return value

def select_from_list(prompt, options, allow_multiple=False):
    """Present a list of options and get selection(s)."""
    print(f"\n{prompt}")
    for key, value in options.items():
        if isinstance(value, tuple):
            print(f"  {key}. {value[1]}")
        else:
            print(f"  {key}. {value}")

    if allow_multiple:
        print("\n  Enter numbers separated by commas (e.g., 1,3,5)")
        selection = input("  Your selection: ").strip()
        selections = [s.strip() for s in selection.split(',')]

        results = []
        for sel in selections:
            if sel in options:
                results.append(options[sel])
            else:
                print(f"  ⚠️  Skipping invalid selection: {sel}")

        return results
    else:
        while True:
            selection = input("  Your selection: ").strip()
            if selection in options:
                return options[selection]
            print(f"  ❌ Invalid selection. Please choose from {', '.join(options.keys())}\n")

def select_tags():
    """Interactive tag selection."""
    print("\n📋 Available Tags (select relevant ones):")

    # Group tags by type
    print("\n  Platform Tags:")
    platforms = ['AWS', 'Azure', 'GCP', 'Kubernetes', 'Multi-Cloud']
    for i, tag in enumerate(platforms, 1):
        print(f"    {i}. {tag}")

    print("\n  Resource Type Tags:")
    types = ['CTF', 'Labs & Training', 'Tool', 'Certification', 'Job Search', 'Newsletter']
    for i, tag in enumerate(types, len(platforms) + 1):
        print(f"    {i}. {tag}")

    print("\n  Security Focus Tags:")
    focus = ['Vulnerability Testing', 'Penetration Testing', 'Cloud Scanning',
             'Secrets Management', 'Compliance', 'AI Security', 'IAM', 'DevSecOps']
    for i, tag in enumerate(focus, len(platforms) + len(types) + 1):
        print(f"    {i}. {tag}")

    print("\n  Other Tags:")
    other = ['NEW 2026', 'Free', 'Paid', 'Open Source']
    for i, tag in enumerate(other, len(platforms) + len(types) + len(focus) + 1):
        print(f"    {i}. {tag}")

    all_tags = platforms + types + focus + other

    print("\n  Enter tag numbers separated by commas (e.g., 1,6,10)")
    print("  Recommended: 2-5 tags")

    while True:
        selection = input("  Your selection: ").strip()
        if not selection:
            print("  ❌ Please select at least one tag\n")
            continue

        try:
            indices = [int(s.strip()) - 1 for s in selection.split(',')]
            selected_tags = [all_tags[i] for i in indices if 0 <= i < len(all_tags)]

            if not selected_tags:
                print("  ❌ No valid tags selected. Please try again.\n")
                continue

            return selected_tags
        except (ValueError, IndexError):
            print("  ❌ Invalid selection. Please use numbers separated by commas.\n")

def create_resource_html(name, url, description, tags, tooltip='', category_id=None):
    """Generate the HTML for a resource card, matching the category pages."""
    def esc(text):
        return html.escape(text, quote=True)

    spans = []
    lead = CATEGORY_LEAD_TAG.get(category_id)
    if lead:
        spans.append(f'<span class="tag {lead[0]}">{lead[1]}</span>')
    lead_label = html.unescape(lead[1]) if lead else None
    for tag in tags:
        if tag != lead_label:
            spans.append(f'<span class="tag">{esc(tag)}</span>')
    tags_html = '\n'.join(' ' * 32 + t for t in spans)

    tooltip_attr = f' data-tooltip="{esc(tooltip)}"' if tooltip else ''

    # Predict the preview filename with generate_preview.py's own logic. The
    # image may not exist yet; CI captures it. No onerror= fallback: the
    # production CSP is script-src 'self', which blocks inline handlers, so
    # it never ran there anyway. A bare <img> rather than <picture>, because
    # no WebP exists yet; generate_webp.py + wrap_img_webp.py add it.
    img_filename = _predict_preview_filename(url)

    return (
        f'<a href="{esc(url)}" class="card-link" target="_blank" rel="noopener noreferrer">\n'
        f'                        <div class="resource-card"{tooltip_attr}>\n'
        f'                            <img src="img/previews/{img_filename}" alt="{esc(name)} preview" class="resource-preview" loading="lazy" decoding="async">\n'
        f'                            <h3>{esc(name)}</h3>\n'
        f'                            <p>{esc(description)}</p>\n'
        f'                            <div class="resource-tags">\n'
        f'{tags_html}\n'
        f'                            </div>\n'
        f'                        </div>\n'
        f'                    </a>'
    )


def _predict_preview_filename(url):
    """Match generate_preview.generate_filename_from_url so submitted cards point at the right preview."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    path = parsed.path.strip('/').replace('/', '-')
    filename = f"{domain}-{path}" if path else domain
    filename = filename.lower()
    filename = ''.join(c if c.isalnum() or c in ['-', '_'] else '-' for c in filename)
    filename = filename[:100]
    return f"{filename}.jpg"

def category_page(category_id):
    """The file that holds this category's cards."""
    return REPO / f'resources-{category_id}.html'


# The end of the one resource grid on a category page: the last card's </a>
# (or the opening tag, on an empty page), then the grid, the category-content
# wrapper and the section closing. Anchoring on the whole tail is what makes
# "insert after the last card" unambiguous.
GRID_END_RE = re.compile(
    r'(</a>|<div class="resource-grid">)(\s*</div>\s*</div>\s*</section>)'
)


def insert_card(content, card_html):
    """Return content with card_html appended to the resource grid, or None."""
    matches = list(GRID_END_RE.finditer(content))
    if len(matches) != 1:
        return None
    m = matches[0]
    return content[:m.end(1)] + card_html + content[m.start(2):]


def find_existing(url):
    """Category pages that already carry a card for this exact URL."""
    needle = f'href="{html.escape(url, quote=True)}"'
    return [p.name for p in sorted(REPO.glob('resources-*.html'))
            if needle in p.read_text(encoding='utf-8')]


def run_generators():
    """Stamp the card id and refresh every count, as CI's gates expect.

    stamp_card_ids.py --check and sync_counts.py --check both run in CI, so a
    card committed without these fails the PR even though it renders fine.
    """
    for script in ('stamp_card_ids.py', 'sync_counts.py'):
        result = subprocess.run([sys.executable, str(REPO / 'tools' / script)],
                                cwd=REPO, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"{script} failed:\n{result.stdout}{result.stderr}"
    return True, ''


def git_command(args, capture_output=True):
    """Run a git command and return the result."""
    try:
        result = subprocess.run(
            ['git'] + args,
            capture_output=capture_output,
            text=True,
            check=True
        )
        return True, result.stdout.strip() if capture_output else ""
    except subprocess.CalledProcessError as e:
        return False, e.stderr if capture_output else str(e)

def check_git_status():
    """Check if we're in a git repository and get current status."""
    success, output = git_command(['status', '--porcelain'])
    if not success:
        return False, "Not in a git repository"

    if output:
        return False, "Working directory has uncommitted changes. Please commit or stash them first."

    return True, ""

def create_branch_and_commit(resource_name):
    """Create a new branch and commit the changes."""
    # Create branch name from resource name
    branch_name = f"add-{re.sub(r'[^a-z0-9]+', '-', resource_name.lower())}"
    branch_name = branch_name[:50]  # Limit length

    print(f"\n📝 Creating git branch: {branch_name}")

    # Create and checkout new branch
    success, output = git_command(['checkout', '-b', branch_name])
    if not success:
        return False, f"Failed to create branch: {output}"

    # The tree was clean when the tool started (check_git_status), so every
    # change is ours: the category page, the counts sync_counts.py refreshed
    # across the site, and any preview image and mapping entry. Stage those
    # paths by name rather than with -A.
    # -z, and not through git_command(): that strips stdout, which eats the
    # leading space of the first " M path" entry and shifts its path by one.
    status = subprocess.run(['git', 'status', '--porcelain', '-z', '--untracked-files=all'],
                            cwd=REPO, capture_output=True, text=True)
    if status.returncode != 0:
        return False, f"Failed to read git status: {status.stderr}"
    paths = [entry[3:] for entry in status.stdout.split('\0') if len(entry) > 3]
    if not paths:
        return False, "Nothing to commit"
    success, output = git_command(['add', '--'] + paths)
    if not success:
        return False, f"Failed to stage changes: {output}"

    # Commit
    commit_message = f"Add {resource_name} to resources"
    success, output = git_command(['commit', '-m', commit_message])
    if not success:
        return False, f"Failed to commit: {output}"

    return True, branch_name

def main():
    """Main interactive workflow."""
    print_header("🚀 CSOH Resource Submission Tool")

    print("This tool will help you add a new resource to CSOH.org")
    print("It will:")
    print("  ✅ Validate your URL for security")
    print("  ✅ Generate the proper HTML (with hover tooltip)")
    print("  ✅ Create a git branch and commit")
    print("  ✅ Provide instructions for creating a PR")

    print("\n" + "="*70 + "\n")

    # Check git status
    print("🔍 Checking git repository status...")
    git_ok, git_msg = check_git_status()
    if not git_ok:
        print(f"❌ {git_msg}")
        print("\nPlease resolve this before continuing.")
        return 1
    print("✅ Git repository is clean\n")

    # Step 1: Get resource name
    print_section("Step 1: Resource Information")
    name = get_input("Resource name (e.g., 'CloudGoat', 'OWASP EKS Goat')")

    # Step 2: Get and validate URL
    print_section("Step 2: Resource URL")
    print("Enter the full URL for this resource")

    while True:
        url = get_input("URL (must start with http:// or https://)")

        print("\n🔒 Validating URL security...")
        is_safe, result = validate_url(url)

        if not is_safe or result.get('errors'):
            print("❌ URL validation failed:")
            for error in result.get('errors', []):
                print(f"   • {error}")

            retry = input("\nTry a different URL? (y/n): ").strip().lower()
            if retry != 'y':
                print("\n⛔ Cannot proceed with unsafe URL. Exiting.")
                return 1
            continue

        if result.get('warnings'):
            print("⚠️  URL has warnings:")
            for warning in result['warnings']:
                print(f"   • {warning}")

            proceed = input("\nProceed anyway? (y/n): ").strip().lower()
            if proceed != 'y':
                retry = input("Try a different URL? (y/n): ").strip().lower()
                if retry != 'y':
                    print("\n⛔ Exiting.")
                    return 1
                continue

        print("✅ URL is safe!")

        existing = find_existing(url)
        if existing:
            print(f"⚠️  This URL is already listed on: {', '.join(existing)}")
            retry = input("Try a different URL? (y/n): ").strip().lower()
            if retry != 'y':
                print("\n⛔ Exiting.")
                return 1
            continue
        break

    # Step 3: Get description
    print_section("Step 3: Description")
    print("Write a brief description (1-2 sentences)")
    print("Explain what it is and why it's useful for cloud security professionals")
    description = get_input("Description")

    # Step 4: Extended Tooltip Description
    print_section("Step 4: Extended Tooltip Description")
    print("Write 2-3 sentences that appear when someone hovers over the card.")
    print("Cover what makes it unique, who benefits most, and any prerequisites.")
    print("(Press Enter to skip - you can always add one later)")
    tooltip = get_input("Tooltip description", required=False)

    # Step 5: Select category
    print_section("Step 5: Category")
    category_id, category_name = select_from_list(
        "Select the main category for this resource:",
        CATEGORIES
    )

    # Step 6: Select tags
    print_section("Step 6: Tags")
    tags = select_tags()

    # Step 7: Review
    print_section("📋 Review Your Submission")
    print(f"Name:        {name}")
    print(f"URL:         {url}")
    print(f"Category:    {category_name}")
    print(f"Tags:        {', '.join(tags)}")
    print(f"Description: {description}")
    print(f"Tooltip:     {tooltip if tooltip else '(none)'}")

    confirm = input("\n✅ Does this look correct? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n⛔ Submission cancelled.")
        return 0

    # Step 7.5: Generate preview image (optional)
    preview_path = None
    generate_preview_prompt = input("\n🖼️  Generate preview image automatically? (y/n, default=y): ").strip().lower()

    if generate_preview_prompt in ('', 'y', 'yes'):
        print_section("🖼️  Generating Preview Image")
        print("This may take 10-30 seconds...")

        try:
            # Import preview generator
            sys.path.insert(0, str(Path(__file__).parent))
            from generate_preview import generate_preview

            success, preview_path, message = generate_preview(url)

            if success:
                print(f"✅ {message}")
                print(f"   Preview: {preview_path}")
            else:
                print(f"⚠️  {message}")
                print("   Preview will be auto-generated later by GitHub Actions")

        except ImportError as e:
            print(f"⚠️  Preview generator not available: {e}")
            print("   Preview will be auto-generated later by GitHub Actions")
        except Exception as e:
            print(f"⚠️  Could not generate preview: {e}")
            print("   Preview will be auto-generated later by GitHub Actions")
    else:
        print("\n⏭️  Skipping preview generation")
        print("   Preview will be auto-generated later by GitHub Actions")

    # Step 8: Generate HTML and update file
    print_section("Step 8: Generating and Inserting HTML")

    resource_html = create_resource_html(name, url, description, tags, tooltip, category_id)
    print("Generated HTML:")
    print(resource_html)

    page = category_page(category_id)
    if not page.exists():
        print(f"\n❌ Could not find {page.name}")
        print("You may need to add the resource manually; the HTML is above.")
        return 1

    print(f"\n📝 Reading {page.name}...")
    new_content = insert_card(page.read_text(encoding='utf-8'), resource_html)
    if new_content is None:
        print(f"\n❌ Could not find the resource grid in {page.name}")
        print("You may need to add the resource manually; the HTML is above.")
        return 1

    print(f"💾 Writing updated {page.name}...")
    page.write_text(new_content, encoding='utf-8')

    print("🔧 Stamping the card id and refreshing counts...")
    ok, err = run_generators()
    if not ok:
        print(f"❌ {err}")
        print(f"The card is in {page.name}; fix the error above, then commit.")
        return 1

    print(f"✅ Successfully updated {page.name}!")

    # Step 9: Create git branch and commit
    print_section("Step 9: Creating Git Branch and Commit")

    success, branch_name = create_branch_and_commit(name)
    if not success:
        print(f"❌ {branch_name}")
        print(f"\nThe resource has been added to {category_page(category_id).name}, but git operations failed.")
        print("You'll need to commit and push manually.")
        return 1

    print(f"✅ Created branch: {branch_name}")
    print("✅ Committed changes")

    # Step 10: Push and create PR
    print_section("Step 10: Next Steps - Create Pull Request")

    print("Your changes are ready! Here's what to do next:\n")
    print("1. Push your branch to GitHub:")
    print(f"   git push origin {branch_name}\n")
    print("2. Go to GitHub and create a Pull Request:")
    print("   https://github.com/CloudSecurityOfficeHours/csoh.org/pulls\n")
    print("3. In your PR description, include:")
    print(f"   Resource: {name}")
    print(f"   URL: {url}")
    print(f"   Category: {category_name}")
    print(f"   \n   {description}\n")
    print("4. Wait for automated checks to complete:")
    print("   ✅ URL safety validation")
    print("   🖼️  Preview image generation (if not done locally)")
    print("5. A maintainer will review and merge your PR!\n")

    auto_push = input("Would you like to push now? (y/n): ").strip().lower()
    if auto_push == 'y':
        print(f"\n🚀 Pushing to origin/{branch_name}...")
        success, output = git_command(['push', '-u', 'origin', branch_name], capture_output=True)
        if success:
            print("✅ Successfully pushed!")
            print("\n🌐 Create your PR here:")
            print(f"   https://github.com/CloudSecurityOfficeHours/csoh.org/compare/{branch_name}?expand=1")
        else:
            print(f"❌ Push failed: {output}")
            print(f"\nYou can push manually with: git push origin {branch_name}")

    print_header("✨ Submission Complete!")
    print("\nThank you for contributing to CSOH! 🙏")
    print("Your submission will help cloud security professionals worldwide.")

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⛔ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
