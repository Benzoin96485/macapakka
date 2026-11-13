#!/bin/zsh
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
music_python="${VIBACAPPELLA_PYTHON:-/Users/weiliangluo/src/vibacappella-claude/_work/venv/bin/python}"
source_dir="$project_dir/outputs/EYKM_Acappella_v3/source"
export OPENBLAS_NUM_THREADS=1
"$music_python" -B "$source_dir/build_v3.py"
"$music_python" -B "$source_dir/render_notation.py"
"$music_python" -B "$source_dir/render_samples.py"
"$music_python" -B "$source_dir/validate_v3.py"
"$music_python" -B "$source_dir/document_release.py"
