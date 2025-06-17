#!/usr/bin/env python3
"""
Manual Git Test Script
Use this to test different Git authentication methods
"""

import subprocess
import json
from urllib.parse import quote

def test_git_access():
    """Test Git access with different methods"""
    
    # Load credentials
    with open("scripts/overleaf-monitor/data/git_config.json", 'r') as f:
        git_config = json.load(f)
    
    username = git_config.get('username')
    token = git_config.get('token')
    project_id = "68428c5d41c2ef888f0b2a5e"
    
    print(f"Testing Git access for {username}")
    print(f"Project ID: {project_id}")
    print()
    
    # Method 1: URL encoded credentials
    encoded_username = quote(username, safe='')
    encoded_token = quote(token, safe='')
    url1 = f"https://{encoded_username}:{encoded_token}@git.overleaf.com/{project_id}"
    
    print("🧪 Method 1: URL encoded credentials")
    result1 = subprocess.run(['git', 'ls-remote', url1], 
                           capture_output=True, text=True, timeout=30)
    if result1.returncode == 0:
        print("✅ Success!")
    else:
        print(f"❌ Failed: {result1.stderr}")
    print()
    
    # Method 2: Try cloning to a temp directory
    print("🧪 Method 2: Test clone to temp directory")
    temp_dir = "/tmp/overleaf_test_clone"
    subprocess.run(['rm', '-rf', temp_dir], capture_output=True)
    
    result2 = subprocess.run(['git', 'clone', url1, temp_dir], 
                           capture_output=True, text=True, timeout=60)
    if result2.returncode == 0:
        print("✅ Clone successful!")
        subprocess.run(['rm', '-rf', temp_dir], capture_output=True)
    else:
        print(f"❌ Clone failed: {result2.stderr}")
    print()
    
    # Method 3: Check if we can access Overleaf Git at all
    print("🧪 Method 3: Test basic Overleaf Git access")
    basic_url = f"https://git.overleaf.com/{project_id}"
    result3 = subprocess.run(['git', 'ls-remote', basic_url], 
                           capture_output=True, text=True, timeout=30)
    if result3.returncode == 0:
        print("✅ Repository is accessible (but may need auth)")
    else:
        print(f"❌ Repository not accessible: {result3.stderr}")

if __name__ == "__main__":
    test_git_access()
