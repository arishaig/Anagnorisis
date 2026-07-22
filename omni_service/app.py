"""
omni_service/app.py — standalone GPU-backed description webservice.

Wraps the same OmniDescriptor + MetadataSearch code the main Anagnorisis app
uses, as a small Flask API + browser UI meant to run directly on a machine
with a GPU (e.g. a desktop), decoupled from the CPU-only cluster deployment.

Media is read entirely over HTTP from a small unauthenticated nginx instance
in the cluster (see k8s/apps/media/omni-media-server.yaml) — this machine
never mounts the NFS share itself. cv2.VideoCapture()/ffmpeg both read HTTP
URLs directly (including Range-based seeking), and HttpVideoSearch
reproduces the cluster's exact sampled-hash algorithm over HTTP Range
requests, so file hashes/cache keys match what the cluster would compute
from its own NFS mount.

Run from the repo root:

    python omni_service/app.py

Model load/unload is lazy and automatic: OmniDescriptor loads on first
/describe call and frees VRAM again after 5 minutes of inactivity.
"""
import os
import sys
import traceback
import multiprocessing
from urllib.parse import quote, urljoin

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

import requests
from flask import Flask, request, jsonify, render_template

from src.app_factory.config_manager import ConfigManager
from src.metadata_search import MetadataSearch
from omni_service.http_video_search import HttpVideoSearch

SERVICE_ROOT = os.path.dirname(os.path.abspath(__file__))

cfg, paths = ConfigManager.setup(SERVICE_ROOT)

MEDIA_BASE_URL = cfg.videos.media_base_url.rstrip("/") + "/"

video_engine = HttpVideoSearch(cfg)
metadata_search = MetadataSearch(engine=video_engine)

app = Flask(__name__)


def _url_for(rel_path: str) -> str:
    """rel_path is always relative (URL-safe segments joined with '/')."""
    return urljoin(MEDIA_BASE_URL, quote(rel_path.strip("/")))


def _describe_one(rel_path: str) -> dict:
    ext = os.path.splitext(rel_path)[1].lower()
    if ext not in set(cfg.videos.media_formats):
        return {"file_path": rel_path, "error": f"unsupported extension: {ext}"}

    url = _url_for(rel_path)
    head = requests.head(url, timeout=10)
    if head.status_code != 200:
        return {"file_path": rel_path, "error": f"not found ({head.status_code})"}

    description = metadata_search.generate_full_description(
        url, MEDIA_BASE_URL, generate_desc_if_not_in_cache=True,
    )
    return {
        "file_path": rel_path,
        "file_hash": video_engine.get_file_hash(url),
        "model_hash": metadata_search.omni_descriptor.model_hash,
        "description": description,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/browse")
def browse():
    subpath = request.args.get("path", "").strip("/")
    listing_url = _url_for(subpath + "/" if subpath else "")

    try:
        r = requests.get(listing_url, timeout=15)
        r.raise_for_status()
        entries = r.json()
    except Exception as e:
        return jsonify({"error": f"failed to list {listing_url}: {e}"}), 502

    formats = set(cfg.videos.media_formats)
    dirs, files = [], []
    for entry in entries:
        name = entry.get("name")
        rel = f"{subpath}/{name}" if subpath else name
        if entry.get("type") == "directory":
            dirs.append({"name": name, "path": rel})
        elif os.path.splitext(name)[1].lower() in formats:
            files.append({"name": name, "path": rel})

    described = {}
    urls = [_url_for(f["path"]) for f in files]
    undescribed = metadata_search.get_undescribed_files(urls) if urls else []
    if undescribed is not None:
        undescribed_set = set(undescribed)
        for f, u in zip(files, urls):
            described[f["path"]] = u not in undescribed_set

    return jsonify({
        "path": subpath,
        "dirs": sorted(dirs, key=lambda d: d["name"].lower()),
        "files": [
            {"name": f["name"], "path": f["path"], "described": described.get(f["path"])}
            for f in sorted(files, key=lambda f: f["name"].lower())
        ],
    })


@app.get("/health")
def health():
    import torch
    media_ok = True
    try:
        requests.head(MEDIA_BASE_URL, timeout=5).raise_for_status()
    except Exception:
        media_ok = False
    return jsonify({
        "status": "ok",
        "cuda_available": torch.cuda.is_available(),
        "omni_model": cfg.omni.model_name,
        "model_loaded": bool(metadata_search.omni_descriptor.model_hash),
        "media_base_url": MEDIA_BASE_URL,
        "media_reachable": media_ok,
    })


@app.post("/describe")
def describe():
    data = request.get_json(force=True) or {}
    file_path = data.get("file_path")
    if not file_path:
        return jsonify({"error": "file_path is required"}), 400

    try:
        result = _describe_one(file_path)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    if "error" in result:
        return jsonify(result), 404 if "not found" in result["error"] else 400
    return jsonify(result)


@app.post("/describe_batch")
def describe_batch():
    data = request.get_json(force=True) or {}
    file_paths = data.get("file_paths") or []
    results = []
    for fp in file_paths:
        try:
            results.append(_describe_one(fp))
        except Exception as e:
            results.append({"file_path": fp, "error": str(e)})
    return jsonify({"results": results})


@app.post("/unload")
def unload():
    """Force-free VRAM immediately instead of waiting for the idle timeout."""
    metadata_search.omni_descriptor.unload()
    return jsonify({"status": "unloaded"})


if __name__ == "__main__":
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass
    port = int(os.environ.get("OMNI_SERVICE_PORT", "5050"))
    # Bind to localhost only by default — this is a personal desktop tool,
    # not something meant to be reachable from the rest of the network.
    app.run(host=os.environ.get("OMNI_SERVICE_HOST", "127.0.0.1"), port=port)
