"""Minimal wrapper over Weaviate for storing ``RaptorNode`` objects."""

from __future__ import annotations

from typing import Callable, List
from uuid import uuid4

import numpy as np
import weaviate
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes import query as wv_query

from config.embeddings import openai_embedder
from utils.logger import get_logger

EmbedderFn = Callable[[str], List[float]]
logger = get_logger(__name__)


class FlatRaptorIndex:
    """Simplified index that clusters chunks after extraction."""

    CLASS_NAME = "RaptorNode"

    def __init__(
        self,
        client: weaviate.Client,
        embedder: EmbedderFn | None = None,
        alpha: float = 0.5,
    ) -> None:
        self.client = client
        self.embedder = embedder or openai_embedder
        self.alpha = alpha
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the ``RaptorNode`` class if it doesn't exist."""
        if self.client.collections.exists(self.CLASS_NAME):
            return
        self.client.collections.create(
            name=self.CLASS_NAME,
            vectorizer_config=Configure.Vectorizer.none(),
            inverted_index_config=Configure.inverted_index(),
            properties=[
                Property(name="text_vec", data_type=DataType.NUMBER_ARRAY),
                Property(name="fact_vec", data_type=DataType.NUMBER_ARRAY),
                Property(name="centroid", data_type=DataType.NUMBER_ARRAY),
            ],
        )

    def insert_chunk(self, text: str, triple_text: str) -> str:
        """Insert a new ``RaptorNode`` for the given chunk text.

        Both ``text`` and ``triple_text`` are embedded and blended with
        ``alpha`` to produce a centroid vector. The node UUID is returned.
        """
        text_vec = self.embedder(text)
        fact_vec = self.embedder(triple_text)
        centroid = (
            np.array(text_vec) * self.alpha + np.array(fact_vec) * (1 - self.alpha)
        ).tolist()

        coll = self.client.collections.get(self.CLASS_NAME)
        res = coll.query.near_vector(
            near_vector=centroid,
            limit=1,
            return_metadata=wv_query.MetadataQuery(distance=True),
        )
        if res.objects and res.objects[0].metadata.distance <= 0.1:
            node_id = res.objects[0].uuid
            logger.debug("Merged with existing RaptorNode %s", node_id)
            return node_id

        node_id = str(uuid4())
        coll.data.insert(
            uuid=node_id,
            properties={
                "text_vec": text_vec,
                "fact_vec": fact_vec,
                "centroid": centroid,
            },
            vector=centroid,
        )
        logger.debug("Inserted RaptorNode %s", node_id)
        return node_id
