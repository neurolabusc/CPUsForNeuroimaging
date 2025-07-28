#!/usr/bin/env python3

import sys
from pathlib import Path
import subprocess

# Resolve the directory of this script
script_dir = Path(__file__).resolve().parent
default_folder = script_dir / "dwi"

# Determine folder to use
if len(sys.argv) == 2:
    folder = Path(sys.argv[1]).resolve()
else:
    folder = default_folder
    if not folder.exists():
        print(f"Error: No argument provided and default folder does not exist:\n  {folder}")
        print("Please provide a valid folder path as an argument.")
        sys.exit(1)

# Construct required file paths
script_path = folder / "dwi_process.py"
dwi_path = folder / "sub-M2304_dwi.nii.gz"
pa_path = folder / "sub-M2304_dwi_PA.nii.gz"

# Check if all required files exist
missing = [p for p in [script_path, dwi_path, pa_path] if not p.exists()]
if missing:
    print("Error: Missing required files:")
    for p in missing:
        print(f"  {p}")
    sys.exit(1)

# Run the command
cmd = [
    "python",
    str(script_path),
    str(dwi_path),
    str(pa_path),
]

print(f"Running: {' '.join(cmd)}")
subprocess.run(cmd, check=True)
