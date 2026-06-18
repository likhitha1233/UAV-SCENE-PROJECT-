#!/usr/bin/env bash
#
# download_datasets.sh
# =====================
#
# Task 1 deliverable: download/store the two source datasets on your
# server:
#   (A) HOTC -- Hyperspectral Object Tracking Challenge (hsitracking.com)
#   (B) UAV-HSI-Crop (ScienceDB, DOI 10.57760/sciencedb.01898)
#
# -----------------------------------------------------------------------
# NOTES -- PLEASE READ BEFORE RUNNING
# -----------------------------------------------------------------------
# 1. Run on YOUR server (not the authoring sandbox; no network egress there).
#
# 2. HOTC Google Drive IDs are filled in (train / val / test confirmed
#    from https://www.hsitracking.com/contest/ ).
#    Baidu YunPan alternative: see download_hotc_baidu() at the bottom
#    of this file (Baidu access code: 886c).
#
# 3. UAV-HSI-Crop URL is still a placeholder (UAV_HSI_CROP_URL below).
#    Visit https://www.scidb.cn/en/detail?dataSetId=6de15e4ec9b74dacab12e29cb557f041
#    to obtain the link. If ScienceDB requires a browser session, download
#    the archive manually into $UAV_DIR/raw/ and re-run with
#    --skip-uav-download.
#
# 4. "Mini" = HOTC validation split (75 labeled sequences, ~5x smaller
#    than training). See HOTC_MINI_SEQUENCE_IDS to override with a
#    finer sub-selection of individual sequence folders.
# -----------------------------------------------------------------------
# EXPECTED OUTPUT LAYOUT (per dataset documentation reviewed so far)
# -----------------------------------------------------------------------
# $DATA_ROOT/
#   HOTC/
#     train/   <406 sequence folders>
#     val/     <75 sequence folders>
#     test/    <75 sequence folders, unlabeled>
#   Each sequence folder is expected to contain, per the contest docs:
#     - VIS/    2D-mosaic frames, 16 bands after calibration
#     - NIR/    2D-mosaic frames, 25 bands
#     - RedNIR/ 2D-mosaic frames, 15 usable bands (last band reported all-zero)
#     - false-color video (CIE-derived RGB-like video)
#     - groundtruth.txt (per-frame bbox: center_x, center_y, w, h) for
#       train/val; absent for test
#     - 11 challenge-attribute flags (occlusion, scale variation, etc.)
#   X2Cube-style conversion (2D mosaic -> 3D cube) is documented as a
#   separate provided script, not duplicated here -- this script only
#   downloads/stores the raw distribution.
#
#   UAV-HSI-Crop/
#     raw/      downloaded archive(s) as distributed
#     patches/  extracted 96x96x200 .npy patches, ~80/20 train/test split
#
# -----------------------------------------------------------------------

set -euo pipefail

# ============================ CONFIGURATION =============================

DATA_ROOT="${DATA_ROOT:-/data/hsi_datasets}"
HOTC_DIR="$DATA_ROOT/HOTC"
UAV_DIR="$DATA_ROOT/UAV-HSI-Crop"

# --- HOTC: Google Drive folder IDs (confirmed from hsitracking.com) ----
HOTC_TRAIN_GDRIVE_ID="1r3wBl0ttYecktRB6LUPvyicTS6zZXKW0"   # 406 labeled training sequences
HOTC_VAL_GDRIVE_ID="17K86Z6Sd0mPtNUF3KAskrdb5O8hbxfyD"     # 75 labeled validation sequences
HOTC_TEST_GDRIVE_ID="1CUVcq-i-o7HXBtc7m9xflsgEnyJBvSoi"    # 75 unlabeled ranking/test sequences

# --- HOTC "mini" definition -------------------------------------------
# No separately packaged "mini" release exists. The validation split
# (75 labeled sequences, all 11 challenge attributes covered) is used as
# the mini set: it is ~5x smaller than training and carries ground-truth
# bounding boxes, making it the natural development/quick-iteration subset.
# --mini downloads HOTC_VAL only.
# Populate this array with individual sequence folder IDs (from within
# the val folder) only if you want a finer-grained sub-selection:
HOTC_MINI_SEQUENCE_IDS=()

# --- UAV-HSI-Crop: fill in from the ScienceDB / Aliyun-Drive page -------
UAV_HSI_CROP_URL="REPLACE_ME_UAV_HSI_CROP_DOWNLOAD_URL"

# ============================ ARG PARSING ===============================

MODE="full"           # full | mini
DO_HOTC=1
DO_UAV=1
SKIP_UAV_DOWNLOAD=0

for arg in "$@"; do
  case "$arg" in
    --mini) MODE="mini" ;;
    --full) MODE="full" ;;
    --hotc-only) DO_UAV=0 ;;
    --uav-only) DO_HOTC=0 ;;
    --skip-uav-download) SKIP_UAV_DOWNLOAD=1 ;;
    -h|--help)
      sed -n '2,70p' "$0"; exit 0 ;;
    *)
      echo "Unknown argument: $arg (see --help)"; exit 1 ;;
  esac
done

# ============================ HELPERS ====================================

check_deps() {
  command -v gdown >/dev/null 2>&1 || {
    echo "gdown not found. Install with: pip install gdown --break-system-packages"
    exit 1
  }
}

require_id() {
  local val="$1" name="$2"
  if [[ "$val" == REPLACE_ME* ]]; then
    echo "ERROR: $name is still a placeholder. Edit the CONFIGURATION"
    echo "       section of this script (or export the corresponding"
    echo "       environment variable) before running."
    exit 1
  fi
}

# ============================ HOTC =======================================

download_hotc_full() {
  require_id "$HOTC_TRAIN_GDRIVE_ID" HOTC_TRAIN_GDRIVE_ID
  require_id "$HOTC_VAL_GDRIVE_ID"   HOTC_VAL_GDRIVE_ID
  require_id "$HOTC_TEST_GDRIVE_ID"  HOTC_TEST_GDRIVE_ID

  mkdir -p "$HOTC_DIR/train" "$HOTC_DIR/val" "$HOTC_DIR/test"

  echo "[HOTC] Downloading train split (406 sequences expected) ..."
  gdown --folder "$HOTC_TRAIN_GDRIVE_ID" -O "$HOTC_DIR/train"

  echo "[HOTC] Downloading val split (75 sequences expected) ..."
  gdown --folder "$HOTC_VAL_GDRIVE_ID" -O "$HOTC_DIR/val"

  echo "[HOTC] Downloading test split (75 unlabeled sequences expected) ..."
  gdown --folder "$HOTC_TEST_GDRIVE_ID" -O "$HOTC_DIR/test"
}

download_hotc_mini() {
  mkdir -p "$HOTC_DIR/mini"

  if [[ ${#HOTC_MINI_SEQUENCE_IDS[@]} -eq 0 ]]; then
    echo "[HOTC mini] Downloading full validation split as mini (75 labeled sequences) ..."
    require_id "$HOTC_VAL_GDRIVE_ID" HOTC_VAL_GDRIVE_ID
    gdown --folder "$HOTC_VAL_GDRIVE_ID" -O "$HOTC_DIR/mini"
  else
    local i=0
    for seq_id in "${HOTC_MINI_SEQUENCE_IDS[@]}"; do
      i=$((i+1))
      echo "[HOTC mini] Downloading sequence $i/${#HOTC_MINI_SEQUENCE_IDS[@]} ..."
      gdown --folder "$seq_id" -O "$HOTC_DIR/mini"
    done
  fi
}

# ============================ UAV-HSI-Crop ===============================

download_uav_hsi_crop() {
  mkdir -p "$UAV_DIR/raw" "$UAV_DIR/patches"

  if [[ "$SKIP_UAV_DOWNLOAD" -eq 1 ]]; then
    echo "[UAV-HSI-Crop] --skip-uav-download set; expecting archive(s)"
    echo "  already placed in $UAV_DIR/raw/"
  else
    require_id "$UAV_HSI_CROP_URL" UAV_HSI_CROP_URL
    echo "[UAV-HSI-Crop] Downloading from $UAV_HSI_CROP_URL ..."
    wget -c "$UAV_HSI_CROP_URL" -P "$UAV_DIR/raw"
  fi

  echo "[UAV-HSI-Crop] Extracting archives in $UAV_DIR/raw -> $UAV_DIR/patches ..."
  shopt -s nullglob
  for f in "$UAV_DIR"/raw/*.zip; do
    unzip -o "$f" -d "$UAV_DIR/patches"
  done
  for f in "$UAV_DIR"/raw/*.tar "$UAV_DIR"/raw/*.tar.gz "$UAV_DIR"/raw/*.tgz; do
    tar -xf "$f" -C "$UAV_DIR/patches"
  done
  shopt -u nullglob
  echo "[UAV-HSI-Crop] Done. Expect 96x96x200 .npy patches under $UAV_DIR/patches"
}

# ============================ MAIN =======================================

mkdir -p "$DATA_ROOT"

if [[ "$DO_HOTC" -eq 1 ]]; then
  check_deps
  if [[ "$MODE" == "mini" ]]; then
    download_hotc_mini
  else
    download_hotc_full
  fi
fi

if [[ "$DO_UAV" -eq 1 ]]; then
  download_uav_hsi_crop
fi

echo ""
echo "Done. Data root: $DATA_ROOT"
echo "Run 'find \"$DATA_ROOT\" -maxdepth 3 -type d' to review the layout."

# ============================ BAIDU ALTERNATIVE ==========================
# If Google Drive is inaccessible from your server, use Baidu YunPan.
# Access code confirmed from https://www.hsitracking.com/contest/ : 886c
# Usage: manually download from https://pan.baidu.com/s/1FY2L6L9SDKw-V-bUkuosSA/
# then place the extracted folders at $HOTC_DIR/train, val, test respectively.
# download_hotc_baidu() is provided as a reference stub only -- Baidu's
# CLI tool (bypy / BaiduPCS-Go) must be configured separately.
download_hotc_baidu() {
  echo "[HOTC Baidu] URL:  https://pan.baidu.com/s/1FY2L6L9SDKw-V-bUkuosSA/"
  echo "[HOTC Baidu] Code: 886c"
  echo "[HOTC Baidu] Download via Baidu web UI or a configured Baidu CLI tool,"
  echo "             then place train/val/test subfolders under $HOTC_DIR/"
}
