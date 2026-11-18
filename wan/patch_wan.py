#!/usr/bin/env python3
# Applies the two pod-local Wan edits needed for TI2V-5B without flash-attn or the S2V/animate models.
# Run on a COPY of the pinned code (never the volume copy). Fails loudly if upstream text changes.
# Usage: python3 wan/patch_wan.py /root/wan2.2
import pathlib, sys

root = pathlib.Path(sys.argv[1])

def patch(rel, pairs):
    p = root / rel
    s = p.read_text()
    for old, new in pairs:
        n = s.count(old)
        if n != 1:
            sys.exit(f"PATCH_FAIL {rel}: expected 1 match, found {n}: {old!r}")
        s = s.replace(old, new)
    p.write_text(s)
    print(f"PATCH_OK {rel}")

# 1. Drop the speech2video and animate imports (their models are not used here).
patch("wan/__init__.py", [
    ("from .speech2video import WanS2V\n", ""),
    ("from .animate import WanAnimate", ""),
])

# 2. Use attention(), which falls back to torch scaled_dot_product_attention when flash-attn is absent.
patch("wan/modules/model.py", [
    ("from .attention import flash_attention", "from .attention import attention as flash_attention"),
])
