#!/usr/bin/env python3
# Loads the models that failed or can fail silently, before the render. Run with /root/venv_ditto/bin/python.
# Usage: check_ditto_models.py DATA_ROOT
import sys, os
root = sys.argv[1]
bad = []
try:
    import onnxruntime as ort
    f = os.path.join(root, "aux_models", "det_10g.onnx")
    sess = ort.InferenceSession(f, providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    first = sess.get_providers()[0]
    print(f"{'OK  ' if first == 'CUDAExecutionProvider' else 'FAIL'} onnx providers {sess.get_providers()}")
    if first != "CUDAExecutionProvider": bad.append("onnx_cuda_fallback_to_cpu")
except Exception as e:
    print(f"FAIL onnx load {type(e).__name__}: {e}"); bad.append("onnx_load")
try:
    from mediapipe.tasks.python import vision, BaseOptions
    t = os.path.join(root, "aux_models", "face_landmarker.task")
    vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path=t), num_faces=1))
    print("OK   mediapipe FaceLandmarker loads")
except Exception as e:
    print(f"FAIL mediapipe {type(e).__name__}: {e}"); bad.append("mediapipe")
if bad:
    print("DITTO_MODELS_FAIL", bad); sys.exit(1)
print("DITTO_MODELS_OK")
