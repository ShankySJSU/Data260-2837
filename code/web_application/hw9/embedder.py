"""Query embeddings: sentence-transformers/all-MiniLM-L6-v2 (384-d, L2-normalised).

HW9_EMBEDDER=hash is a bag-of-words stand-in used ONLY by the offline smoke test
(no model download); all reported results use MiniLM.
"""

import hashlib
import os
import re

import numpy as np

from . import config as cfg

_MODEL = {}


def embedder_name():
    return "hash-bow (smoke test only)" if os.getenv("HW9_EMBEDDER") == "hash" else cfg.EMBED_MODEL


def embed(text):
    """Return a float32 unit vector of length EMBED_DIM."""
    if os.getenv("HW9_EMBEDDER") == "hash":
        vec = np.zeros(cfg.EMBED_DIM, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9']+", text.lower()):
            vec[int(hashlib.md5(tok.encode()).hexdigest(), 16) % cfg.EMBED_DIM] += 1.0
    else:
        if "m" not in _MODEL:
            from sentence_transformers import SentenceTransformer
            _MODEL["m"] = SentenceTransformer(cfg.EMBED_MODEL)
        vec = np.asarray(_MODEL["m"].encode(text, normalize_embeddings=True), dtype=np.float32)
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def cosine(a, b):
    return float(np.dot(a, b))  # both unit vectors
