"""Layer 14 - Explicit approval checkpoints.

Discovery and enrichment are SEPARATE approval gates. The pipeline must not
chain discovery into enrichment without a distinct explicit approval turn
between them. Live execution checks these flags; offline dry-runs ignore them
(no live calls are made regardless).
"""

class Approvals:
    def __init__(self):
        self.discovery = False
        self.enrichment = False

    def approve_discovery(self):
        self.discovery = True

    def approve_enrichment(self):
        self.enrichment = True

    def reset(self):
        self.discovery = False
        self.enrichment = False
