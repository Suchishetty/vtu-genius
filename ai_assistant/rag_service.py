"""Persistent, per-student PDF retrieval using ChromaDB."""

import logging
import re
from pathlib import Path

from django.conf import settings

from .services import AIService


logger = logging.getLogger(__name__)


class RAGService:
    """Index notes and retrieve only chunks owned by the requesting student."""

    collection_name = "student_note_chunks"
    embedding_model_name = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_size = 900
    chunk_overlap = 150
    max_pdf_chars = 200000
    _embedding_model = None

    @staticmethod
    def _is_enabled():
        return settings.RAG_ENABLED

    def __init__(self):
        if not self._is_enabled():
            raise RuntimeError("RAG indexing is disabled in this environment.")
        import chromadb

        database_path = Path(settings.CHROMA_DB_PATH)
        self.client = chromadb.PersistentClient(path=str(database_path))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @classmethod
    def _get_embedding_model(cls):
        """Load the embedding model once per Django process."""
        if cls._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            cls._embedding_model = SentenceTransformer(cls.embedding_model_name)
        return cls._embedding_model

    def _embed(self, texts):
        return self._get_embedding_model().encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()

    def _split_text(self, text):
        """Create readable, overlapping chunks without producing tiny fragments."""
        paragraphs = [
            re.sub(r"\s+", " ", paragraph).strip()
            for paragraph in re.split(r"\n\s*\n", text)
        ]
        paragraphs = [paragraph for paragraph in paragraphs if paragraph]
        chunks = []
        current = ""

        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 1 > self.chunk_size:
                chunks.append(current)
                overlap = current[-self.chunk_overlap:]
                current = f"{overlap} {paragraph}".strip()
            else:
                current = f"{current} {paragraph}".strip()

            while len(current) > self.chunk_size * 2:
                chunks.append(current[:self.chunk_size])
                current = current[self.chunk_size - self.chunk_overlap:].strip()

        if current:
            chunks.append(current)

        # Keep only useful chunks. A short final fragment is joined to its predecessor.
        if len(chunks) > 1 and len(chunks[-1]) < 200:
            chunks[-2] = f"{chunks[-2]} {chunks[-1]}"
            chunks.pop()
        return [chunk for chunk in chunks if len(chunk) >= 100]

    def _extract_note_text(self, note):
        if not note.pdf:
            return ""
        try:
            note.pdf.open("rb")
            return AIService.extract_pdf_text(note.pdf, max_chars=self.max_pdf_chars)
        finally:
            try:
                note.pdf.close()
            except Exception:
                pass

    def index_note(self, note):
        """Extract, chunk, embed, and persist one note. Safe to call on re-upload."""
        if not self._is_enabled():
            logger.info(
                "RAG indexing skipped for note_id=%s because RAG_ENABLED=False",
                note.pk,
            )
            return 0

        text = self._extract_note_text(note)
        chunks = self._split_text(text)
        if not chunks:
            logger.warning("RAG indexing skipped for note_id=%s: no readable PDF text", note.pk)
            return 0

        self.delete_note_from_index(note)
        metadata = {
            "student_id": str(note.student_id),
            "note_id": str(note.pk),
            "subject": str(note.subject),
            "semester": str(note.semester),
            "unit": str(note.unit),
        }
        ids = [f"note_{note.pk}_chunk_{number}" for number in range(len(chunks))]
        self.collection.add(
            ids=ids,
            documents=chunks,
            embeddings=self._embed(chunks),
            metadatas=[metadata.copy() for _ in chunks],
        )
        logger.info("RAG indexed note_id=%s chunks=%d", note.pk, len(chunks))
        return len(chunks)

    def delete_note_from_index(self, note):
        """Remove all vector chunks for a note without touching other students' data."""
        if not self._is_enabled():
            logger.info(
                "RAG index cleanup skipped for note_id=%s because RAG_ENABLED=False",
                note.pk,
            )
            return

        self.collection.delete(
            where={
                "$and": [
                    {"student_id": str(note.student_id)},
                    {"note_id": str(note.pk)},
                ]
            }
        )
        logger.info("RAG deleted chunks for note_id=%s", note.pk)

    def search_relevant_chunks(
        self,
        student_profile,
        question,
        top_k=5,
        note_id=None,
        subject=None,
        unit=None,
    ):
        """Return chunks filtered by student and optional note metadata."""
        if not self._is_enabled():
            logger.info(
                "RAG retrieval skipped for student_id=%s because RAG_ENABLED=False",
                student_profile.pk,
            )
            return []
        if not question or not question.strip():
            return []
        filters = [{"student_id": str(student_profile.pk)}]
        if note_id is not None:
            filters.append({"note_id": str(note_id)})
        if subject is not None:
            filters.append({"subject": str(subject)})
        if unit is not None:
            filters.append({"unit": str(unit)})
        result = self.collection.query(
            query_embeddings=self._embed([question.strip()]),
            n_results=top_k,
            where=(filters[0] if len(filters) == 1 else {"$and": filters}),
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0] or []
        metadatas = result.get("metadatas", [[]])[0] or []
        distances = result.get("distances", [[]])[0] or []
        chunks = [
            {"text": text, "metadata": metadata, "distance": distance}
            for text, metadata, distance in zip(documents, metadatas, distances)
        ]
        logger.info(
            "RAG search student_id=%s note_id=%s results=%d",
            student_profile.pk,
            note_id,
            len(chunks),
        )
        return chunks
