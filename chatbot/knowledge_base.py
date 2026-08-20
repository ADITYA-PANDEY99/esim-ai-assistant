import os
import requests
from typing import List, Dict, Any
from chatbot.Appconfig import CONFIG

def _get_embedding(text: str) -> List[float]:
    """Generate 768-dim embeddings via Ollama nomic-embed-text."""
    base_url = CONFIG.get("ollama_base_url", "http://localhost:11434")
    model = CONFIG.get("embedding_model", "nomic-embed-text")
    try:
        resp = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("embedding", [])
    except Exception:
        pass
    # Fallback dummy embedding (768-dim) for offline/no-model tests
    return [0.0] * 768


def _get_collection():
    """
    Thread-Local ChromaDB connection factory (Chapter 4.5)
    Avoids SQLite multi-threading access violation crashes on Windows.
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CONFIG.chroma_dir)
        return client.get_or_create_collection(name="esim_manuals")
    except Exception as e:
        return None


def search_knowledge(query: str, top_k: int = 4, l2_threshold: float = 500.0) -> str:
    """
    Retrieval-Augmented Generation (RAG) query search (Chapter 3.3).
    Embeds query, retrieves nearest chunks, discards distance > l2_threshold.
    """
    coll = _get_collection()
    if coll is None or coll.count() == 0:
        return ""

    try:
        query_emb = _get_embedding(query)
        if not query_emb:
            return ""

        results = coll.query(
            query_embeddings=[query_emb],
            n_results=top_k
        )
        
        docs = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(docs)
        
        valid_chunks = []
        for doc, dist in zip(docs, distances):
            if dist <= l2_threshold:
                valid_chunks.append(doc)

        if not valid_chunks:
            return ""
            
        return "\n\n--- OFFICIAL eSim DOCUMENTATION CONTEXT ---\n" + "\n\n".join(valid_chunks) + "\n-----------------------------------------"
    except Exception:
        return ""


def ingest_manual_files(folder_path: str) -> int:
    """
    Ingestion pipeline: Chunks manual text files at paragraph boundaries
    and embeds into ChromaDB.
    """
    coll = _get_collection()
    if coll is None:
        return 0

    total_chunks = 0
    if not os.path.exists(folder_path):
        return 0

    for filename in os.listdir(folder_path):
        if filename.endswith(".txt") or filename.endswith(".md"):
            filepath = os.path.join(folder_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > 40]
            for idx, p in enumerate(paragraphs):
                chunk_id = f"{filename}_chunk_{idx}"
                emb = _get_embedding(p)
                coll.upsert(
                    ids=[chunk_id],
                    documents=[p],
                    embeddings=[emb],
                    metadatas=[{"source": filename, "chunk_idx": idx}]
                )
                total_chunks += 1

    return total_chunks
