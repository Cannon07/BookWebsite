#!/usr/bin/env python3
"""
Step 4: Git Clone Operation Test
This script tests the actual Git clone operation that was timing out in the pipeline
"""

import os
import sys
import json
import logging
import subprocess
import shutil
import time
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    config_file = os.path.join(script_dir, "data", "config.json")
    
    with open(config_file, 'r') as f:
        config = json.load(f)
    
    # Convert relative paths to absolute
    for key in ['project_dir', 'chapters_dir']:
        if key in config and config[key] and not os.path.isabs(config[key]):
            config[key] = os.path.join(project_root, config[key])
    
    config['script_dir'] = script_dir
    
    # Load git credentials
    git_config_file = os.path.join(script_dir, "data", "git_config.json")
    if os.path.exists(git_config_file):
        with open(git_config_file, 'r') as f:
            git_config = json.load(f)
        config['git_username'] = git_config.get('username')
        config['git_token'] = git_config.get('token')
    
    return config

def setup_credential_helper(config, logger):
    """Set up credential helper exactly like working git_sync.py"""
    logger.info("🔧 Setting up Git credential helper...")
    
    try:
        script_dir = config['script_dir']
        credential_file = os.path.join(script_dir, "data", ".git-credentials")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(credential_file), exist_ok=True)
        
        # Create credential entry
        git_username = config['git_username']
        git_token = config['git_token']
        git_url_with_creds = f"https://{git_username}:{git_token}@git.overleaf.com"
        
        with open(credential_file, 'w') as f:
            f.write(f"{git_url_with_creds}\\n")
        
        # Set secure permissions
        os.chmod(credential_file, 0o600)
        
        # Configure git to use this credential store
        abs_credential_file = os.path.abspath(credential_file)
        subprocess.run([
            'git', 'config', '--global', 'credential.helper', f'store --file={abs_credential_file}'
        ], check=True)
        
        logger.info("✅ Git credential helper configured")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error setting up credential helper: {e}")
        return False

def test_shallow_clone(config, test_dir, logger):
    """Test shallow clone (faster, less data)"""
    logger.info("🌱 Testing shallow clone (--depth 1)...")
    
    project_id = config['project_id']
    git_url = f"https://git.overleaf.com/{project_id}"
    
    start_time = time.time()
    
    try:
        result = subprocess.run([
            'git', 'clone', '--depth', '1', git_url, test_dir
        ], capture_output=True, text=True, timeout=60)  # Shorter timeout for shallow clone
        
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        
        if result.returncode == 0:
            logger.info(f"   ✅ Shallow clone succeeded in {duration}s")
            
            # Get repository info
            repo_size = get_directory_size(test_dir)
            file_count = count_files(test_dir)
            tex_count = count_tex_files(test_dir)
            
            logger.info(f"   📊 Repository size: {repo_size:.2f} MB")
            logger.info(f"   📄 Total files: {file_count}")
            logger.info(f"   📝 .tex files: {tex_count}")
            
            return True, duration, {
                'size_mb': repo_size,
                'file_count': file_count,
                'tex_count': tex_count
            }
        else:
            logger.error(f"   ❌ Shallow clone failed in {duration}s: {result.stderr}")
            return False, duration, None
            
    except subprocess.TimeoutExpired:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        logger.error(f"   ❌ Shallow clone timed out after {duration}s")
        return False, duration, None
    except Exception as e:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        logger.error(f"   ❌ Shallow clone error after {duration}s: {e}")
        return False, duration, None

def test_full_clone(config, test_dir, logger):
    """Test full clone with complete history"""
    logger.info("🌳 Testing full clone (complete history)...")
    
    project_id = config['project_id']
    git_url = f"https://git.overleaf.com/{project_id}"
    
    start_time = time.time()
    
    try:
        result = subprocess.run([
            'git', 'clone', git_url, test_dir
        ], capture_output=True, text=True, timeout=180)  # Longer timeout for full clone
        
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        
        if result.returncode == 0:
            logger.info(f"   ✅ Full clone succeeded in {duration}s")
            
            # Get repository info
            repo_size = get_directory_size(test_dir)
            file_count = count_files(test_dir)
            tex_count = count_tex_files(test_dir)
            
            logger.info(f"   📊 Repository size: {repo_size:.2f} MB")
            logger.info(f"   📄 Total files: {file_count}")
            logger.info(f"   📝 .tex files: {tex_count}")
            
            return True, duration, {
                'size_mb': repo_size,
                'file_count': file_count,
                'tex_count': tex_count
            }
        else:
            logger.error(f"   ❌ Full clone failed in {duration}s: {result.stderr}")
            return False, duration, None
            
    except subprocess.TimeoutExpired:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        logger.error(f"   ❌ Full clone timed out after {duration}s")
        return False, duration, None
    except Exception as e:
        end_time = time.time()
        duration = round(end_time - start_time, 2)
        logger.error(f"   ❌ Full clone error after {duration}s: {e}")
        return False, duration, None

def get_directory_size(directory):
    """Get directory size in MB"""
    total_size = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                total_size += os.path.getsize(file_path)
            except:
                pass
    return total_size / (1024 * 1024)  # Convert to MB

def count_files(directory):
    """Count total files in directory"""
    count = 0
    for root, dirs, files in os.walk(directory):
        count += len(files)
    return count

def count_tex_files(directory):
    """Count .tex files in directory"""
    count = 0
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.tex'):
                count += 1
    return count

def test_git_operations(test_dir, logger):
    """Test basic Git operations on cloned repository"""
    logger.info("🧪 Testing Git operations on cloned repository...")
    
    operations_results = {
        'status': False,
        'log': False,
        'remote': False,
        'branch': False
    }
    
    try:
        # Test git status
        result = subprocess.run([
            'git', '-C', test_dir, 'status', '--porcelain'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("   ✅ git status: Working")
            operations_results['status'] = True
        
        # Test git log
        result = subprocess.run([
            'git', '-C', test_dir, 'log', '--oneline', '-5'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("   ✅ git log: Working")
            operations_results['log'] = True
            
            # Show recent commits
            commits = result.stdout.strip().split('\\n')
            logger.info(f"   📝 Recent commits: {len(commits)}")
        
        # Test git remote
        result = subprocess.run([
            'git', '-C', test_dir, 'remote', '-v'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("   ✅ git remote: Working")
            operations_results['remote'] = True
        
        # Test git branch
        result = subprocess.run([
            'git', '-C', test_dir, 'branch'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("   ✅ git branch: Working")
            operations_results['branch'] = True
        
    except Exception as e:
        logger.warning(f"   ⚠️  Git operations test error: {e}")
    
    return operations_results

def cleanup_test_directory(test_dir, logger):
    """Clean up test directory"""
    if os.path.exists(test_dir):
        try:
            shutil.rmtree(test_dir)
            logger.info(f"   🗑️  Cleaned up test directory: {test_dir}")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not clean up test directory: {e}")

def test_step4():
    """Test Step 4: Git Clone Operations"""
    logger = setup_logging()
    
    logger.info("=" * 60)
    logger.info("🧪 STEP 4 TEST: Git Clone Operation")
    logger.info("=" * 60)
    
    # Load configuration
    config = load_config_from_env()
    project_id = config['project_id']
    
    logger.info(f"📥 Testing Git clone for project: {project_id}")
    logger.info("")
    
    # Set up credentials
    logger.info("📋 STEP 4.1: Credential Setup")
    if not setup_credential_helper(config, logger):
        logger.error("❌ Failed to set up credentials")
        return False
    logger.info("")
    
    # Create test directories
    test_base = os.path.join(os.path.dirname(config['project_dir']), 'clone_test')
    shallow_test_dir = os.path.join(test_base, 'shallow_clone')
    full_test_dir = os.path.join(test_base, 'full_clone')
    
    # Clean up any existing test directories
    for test_dir in [shallow_test_dir, full_test_dir]:
        cleanup_test_directory(test_dir, logger)
    
    os.makedirs(test_base, exist_ok=True)
    
    results = {
        'shallow_clone': {'success': False, 'duration': 0, 'info': None},
        'full_clone': {'success': False, 'duration': 0, 'info': None},
        'git_operations': {'success': False, 'results': None}
    }
    
    try:
        # Test shallow clone
        logger.info("📋 STEP 4.2: Shallow Clone Test")
        success, duration, info = test_shallow_clone(config, shallow_test_dir, logger)
        results['shallow_clone'] = {'success': success, 'duration': duration, 'info': info}
        logger.info("")
        
        if success:
            # Test Git operations on shallow clone
            logger.info("📋 STEP 4.3: Git Operations Test (Shallow Clone)")
            operations = test_git_operations(shallow_test_dir, logger)
            results['git_operations'] = {'success': all(operations.values()), 'results': operations}
            logger.info("")
        
        # Test full clone
        logger.info("📋 STEP 4.4: Full Clone Test")
        success, duration, info = test_full_clone(config, full_test_dir, logger)
        results['full_clone'] = {'success': success, 'duration': duration, 'info': info}
        logger.info("")
        
        # Summary
        logger.info("📊 STEP 4 SUMMARY:")
        logger.info(f"   Shallow Clone: {'✅' if results['shallow_clone']['success'] else '❌'} ({results['shallow_clone']['duration']}s)")
        logger.info(f"   Full Clone: {'✅' if results['full_clone']['success'] else '❌'} ({results['full_clone']['duration']}s)")
        logger.info(f"   Git Operations: {'✅' if results['git_operations']['success'] else '❌'}")
        
        if results['shallow_clone']['info']:
            info = results['shallow_clone']['info']
            logger.info(f"   Repository Size: {info['size_mb']:.2f} MB")
            logger.info(f"   .tex Files Found: {info['tex_count']}")
        
        logger.info("")
        
        # Determine overall success
        step_passed = (results['shallow_clone']['success'] or results['full_clone']['success'])
        
        if step_passed:
            logger.info("✅ STEP 4 PASSED: Git clone operations are working!")
            logger.info("🎯 Next: Step 5 will test file copying and change detection")
            
            # Provide recommendations
            if results['shallow_clone']['success'] and results['shallow_clone']['duration'] < 60:
                logger.info("💡 RECOMMENDATION: Use shallow clone for faster performance")
            elif results['full_clone']['success']:
                logger.info("💡 RECOMMENDATION: Use full clone (shallow clone may have issues)")
            
        else:
            logger.error("❌ STEP 4 FAILED: Git clone operations are not working")
            logger.error("🔧 Check network connectivity and repository access")
        
        return step_passed
        
    finally:
        # Clean up test directories
        logger.info("📋 STEP 4.5: Cleanup")
        cleanup_test_directory(shallow_test_dir, logger)
        cleanup_test_directory(full_test_dir, logger)
        cleanup_test_directory(test_base, logger)

if __name__ == "__main__":
    success = test_step4()
    sys.exit(0 if success else 1)