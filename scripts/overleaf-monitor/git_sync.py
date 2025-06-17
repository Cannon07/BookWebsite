#!/usr/bin/env python3
"""
Step 3: Git-based Overleaf Downloader (Premium)
Uses Overleaf Premium Git integration with automated token authentication
"""

import os
import sys
import json
import subprocess
import shutil
import getpass
import tempfile
from datetime import datetime
from pathlib import Path

# Auto-detect the base directory (integrated setup)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))  # Go up from scripts/overleaf-monitor to project root
CONFIG_FILE = os.path.join(SCRIPT_DIR, "data", "config.json")
GIT_CONFIG_FILE = os.path.join(SCRIPT_DIR, "data", "git_config.json")

def load_config():
    """Load configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return None

def setup_git_config():
    """Set up Git configuration for Overleaf"""
    config = load_config()
    if not config:
        return None
    
    project_id = config["project_id"]
    git_url = f"https://git.overleaf.com/{project_id}"
    
    print("🔧 Git Integration Setup")
    print("=" * 30)
    print()
    print("📋 We need your Overleaf Git credentials:")
    print(f"   Repository URL: {git_url}")
    print()
    print("🔑 To get your Git token:")
    print("1. Go to Overleaf → Account Settings → Git Integration")
    print("2. Generate a new Git token (if you don't have one)")
    print("3. Use your Overleaf email as username")
    print("4. Use the Git token as password")
    print()
    
    # Check if we have saved git config
    if os.path.exists(GIT_CONFIG_FILE):
        try:
            with open(GIT_CONFIG_FILE, 'r') as f:
                git_config = json.load(f)
            
            print("🔍 Found saved Git configuration")
            use_saved = input("Use saved credentials? (y/n): ").strip().lower()
            if use_saved in ['y', 'yes']:
                return git_config
        except:
            pass
    
    # Get new credentials
    print("🔐 Enter your Overleaf Git credentials:")
    username = input("Overleaf email: ").strip()
    token = getpass.getpass("Git token: ")
    
    git_config = {
        "username": username,
        "token": token,
        "git_url": git_url,
        "project_id": project_id,
        "created_at": datetime.now().isoformat()
    }
    
    # Save credentials
    save_creds = input("Save credentials for future use? (y/n): ").strip().lower()
    if save_creds in ['y', 'yes']:
        try:
            with open(GIT_CONFIG_FILE, 'w') as f:
                json.dump(git_config, f, indent=2)
            os.chmod(GIT_CONFIG_FILE, 0o600)  # Secure permissions
            print("🔐 Credentials saved securely")
        except Exception as e:
            print(f"⚠️  Could not save credentials: {e}")
    
    return git_config

def setup_git_credential_helper(git_config):
    """Set up Git credential helper to automate authentication"""
    try:
        print("🔧 Setting up Git credential helper...")
        
        # Method 1: Use git credential store (stores in plaintext but secure file permissions)
        credential_file = os.path.join(SCRIPT_DIR, "data", ".git-credentials")
        
        # Create credential entry
        git_url_with_creds = f"https://{git_config['username']}:{git_config['token']}@git.overleaf.com"
        
        with open(credential_file, 'w') as f:
            f.write(f"{git_url_with_creds}\n")
        
        # Set secure permissions
        os.chmod(credential_file, 0o600)
        
        # Configure git to use this credential store
        subprocess.run([
            'git', 'config', '--global', 'credential.helper', f'store --file={credential_file}'
        ], check=True)
        
        print("✅ Git credential helper configured")
        return True
        
    except Exception as e:
        print(f"❌ Error setting up credential helper: {e}")
        return False

def setup_git_credential_manager(git_config):
    """Alternative: Set up credential using environment variables"""
    git_url = git_config["git_url"]
    username = git_config["username"]
    token = git_config["token"]
    
    # Create URL with embedded credentials
    auth_url = git_url.replace("https://", f"https://{username}:{token}@")
    
    return auth_url

def clone_or_pull_repository(git_config, project_dir):
    """Clone repository or pull updates if it already exists"""
    git_url = git_config["git_url"]
    
    try:
        if os.path.exists(project_dir):
            # Directory exists - check if it's a git repository
            if os.path.exists(os.path.join(project_dir, '.git')):
                print(f"📂 Repository exists, pulling updates...")
                
                # Pull latest changes
                result = subprocess.run([
                    'git', '-C', project_dir, 'pull', 'origin', 'master'
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    print("✅ Successfully pulled latest changes")
                    return True
                else:
                    print(f"⚠️  Pull failed: {result.stderr}")
                    print("   Trying fresh clone...")
                    
                    # Backup and try fresh clone
                    backup_name = f"project_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    backup_path = os.path.join(os.path.dirname(project_dir), backup_name)
                    shutil.move(project_dir, backup_path)
                    print(f"🗂️  Backed up existing directory to: {backup_name}")
            else:
                # Directory exists but not a git repo - backup and clone fresh
                backup_name = f"project_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                backup_path = os.path.join(os.path.dirname(project_dir), backup_name)
                shutil.move(project_dir, backup_path)
                print(f"🗂️  Backed up non-git directory to: {backup_name}")
        
        # Clone repository
        print(f"📥 Cloning repository: {git_url}")
        
        # Method 1: Try with credential helper
        result = subprocess.run([
            'git', 'clone', git_url, project_dir
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print("✅ Successfully cloned repository")
            return True
        else:
            print(f"⚠️  Clone with credential helper failed: {result.stderr}")
            print("   Trying with embedded credentials...")
            
            # Method 2: Try with embedded credentials
            auth_url = setup_git_credential_manager(git_config)
            
            result = subprocess.run([
                'git', 'clone', auth_url, project_dir
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                print("✅ Successfully cloned with embedded credentials")
                
                # Remove the credential from git config for security
                try:
                    subprocess.run([
                        'git', '-C', project_dir, 'remote', 'set-url', 'origin', git_url
                    ], capture_output=True)
                except:
                    pass
                
                return True
            else:
                print(f"❌ Clone failed: {result.stderr}")
                return False
                
    except subprocess.TimeoutExpired:
        print("❌ Git operation timed out")
        return False
    except Exception as e:
        print(f"❌ Git operation error: {e}")
        return False

def copy_tex_files_to_chapters(source_dir):
    """Copy .tex files from git repository to chapters directory"""
    config = load_config()
    if not config:
        return False
    
    target_dir = config["chapters_dir"]
    
    print(f"📂 Copying .tex files to chapters directory...")
    print(f"   Source: {source_dir}")
    print(f"   Target: {target_dir}")
    
    try:
        # Find .tex files
        tex_files = []
        for root, dirs, files in os.walk(source_dir):
            # Skip .git directory
            if '.git' in dirs:
                dirs.remove('.git')
            
            for file in files:
                if file.endswith('.tex'):
                    tex_files.append(os.path.join(root, file))
        
        if not tex_files:
            print("❌ No .tex files found in git repository")
            return False
        
        print(f"📄 Found {len(tex_files)} .tex files")
        
        # Ensure target directory exists
        os.makedirs(target_dir, exist_ok=True)
        
        # Copy files and track changes
        updated_files = []
        for tex_file in tex_files:
            filename = os.path.basename(tex_file)
            target_file = os.path.join(target_dir, filename)
            
            # Check if file is different
            file_changed = True
            if os.path.exists(target_file):
                try:
                    with open(tex_file, 'r', encoding='utf-8', errors='ignore') as f1:
                        new_content = f1.read()
                    with open(target_file, 'r', encoding='utf-8', errors='ignore') as f2:
                        old_content = f2.read()
                    
                    if new_content == old_content:
                        file_changed = False
                        print(f"   ⏭️  No changes: {filename}")
                    else:
                        # Backup changed file
                        backup_file = f"{target_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.copy2(target_file, backup_file)
                        print(f"   💾 Backed up: {filename}")
                except:
                    file_changed = True
            
            if file_changed:
                shutil.copy2(tex_file, target_file)
                updated_files.append(filename)
                status = "Updated" if os.path.exists(target_file + ".backup*") else "Added"
                print(f"   ✅ {status}: {filename}")
        
        if updated_files:
            print(f"✅ Successfully updated {len(updated_files)} files")
        else:
            print("ℹ️  All files were already up to date")
        
        return True
        
    except Exception as e:
        print(f"❌ Error copying files: {e}")
        return False

def show_git_info(project_dir):
    """Show Git repository information"""
    try:
        print("📊 Git Repository Info:")
        
        # Get latest commit info
        result = subprocess.run([
            'git', '-C', project_dir, 'log', '-1', '--pretty=format:%h - %s (%cr) <%an>'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   📝 Latest commit: {result.stdout}")
        
        # Get branch info
        result = subprocess.run([
            'git', '-C', project_dir, 'branch', '--show-current'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   🌿 Branch: {result.stdout.strip()}")
        
        # Get status
        result = subprocess.run([
            'git', '-C', project_dir, 'status', '--porcelain'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            if result.stdout.strip():
                print(f"   ⚠️  Uncommitted changes detected")
            else:
                print(f"   ✅ Working directory clean")
        
    except Exception as e:
        print(f"   ⚠️  Could not get git info: {e}")

def main():
    """Main function for Git-based download"""
    print("=== Step 3: Git-based Overleaf Download (Premium) ===")
    print()
    
    config = load_config()
    if not config:
        return False
    
    project_dir = config["project_dir"]
    
    # Convert relative path to absolute path based on project root
    if not os.path.isabs(project_dir):
        project_dir = os.path.join(BASE_DIR, project_dir)
    
    # Set up Git configuration
    git_config = setup_git_config()
    if not git_config:
        print("❌ Could not set up Git configuration")
        return False
    
    print()
    
    # Set up credential helper
    setup_git_credential_helper(git_config)
    
    print()
    
    # Clone or pull repository
    if not clone_or_pull_repository(git_config, project_dir):
        print("❌ Could not clone/pull repository")
        return False
    
    print()
    
    # Show git info
    show_git_info(project_dir)
    
    print()
    
    # Copy files to chapters directory
    if copy_tex_files_to_chapters(project_dir):
        print()
        print("✅ Step 3 completed successfully!")
        print()
        print("🎯 What happened:")
        print("1. ✅ Set up Git authentication with your token")
        print("2. ✅ Cloned/pulled your Overleaf repository")
        print("3. ✅ Copied .tex files to chapters directory")
        print()
        print("📊 Next: Run change detection:")
        print("   python3 scripts/step2_change_detector.py")
        print()
        print("🔄 For future runs:")
        print("   - Credentials are saved securely")
        print("   - Git will automatically pull latest changes")
        print("   - Much faster than cloning each time")
        
        return True
    else:
        print()
        print("❌ Step 3 failed during file copying")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)