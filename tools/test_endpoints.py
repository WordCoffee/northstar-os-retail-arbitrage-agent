#!/usr/bin/env python
"""Test the Sourcescout API endpoints with proper error handling."""
import subprocess
import sys
import time
import urllib.request
import json
import os

def main():
    # Kill any existing server on port 8000
    try:
        subprocess.run(["taskkill", "/F", "/FI", "PORTS eq 8000", "/IM", "python.exe"], 
                       capture_output=True, check=False)
    except:
        pass
    
    # Start the server
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "Northstar_backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to start
    time.sleep(3)
    
    # Check if process is still alive
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print(f"Server exited with code {proc.returncode}")
        print(f"STDOUT: {stdout.decode()[:500]}")
        print(f"STDERR: {stderr.decode()[:500]}")
        return
    
    endpoints = [
        '/api/sourcescout',
        '/api/sourcescout/matches',
        '/api/sourcescout/mismatches',
        '/api/sourcescout/review',
        '/api/sourcescout/summary'
    ]
    
    print("Testing endpoints...")
    for ep in endpoints:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000' + ep, timeout=5) as r:
                d = json.load(r)
                print(f"{ep}: {d.get('count', 'N/A')} items")
        except Exception as e:
            print(f"{ep}: ERROR - {e}")
    
    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except:
        proc.kill()

if __name__ == "__main__":
    import urllib.request
    import json
    import time
    main()