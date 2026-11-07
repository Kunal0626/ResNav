"""Text encoders behind one interface, so ranking degrades instead of failing.

The original engine imported `sentence_transformers` at call time with no
fallback: if the package was absent — which it is on any deploy target where a
2.5 GB torch wheel does not fit — every search raised ImportError and returned a
500. Here the transformer path is opt-in via ENABLE_TRANSFORMERS, and a TF-IDF
encoder covers the default case.

Both encoders return L2-normalised dense matrices, so cosine similarity is just
a dot product and the downstream scoring code is identical either way.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

import numpy as np

log = logging.getLogger(__name__)


class Encoder:
    """Interface: fit an optional corpus, then encode texts to unit vectors."""

    name = "base"

    def fit(self, corpus: Sequence[str]) -> None:  # pragma: no cover - trivial
        pass

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        raise NotImplementedError


def _normalise(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    # Zero vectors (a document with no in-vocabulary terms) would divide by zero.
    norms[norms == 0] = 1.0
    return matrix / norms


class TfidfEncoder(Encoder):
    """Word + character n-gram TF-IDF, reduced to a dense vector via SVD.

    Character n-grams matter here because relief queries are full of typos and
    transliterations ("paani", "medcine") that pure word features miss.
    """

    name = "tfidf"

    def __init__(self, n_components: int = 128):
        self._n_components = n_components
        self._vectoriser = None
        self._svd = None
        self._lock = threading.Lock()

    def fit(self, corpus: Sequence[str]) -> None:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import FeatureUnion

        corpus = [t for t in corpus if t and t.strip()]
        if not corpus:
            raise ValueError("Cannot fit TfidfEncoder on an empty corpus.")

        with self._lock:
            self._vectoriser = FeatureUnion([
                ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2),
                                         sublinear_tf=True, min_df=1)),
                ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                         sublinear_tf=True, min_df=1)),
            ])
            sparse = self._vectoriser.fit_transform(corpus)

            # SVD needs strictly fewer components than features and samples.
            n_components = min(self._n_components, sparse.shape[1] - 1, len(corpus) - 1)
            if n_components >= 2:
                self._svd = TruncatedSVD(n_components=n_components, random_state=42)
                self._svd.fit(sparse)
            else:
                # Corpus too small to reduce; cosine on raw TF-IDF is fine.
                self._svd = None
            log.info("TF-IDF encoder fitted on %d documents (dim=%s).",
                     len(corpus), n_components if self._svd else sparse.shape[1])

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        if self._vectoriser is None:
            raise RuntimeError("TfidfEncoder.encode() called before fit().")
        sparse = self._vectoriser.transform(list(texts))
        dense = self._svd.transform(sparse) if self._svd is not None else sparse.toarray()
        return _normalise(np.asarray(dense, dtype=np.float32))


class TransformerEncoder(Encoder):
    """SentenceTransformer wrapper. Model is loaded once and reused."""

    name = "sentence-transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer

                    log.info("Loading SentenceTransformer '%s'…", self._model_name)
                    self._model = SentenceTransformer(self._model_name, device="cpu")
                    log.info("Model loaded (dim=%d).", self._model.get_sentence_embedding_dimension())
        return self._model

    def encode(self, texts: Sequence[str]) -> np.ndarray:
        model = self._load()
        vectors = model.encode(list(texts), normalize_embeddings=True,
                               show_progress_bar=False, batch_size=32)
        return np.asarray(vectors, dtype=np.float32)


def build_encoder(*, prefer_transformers: bool) -> Encoder:
    """Pick the best encoder that this environment can actually run."""
    if prefer_transformers:
        try:
            import sentence_transformers  # noqa: F401

            return TransformerEncoder()
        except ImportError:
            log.warning(
                "ENABLE_TRANSFORMERS is set but sentence-transformers is not installed; "
                "falling back to TF-IDF. Install with: pip install -r requirements-ml.txt"
            )
    return TfidfEncoder()


def cosine_scores(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of one unit vector against a unit-vector matrix."""
    if matrix.size == 0:
        return np.zeros(0, dtype=np.float32)
    return np.clip(matrix @ query_vector.ravel(), -1.0, 1.0)
