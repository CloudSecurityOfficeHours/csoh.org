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
import os
import re
import subprocess
from pathlib import Path
from check_url_safety import URLSafetyChecker

# Category mappings
CATEGORIES = {
    '1': ('ctf-challenges', 'CTF Challenges & Vulnerable Environments'),
    '2': ('labs-training', 'Hands-On Labs & Training Platforms'),
    '3': ('security-tools', 'Security Tools & Platforms'),
    '4': ('certifications', 'Certifications & Professional Development'),
    '5': ('ai-security', 'AI Security Resources'),
    '6': ('job-search', 'Job Search Resources'),
}

# Available tags
AVAILABLE_TAGS = [
    'AWS', 'Azure', 'GCP', 'Kubernetes', 'Multi-Cloud',
    'CTF', 'Labs & Training', 'Tool', 'Certification', 'Job Search',
    'Vulnerability Testing', 'Penetration Testing', 'Cloud Scanning',
    'Secrets Management', 'Compliance', 'AI Security', 'IAM', 'DevSecOps',
    'NEW 2025', 'Free', 'Paid', 'Open Source'
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
    types = ['CTF', 'Labs & Training', 'Tool', 'Certification', 'Job Search']
    for i, tag in enumerate(types, len(platforms) + 1):
        print(f"    {i}. {tag}")
    
    print("\n  Security Focus Tags:")
    focus = ['Vulnerability Testing', 'Penetration Testing', 'Cloud Scanning', 
             'Secrets Management', 'Compliance', 'AI Security', 'IAM', 'DevSecOps']
    for i, tag in enumerate(focus, len(platforms) + len(types) + 1):
        print(f"    {i}. {tag}")
    
    print("\n  Other Tags:")
    other = ['NEW 2025', 'Free', 'Paid', 'Open Source']
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

def create_resource_html(name, url, description, tags):
    """Generate the HTML for a resource card."""
    tags_html = '\n            '.join([f'<span class="tag">{tag}</span>' for tag in tags])
    
    html = f'''    <a href="{url}" target="_blank" class="card-link" rel="noopener noreferrer">
        <div class="resource-card">
            <h3>{name}</h3>
            <p>{description}</p>
            <div class="resource-tags">
                {tags_html}
            </div>
        </div>
    </a>'''
    
    return html

def find_category_section(html_content, category_id):
    """Find the section for a specific category in the HTML."""
    # Map category IDs to section IDs in resources.html
    section_map = {
        'ctf-challenges': 'ctf-challenges',
        'labs-training': 'labs-training',
        'security-tools': 'security-tools',
        'certifications': 'certifications',
        'ai-security': 'ai-security',
        'job-search': 'job-search',
    }
    
    section_id = section_map.get(category_id)
    if not section_id:
        return None, None
    
    # Find the section by ID
    section_pattern = rf'<div[^>]+class="category-section"[^>]+id="{section_id}"[^>]*>(.*)</div>'
    match = re.search(section_pattern, html_content, re.DOTALL)
    
    if not match:
        return None, None
    
    return match.start(), match.end()

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
    
    # Add the modified file
    success, output = git_command(['add', 'resources.html'])
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
    print("  ✅ Generate the proper HTML")
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
        break
    
    # Step 3: Get description
    print_section("Step 3: Description")
    print("Write a brief description (1-2 sentences)")
    print("Explain what it is and why it's useful for cloud security professionals")
    description = get_input("Description")
    
    # Step 4: Select category
    print_section("Step 4: Category")
    category_id, category_name = select_from_list(
        "Select the main category for this resource:",
        CATEGORIES
    )
    
    # Step 5: Select tags
    print_section("Step 5: Tags")
    tags = select_tags()
    
    # Step 6: Review
    print_section("📋 Review Your Submission")
    print(f"Name:        {name}")
    print(f"URL:         {url}")
    print(f"Category:    {category_name}")
    print(f"Tags:        {', '.join(tags)}")
    print(f"Description: {description}")
    
    confirm = input("\n✅ Does this look correct? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n⛔ Submission cancelled.")
        return 0
    
    # Step 6.5: Generate preview image (optional)
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
    
    # Step 7: Generate HTML and update file
    print_section("Step 7: Generating and Inserting HTML")
    
    resource_html = create_resource_html(name, url, description, tags)
    print("Generated HTML:")
    print(resource_html)
    
    # Read resources.html
    workspace_root = Path(__file__).parent.parent
    resources_file = workspace_root / 'resources.html'
    
    if not resources_file.exists():
        print(f"\n❌ Could not find resources.html at {resources_file}")
        return 1
    
    print(f"\n📝 Reading {resources_file}...")
    with open(resources_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the category section
    start, end = find_category_section(content, category_id)
    if start is None:
        print(f"\n❌ Could not find section for category: {category_name}")
        print("You may need to add the resource manually.")
        print("\nGenerated HTML has been saved. You can copy it from above.")
        return 1
    
    # Find the last </a> before </section> to insert before
    section_content = content[start:end]
    last_card_end = section_content.rfind('</a>')
    
    if last_card_end == -1:
        print("\n❌ Could not find insertion point in section")
        return 1
    
    # Insert the new resource after the last card
    insertion_point = start + last_card_end + 4  # After </a>
    new_content = content[:insertion_point] + '\n\n' + resource_html + content[insertion_point:]
    
    # Write back
    print(f"💾 Writing updated resources.html...")
    with open(resources_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Successfully updated resources.html!")
    
    # Step 8: Create git branch and commit
    print_section("Step 8: Creating Git Branch and Commit")
    
    success, branch_name = create_branch_and_commit(name)
    if not success:
        print(f"❌ {branch_name}")
        print("\nThe resource has been added to resources.html, but git operations failed.")
        print("You'll need to commit and push manually.")
        return 1
    
    print(f"✅ Created branch: {branch_name}")
    print(f"✅ Committed changes")
    
    # Step 9: Push and create PR
    print_section("Step 9: Next Steps - Create Pull Request")
    
    print("Your changes are ready! Here's what to do next:\n")
    print(f"1. Push your branch to GitHub:")
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
    print("5. A maintainer will review and merge your PR!\n")
    
    auto_push = input("Would you like to push now? (y/n): ").strip().lower()
    if auto_push == 'y':
        print(f"\n🚀 Pushing to origin/{branch_name}...")
        success, output = git_command(['push', '-u', 'origin', branch_name], capture_output=True)
        if success:
            print("✅ Successfully pushed!")
            print(f"\n🌐 Create your PR here:")
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
