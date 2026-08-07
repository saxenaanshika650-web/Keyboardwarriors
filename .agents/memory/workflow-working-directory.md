---
name: Artifact workflow working directory
description: Managed artifact workflows run with the artifact directory as their working directory.
---

Managed artifact commands execute from the artifact's own directory, so commands should reference local entry points directly rather than changing into the artifact directory again.

**Why:** Adding a second directory change caused the service startup command to look for a nested artifact path and fail.

**How to apply:** For artifact-owned workflows, use `uvicorn main:app ...` when the entry point is in the artifact root; use `--app-dir artifacts/<slug>` only for production commands launched from the workspace root.