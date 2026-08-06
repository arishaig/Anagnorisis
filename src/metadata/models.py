"""models.py — the one seam between a media type and an embedding model.

Media types are content kinds (see ``media_types.py``); nothing in the taxonomy
or in ``media_types/*.yaml`` names a model. The mapping from a content kind to
the model that handles it lives here and nowhere else, so replacing CLAP and
SigLIP with a single omni embedding model is an edit to the two tables below —
no group renames, no config migration, no cache-directory churn.

The tables are also the single definition of each type's *embedding identity*
(cache directory and version suffix). The module search engines read their
``cache_prefix`` / ``_get_model_hash_postfix`` from here rather than declaring
their own, because a divergence between the two would not raise — it would just
silently stop the proxy from finding embeddings.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch

from src.audio_embedder import AudioEmbedder
from src.base_search_engine import embedding_cache_key
from src.caching import get_two_level_cache
from src.image_embedder import ImageEmbedder
from src.metadata.media_types import MediaType
from src.metadata.proxy import EmbeddingProxyGenerator


@dataclass(frozen=True)
class EmbeddingModel:
    """How one media type turns file content into a vector.

    embedder_cls  A singleton embedder in src/ — constructing it is free, and
                  only ``initiate()`` loads anything.
    cache_prefix  Sub-directory of the cache holding this type's embeddings.
    version       Cache-key suffix; bump by hand to invalidate this type's
                  embeddings after an incompatible change.
    """

    embedder_cls: type
    cache_prefix: str
    version: str = ''


# Types absent from this table have no content embedding, and therefore no
# embedding proxy — they are described by filename, path and metadata alone.
_EMBEDDING_MODELS: dict[str, EmbeddingModel] = {
    # cache_prefix is 'music' rather than 'audio' only because that is where
    # existing installations already have their CLAP embeddings; renaming it
    # would silently orphan them and force a full re-embed.
    'audio': EmbeddingModel(AudioEmbedder, cache_prefix='music', version='v1.2'),
    'images': EmbeddingModel(ImageEmbedder, cache_prefix='images', version='_v1.0.1'),
}

# Which OmniDescriptor method produces a natural-language description of each
# type. Types absent here get no automatic description.
_DESCRIBE_METHODS: dict[str, str] = {
    'audio': 'describe_audio_sampled',
    'images': 'describe_image',
    'videos': 'describe_video_sampled',
    'text': 'describe_text',
}


# ---- lookups ----------------------------------------------------------

def embedding_model_for(type_name: str) -> Optional[EmbeddingModel]:
    """The embedding model for *type_name*, or None if it has none."""
    return _EMBEDDING_MODELS.get(type_name)


def cache_prefix_for(type_name: str) -> str:
    """Cache sub-directory for a type's embeddings. Raises if it has no model."""
    return _require(type_name).cache_prefix


def embedding_version_for(type_name: str) -> str:
    """Cache-key version suffix for a type's embeddings."""
    return _require(type_name).version


def describe_method_for(type_name: Optional[str]) -> Optional[str]:
    """OmniDescriptor method name for *type_name*, or None if undescribable."""
    return _DESCRIBE_METHODS.get(type_name) if type_name else None


def _require(type_name: str) -> EmbeddingModel:
    model = _EMBEDDING_MODELS.get(type_name)
    if model is None:
        raise KeyError(
            f"Media type '{type_name}' has no embedding model in "
            f"src/metadata/models.py. Known: {', '.join(_EMBEDDING_MODELS)}."
        )
    return model


# ---- proxy construction -----------------------------------------------

class _ProxySource:
    """Gives the embedding proxy a model without giving it a search engine.

    Reads embeddings straight from the cache the module engines write to, so a
    proxy section costs no model load and no file read. The model is loaded only
    to embed the tag vocabulary, which happens once per vocabulary.
    """

    def __init__(self, cfg, media_type: MediaType, model: EmbeddingModel):
        self._cfg = cfg
        self._model = model
        self.name = media_type.name
        self._cache = get_two_level_cache(
            cache_dir=f"{cfg.main.cache_path}/{model.cache_prefix}",
            name=model.cache_prefix,
        )

    @property
    def _embedder(self):
        # Embedders are singletons, so this is the same instance the module
        # engine uses — including its model_hash once anything has loaded it.
        return self._model.embedder_cls(self._cfg)

    @property
    def model_hash(self) -> Optional[str]:
        """Hash of the loaded model, or None while no model has been loaded."""
        return self._embedder.model_hash

    def embedding_key(self, file_path: str) -> Optional[str]:
        """Cache key of *file_path*'s content embedding, or None if unknowable."""
        model_hash = self.model_hash
        if not model_hash:
            return None
        return embedding_cache_key(file_path, model_hash, self._model.version)

    def cached_embedding(self, file_path: str) -> Optional[np.ndarray]:
        """The file's content embedding if already computed, else None.

        Never loads a model and never reads the file.
        """
        key = self.embedding_key(file_path)
        if key is None:
            return None
        value = self._cache.get(key)
        if value is None:
            return None
        if isinstance(value, torch.Tensor):
            return value.detach().cpu().numpy().ravel().astype(np.float32)
        return np.asarray(value, dtype=np.float32).ravel()

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a tag string. Loads the model if it is not loaded yet."""
        embedder = self._embedder
        if not embedder.model_hash:
            embedder.initiate(self._cfg.main.embedding_models_path)
        return np.asarray(embedder.embed_text(text), dtype=np.float32).ravel()


_PROXIES: dict[str, Optional[EmbeddingProxyGenerator]] = {}
_PROXIES_LOCK = threading.Lock()


def get_proxy(cfg, media_type: Optional[MediaType]) -> Optional[EmbeddingProxyGenerator]:
    """Process-wide proxy generator for *media_type*, or None if it has no model."""
    if media_type is None:
        return None
    if media_type.name not in _PROXIES:
        with _PROXIES_LOCK:
            if media_type.name not in _PROXIES:
                _PROXIES[media_type.name] = _build_proxy(cfg, media_type)
    return _PROXIES[media_type.name]


def _build_proxy(cfg, media_type: MediaType) -> Optional[EmbeddingProxyGenerator]:
    model = _EMBEDDING_MODELS.get(media_type.name)
    if model is None:
        return None
    return EmbeddingProxyGenerator(
        source=_ProxySource(cfg, media_type, model),
        tags=media_type.tags,
        threshold=media_type.tags_threshold,
        cache_path=cfg.main.cache_path,
    )
