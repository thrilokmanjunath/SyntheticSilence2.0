import hashlib
import logging
import numpy as np

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

log = logging.getLogger("syntheticsilence")


class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initializes the sentence transformer model.
        Using all-MiniLM-L6-v2 for local execution, with serverless fallback when
        running in environments with strict package size caps (e.g. Vercel).
        """
        self.model_name = model_name
        if HAS_SENTENCE_TRANSFORMERS:
            self.model = SentenceTransformer(model_name)
        else:
            log.warning("sentence-transformers not installed; using deterministic serverless fallback.")
            self.model = None

    def get_embeddings(self, texts: list[str]) -> np.ndarray:
        """
        Returns a numpy array of embeddings for the given texts (384-dimensional).
        """
        if not texts:
            return np.array([])

        if self.model is not None:
            return self.model.encode(texts, convert_to_numpy=True)

        rows = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            vec = rng.normal(size=384)
            vec /= np.linalg.norm(vec) + 1e-12
            rows.append(vec)
        return np.array(rows)
