#!/usr/bin/env bash
# Preflight for the Wan test: CUDA visible to the Wan venv and the Wan modules the generator imports.
set -euo pipefail
/root/venv_wan/bin/python -c "import torch; assert torch.cuda.is_available(), 'no CUDA'; print('CUDA_OK', torch.version.cuda)"
cd /root/wan2.2 && /root/venv_wan/bin/python -c "import wan.textimage2video, wan.distributed.util, wan.utils.prompt_extend, wan.utils.utils, wan.utils.fm_solvers_unipc; print('WAN_IMPORT_OK')" || { echo WAN_IMPORT_FAIL; exit 1; }
echo PREFLIGHT_OK
