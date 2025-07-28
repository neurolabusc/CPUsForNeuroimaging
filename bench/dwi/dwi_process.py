#!/usr/bin/env python3

import os
import shutil
import sys
import subprocess
import json
import time

def report_elapsed_time(start_time, comment=""):
    elapsed = time.time() - start_time
    print(f"{comment} completed in {int(elapsed)} seconds.")

def get_max_value(nifti_path):
    result = subprocess.run(
        ["fslstats", nifti_path, "-R"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True
    )
    min_val, max_val = map(float, result.stdout.strip().split())
    return max_val

def prepare_seed_list(pth, template_roiWThr, max_index=189, isGz=False):
    mask_dir = os.path.join(pth, "masks")
    seedlist = os.path.join(pth, "seeds.txt")
    pad_width = len(str(max_index))

    os.makedirs(mask_dir, exist_ok=True)
    if os.path.exists(seedlist):
        os.remove(seedlist)

    for i in range(1, max_index + 1):
        padded_i = str(i).zfill(pad_width)
        out_name = f"roi{padded_i}.nii.gz"
        out_path = os.path.join(mask_dir, out_name)

        # Run fslmaths to extract the region
        subprocess.run([
            "fslmaths", template_roiWThr,
            "-thr", str(i), "-uthr", str(i),
            out_path
        ], check=True)

        # Optional decompression
        if not isGz:
            nii_path = out_path[:-3]  # Strip '.gz'
            subprocess.run(["gunzip", "-f", out_path], check=True)
            maski = nii_path
        else:
            maski = out_path

        # Get mean value of the mask
        result = subprocess.run(
            ["fslstats", maski, "-M"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        try:
            mean_val = float(result.stdout.strip())
        except ValueError:
            mean_val = 0

        if mean_val > 0:
            with open(seedlist, "a") as f:
                f.write(maski + "\n")
        else:
            os.remove(maski)


def is_cuda_available():
    try:
        result = subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def run_probtrackx(temp_dir):
    wAtlas_path = os.path.join(temp_dir, "wAtlas")
    max_index = get_max_value(wAtlas_path)
    prepare_seed_list(temp_dir, wAtlas_path, int(max_index))
    seedlist = os.path.join(temp_dir, "seeds.txt")
    merged = os.path.join(temp_dir, "bedpost.bedpostX", "merged")
    mask = os.path.join(temp_dir, "bedpost.bedpostX", "nodif_brain_mask")
    outdir = os.path.join(temp_dir, "prob")
    print("Running probtrackx2...")
    start_time = time.time()
    # Decide whether to use GPU or CPU
    cmd = "probtrackx2_gpu" if is_cuda_available() else "probtrackx2"
    print(f"Using {'GPU' if 'gpu' in cmd else 'CPU'} version: {cmd}")
    start_time = time.time()
    run(f"{cmd} --network -x {seedlist}  -l --onewaycondition -c 0.2 -S 2000 --steplength=0.5 -P 5000 --fibthresh=0.01 --distthresh=0.0 --sampvox=0.0 --forcedir --opd -s {merged} -m {mask}  --dir={outdir}")
    report_elapsed_time(start_time, "probtrackx2")


def clear_temp_folder(temp_dir):
    if os.path.exists(temp_dir):
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # remove file or symlink
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # remove directory
            except Exception as e:
                print(f"Warning: Failed to delete {file_path}. Reason: {e}")

def get_total_readout_time(dwi_path):
    # Handle .nii or .nii.gz → expect matching .json
    base = dwi_path
    if base.endswith('.gz'):
        base = base[:-7]
    elif base.endswith('.nii'):
        base = base[:-4]
    json_path = base + '.json'

    try:
        with open(json_path, 'r') as f:
            metadata = json.load(f)
        return float(metadata.get("TotalReadoutTime", 0.03))
    except Exception as e:
        print(f"Warning: Could not read {json_path} or missing 'TotalReadoutTime'. Assuming 0.03")
        return 0.03


def run(cmd):
    print(f'Running: {cmd}')
    subprocess.run(cmd, shell=True, check=True)

def read_bval(bval_path):
    with open(bval_path) as f:
        return f.read().strip().split()

def read_bvec(bvec_path):
    with open(bvec_path) as f:
        return [line.strip().split() for line in f.readlines()]

def get_sidecar_path(nifti_path, ext):
    for suffix in [".nii", ".nii.gz"]:
        if nifti_path.endswith(suffix):
            return nifti_path.replace(suffix, ext)
    return nifti_path + ext  # fallback

def run_dtifit(fsl_dir, temp_dir):
    # Get the standard brain template from FSLDIR
    dwi = os.path.join(temp_dir, "dwi_eddy")
    dwio = dwi # os.path.join(temp_dir, "dwio")
    mask = os.path.join(temp_dir, "bet_Cor_mask")
    bvec = os.path.join(temp_dir, "dwi_eddy.eddy_rotated_bvecs")
    bval = os.path.join(temp_dir, "dwi_merge.bval")
    run(f"dtifit --data={dwi} --out={dwio} --mask={mask} --bvecs={bvec} --bvals={bval}")
    fa = dwi + "_FA"
    faEro = fa + "ero"
    run(f"fslmaths {fa} -ero {faEro}")
    faThr = fa + "thr"
    run(f"fslmaths {fa} -ero -thr 0.15 -bin {faThr}")
    # Prepare for bedpostx
    bed_dir = os.path.join(temp_dir, "bedpost")
    os.makedirs(bed_dir, exist_ok=True)
    monitor_dir = bed_dir + ".bedpostX"
    if os.path.exists(monitor_dir):
        print(f"{monitor_dir} already exists. Skipping BEDPOSTX")
        return
    print("Preparing BEDPOSTX input...")
    data_path = os.path.join(bed_dir, "data.nii.gz")
    mask_path = os.path.join(bed_dir, "nodif_brain_mask.nii.gz")
    bvecs_path = os.path.join(bed_dir, "bvecs")
    bvals_path = os.path.join(bed_dir, "bvals")

    shutil.copyfile(dwi + ".nii.gz", data_path)
    shutil.copyfile(faThr + ".nii.gz", mask_path)
    shutil.copyfile(bvec, bvecs_path)
    shutil.copyfile(bval, bvals_path)

    # Run bedpostx and wait
    print("Running BEDPOSTX...")
    start_time = time.time()
    # Decide whether to use GPU or CPU
    bedpostx_cmd = "bedpostx_gpu" if is_cuda_available() else "bedpostx"
    print(f"Using {'GPU' if 'gpu' in bedpostx_cmd else 'CPU'} version: {bedpostx_cmd}")
    # Run bedpostx and wait
    start_time = time.time()
    run(f"{bedpostx_cmd} {bed_dir}")
    xfms_eye = os.path.join(monitor_dir, "xfms", "eye.mat")
    while not os.path.isfile(xfms_eye):
        time.sleep(10)  # Check every 10 seconds
    report_elapsed_time(start_time, "bedpostx")



def run_flirt(fsl_dir, temp_dir):
    # Get the standard brain template from FSLDIR
    standard_brain = os.path.join(fsl_dir, "data", "standard", "MNI152_T1_1mm_brain.nii.gz")
    # Paths for outputs
    vol1_path = os.path.join(temp_dir, "b0_Cor")
    wT1_path = os.path.join(temp_dir, "wT1")
    wT1mat_path = os.path.join(temp_dir, "wT1mat")
    # Run flirt
    run(
        f"flirt -in {standard_brain} -ref {vol1_path} "
        f"-out {wT1_path} -omat {wT1mat_path} -bins 256 -cost corratio "
        f"-searchrx -90 90 -searchry -90 90 -searchrz -90 90 -dof 12 -interp trilinear"
    )
    # Get the atlas template from FSLDIR
    atlas = os.path.join(fsl_dir, "data", "atlases", "HarvardOxford", "HarvardOxford-cort-maxprob-thr25-1mm.nii.gz")
    wAtlas_path = os.path.join(temp_dir, "wAtlas")
    # apply flirt to atlas
    run(
        f"flirt -in {atlas} -ref {vol1_path} "
        f"-out {wAtlas_path} -applyxfm -init {wT1mat_path} -interp nearestneighbour"
    )

def run_topup(temp_dir, dwi, dwi_pa):
    # https://andysbrainbook.readthedocs.io/en/latest/TBSS/TBSS_Course/TBSS_04_TopUpEddy.html
    ap_out = os.path.join(temp_dir, "AP")
    pa_out = os.path.join(temp_dir, "PA")
    run(f"fslroi {dwi} {ap_out} 0 1")
    run(f"fslroi {dwi_pa} {pa_out} 0 1")

    # Get TotalReadoutTime
    readout_time = get_total_readout_time(dwi)

    # Write acq_param.txt
    acq_param_path = os.path.join(temp_dir, "acq_param.txt")
    with open(acq_param_path, "w") as f:
        f.write(f"0 1 0 {readout_time:.5f}\n")
        f.write(f"0 -1 0 {readout_time:.5f}\n")

    ap_path = os.path.join(temp_dir, "AP")
    pa_path = os.path.join(temp_dir, "PA")
    ap_pa_path = os.path.join(temp_dir, "AP_PA")
    acq_param_path = os.path.join(temp_dir, "acq_param.txt")
    topup_out = os.path.join(temp_dir, "AP_PA_topup")

    # Merge AP and PA images
    run(f"fslmerge -t {ap_pa_path} {ap_path} {pa_path}")

    # Run topup --nthr
    n_threads = max(os.cpu_count() - 1, 1)
    start_time = time.time()
    run(f"topup --imain={ap_pa_path} --datain={acq_param_path} --nthr={n_threads} --config=b02b0_1.cnf --out={topup_out}")
    report_elapsed_time(start_time, "topup")
    vol1in_path = os.path.join(temp_dir, "b0")
    run(f"fslroi {dwi} {vol1in_path} 0 1")
    vol1_path = os.path.join(temp_dir, "b0_Cor")
    run(f"applytopup --imain={vol1in_path} --inindex=1 --datain={acq_param_path} --topup={topup_out} --method=jac --out={vol1_path}")

    mask_path = os.path.join(temp_dir, "bet_Cor")
    run(f"bet {vol1_path} {mask_path} -m -f 0.2")
    mask_path = os.path.join(temp_dir, "bet_Cor_mask")

    dwi_merge_path = os.path.join(temp_dir, "dwi_merge")
    run(f"fslmerge -t {dwi_merge_path} {dwi} {dwi_pa}")
    bval_1 = read_bval(get_sidecar_path(dwi, ".bval"))
    bval_2 = read_bval(get_sidecar_path(dwi_pa, ".bval"))
    bvec_1 = read_bvec(get_sidecar_path(dwi, ".bvec"))
    bvec_2 = read_bvec(get_sidecar_path(dwi_pa, ".bvec"))
    bval_cat = bval_1 + bval_2
    bvec_cat = [v1 + v2 for v1, v2 in zip(bvec_1, bvec_2)]
    # Write concatenated files
    bval_merge_path = os.path.join(temp_dir, "dwi_merge.bval")
    with open(bval_merge_path, "w") as f:
        f.write(" ".join(bval_cat) + "\n")
    bvec_merge_path = os.path.join(temp_dir, "dwi_merge.bvec")
    with open(bvec_merge_path, "w") as f:
        for row in bvec_cat:
            f.write(" ".join(row) + "\n")
    print(f"Wrote {len(bval_1)} + {len(bval_2)} volumes to {bval_merge_path}")
    # ---- Generate index.txt for eddy ----
    index_path = os.path.join(temp_dir, "index.txt")
    index_list = ["1"] * len(bval_1) + ["2"] * len(bval_2)
    with open(index_path, "w") as f:
        f.write(" ".join(index_list) + "\n")
    print(f"Wrote index file with {len(index_list)} entries to {index_path}")
    ap_eddy_path = os.path.join(temp_dir, "dwi_eddy")
    # watch -n0.1 nvidia-smi
    # n.b. ` --repol --slm=linear` optional PMID: 27393418
    n_threads = max(os.cpu_count() - 1, 1)
    # eddy will crash if a GPU is detected and n_threads > 1
    if is_cuda_available():
      n_threads = 1
    start_time = time.time()
    run(f"eddy diffusion --imain={dwi_merge_path} --mask={mask_path} --nthr={n_threads} --index={index_path} --acqp={acq_param_path} --bvecs={bvec_merge_path} --bvals={bval_merge_path} --slm=linear --repol --fwhm=0 --topup={topup_out} --flm=quadratic --out={ap_eddy_path} --data_is_shelled")
    report_elapsed_time(start_time, "eddy")

def main():
    fsl_dir = os.environ.get("FSLDIR")
    if not fsl_dir:
        raise EnvironmentError("FSLDIR environment variable is not set.")
    if len(sys.argv) != 3:
        print("Usage: python dwi_process.py <dwi> <dwi_pa>")
        sys.exit(1)
    dwi = sys.argv[1]
    dwi_pa = sys.argv[2]
    base_dir = os.path.dirname(os.path.abspath(dwi))
    temp_dir = os.path.join(base_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    start_time = time.time()
    clear_temp_folder(temp_dir)
    run_topup(temp_dir, dwi, dwi_pa)
    run_dtifit(fsl_dir, temp_dir)
    run_flirt(fsl_dir, temp_dir)
    run_probtrackx(temp_dir)
    report_elapsed_time(start_time, "end-to-end")
    
if __name__ == '__main__':
    main()
