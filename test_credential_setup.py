#!/usr/bin/env python3
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
            f.write(f"{git_url_with_creds}\n")
        
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
        print("\n🎯 Credential setup is working correctly!")
    else:
        print("\n❌ Credential setup needs fixing")
    exit(0 if success else 1)
