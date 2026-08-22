import re
import time
import numpy as np
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
import chromadb

from ..core.config import settings

# ---------------------------------------------------------------------------
# Chroma setup — embedded/local, no separate server needed. Data persists in
# a folder called "chroma_data" inside the backend directory.
# ---------------------------------------------------------------------------
_chroma_client = chromadb.PersistentClient(path="./chroma_data")
_collection = _chroma_client.get_or_create_collection(name="document_chunks")

EMBEDDING_MODEL = "models/gemini-embedding-001"
MAX_EMBED_RETRIES = 5
EMBED_BACKOFF_SECONDS = 3


def embed_text(text: str, task_type: str = "retrieval_document") -> list[float]:
    """Embeds a single piece of text via Gemini's embedding model, with retry on rate limits."""
    for attempt in range(MAX_EMBED_RETRIES):
        try:
            result = genai.embed_content(
                model=EMBEDDING_MODEL,
                content=text,
                task_type=task_type,
            )
            return result["embedding"]
        except google_exceptions.ResourceExhausted:
            wait = EMBED_BACKOFF_SECONDS * (2 ** attempt)
            print(f"[RAG] Embedding rate-limited, waiting {wait}s (attempt {attempt + 1}/{MAX_EMBED_RETRIES})...")
            time.sleep(wait)
    raise Exception("Embedding failed after multiple retries — rate limit exceeded.")


def embed_texts(texts: list[str], task_type: str = "retrieval_document") -> list[list[float]]:
    """Embeds a list of texts one at a time (safer against rate limits than a single big batch call)."""
    embeddings = []
    for t in texts:
        embeddings.append(embed_text(t, task_type))
        time.sleep(0.5)  # small gap between calls to be gentle on quota
    return embeddings


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def _split_into_sentences(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def semantic_chunk(
    text: str,
    group_size: int = 3,
    similarity_threshold: float = 0.72,
    max_chunk_chars: int = 2000,
) -> list[str]:
    """
    Groups sentences into small units, embeds each unit, then merges consecutive
    units into a chunk as long as they stay semantically similar (same topic).
    A new chunk starts when similarity drops (topic change) or the chunk gets too long.
    """
    sentences = _split_into_sentences(text)
    if not sentences:
        return []

    units = [" ".join(sentences[i:i + group_size]) for i in range(0, len(sentences), group_size)]
    if len(units) == 1:
        return units

    unit_embeddings = embed_texts(units, task_type="retrieval_document")

    chunks = []
    current_chunk = units[0]
    current_embedding = unit_embeddings[0]

    for i in range(1, len(units)):
        similarity = _cosine_similarity(current_embedding, unit_embeddings[i])
        fits_size = len(current_chunk) + len(units[i]) <= max_chunk_chars

        if similarity >= similarity_threshold and fits_size:
            current_chunk += " " + units[i]
            # running average embedding, so the chunk's "topic" adapts as it grows
            current_embedding = list(
                (np.array(current_embedding) + np.array(unit_embeddings[i])) / 2
            )
        else:
            chunks.append(current_chunk)
            current_chunk = units[i]
            current_embedding = unit_embeddings[i]

    chunks.append(current_chunk)
    return chunks


def index_document(document_id: int, user_id: int, text: str) -> None:
    """
    Semantically chunks a document's text, embeds each chunk, and stores them
    in ChromaDB tagged with the document's id (so retrieval can be scoped to it).
    """
    if not text or not text.strip():
        return

    chunks = semantic_chunk(text)
    if not chunks:
        return

    embeddings = embed_texts(chunks, task_type="retrieval_document")
    ids = [f"doc{document_id}_chunk{i}" for i in range(len(chunks))]
    metadatas = [{"document_id": document_id, "user_id": user_id, "chunk_index": i} for i in range(len(chunks))]

    _collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )


def retrieve_relevant_chunks(document_id: int, question: str, top_k: int = 5) -> list[str]:
    """Embeds the question and returns the top_k most semantically relevant chunks for this document."""
    query_embedding = embed_text(question, task_type="retrieval_query")

    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"document_id": document_id},
    )

    documents = results.get("documents") or [[]]
    return documents[0] if documents else []


def delete_document_chunks(document_id: int) -> None:
    """Removes all stored chunks for a document (call this when the document itself is deleted)."""
    try:
        _collection.delete(where={"document_id": document_id})
    except Exception:
        pass  # nothing to delete, or collection empty — safe to ignore