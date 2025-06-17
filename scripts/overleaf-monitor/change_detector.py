#!/usr/bin/env python3
"""
Step 2: Hash-based Change Detector for Overleaf Files
This script detects changes in .tex files by comparing SHA256 hashes
"""

import os
import json
import hashlib
import sys
from datetime import datetime
from pathlib import Path

# Auto-detect the base directory (where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)  # Go up one level from scripts/ to base
CONFIG_FILE = os.path.join(BASE_DIR, "data", "config.json")

def load_config():
    """Load configuration from config.json"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        print(f"   Make sure {CONFIG_FILE} exists and is valid JSON")
        return None

def calculate_file_hash(filepath):
    """Calculate SHA256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return None

def should_monitor_file(filepath, config):
    """Check if file should be monitored based on config"""
    # Check file extension
    file_ext = os.path.splitext(filepath)[1]
    if file_ext not in config.get('file_extensions', ['.tex']):
        return False
    
    # Check if in excluded directory
    relative_path = filepath
    for exclude_dir in config.get('exclude_dirs', []):
        if exclude_dir in relative_path:
            return False
    
    return True

def scan_directory_for_files(directory, config):
    """Scan directory for files to monitor"""
    monitored_files = {}
    file_count = 0
    
    if not os.path.exists(directory):
        print(f"❌ Directory doesn't exist: {directory}")
        return monitored_files
    
    print(f"🔍 Scanning directory: {directory}")
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in config.get('exclude_dirs', [])]
        
        for file in files:
            filepath = os.path.join(root, file)
            
            if should_monitor_file(filepath, config):
                relative_path = os.path.relpath(filepath, directory)
                file_hash = calculate_file_hash(filepath)
                
                if file_hash:
                    file_stats = os.stat(filepath)
                    monitored_files[relative_path] = {
                        'hash': file_hash,
                        'size': file_stats.st_size,
                        'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                        'full_path': filepath
                    }
                    file_count += 1
                    print(f"   📄 Found: {relative_path}")
    
    print(f"✅ Found {file_count} files to monitor")
    return monitored_files

def load_previous_hashes(config):
    """Load previously stored hashes"""
    hash_file = config['hash_file']
    try:
        with open(hash_file, 'r') as f:
            data = json.load(f)
            print(f"📋 Loaded previous hashes for {len(data.get('hashes', {}))} files")
            return data
    except FileNotFoundError:
        print("ℹ️  No previous hash file found (first run)")
        return {'hashes': {}, 'timestamp': None, 'file_count': 0}
    except Exception as e:
        print(f"❌ Error loading previous hashes: {e}")
        return {'hashes': {}, 'timestamp': None, 'file_count': 0}

def save_hashes(current_hashes, config):
    """Save current hashes to file"""
    hash_file = config['hash_file']
    data = {
        'timestamp': datetime.now().isoformat(),
        'file_count': len(current_hashes),
        'hashes': current_hashes
    }
    
    try:
        os.makedirs(os.path.dirname(hash_file), exist_ok=True)
        with open(hash_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"💾 Saved hashes for {len(current_hashes)} files")
        return True
    except Exception as e:
        print(f"❌ Error saving hashes: {e}")
        return False

def analyze_changes(current_hashes, previous_data):
    """Analyze changes between current and previous hashes"""
    previous_hashes = previous_data.get('hashes', {})
    
    changes = {
        'modified': [],
        'added': [],
        'deleted': [],
        'total_changes': 0
    }
    
    # Check for new or modified files
    for file_path, current_info in current_hashes.items():
        if file_path not in previous_hashes:
            changes['added'].append({
                'file': file_path,
                'size': current_info['size']
            })
            changes['total_changes'] += 1
        elif previous_hashes[file_path]['hash'] != current_info['hash']:
            changes['modified'].append({
                'file': file_path,
                'old_size': previous_hashes[file_path]['size'],
                'new_size': current_info['size'],
                'old_modified': previous_hashes[file_path].get('modified', 'unknown'),
                'new_modified': current_info['modified']
            })
            changes['total_changes'] += 1
    
    # Check for deleted files
    for file_path in previous_hashes:
        if file_path not in current_hashes:
            changes['deleted'].append(file_path)
            changes['total_changes'] += 1
    
    return changes

def print_change_summary(changes):
    """Print a summary of detected changes"""
    if changes['total_changes'] == 0:
        print("✅ No changes detected")
        return False
    
    print(f"🚀 CHANGES DETECTED! ({changes['total_changes']} total)")
    print()
    
    if changes['added']:
        print("➕ NEW FILES:")
        for item in changes['added']:
            print(f"   + {item['file']} ({item['size']} bytes)")
        print()
    
    if changes['modified']:
        print("✏️  MODIFIED FILES:")
        for item in changes['modified']:
            size_change = item['new_size'] - item['old_size']
            size_indicator = f"({size_change:+d} bytes)" if size_change != 0 else "(same size)"
            print(f"   * {item['file']} {size_indicator}")
        print()
    
    if changes['deleted']:
        print("❌ DELETED FILES:")
        for file_path in changes['deleted']:
            print(f"   - {file_path}")
        print()
    
    return True

def test_with_sample_directory():
    """Test the change detection with the configured chapters directory"""
    config = load_config()
    if not config:
        return False
    
    print("=== Step 2: Testing Hash-based Change Detection ===")
    print()
    
    # Use the configured chapters directory
    chapters_dir = config.get('chapters_dir')
    if not chapters_dir or chapters_dir == "NEED_TO_SET_THIS":
        print("❌ Please set 'chapters_dir' in the config file first!")
        print(f"   Edit: {CONFIG_FILE}")
        return False
    
    print(f"📁 Monitoring directory: {chapters_dir}")
    print(f"💾 Hash storage: {config['hash_file']}")
    print()
    
    # Scan for current files
    current_hashes = scan_directory_for_files(chapters_dir, config)
    
    if not current_hashes:
        print("❌ No files found to monitor!")
        print("   Check that your chapters directory contains .tex files")
        return False
    
    print()
    
    # Load previous hashes
    previous_data = load_previous_hashes(config)
    
    # Analyze changes
    changes = analyze_changes(current_hashes, previous_data)
    
    # Print results
    changes_detected = print_change_summary(changes)
    
    # Save current hashes
    if save_hashes(current_hashes, config):
        print()
        if changes_detected:
            print("🎯 In a real pipeline, this would now:")
            print("   1. Download latest files from Overleaf")
            print("   2. Trigger your conversion script")
            print("   3. Update your website")
        else:
            print("ℹ️  System ready - will detect changes on next run")
    
    print()
    print("✅ Step 2 completed!")
    if not changes_detected:
        print()
        print("💡 To test change detection:")
        print("   1. Modify any .tex file in your chapters directory")
        print("   2. Run this script again")
        print("   3. You should see the changes detected!")
    
    return True

def main():
    """Main function"""
    if not test_with_sample_directory():
        print()
        print("❌ Step 2 failed!")
        print("   Please check the configuration and try again")
        sys.exit(1)

if __name__ == "__main__":
    main()