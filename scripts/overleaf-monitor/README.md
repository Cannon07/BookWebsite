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
