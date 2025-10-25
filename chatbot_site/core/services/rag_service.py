from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from chromadb import Client
from chromadb.config import Settings as ChromaSettings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from django.conf import settings
from django.utils import timezone
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ..models import DiscussionSession


@dataclass
class RetrievedChunk:
    text: str
    score: float
    metadata: Optional[Dict[str, object]] = None


_CHROMA_CLIENT = Client(ChromaSettings(anonymized_telemetry=False))


class RagService:
    """Utility for building and querying a lightweight RAG index."""

    def __init__(self, session: DiscussionSession) -> None:
        self.session = session
        self._client = _CHROMA_CLIENT
        self._embedding_function = OpenAIEmbeddingFunction(
            api_key=settings.OPENAI_API_KEY,
            model_name=settings.OPENAI_EMBEDDING_MODEL,
        )
        self._collection_name = f"session-{session.pk}"
        self._collection = self._get_or_create_collection()
        self._text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=160)

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------
    def build_index(self) -> int:
        """Recreate the vector index from the session's knowledge base."""

        raw_text = (self.session.knowledge_base or "").strip()
        self._reset_collection()
        if not raw_text:
            self.session.rag_chunk_count = 0
            self.session.rag_last_built_at = timezone.now()
            self.session.save(update_fields=["rag_chunk_count", "rag_last_built_at"])
            return 0

        chunks = self._text_splitter.split_text(raw_text)
        if not chunks:
            self.session.rag_chunk_count = 0
            self.session.rag_last_built_at = timezone.now()
            self.session.save(update_fields=["rag_chunk_count", "rag_last_built_at"])
            return 0

        chunk_ids = [f"knowledge-{index}" for index in range(len(chunks))]
        chunk_metadata = [
            {
                "session": self.session.s_id,
                "chunk_index": index,
            }
            for index in range(len(chunks))
        ]
        self._collection.add(ids=chunk_ids, documents=chunks, metadatas=chunk_metadata)
        self.session.rag_chunk_count = len(chunks)
        self.session.rag_last_built_at = timezone.now()
        self.session.save(update_fields=["rag_chunk_count", "rag_last_built_at"])
        return len(chunks)

    def _get_or_create_collection(self):
        return self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_function,
            metadata={"session": self.session.s_id},
        )

    def _reset_collection(self) -> None:
        try:
            self._client.delete_collection(name=self._collection_name)
        except ValueError:
            pass
        self._collection = self._client.create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_function,
            metadata={"session": self.session.s_id},
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 4) -> List[RetrievedChunk]:
        if self._collection.count() == 0:
            return []
        result = self._collection.query(
            query_texts=[query],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents") or []
        if not documents or not documents[0]:
            return []

        metadatas = result.get("metadatas") or [[]]
        distances = result.get("distances") or [[]]

        retrieved: List[RetrievedChunk] = []
        for index, document in enumerate(documents[0]):
            metadata: Optional[Dict[str, object]] = None
            if metadatas and metadatas[0] and index < len(metadatas[0]):
                metadata = metadatas[0][index]
            distance = 0.0
            if distances and distances[0] and index < len(distances[0]) and distances[0][index] is not None:
                distance = float(distances[0][index])
            score = 1.0 - distance
            retrieved.append(RetrievedChunk(text=document, score=score, metadata=metadata))
        return retrieved
