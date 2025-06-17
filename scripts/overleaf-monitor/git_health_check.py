#!/usr/bin/env python3
"""
Step 2: Git Repository Health Check Test
This script tests repository detection and health validation without performing Git operations
"""

import os
import sys
import json
import logging
import subprocess
import shutil
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

def mask_sensitive_data(value, show_chars=4):
    """Mask sensitive data for logging"""
    if not value or len(value) <= show_chars:
        return "***"
    return value[:show_chars] + "***" + value[-2:]

def load_config_from_env():
    """Load configuration - simplified from Step 1"""
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github_actions:
        workspace = os.getenv('GITHUB_WORKSPACE', os.getcwd())
        config = {
            'environment': 'github_actions',
            'project_id': os.getenv('OVERLEAF_PROJECT_ID', '68428c5d41c2ef888f0b2a5e'),
            'project_dir': os.path.join(workspace, 'overleaf-project'),
            'chapters_dir': os.path.join(workspace, 'chapters'),
            'git_username': os.getenv('OVERLEAF_GIT_USERNAME'),
            'git_token': os.getenv('OVERLEAF_GIT_TOKEN'),
        }
    else:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            config_file = os.path.join(script_dir, "data", "config.json")
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            # Convert relative paths to absolute
            for key in ['project_dir', 'chapters_dir']:
                if key in config and config[key] and not os.path.isabs(config[key]):
                    config[key] = os.path.join(project_root, config[key])
            
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

def check_directory_exists(path, logger):
    """Check if directory exists and get info"""
    logger.info(f"   📁 Checking directory: {path}")
    
    if not os.path.exists(path):
        logger.info("      ❌ Directory does not exist")
        return {
            'exists': False,
            'is_directory': False,
            'is_git_repo': False,
            'status': 'missing'
        }
    
    if not os.path.isdir(path):
        logger.warning("      ⚠️  Path exists but is not a directory")
        return {
            'exists': True,
            'is_directory': False,
            'is_git_repo': False,
            'status': 'not_directory'
        }
    
    logger.info("      ✅ Directory exists")
    
    # Check if it's a git repository
    git_dir = os.path.join(path, '.git')
    if os.path.exists(git_dir):
        logger.info("      ✅ .git directory found")
        return {
            'exists': True,
            'is_directory': True,
            'is_git_repo': True,
            'git_dir': git_dir,
            'status': 'git_repo'
        }
    else:
        logger.info("      ⚠️  No .git directory found")
        return {
            'exists': True,
            'is_directory': True,
            'is_git_repo': False,
            'status': 'not_git_repo'
        }

def check_git_health(project_dir, logger):
    """Check Git repository health"""
    logger.info(f"   🏥 Running Git health check...")
    
    health_results = {
        'can_run_status': False,
        'status_clean': False,
        'has_commits': False,
        'remote_configured': False,
        'health_score': 0
    }
    
    try:
        # Test 1: Can we run git status?
        logger.info("      🧪 Test 1: Git status check...")
        result = subprocess.run([
            'git', '-C', project_dir, 'status', '--porcelain'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("         ✅ Git status command succeeded")
            health_results['can_run_status'] = True
            health_results['health_score'] += 25
            
            # Check if working directory is clean
            if not result.stdout.strip():
                logger.info("         ✅ Working directory is clean")
                health_results['status_clean'] = True
                health_results['health_score'] += 25
            else:
                logger.info("         ⚠️  Working directory has uncommitted changes")
                logger.info(f"         Changes: {len(result.stdout.strip().split())} files")
        else:
            logger.error(f"         ❌ Git status failed: {result.stderr}")
            return health_results
        
        # Test 2: Check if repository has commits
        logger.info("      🧪 Test 2: Commit history check...")
        result = subprocess.run([
            'git', '-C', project_dir, 'log', '--oneline', '-1'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            logger.info("         ✅ Repository has commit history")
            health_results['has_commits'] = True
            health_results['health_score'] += 25
            
            # Show latest commit
            commit_info = result.stdout.strip()
            logger.info(f"         Latest commit: {commit_info}")
        else:
            logger.warning("         ⚠️  No commits found or git log failed")
        
        # Test 3: Check remote configuration
        logger.info("      🧪 Test 3: Remote configuration check...")
        result = subprocess.run([
            'git', '-C', project_dir, 'remote', '-v'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout.strip():
            logger.info("         ✅ Remote repositories configured")
            health_results['remote_configured'] = True
            health_results['health_score'] += 25
            
            # Show remotes
            remotes = result.stdout.strip().split('\n')
            for remote in remotes:
                if 'git.overleaf.com' in remote:
                    logger.info(f"         📡 {remote}")
        else:
            logger.warning("         ⚠️  No remote repositories configured")
            
    except subprocess.TimeoutExpired:
        logger.error("      ❌ Git health check timed out")
    except Exception as e:
        logger.error(f"      ❌ Git health check error: {e}")
    
    return health_results

def get_repository_info(project_dir, logger):
    """Get additional repository information"""
    logger.info("   📊 Gathering repository information...")
    
    repo_info = {}
    
    try:
        # Get repository size
        if os.path.exists(project_dir):
            total_size = 0
            file_count = 0
            tex_count = 0
            
            for root, dirs, files in os.walk(project_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        
                        if file.endswith('.tex'):
                            tex_count += 1
                    except:
                        pass
            
            repo_info['total_size_mb'] = round(total_size / (1024 * 1024), 2)
            repo_info['file_count'] = file_count
            repo_info['tex_file_count'] = tex_count
            
            logger.info(f"      📁 Repository size: {repo_info['total_size_mb']} MB")
            logger.info(f"      📄 Total files: {repo_info['file_count']}")
            logger.info(f"      📝 .tex files: {repo_info['tex_file_count']}")
    
    except Exception as e:
        logger.warning(f"      ⚠️  Could not gather repository info: {e}")
    
    return repo_info

def determine_required_action(dir_check, health_results, logger):
    """Determine what action is needed based on checks"""
    logger.info("   🎯 Determining required action...")
    
    if not dir_check['exists']:
        action = 'clone_new'
        reason = 'Directory does not exist'
    elif not dir_check['is_directory']:
        action = 'backup_and_clone'
        reason = 'Path exists but is not a directory'
    elif not dir_check['is_git_repo']:
        action = 'backup_and_clone'
        reason = 'Directory exists but is not a Git repository'
    elif not health_results['can_run_status']:
        action = 'backup_and_clone'
        reason = 'Git repository is corrupted (cannot run git status)'
    elif health_results['health_score'] >= 75:
        action = 'pull_updates'
        reason = f'Repository is healthy (score: {health_results["health_score"]}/100)'
    elif health_results['health_score'] >= 50:
        action = 'pull_updates_cautious'
        reason = f'Repository has issues but may be recoverable (score: {health_results["health_score"]}/100)'
    else:
        action = 'backup_and_clone'
        reason = f'Repository is unhealthy (score: {health_results["health_score"]}/100)'
    
    logger.info(f"      🎯 Recommended action: {action}")
    logger.info(f"      📝 Reason: {reason}")
    
    return {
        'action': action,
        'reason': reason,
        'health_score': health_results.get('health_score', 0)
    }

def test_step2():
    """Test Step 2: Git Repository Health Check"""
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("🧪 STEP 2 TEST: Git Repository Health Check")
    logger.info("=" * 60)
    
    # Load configuration
    config, error = load_config_from_env()
    if error or not config:
        logger.error(f"❌ Configuration loading failed: {error}")
        return False
    
    project_dir = config['project_dir']
    logger.info(f"🔍 Checking Git repository health for: {project_dir}")
    logger.info("")
    
    # Step 2.1: Check directory existence and type
    logger.info("📋 STEP 2.1: Directory Existence Check")
    dir_check = check_directory_exists(project_dir, logger)
    logger.info("")
    
    # Step 2.2: Git health check (if it's a Git repo)
    logger.info("📋 STEP 2.2: Git Health Check")
    if dir_check['is_git_repo']:
        health_results = check_git_health(project_dir, logger)
    else:
        logger.info("   ⏭️  Skipping Git health check (not a Git repository)")
        health_results = {
            'can_run_status': False,
            'status_clean': False,
            'has_commits': False,
            'remote_configured': False,
            'health_score': 0
        }
    logger.info("")
    
    # Step 2.3: Repository information
    logger.info("📋 STEP 2.3: Repository Information")
    repo_info = get_repository_info(project_dir, logger)
    logger.info("")
    
    # Step 2.4: Determine required action
    logger.info("📋 STEP 2.4: Action Determination")
    action_plan = determine_required_action(dir_check, health_results, logger)
    logger.info("")
    
    # Summary
    logger.info("📊 STEP 2 SUMMARY:")
    logger.info(f"   Directory Status: {dir_check['status']}")
    logger.info(f"   Git Health Score: {health_results['health_score']}/100")
    logger.info(f"   Recommended Action: {action_plan['action']}")
    logger.info(f"   Files Found: {repo_info.get('file_count', 'N/A')}")
    logger.info(f"   .tex Files: {repo_info.get('tex_file_count', 'N/A')}")
    logger.info("")
    
    # Determine if step passed
    step_passed = True
    
    if action_plan['action'] in ['clone_new', 'backup_and_clone']:
        logger.info("✅ STEP 2 PASSED: Repository needs fresh setup - this is expected")
        logger.info("🎯 Next: Step 3 will handle credential setup and cloning")
    elif action_plan['action'] in ['pull_updates', 'pull_updates_cautious']:
        logger.info("✅ STEP 2 PASSED: Repository exists and can be updated")
        logger.info("🎯 Next: Step 3 will handle credential setup and pulling")
    else:
        logger.error("❌ STEP 2 FAILED: Unexpected action recommendation")
        step_passed = False
    
    return step_passed

if __name__ == "__main__":
    success = test_step2()
    sys.exit(0 if success else 1)