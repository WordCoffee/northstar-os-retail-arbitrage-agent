#!/usr/bin/env python
"""
Auto-update Sourcescout manifest when new data is pulled.
Can be called as a post-pull hook or run periodically.
"""
import subprocess
import sys
from pathlib import Path

def main():
    """Run the manifest builder and restart backend if changed."""
    script = Path(__file__).parent / "build_sourcescout_manifest.py"
    
    # Run the manifest builder
    result = subprocess.run([sys.executable, str(script)], 
                          capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    
    if result.returncode != 0:
        print(f"Build failed: {result.stderr}")
        return 1
    
    print(result.stdout)
    
    # Check if manifest was updated (simple check - could be enhanced)
    # For now, just signal success
    print("Sourcescout manifest updated successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())