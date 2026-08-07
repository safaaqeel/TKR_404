"""
Knowledge Base search + document preview. Powers the Knowledge Base page,
backed by ChromaDB via app/rag/retriever.py.
"""
from fastapi import APIRouter, HTTPException
from app.rag.retriever import retrieve_relevant_documents
from app.rag.vector_store import get_document_chunks

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.get("/search")
async def search_knowledge_base(q: str, top_k: int = 8):
    results = retrieve_relevant_documents(q, top_k=top_k)
    return {"query": q, "results": results}


@router.get("/document/{doc_id}")
async def get_document(doc_id: str):
    """Full chunk-by-chunk content of one indexed document, ordered by
    chunk_index. Used by the Knowledge Base page's document preview."""
    chunks = get_document_chunks(doc_id)
    if not chunks:
        raise HTTPException(status_code=404, detail=f"No indexed document with id {doc_id!r}.")

    filename = chunks[0].metadata.get("filename", "")
    source_type = chunks[0].metadata.get("source_type", "")
    return {
        "id": doc_id,
        "filename": filename,
        "source_type": source_type,
        "chunk_count": len(chunks),
        "chunks": [
            {
                "chunk_index": c.metadata.get("chunk_index", 0),
                "page_number": c.metadata.get("page_number"),
                "text": c.text,
            }
            for c in chunks
        ],
    }