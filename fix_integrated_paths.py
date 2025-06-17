#!/usr/bin/env python3
"""
Fix all remaining absolute path issues in the integrated setup
"""

import os
import re

def fix_git_sync_credential_path():
    """Fix the credential path in git_sync.py"""
    
    git_sync_file = "scripts/overleaf-monitor/git_sync.py"
    
    if not os.path.exists(git_sync_file):
        print(f"❌ Git sync file not found: {git_sync_file}")
        return False
    
    print(f"🔧 Fixing credential paths in {git_sync_file}")
    
    with open(git_sync_file, 'r') as f:
        content = f.read()
    
    # Find and fix the credential file path
    old_credential_path = 'credential_file = os.path.join(BASE_DIR, "data", ".git-credentials")'
    new_credential_path = 'credential_file = os.path.join(SCRIPT_DIR, "data", ".git-credentials")'
    
    if old_credential_path in content:
        content = content.replace(old_credential_path, new_credential_path)
        print("   ✅ Fixed credential file path")
    
    # Also fix any other BASE_DIR references that should be SCRIPT_DIR
    # Look for patterns like BASE_DIR + "data" which should be SCRIPT_DIR + "data"
    content = re.sub(
        r'os\.path\.join\(BASE_DIR, "data"',
        'os.path.join(SCRIPT_DIR, "data"',
        content
    )
    
    with open(git_sync_file, 'w') as f:
        f.write(content)
    
    print("✅ Fixed git_sync.py credential paths")
    return True

def fix_credential_helper_script():
    """Fix the credential helper setup script we created earlier"""
    
    credential_script = "fix_with_credential_helper.py"
    
    if os.path.exists(credential_script):
        print(f"🔧 Fixing paths in {credential_script}")
        
        with open(credential_script, 'r') as f:
            content = f.read()
        
        # Fix the credential file path to use the correct integrated path
        old_path = 'credential_file = "scripts/overleaf-monitor/data/.git-credentials"'
        new_path = 'credential_file = os.path.join("scripts", "overleaf-monitor", "data", ".git-credentials")'
        
        if old_path in content:
            content = content.replace(old_path, new_path)
            print("   ✅ Fixed credential file path in helper script")
        
        with open(credential_script, 'w') as f:
            f.write(content)

def fix_pipeline_credential_paths():
    """Fix credential paths in the main pipeline"""
    
    pipeline_file = "scripts/overleaf-monitor/github_actions_pipeline.py"
    
    if not os.path.exists(pipeline_file):
        print(f"❌ Pipeline file not found: {pipeline_file}")
        return False
    
    print(f"🔧 Fixing credential paths in {pipeline_file}")
    
    with open(pipeline_file, 'r') as f:
        content = f.read()
    
    # Fix any hardcoded credential file paths
    old_patterns = [
        'credential_file = os.path.join(os.path.dirname(__file__), "data", ".git-credentials")',
        'credential_file = "scripts/overleaf-monitor/data/.git-credentials"'
    ]
    
    new_pattern = '''# Get the script directory (scripts/overleaf-monitor)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            credential_file = os.path.join(script_dir, "data", ".git-credentials")'''
    
    for old_pattern in old_patterns:
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)
            print("   ✅ Fixed credential file path in pipeline")
    
    with open(pipeline_file, 'w') as f:
        f.write(content)
    
    print("✅ Fixed pipeline credential paths")
    return True

def create_test_credential_setup():
    """Create a test script to verify credential setup works"""
    
    test_script_content = '''#!/usr/bin/env python3
"""
Test credential setup for integrated Overleaf monitor
"""

import os
import json
import subprocess

def test_credential_setup():
    """Test if credential setup works correctly"""
    
    print("🧪 Testing Credential Setup")
    print("=" * 30)
    
    # Check if we're in the right directory
    if not os.path.exists("scripts/overleaf-monitor"):
        print("❌ Not in BookWebsite directory")
        return False
    
    # Load git config
    git_config_file = "scripts/overleaf-monitor/data/git_config.json"
    
    if not os.path.exists(git_config_file):
        print(f"❌ Git config not found: {git_config_file}")
        return False
    
    try:
        with open(git_config_file, 'r') as f:
            git_config = json.load(f)
        
        username = git_config.get('username')
        token = git_config.get('token')
        
        if not username or not token:
            print("❌ Missing credentials in git config")
            return False
        
        print(f"✅ Found credentials for: {username}")
        
        # Set up credential file
        credential_file = "scripts/overleaf-monitor/data/.git-credentials"
        credential_dir = os.path.dirname(credential_file)
        
        print(f"📁 Credential directory: {credential_dir}")
        print(f"📄 Credential file: {credential_file}")
        
        # Ensure directory exists
        os.makedirs(credential_dir, exist_ok=True)
        
        # Create credential entry
        git_url_with_creds = f"https://{username}:{token}@git.overleaf.com"
        
        with open(credential_file, 'w') as f:
            f.write(f"{git_url_with_creds}\\n")
        
        # Set secure permissions
        os.chmod(credential_file, 0o600)
        
        print("✅ Created credential file")
        
        # Configure git credential helper
        abs_credential_file = os.path.abspath(credential_file)
        print(f"🔧 Configuring Git with: {abs_credential_file}")
        
        result = subprocess.run([
            'git', 'config', '--global', 'credential.helper', f'store --file={abs_credential_file}'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Git credential helper configured")
        else:
            print(f"❌ Error configuring credential helper: {result.stderr}")
            return False
        
        # Test the setup
        print("🧪 Testing Git access...")
        
        project_id = "68428c5d41c2ef888f0b2a5e"
        git_url = f"https://git.overleaf.com/{project_id}"
        
        result = subprocess.run([
            'git', 'ls-remote', git_url
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            print("✅ Git access is working!")
            print("   Credential setup is correct")
            return True
        else:
            print(f"❌ Git access failed: {result.stderr}")
            return False
        
    except Exception as e:
        print(f"❌ Error testing credential setup: {e}")
        return False

if __name__ == "__main__":
    success = test_credential_setup()
    if success:
        print("\\n🎯 Credential setup is working correctly!")
    else:
        print("\\n❌ Credential setup needs fixing")
    exit(0 if success else 1)
'''
    
    with open("test_credential_setup.py", 'w') as f:
        f.write(test_script_content)
    
    os.chmod("test_credential_setup.py", 0o755)
    print("✅ Created test script: test_credential_setup.py")

def main():
    """Fix all remaining absolute path issues"""
    print("🔧 Fixing All Remaining Absolute Path Issues")
    print("=" * 50)
    
    if not os.path.exists("scripts/overleaf-monitor"):
        print("❌ Not in BookWebsite directory")
        return False
    
    try:
        # Fix git_sync credential paths
        if not fix_git_sync_credential_path():
            return False
        
        print()
        
        # Fix credential helper script paths
        fix_credential_helper_script()
        
        print()
        
        # Fix pipeline credential paths
        if not fix_pipeline_credential_paths():
            return False
        
        print()
        
        # Create test script
        create_test_credential_setup()
        
        print()
        print("✅ All absolute path issues should now be fixed!")
        print()
        print("🧪 Test the credential setup:")
        print("   python3 test_credential_setup.py")
        print()
        print("🧪 Then test git_sync:")
        print("   python3 scripts/overleaf-monitor/git_sync.py")
        print()
        print("🧪 Finally test the main pipeline:")
        print("   python3 scripts/overleaf-monitor/pipeline.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing paths: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)