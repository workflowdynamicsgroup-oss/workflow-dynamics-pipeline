#!/usr/bin/env bash
# Dry checks before any checkpoint copy or GPU spend. Fails in seconds, not minutes.
set -euo pipefail
/root/venv_wan/bin/python -c "import torch; assert torch.cuda.is_available(), 'no CUDA'; print('CUDA_OK', torch.version.cuda)"
python3 -c "import imageio, imageio_ffmpeg; imageio.v3.imwrite('/tmp/t.mp4', [[[0,0,0]]*8]*8, fps=5); print('MP4_WRITE_OK')" || { echo 'MP4_WRITE_FAIL'; exit 1; }
python3 -c "import onnxruntime as ort; p=ort.get_available_providers(); assert 'CUDAExecutionProvider' in p, p; print('ORT_CUDA_OK')"
echo PREFLIGHT_OK
