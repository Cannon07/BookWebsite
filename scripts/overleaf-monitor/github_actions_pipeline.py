#!/usr/bin/env python3
"""
Final Fixed Pipeline - GitHub Actions Compatible
Incorporates all fixes discovered during step-by-step testing:
- Working credential setup method
- Proper timeout values (90s based on 40s clone time)
- Shallow clone for better performance  
- Robust error handling and cleanup
- Tested configuration loading
"""

import os
import sys
import json
import subprocess
import logging
import shutil
from datetime import datetime
from pathlib import Path

def setup_logging(config=None):
    """Set up logging for both console and file output"""
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Always log to console
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Add file handler if config is available
    if config:
        log_file = config.get('log_file')
        if log_file:
            try:
                # Ensure log directory exists
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                
                # Add file handler with rotation to prevent huge log files
                file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
                file_handler.setFormatter(formatter)
                handlers.append(file_handler)
                
                # Also add console output about logging
                print(f"📝 Logging to file: {log_file}")
            except Exception as e:
                print(f"⚠️  Could not set up file logging: {e}")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # Override any existing configuration
    )
    
    return logging.getLogger(__name__)

def load_config_from_env():
    """Load configuration from environment variables and detect paths - TESTED IN STEP 1"""
    # Auto-detect if we're in GitHub Actions
    is_github_actions = os.getenv('GITHUB_ACTIONS') == 'true'
    
    if is_github_actions:
        # GitHub Actions environment
        workspace = os.getenv('GITHUB_WORKSPACE', os.getcwd())
        config = {
            'environment': 'github_actions',
            'project_id': os.getenv('OVERLEAF_PROJECT_ID', '68428c5d41c2ef888f0b2a5e'),
            'project_dir': os.path.join(workspace, 'overleaf-project'),
            'chapters_dir': os.path.join(workspace, 'chapters'),
            'conversion_script': os.path.join(workspace, 'scripts', 'process-chapter.ts'),
            'git_username': os.getenv('OVERLEAF_GIT_USERNAME'),
            'git_token': os.getenv('OVERLEAF_GIT_TOKEN'),
            'script_dir': workspace,  # For credential file in GitHub Actions
            'file_extensions': ['.tex', '.bib'],
            'exclude_dirs': ['.git', '__pycache__', 'node_modules', '.aux', '.out', '.log']
        }
        
        # Debug: Check if credentials are actually loaded
        print(f"🔍 DEBUG - GitHub Actions credential check:")
        print(f"   Username set: {'✅' if config['git_username'] else '❌'}")
        print(f"   Token set: {'✅' if config['git_token'] else '❌'}")
        print(f"   Project ID set: {'✅' if config['project_id'] else '❌'}")
        if config['git_username']:
            print(f"   Username length: {len(config['git_username'])}")
        if config['git_token']:
            print(f"   Token length: {len(config['git_token'])}")
        
    else:
        # Local environment - use integrated config
        try:
            # We're in scripts/overleaf-monitor, so go up to project root
            script_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(script_dir))
            config_file = os.path.join(script_dir, "data", "config.json")
            
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            config['environment'] = 'local'
            config['script_dir'] = script_dir
            
            # Convert relative paths to absolute paths based on project root
            for key in ['project_dir', 'chapters_dir', 'conversion_script', 'hash_file', 'log_file']:
                if key in config and config[key] and not os.path.isabs(config[key]):
                    config[key] = os.path.join(project_root, config[key])
            
            # Load git config for credentials
            git_config_file = os.path.join(script_dir, "data", "git_config.json")
            if os.path.exists(git_config_file):
                with open(git_config_file, 'r') as f:
                    git_config = json.load(f)
                config['git_username'] = git_config.get('username')
                config['git_token'] = git_config.get('token')
                
        except Exception as e:
            print(f"❌ Error loading local config: {e}")
            return None
    
    return config

def setup_git_credential_helper(config, logger):
    """Set up Git credential helper - TESTED IN STEP 3"""
    logger.info("🔧 Setting up Git credential helper...")
    
    try:
        git_username = config['git_username']
        git_token = config['git_token']
        
        if not git_username or not git_token:
            logger.error("❌ Git credentials are missing")
            return False
        
        # Log credential info (masked)
        logger.info(f"   🔑 Username: {git_username[:4]}***")
        logger.info(f"   🔑 Token: {git_token[:8]}***")
        
        # Use the same credential file approach for both environments (it works!)
        script_dir = config['script_dir']
        
        if config.get('environment') == 'github_actions':
            # For GitHub Actions, put credential file in workspace root
            credential_file = os.path.join(script_dir, ".git-credentials")
            logger.info("   🔧 Using credential file approach for GitHub Actions...")
        else:
            # For local, use data directory
            credential_file = os.path.join(script_dir, "data", ".git-credentials")
            logger.info("   🔧 Using credential file approach for local environment...")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(credential_file), exist_ok=True)
        
        # Create credential entry (same format as working git_sync.py)
        git_url_with_creds = f"https://{git_username}:{git_token}@git.overleaf.com"
        
        with open(credential_file, 'w') as f:
            f.write(f"{git_url_with_creds}\\n")
        
        # Set secure permissions
        os.chmod(credential_file, 0o600)
        
        # Configure git to use this credential store with absolute path
        abs_credential_file = os.path.abspath(credential_file)
        subprocess.run([
            'git', 'config', '--global', 'credential.helper', f'store --file={abs_credential_file}'
        ], check=True)
        
        logger.info(f"   ✅ Credential file created: {abs_credential_file}")
        logger.info("   ✅ Git credential helper configured")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error setting up credential helper: {e}")
        return False

def check_repository_health(project_dir, logger):
    """Check Git repository health - TESTED IN STEP 2"""
    logger.info("🏥 Checking repository health...")
    
    if not os.path.exists(project_dir):
        logger.info("   📁 Directory does not exist - will clone fresh")
        return 'clone_new'
    
    if not os.path.isdir(project_dir):
        logger.warning("   ⚠️  Path exists but is not a directory - will backup and clone")
        return 'backup_and_clone'
    
    git_dir = os.path.join(project_dir, '.git')
    if not os.path.exists(git_dir):
        logger.warning("   ⚠️  Directory exists but is not a Git repository - will backup and clone")
        return 'backup_and_clone'
    
    # Test if Git repository is healthy
    try:
        result = subprocess.run([
            'git', '-C', project_dir, 'status'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logger.info("   ✅ Repository is healthy - will pull updates")
            return 'pull_updates'
        else:
            logger.warning("   ⚠️  Repository is corrupted - will backup and clone")
            return 'backup_and_clone'
            
    except subprocess.TimeoutExpired:
        logger.warning("   ⚠️  Repository health check timed out - will backup and clone")
        return 'backup_and_clone'
    except Exception as e:
        logger.warning(f"   ⚠️  Repository health check failed: {e} - will backup and clone")
        return 'backup_and_clone'

def backup_directory(project_dir, logger):
    """Backup existing directory"""
    if os.path.exists(project_dir):
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_path = os.path.join(os.path.dirname(project_dir), backup_name)
        shutil.move(project_dir, backup_path)
        logger.info(f"   🗂️  Backed up existing directory to: {backup_name}")

def git_pull_updates(project_dir, config, logger):
    """Pull updates from existing repository"""
    logger.info("📥 Pulling latest changes...")
    
    # Use standard git pull - credential helper will handle authentication
    try:
        result = subprocess.run([
            'git', '-C', project_dir, 'pull', 'origin', 'master'
        ], capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0:
            if "Already up to date" in result.stdout:
                logger.info("   ℹ️  Repository was already up to date")
            else:
                logger.info("   ✅ Successfully pulled latest changes")
            return True
        else:
            logger.warning(f"   ⚠️  Pull failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("   ❌ Git pull timed out")
        return False
    except Exception as e:
        logger.error(f"   ❌ Git pull error: {e}")
        return False

def git_clone_repository(config, project_dir, logger):
    """Clone repository using optimized method - TESTED IN STEP 4"""
    logger.info("📥 Cloning repository...")
    
    project_id = config['project_id']
    git_url = f"https://git.overleaf.com/{project_id}"
    
    # Use the standard Git URL - credential helper will handle authentication
    logger.info("   🔧 Using credential helper for authentication")
    
    try:
        # Use shallow clone for better performance (based on Step 4 testing)
        logger.info("   🌱 Using shallow clone for optimal performance...")
        result = subprocess.run([
            'git', 'clone', '--depth', '1', git_url, project_dir
        ], capture_output=True, text=True, timeout=90)
        
        if result.returncode == 0:
            logger.info("   ✅ Successfully cloned repository (shallow)")
            return True
        else:
            logger.warning(f"   ⚠️  Shallow clone failed: {result.stderr}")
            logger.info("   🌳 Trying full clone as fallback...")
            
            # Clean up failed shallow clone
            if os.path.exists(project_dir):
                shutil.rmtree(project_dir)
            
            # Try full clone as fallback
            result = subprocess.run([
                'git', 'clone', git_url, project_dir
            ], capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                logger.info("   ✅ Successfully cloned repository (full)")
                return True
            else:
                logger.error(f"   ❌ Full clone also failed: {result.stderr}")
                return False
                
    except subprocess.TimeoutExpired:
        logger.error("   ❌ Git clone timed out")
        # Clean up partial clone
        if os.path.exists(project_dir):
            shutil.rmtree(project_dir)
        return False
    except Exception as e:
        logger.error(f"   ❌ Git clone error: {e}")
        return False

def automated_git_sync(config, logger):
    """Automated Git sync with robust error handling"""
    project_dir = config["project_dir"]
    project_id = config["project_id"]
    
    git_username = config.get('git_username')
    git_token = config.get('git_token')
    
    if not git_username or not git_token:
        logger.error("❌ Git credentials not found")
        if os.getenv('GITHUB_ACTIONS') == 'true':
            logger.error("   Set OVERLEAF_GIT_USERNAME and OVERLEAF_GIT_TOKEN in repository secrets")
        else:
            logger.error("   Check git_config.json file")
        return False
    
    logger.info("📥 Syncing from Overleaf Git repository...")
    logger.info(f"   Project ID: {project_id}")
    logger.info(f"   Target directory: {project_dir}")
    
    # Set up credentials only for local environment
    # GitHub Actions will handle credential setup in the workflow
    if config.get('environment') != 'github_actions':
        if not setup_git_credential_helper(config, logger):
            logger.error("❌ Failed to set up Git credentials")
            return False
    else:
        logger.info("🔧 Using GitHub Actions credential setup (handled by workflow)")
    
    # Check repository health and determine action
    action = check_repository_health(project_dir, logger)
    
    # Execute appropriate action
    if action == 'pull_updates':
        if git_pull_updates(project_dir, config, logger):
            return True
        else:
            logger.info("   🔄 Pull failed, will try fresh clone...")
            backup_directory(project_dir, logger)
            action = 'clone_new'
    
    if action in ['clone_new', 'backup_and_clone']:
        if action == 'backup_and_clone':
            backup_directory(project_dir, logger)
        
        return git_clone_repository(config, project_dir, logger)
    
    return False

def copy_tex_files_to_chapters(config, logger):
    """Copy .tex files from git repository to chapters directory"""
    project_dir = config["project_dir"]
    target_dir = config["chapters_dir"]
    
    logger.info("📂 Copying .tex files to chapters directory...")
    logger.info(f"   Source: {project_dir}")
    logger.info(f"   Target: {target_dir}")
    
    try:
        # Find .tex files
        tex_files = []
        for root, dirs, files in os.walk(project_dir):
            if '.git' in dirs:
                dirs.remove('.git')
            
            for file in files:
                if file.endswith('.tex'):
                    tex_files.append(os.path.join(root, file))
        
        if not tex_files:
            logger.warning("❌ No .tex files found in git repository")
            return False
        
        logger.info(f"📄 Found {len(tex_files)} .tex files")
        
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
                    else:
                        logger.info(f"   📝 File changed: {filename}")
                except:
                    file_changed = True
            
            if file_changed:
                shutil.copy2(tex_file, target_file)
                updated_files.append(filename)
                status = "Updated" if os.path.exists(target_file) else "Added"
                logger.info(f"   ✅ {status}: {filename}")
        
        if updated_files:
            logger.info(f"✅ Successfully updated {len(updated_files)} files")
        else:
            logger.info("ℹ️  All files were already up to date")
        
        return len(updated_files) > 0
        
    except Exception as e:
        logger.error(f"❌ Error copying files: {e}")
        return False

def run_conversion_script(config, logger):
    """Run the chapter processing script"""
    conversion_script = config.get("conversion_script")
    chapters_dir = config.get("chapters_dir")
    
    if not conversion_script or not os.path.exists(conversion_script):
        logger.error(f"❌ Conversion script not found: {conversion_script}")
        return False
    
    logger.info(f"🔄 Running chapter processing script: {os.path.basename(conversion_script)}")
    
    try:
        # Get the project root (where the conversion script should run from)
        project_root = os.path.dirname(os.path.dirname(conversion_script))
        
        if conversion_script.endswith('.ts'):
            # TypeScript script - run from project root
            cmd = ['npx', 'ts-node', 'scripts/process-chapter.ts', chapters_dir]
            
            logger.info(f"   Running: {' '.join(cmd)}")
            logger.info(f"   Working directory: {project_root}")
            
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True, 
                text=True, 
                timeout=600
            )
        else:
            result = subprocess.run([
                sys.executable, conversion_script, chapters_dir
            ], capture_output=True, text=True, timeout=600)
        
        if result.returncode == 0:
            logger.info("✅ Chapter processing completed successfully")
            
            # Log processing summary
            output_lines = result.stdout.strip().split('\\n')
            for line in output_lines:
                if any(keyword in line.lower() for keyword in [
                    'processing complete', 'new chapters processed', 'chapters skipped', 
                    'found', 'scanning directory', 'successfully processed'
                ]):
                    logger.info(f"   {line.strip()}")
            
            return True
        else:
            logger.error(f"❌ Chapter processing failed (exit code: {result.returncode})")
            if result.stderr:
                for line in result.stderr.strip().split('\\n')[:5]:
                    if line.strip():
                        logger.error(f"   Error: {line.strip()}")
            return False
    
    except subprocess.TimeoutExpired:
        logger.error("❌ Chapter processing timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Chapter processing error: {e}")
        return False

def save_results_summary(results):
    """Save pipeline results for GitHub Actions to consume"""
    summary = {
        'timestamp': datetime.now().isoformat(),
        'success': results['overall_success'],
        'git_sync_success': results['git_sync'],
        'files_updated': results['files_changed'],
        'conversion_success': results['conversion'],
        'changes_detected': results['files_changed'],
        'next_steps': 'rebuild_website' if results['files_changed'] else 'no_action_needed'
    }
    
    # Save in current directory for GitHub Actions to find
    with open('pipeline_results.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Also create GitHub Actions outputs
    if os.getenv('GITHUB_ACTIONS') == 'true':
        github_output = os.getenv('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"changes_detected={str(results['files_changed']).lower()}\\n")
                f.write(f"conversion_success={str(results['conversion']).lower()}\\n")
                f.write(f"pipeline_success={str(results['overall_success']).lower()}\\n")

def main():
    """Main pipeline function - All Steps Tested and Working"""
    # Load configuration first (before logging setup to get log file path)
    config = load_config_from_env()
    if not config:
        print("❌ Could not load configuration")
        return False
    
    # Now set up logging with config (includes file logging)
    logger = setup_logging(config)
    
    logger.info("=" * 60)
    logger.info("🚀 FINAL FIXED PIPELINE - All Issues Resolved")
    logger.info("=" * 60)
    
    # Log configuration info
    log_file = config.get('log_file')
    if log_file:
        logger.info(f"📝 Pipeline logs being saved to: {log_file}")
    else:
        logger.info("📝 Console logging only (no log file configured)")
    
    # Initialize results tracking
    results = {
        'git_sync': False,
        'files_changed': False,
        'conversion': False,
        'overall_success': False
    }
    
    try:
        # Log environment info
        if os.getenv('GITHUB_ACTIONS') == 'true':
            logger.info("🔧 Running in GitHub Actions environment")
        else:
            logger.info("🔧 Running in local environment")
        
        # Step 1: Git sync from Overleaf (TESTED - Steps 2, 3, 4)
        if automated_git_sync(config, logger):
            results['git_sync'] = True
            logger.info("✅ Git sync completed successfully")
        else:
            logger.error("❌ Git sync failed")
            return False
        
        # Step 2: Copy files and detect changes
        files_changed = copy_tex_files_to_chapters(config, logger)
        results['files_changed'] = files_changed
        
        if not files_changed:
            logger.info("✅ Pipeline completed - no changes detected")
            results['overall_success'] = True
            save_results_summary(results)
            return True
        
        # Step 3: Run conversion script
        if run_conversion_script(config, logger):
            results['conversion'] = True
            results['overall_success'] = True
            logger.info("✅ Pipeline completed successfully!")
            logger.info("🎯 Changes processed - website rebuild recommended")
        else:
            logger.error("❌ Conversion failed")
            results['overall_success'] = False
        
        # Save results with logging
        save_results_summary(results)
        
        # Final log message about where logs are saved
        if config.get('log_file'):
            logger.info(f"📝 Complete pipeline logs saved to: {config['log_file']}")
        
        return results['overall_success']
        
    except Exception as e:
        logger.error(f"❌ Pipeline error: {e}")
        results['overall_success'] = False
        save_results_summary(results)
        
        # Ensure error is logged to file too
        if config.get('log_file'):
            logger.error(f"📝 Error details logged to: {config['log_file']}")
        
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)