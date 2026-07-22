# Omni description webservice (desktop/GPU)

Self-hosted, browser-driven webapp wrapping this repo's `OmniDescriptor` +
`MetadataSearch`. Meant to run on a machine with a GPU (e.g. your desktop) so
the CPU-only cluster deployment never has to load the vision-language model
itself.

**No NFS mount, no local copy of the media library.** Video files are read
entirely over HTTP, straight from a small dedicated nginx instance in the
cluster (`k8s/apps/media/omni-media-server.yaml`) that serves the media
share read-only with directory-listing (`autoindex_format json`) and
Range-request support. `ffmpeg`/OpenCV can both read frames and audio
directly from an HTTP URL, so nothing is downloaded up front — only the
byte ranges actually needed for hashing and frame/audio sampling.

That nginx instance is deliberately unauthenticated (no accounts) and
reachable at `https://omni-media.arishaig.site` (Traefik, wildcard cert,
gated by the `local-only` LAN IP allowlist — not Authelia, so no login) or
directly via its NodePort (`http://<any-node-ip>:30817`, bypassing Traefik
entirely). This is intentionally scoped to "temporary, local, don't care
about auth" use; tear it down (remove it from
`k8s/apps/media/kustomization.yaml` and its IngressRoute) once you're done
with this tool.

## Setup

1. Make sure `k8s/apps/media/omni-media-server.yaml` (+ its ConfigMap) has
   been applied via the normal Flux pipeline (commit + push — not
   `kubectl apply`).
2. Edit `omni_service/config.yaml`:
   - `videos.media_base_url` — `https://omni-media.arishaig.site` (or any
     cluster node's IP + `:30817` to bypass Traefik).
   - `main.project_config_directory` — local path for this service's own
     cache/model download dir.
3. Install deps (same as the main app — `torch` w/ CUDA, `transformers`,
   `flask`, `requests`, `xxhash`, etc. from the repo's `requirements.txt`),
   with a CUDA-enabled torch build for your GPU.

## Run

```
python omni_service/app.py
```

First `/describe` call downloads the omni model (`dystrio/MiniCPM-o-4_5-Sculpt-Throughput`
by default, ~5GB VRAM at 4-bit) and loads it into VRAM; it unloads itself
automatically after 5 minutes idle.

## Browser UI

Open `http://localhost:5050/` — a file browser over the media share (via
the nginx source above). Click into folders, hit "Describe" on a file to
generate/view its description (spinner while the model runs), or "Describe
all undescribed here" to walk a whole folder sequentially with a progress
counter. A status bar at top shows GPU availability, whether the model is
currently loaded in VRAM, and whether the media source is reachable. The
"already described" dot next to each file is a cache-only check — it never
triggers a model load just to render the list.

## API

- `GET /health` — status, CUDA availability, model-loaded state, media source reachability.
- `GET /api/browse?path=...` — directory listing (dirs/files) under `path`, with cache-only "described" flags.
- `POST /describe` — `{"file_path": "media/movies/Some Movie (2020)/movie.mkv"}` (relative to `videos.media_base_url`). Returns the generated description, file hash, and omni model hash.
- `POST /describe_batch` — `{"file_paths": [...]}`, same as above for a list.
- `POST /unload` — free VRAM immediately instead of waiting for the idle timeout.

## How hashes stay compatible with the cluster

`http_video_search.py` reimplements `modules.videos.engine.VideoSearch.get_file_hash()`'s
exact sampled-xxh3_128 algorithm (same 1MiB block size, same 5 head/middle/tail
sample positions, same size-mixing step) but reads the sampled byte ranges via
HTTP Range requests instead of local file seeks. Since the hash is purely a
function of file bytes, it comes out identical to what the cluster computes
from its own NFS mount of the same file.

Descriptions are cached locally under
`<project_config_directory>/cache/metadata_cache/`, keyed by
`auto_desc::{file_hash}::{model_hash}::describe_video_sampled` — the same
format the cluster app's own cache uses. To get them into the cluster, copy
that directory onto the `anagnorisis-config` PVC's `cache/metadata_cache/`
path (e.g. via `kubectl cp` through a throwaway pod). The cluster's own
`omni` is disabled (CPU-only), so it only ever *reads* that cache — it's
safe to add new files there while the pod is running.
