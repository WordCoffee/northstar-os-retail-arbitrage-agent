# Reference product photos (owner drop-in folder)

The local fidelity trial (`tools/fidelity-trial.cjs`) reads REAL product photos
from this folder:

- Put at least 5 real reference photos of the product here (JPG/PNG; any size).
- Then run: `node tools/fidelity-trial.cjs`
- The trial composites the real product pixels (no generation), diffs them
  through the fidelity gate, runs the label-region check and the disclosure
  gates, records pass/fail per image and timing, and confirms that every output
  stays export-blocked until a human compare sign-off.

With this folder empty, the harness runs a labeled FIXTURE set and reports the
live trial as **NOT RUN** (no reference photos supplied). Nothing is ever
fetched: the photos stay local, and no provider is contacted.
