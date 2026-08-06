"""src.metadata — the module-independent metadata subsystem.

Everything needed to describe a file in text and search those descriptions
semantically, without knowing which module (if any) owns the file:

  media_types  content-kind taxonomy loaded from media_types/*.yaml
  extractors   internal-metadata readers, one per media type
  models       the single seam where a media type meets an embedding model
  proxy        zero-shot tags + fingerprint derived from cached embeddings
  search       MetadataSearch — builds descriptions, embeds and compares them
  indexer      background schedulers that keep the caches warm

Import submodules directly (``from src.metadata.search import
get_metadata_search``). This file stays free of imports on purpose: the
taxonomy is read during config setup, long before the heavy embedding models
should be pulled into the process.
"""
