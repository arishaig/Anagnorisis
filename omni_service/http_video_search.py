"""
HTTP-backed variant of modules.videos.engine.VideoSearch.

The real VideoSearch.get_file_hash() opens a local file (os.stat + seeked
reads) to compute a sampled xxh3_128 fingerprint. This subclass reproduces
the exact same algorithm — same block size, same sample count, same head/
middle/tail offsets, same final size-mixing step — over HTTP Range requests
instead, so the resulting hash is byte-for-byte identical to what the
cluster computes when it reads the same file from its NFS mount. That's
what lets the two caches (this service's local one, and the cluster pod's)
be merged later.

Nothing else about VideoSearch needs to change: MetadataSearch and
OmniDescriptor both just treat "file_path" as an opaque string, and
cv2.VideoCapture()/ffmpeg both accept HTTP(S) URLs directly.
"""
import os
import requests
import xxhash

from modules.videos.engine import VideoSearch

_BLOCK = 1 * 1024 * 1024  # 1 MiB per sample — must match engine.py
_SAMPLES = 5              # head, middle, tail pattern — must match engine.py


class HttpVideoSearch(VideoSearch):
    def get_file_hash(self, url: str) -> str:
        head = requests.head(url, timeout=10)
        head.raise_for_status()
        size = int(head.headers["Content-Length"])
        last_modified = head.headers.get("Last-Modified", "")

        cache_key = f"HTTP_HASH_OF_FILE::{url}::{size}::{last_modified}::{self.get_hash_algorithm()}"
        cached = self._fast_cache.get(cache_key)
        if cached is not None:
            return cached

        h = xxhash.xxh3_128()
        if size <= _BLOCK * _SAMPLES:
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            h.update(r.content)
        else:
            if _SAMPLES <= 1:
                positions = [0]
            elif _SAMPLES == 2:
                positions = [0, max(0, size - _BLOCK)]
            else:
                step = (size - _BLOCK) // (_SAMPLES - 1)
                positions = [min(i * step, max(0, size - _BLOCK)) for i in range(_SAMPLES)]
                positions[0] = 0
                positions[-1] = max(0, size - _BLOCK)

            for pos in positions:
                end = pos + _BLOCK - 1
                r = requests.get(url, headers={"Range": f"bytes={pos}-{end}"}, timeout=60)
                if r.status_code not in (200, 206) or not r.content:
                    break
                h.update(r.content)
            h.update(size.to_bytes(8, byteorder="little", signed=False))

        result = h.hexdigest()
        self._fast_cache.set(cache_key, result)
        return result
