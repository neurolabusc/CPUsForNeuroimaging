#!/usr/bin/env python3

import sys
from pathlib import Path
import subprocess
import time

# Resolve the directory of this script
script_dir = Path(__file__).resolve().parent
default_folder = script_dir / "ai"

# Determine folder to use
if len(sys.argv) == 2:
    folder = Path(sys.argv[1]).resolve()
else:
    folder = default_folder
if not folder.exists():
    print("Please provide a valid folder path as an argument.")
    sys.exit(1)

# Start timing
start_time = time.time()

# Find all .nii.gz files excluding those starting with "bet_"
nii_files = [f for f in folder.glob("*.nii.gz") if not f.name.startswith("bet_")]

# Process each file
for nii_file in nii_files:
    out_file = nii_file.with_name(f"bet_{nii_file.name}")
    print(f"Processing: {nii_file.name}")
    subprocess.run(["brainchop", "-m", "mindgrab", "-i", str(nii_file), "-o", str(out_file)], check=True)

# Report total time
elapsed = int(time.time() - start_time)
print(f"Processed {len(nii_files)} files in {elapsed} seconds.")
