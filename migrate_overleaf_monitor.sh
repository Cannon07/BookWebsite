#!/bin/bash
# Migration Script: Move Overleaf Monitor to Main BookWebsite Project

echo "=== Overleaf Monitor Migration to BookWebsite ==="
echo ""

# Define paths
BOOKWEBSITE_DIR="/Users/jayshitre/Projects/dfs/BookWebsite2/BookWebsite"
OVERLEAF_MONITOR_DIR="/Users/jayshitre/Projects/dfs/BookWebsite2/overleaf-monitor"

# Check if directories exist
if [ ! -d "$BOOKWEBSITE_DIR" ]; then
    echo "❌ BookWebsite directory not found: $BOOKWEBSITE_DIR"
    exit 1
fi

if [ ! -d "$OVERLEAF_MONITOR_DIR" ]; then
    echo "❌ Overleaf Monitor directory not found: $OVERLEAF_MONITOR_DIR"
    exit 1
fi

echo "📁 Source: $OVERLEAF_MONITOR_DIR"
echo "📁 Target: $BOOKWEBSITE_DIR"
echo ""

# Step 1: Create directory structure
echo "🔧 Step 1: Creating directory structure..."
cd "$BOOKWEBSITE_DIR"

mkdir -p scripts/overleaf-monitor
mkdir -p scripts/overleaf-monitor/logs
mkdir -p scripts/overleaf-monitor/data

echo "✅ Created: scripts/overleaf-monitor/"

# Step 2: Copy scripts
echo ""
echo "📄 Step 2: Copying scripts..."

# Copy the main scripts
if [ -f "$OVERLEAF_MONITOR_DIR/scripts/step2_change_detector.py" ]; then
    cp "$OVERLEAF_MONITOR_DIR/scripts/step2_change_detector.py" scripts/overleaf-monitor/change_detector.py
    echo "✅ Copied: change_detector.py"
fi

if [ -f "$OVERLEAF_MONITOR_DIR/scripts/step3_git_downloader.py" ]; then
    cp "$OVERLEAF_MONITOR_DIR/scripts/step3_git_downloader.py" scripts/overleaf-monitor/git_sync.py
    echo "✅ Copied: git_sync.py"
fi

if [ -f "$OVERLEAF_MONITOR_DIR/scripts/step4_automated_pipeline.py" ]; then
    cp "$OVERLEAF_MONITOR_DIR/scripts/step4_automated_pipeline.py" scripts/overleaf-monitor/automated_pipeline.py
    echo "✅ Copied: automated_pipeline.py"
fi

if [ -f "$OVERLEAF_MONITOR_DIR/scripts/step5_github_actions_pipeline.py" ]; then
    cp "$OVERLEAF_MONITOR_DIR/scripts/step5_github_actions_pipeline.py" scripts/overleaf-monitor/github_actions_pipeline.py
    echo "✅ Copied: github_actions_pipeline.py"
fi

# Step 3: Copy configuration and data
echo ""
echo "⚙️  Step 3: Copying configuration..."

if [ -f "$OVERLEAF_MONITOR_DIR/data/config.json" ]; then
    cp "$OVERLEAF_MONITOR_DIR/data/config.json" scripts/overleaf-monitor/data/
    echo "✅ Copied: config.json"
fi

if [ -f "$OVERLEAF_MONITOR_DIR/data/git_config.json" ]; then
    cp "$OVERLEAF_MONITOR_DIR/data/git_config.json" scripts/overleaf-monitor/data/
    echo "✅ Copied: git_config.json"
fi

if [ -f "$OVERLEAF_MONITOR_DIR/data/overleaf_hashes.json" ]; then
    cp "$OVERLEAF_MONITOR_DIR/data/overleaf_hashes.json" scripts/overleaf-monitor/data/
    echo "✅ Copied: overleaf_hashes.json"
fi

# Step 4: Copy any existing logs (optional)
echo ""
echo "📋 Step 4: Copying logs (if any)..."

if [ -d "$OVERLEAF_MONITOR_DIR/logs" ] && [ "$(ls -A $OVERLEAF_MONITOR_DIR/logs)" ]; then
    cp -r "$OVERLEAF_MONITOR_DIR/logs"/* scripts/overleaf-monitor/logs/ 2>/dev/null || true
    echo "✅ Copied existing logs"
else
    echo "ℹ️  No existing logs to copy"
fi

# Step 5: Update Python requirements
echo ""
echo "📦 Step 5: Updating Python requirements..."

# Check if requirements.txt exists
if [ -f "requirements.txt" ]; then
    echo "📄 Found existing requirements.txt"
    
    # Add overleaf-monitor requirements if not already present
    REQUIREMENTS_TO_ADD=(
        "requests>=2.25.0"
        "beautifulsoup4>=4.9.0"
    )
    
    for req in "${REQUIREMENTS_TO_ADD[@]}"; do
        if ! grep -q "$(echo $req | cut -d'>' -f1)" requirements.txt; then
            echo "$req" >> requirements.txt
            echo "✅ Added: $req"
        else
            echo "ℹ️  Already present: $(echo $req | cut -d'>' -f1)"
        fi
    done
else
    echo "📄 Creating new requirements.txt"
    cat > requirements.txt << 'EOF'
# Existing project requirements
# Add your existing requirements here

# Overleaf Monitor requirements
requests>=2.25.0
beautifulsoup4>=4.9.0
EOF
    echo "✅ Created: requirements.txt"
fi

# Step 6: Create integrated configuration
echo ""
echo "⚙️  Step 6: Creating integrated configuration..."

cat > scripts/overleaf-monitor/data/integrated_config.json << EOF
{
  "project_id": "68428c5d41c2ef888f0b2a5e",
  "project_url": "https://www.overleaf.com/project/68428c5d41c2ef888f0b2a5e",
  "project_dir": "overleaf-project",
  "chapters_dir": "chapters",
  "conversion_script": "scripts/process-chapter.ts",
  "hash_file": "scripts/overleaf-monitor/data/overleaf_hashes.json",
  "log_file": "scripts/overleaf-monitor/logs/overleaf_sync.log",
  "file_extensions": [".tex", ".bib"],
  "exclude_dirs": [".git", "__pycache__", "node_modules", ".aux", ".out", ".log", ".fdb_latexmk", ".fls", ".synctex.gz"]
}
EOF

echo "✅ Created: integrated_config.json"

# Step 7: Create main pipeline script
echo ""
echo "🚀 Step 7: Creating main pipeline script..."

cat > scripts/overleaf-monitor/pipeline.py << 'EOF'
#!/usr/bin/env python3
"""
Main Overleaf Monitor Pipeline for BookWebsite Integration
This script coordinates the complete pipeline from the main project
"""

import os
import sys

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

# Import the GitHub Actions compatible pipeline
try:
    from github_actions_pipeline import main as run_pipeline
    
    if __name__ == "__main__":
        success = run_pipeline()
        sys.exit(0 if success else 1)
        
except ImportError as e:
    print(f"❌ Error importing pipeline: {e}")
    print("   Make sure all required scripts are in place")
    sys.exit(1)
EOF

chmod +x scripts/overleaf-monitor/pipeline.py
echo "✅ Created: pipeline.py"

# Step 8: Create README
echo ""
echo "📖 Step 8: Creating documentation..."

cat > scripts/overleaf-monitor/README.md << 'EOF'
# Overleaf Monitor Integration

This directory contains the Overleaf monitoring and synchronization system integrated into the BookWebsite project.

## Files:
- `pipeline.py` - Main entry point for the pipeline
- `github_actions_pipeline.py` - GitHub Actions compatible pipeline
- `automated_pipeline.py` - Original automated pipeline
- `git_sync.py` - Overleaf Git synchronization
- `change_detector.py` - File change detection
- `data/` - Configuration and hash storage
- `logs/` - Pipeline logs

## Usage:

### Local Testing:
```bash
# From BookWebsite root directory
python3 scripts/overleaf-monitor/pipeline.py
```

### GitHub Actions:
The pipeline is designed to run automatically in GitHub Actions with proper environment variables set.

## Configuration:
- Credentials stored in GitHub repository secrets
- Paths are relative to the BookWebsite project root
- All operations happen within the main project structure
EOF

echo "✅ Created: README.md"

# Step 9: Summary
echo ""
echo "🎯 Migration Summary:"
echo "===================="
echo "✅ Created directory structure in BookWebsite"
echo "✅ Copied all monitoring scripts"
echo "✅ Copied configuration and data"
echo "✅ Updated Python requirements"
echo "✅ Created integrated configuration"
echo "✅ Created main pipeline entry point"
echo "✅ Created documentation"
echo ""
echo "📁 New structure:"
echo "   BookWebsite/"
echo "   ├── scripts/"
echo "   │   ├── process-chapter.ts (existing)"
echo "   │   ├── convert_tex_to_md.py (existing)"
echo "   │   └── overleaf-monitor/"
echo "   │       ├── pipeline.py (main entry)"
echo "   │       ├── github_actions_pipeline.py"
echo "   │       ├── automated_pipeline.py"
echo "   │       ├── git_sync.py"
echo "   │       ├── change_detector.py"
echo "   │       ├── data/ (config and hashes)"
echo "   │       └── logs/"
echo "   ├── chapters/ (LaTeX files)"
echo "   ├── requirements.txt (updated)"
echo "   └── ..."
echo ""
echo "🚀 Next steps:"
echo "1. Update script paths in the copied files"
echo "2. Test the integrated pipeline"
echo "3. Update GitHub Actions workflow"
echo ""
echo "Run: python3 scripts/overleaf-monitor/pipeline.py"
EOF