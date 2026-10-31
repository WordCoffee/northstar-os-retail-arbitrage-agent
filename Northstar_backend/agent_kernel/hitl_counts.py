import os
from pathlib import Path
import json

def hitl_counts(root):
    """Count hitl statuses in state directory."""
    if not root.exists():
        return {'pending': 0, 'approved': 0, 'denied': 0, 'total': 0}
    
    state_path = Path(root) / 'state' / 'hitl'
    pending = approved = denied = 0
    
    if not state_path.exists():
        return {'pending': 0, 'approved': 0, 'denied': 0, 'total': 0}
    
    for hitl_file in state_path.glob('hitl_*.json'):
        try:
            with open(hitl_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                status = data.get('status')
                if status == 'pending':
                    pending += 1
                elif status == 'approved':
                    approved += 1
                elif status == 'denied':
                    denied += 1
        except (json.JSONDecodeError, IOError):
            continue
    
    total = pending + approved + denied
    return {'pending': pending, 'approved': approved, 'denied': denied, 'total': total}
