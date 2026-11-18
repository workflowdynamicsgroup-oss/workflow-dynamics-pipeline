# workflow-dynamics-pipeline

Run wrappers and checks for the Workflow Dynamics video pipeline: Chatterbox narration, Ditto avatar, Wan 2.2 video, FLUX stills, captions and props.

Rules:
- Every pod clones a pinned commit. Nothing runs from an unpinned copy.
- Each run log's first line records the commit hash and the sha256 of the wrapper it ran.
- Each problem gets one line in CHANGELOG.md (symptom, cause, fix) and a commit.
- Only the RTX 4090 and A40 are used for the Chatterbox + Ditto pipeline.
- Preflight checks run before any GPU spend.
