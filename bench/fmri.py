import subprocess
import time
from pathlib import Path
import sys
import os

script_dir = Path(__file__).resolve().parent
default_folder = script_dir / "fmri"

# Determine folder to use
if len(sys.argv) == 2:
    featroot = Path(sys.argv[1]).resolve()
else:
    featroot = default_folder
    if not featroot.exists():
        print(f"Error: No argument provided and default folder does not exist:\n  {featroot}")
        print("Please provide a valid folder path as an argument.")
        sys.exit(1)

fsldir_env = os.environ.get("FSLDIR")
if not fsldir_env:
    sys.exit("FSLDIR environment variable not set.")

fsldir = Path(fsldir_env).resolve()

fsf_template_path = featroot.joinpath("feat_template.fsf")
if not fsf_template_path.exists():
    sys.exit(f"Template file not found: {fsf_template_path}")

fsf_output_path = featroot.joinpath("feat.fsf")

# Read and substitute placeholder
fsf_text = fsf_template_path.read_text().replace("__FEATROOT__", str(featroot))
fsf_text = fsf_text.replace("__FSLDIR__", str(fsldir))

# 1. Validate regstandard image
regstandard_path = Path(os.path.join(fsldir, "data", "standard", "MNI152_T1_2mm_brain.nii.gz"))
if not regstandard_path.exists():
    print(f"Error: Missing regstandard image at {regstandard_path}")
    sys.exit(2)

# 2. Check FUNC.nii or FUNC.nii.gz exists
nii_path = None
for ext in [".nii", ".nii.gz"]:
    test_path = featroot / f"fmrievents008{ext}"
    if test_path.exists():
        nii_path = test_path
        break

if not nii_path:
    print(f"Error: fmrievents008 not found in {featroot}")
    sys.exit(3)

# 3. Write modified FSF
fsf_output_path.write_text(fsf_text)

# 4. Run feat and time it
print(f"Running FEAT with root: {featroot}")
start = time.time()
subprocess.run(["feat", str(fsf_output_path)], check=True)
elapsed = time.time() - start
print(f"FEAT completed in {elapsed:.2f} seconds.")
