#!/usr/bin/env python3
"""
Step 3: Git Credential Setup Test
This script tests credential setup without performing actual Git clone/pull operations
"""

import os
import sys
import json
import logging
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Set up logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    return logging.getLogger(__name__)

def load_config_from_env():
    """Load configuration - simplified from previous steps"""
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github_actions:
        workspace = os.getenv('GITHUB_WORKSPACE', os.getcwd())
        config = {
            'environment': 'github_actions',
            'project_id': os.getenv('OVERLEAF_PROJECT_ID', '68428c5d41c2ef888f0b2a5e'),
            'git_username': os.getenv('OVERLEAF_GIT_USERNAME'),
            'git_token': os.getenv('OVERLEAF_GIT_TOKEN'),
            'script_dir': workspace,  # In GitHub Actions, we'd use workspace
        }
    else:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            config_file = os.path.join(script_dir, "data", "config.json")
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            config['script_dir'] = script_dir
            config['environment'] = 'local'
            
            # Load git credentials
            git_config_file = os.path.join(script_dir, "data", "git_config.json")
            if os.path.exists(git_config_file):
                with open(git_config_file, 'r') as f:
                    git_config = json.load(f)
                config['git_username'] = git_config.get('username')
                config['git_token'] = git_config.get('token')
                
        except Exception as e:
            return None, f"Error loading config: {e}"
    
    return config, None

def backup_existing_git_config(logger):
    """Backup existing Git configuration"""
    logger.info("   💾 Backing up existing Git configuration...")
    
    backup_info = {
        'credential_helper': None,
        'backup_created': False
    }
    
    try:
        # Get current credential helper
        result = subprocess.run([
            'git', 'config', '--global', '--get', 'credential.helper'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            backup_info['credential_helper'] = result.stdout.strip()
            logger.info(f"      🔍 Current credential helper: {backup_info['credential_helper']}")
            backup_info['backup_created'] = True
        else:
            logger.info("      ℹ️  No existing credential helper found")
            
    except Exception as e:
        logger.warning(f"      ⚠️  Could not backup Git config: {e}")
    
    return backup_info

def setup_credential_file(config, logger):
    """Set up credential file exactly like git_sync.py"""
    logger.info("   🔧 Setting up credential file...")
    
    try:
        script_dir = config['script_dir']
        credential_file = os.path.join(script_dir, "data", ".git-credentials")
        
        # Ensure data directory exists
        data_dir = os.path.dirname(credential_file)
        os.makedirs(data_dir, exist_ok=True)
        logger.info(f"      📁 Data directory: {data_dir}")
        
        # Create credential entry (exactly like git_sync.py)
        git_username = config['git_username']
        git_token = config['git_token']
        git_url_with_creds = f"https://{git_username}:{git_token}@git.overleaf.com"
        
        logger.info(f"      📝 Creating credential file: {credential_file}")
        with open(credential_file, 'w') as f:
            f.write(f"{git_url_with_creds}\\n")
        
        # Set secure permissions
        os.chmod(credential_file, 0o600)
        logger.info("      🔒 Set secure permissions (600)")
        
        # Verify file was created correctly
        if os.path.exists(credential_file):
            file_size = os.path.getsize(credential_file)
            logger.info(f"      ✅ Credential file created successfully ({file_size} bytes)")
            
            # Check permissions
            file_stat = os.stat(credential_file)
            permissions = oct(file_stat.st_mode)[-3:]
            logger.info(f"      🔍 File permissions: {permissions}")
            
            return credential_file
        else:
            logger.error("      ❌ Credential file was not created")
            return None
            
    except Exception as e:
        logger.error(f"      ❌ Error setting up credential file: {e}")
        return None

def configure_git_credential_helper(credential_file, logger):
    """Configure Git to use the credential file"""
    logger.info("   ⚙️  Configuring Git credential helper...")
    
    try:
        # Get absolute path for credential file
        abs_credential_file = os.path.abspath(credential_file)
        logger.info(f"      📍 Absolute credential file path: {abs_credential_file}")
        
        # Configure git to use this credential store
        helper_config = f'store --file={abs_credential_file}'
        
        result = subprocess.run([
            'git', 'config', '--global', 'credential.helper', helper_config
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("      ✅ Git credential helper configured successfully")
            logger.info(f"      🔧 Helper config: {helper_config}")
            return True
        else:
            logger.error(f"      ❌ Failed to configure credential helper: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"      ❌ Error configuring credential helper: {e}")
        return False

def verify_credential_setup(logger):
    """Verify the credential setup is working"""
    logger.info("   🧪 Verifying credential setup...")
    
    verification_results = {
        'helper_configured': False,
        'credential_file_exists': False,
        'git_config_readable': False,
        'helper_path_valid': False
    }
    
    try:
        # Check if credential helper is configured
        result = subprocess.run([
            'git', 'config', '--global', '--get', 'credential.helper'
        ], capture_output=True, text=True)
        
        if result.returncode == 0 and result.stdout.strip():
            helper_config = result.stdout.strip()
            logger.info(f"      ✅ Credential helper configured: {helper_config}")
            verification_results['helper_configured'] = True
            
            # Extract file path from helper config
            if '--file=' in helper_config:
                file_path = helper_config.split('--file=')[1]
                logger.info(f"      🔍 Credential file path: {file_path}")
                
                # Check if credential file exists
                if os.path.exists(file_path):
                    logger.info("      ✅ Credential file exists")
                    verification_results['credential_file_exists'] = True
                    verification_results['helper_path_valid'] = True
                    
                    # Check if file is readable
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                        
                        if 'git.overleaf.com' in content:
                            logger.info("      ✅ Credential file contains Overleaf URL")
                            verification_results['git_config_readable'] = True
                        else:
                            logger.warning("      ⚠️  Credential file doesn't contain Overleaf URL")
                            
                    except Exception as e:
                        logger.warning(f"      ⚠️  Could not read credential file: {e}")
                else:
                    logger.error(f"      ❌ Credential file does not exist: {file_path}")
            else:
                logger.warning("      ⚠️  Credential helper config doesn't specify file path")
        else:
            logger.error("      ❌ No credential helper configured")
            
    except Exception as e:
        logger.error(f"      ❌ Error verifying credential setup: {e}")
    
    return verification_results

def test_git_access_without_clone(config, logger):
    """Test Git access without actually cloning"""
    logger.info("   🌐 Testing Git access (without cloning)...")
    
    project_id = config['project_id']
    git_url = f"https://git.overleaf.com/{project_id}"
    
    try:
        # Test ls-remote to check if we can access the repository
        logger.info(f"      🔍 Testing access to: {git_url}")
        
        result = subprocess.run([
            'git', 'ls-remote', '--heads', git_url
        ], capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logger.info("      ✅ Git repository is accessible!")
            
            # Count remote branches
            if result.stdout.strip():
                branches = result.stdout.strip().split('\\n')
                logger.info(f"      📊 Found {len(branches)} remote branch(es)")
                for branch in branches:
                    if 'refs/heads/' in branch:
                        branch_name = branch.split('refs/heads/')[-1]
                        logger.info(f"         🌿 Branch: {branch_name}")
            
            return True
        else:
            logger.error(f"      ❌ Git repository access failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("      ❌ Git access test timed out")
        return False
    except Exception as e:
        logger.error(f"      ❌ Git access test error: {e}")
        return False

def restore_git_config(backup_info, logger):
    """Restore original Git configuration"""
    logger.info("   🔄 Restoring original Git configuration...")
    
    try:
        if backup_info['backup_created'] and backup_info['credential_helper']:
            subprocess.run([
                'git', 'config', '--global', 'credential.helper', backup_info['credential_helper']
            ], capture_output=True, text=True)
            logger.info(f"      ✅ Restored credential helper: {backup_info['credential_helper']}")
        else:
            # Remove the credential helper we set
            subprocess.run([
                'git', 'config', '--global', '--unset', 'credential.helper'
            ], capture_output=True, text=True)
            logger.info("      ✅ Removed test credential helper")
            
    except Exception as e:
        logger.warning(f"      ⚠️  Could not restore Git config: {e}")

def test_step3():
    """Test Step 3: Git Credential Setup"""
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("🧪 STEP 3 TEST: Git Credential Setup")
    logger.info("=" * 60)
    
    # Load configuration
    config, error = load_config_from_env()
    if error or not config:
        logger.error(f"❌ Configuration loading failed: {error}")
        return False
    
    logger.info(f"🔑 Testing credential setup for project: {config['project_id']}")
    logger.info("")
    
    # Backup existing Git config
    logger.info("📋 STEP 3.1: Backup Existing Git Configuration")
    backup_info = backup_existing_git_config(logger)
    logger.info("")
    
    try:
        # Step 3.2: Set up credential file
        logger.info("📋 STEP 3.2: Credential File Setup")
        credential_file = setup_credential_file(config, logger)
        if not credential_file:
            logger.error("❌ Failed to set up credential file")
            return False
        logger.info("")
        
        # Step 3.3: Configure Git credential helper
        logger.info("📋 STEP 3.3: Git Credential Helper Configuration")
        helper_configured = configure_git_credential_helper(credential_file, logger)
        if not helper_configured:
            logger.error("❌ Failed to configure credential helper")
            return False
        logger.info("")
        
        # Step 3.4: Verify credential setup
        logger.info("📋 STEP 3.4: Credential Setup Verification")
        verification_results = verify_credential_setup(logger)
        logger.info("")
        
        # Step 3.5: Test Git access
        logger.info("📋 STEP 3.5: Git Access Test")
        access_success = test_git_access_without_clone(config, logger)
        logger.info("")
        
        # Calculate overall success
        verification_score = sum(verification_results.values())
        max_verification_score = len(verification_results)
        
        logger.info("📊 STEP 3 SUMMARY:")
        logger.info(f"   Credential File: {'✅' if credential_file else '❌'}")
        logger.info(f"   Helper Configured: {'✅' if helper_configured else '❌'}")
        logger.info(f"   Verification Score: {verification_score}/{max_verification_score}")
        logger.info(f"   Git Access Test: {'✅' if access_success else '❌'}")
        logger.info("")
        
        step_passed = (credential_file and helper_configured and 
                      verification_score >= max_verification_score - 1 and access_success)
        
        if step_passed:
            logger.info("✅ STEP 3 PASSED: Credential setup is working!")
            logger.info("🎯 Next: Step 4 will test actual Git clone operation")
        else:
            logger.error("❌ STEP 3 FAILED: Credential setup issues detected")
            logger.error("🔧 Review the errors above before proceeding")
        
        return step_passed
        
    finally:
        # Always restore original Git config
        logger.info("📋 STEP 3.6: Cleanup")
        restore_git_config(backup_info, logger)

if __name__ == "__main__":
    success = test_step3()
    sys.exit(0 if success else 1)