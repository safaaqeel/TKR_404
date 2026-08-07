"""
Purpose:    Load and chunk source documents (PDF, TXT, CSV) into overlapping text
            chunks with citation-ready metadata, for downstream embedding and
            indexing into ChromaDB. Loading and splitting are merged into this
            one module per the canonical spec (replaces old loaders.py + splitter.py).
Inputs:     File paths to .pdf / .txt / .csv files under data/uploads/ (runtime
            uploads) or data/documents/** (curated knowledge base).
Outputs:    list[DocumentChunk] — chunked text (800 tokens, 120 overlap) with
            metadata: doc_id, filename, chunk_index, page_number, source_type,
            ingested_at. Consumed by rag/embeddings.py + rag/vector_store.py.
Depends on: pypdf, pandas, langchain (RecursiveCharacterTextSplitter). No
            project-internal imports — this module is foundational, built first
            (§17), and rag/ never imports from agents/ (§3.3).
Called by:  app/routes.py (POST /api/knowledge/upload), and any ingestion script
            that indexes data/documents/** at startup.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pypdf import PdfReader

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: set[str] = {".pdf", ".txt", ".csv"}
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 120
CSV_ROWS_PER_BLOCK: int = 50


class DocumentLoadError(Exception):
    """Raised when a source file is missing, unsupported, or unreadable."""


@dataclass
class DocumentChunk:
    """One chunk of text plus the metadata rag/vector_store.py needs to persist it."""

    doc_id: str
    filename: str
    chunk_index: int
    text: str
    page_number: int | None
    source_type: str
    ingested_at: str

    def to_metadata(self) -> dict[str, Any]:
        """Metadata dict shaped to match the `documents` collection schema (§6.3)."""
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "source_type": self.source_type,
            "ingested_at": self.ingested_at,
        }


def _new_doc_id() -> str:
    return uuid.uuid4().hex


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_pdf(path: Path) -> list[tuple[str, int | None]]:
    """Extract text page by page. Returns (page_text, page_number) tuples, 1-indexed."""
    try:
        reader = PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001 - surfaced as a structured load error
        raise DocumentLoadError(f"Could not open PDF '{path.name}': {exc}") from exc

    pages: list[tuple[str, int | None]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - one bad page shouldn't fail the doc
            logger.warning(
                "Failed to extract text from page %d of '%s': %s", page_number, path.name, exc
            )
            text = ""
        if text.strip():
            pages.append((text, page_number))
    return pages


def _load_txt(path: Path) -> list[tuple[str, int | None]]:
    """Plain read. TXT files have no page concept, so page_number is always None."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise DocumentLoadError(f"Could not read TXT '{path.name}': {exc}") from exc
    return [(text, None)]


def _load_csv(path: Path) -> list[tuple[str, int | None]]:
    """
    Row/block loader: groups rows into readable text blocks (header + N rows) so the
    text splitter still has natural breakpoints, instead of embedding an entire
    spreadsheet as one blob. This is for RAG ingestion only — structured CSV analysis
    for the Analysis Agent reads data/datasets/*.csv directly via pandas, not this path.
    """
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:  # noqa: BLE001 - structured error, never a raw traceback
        raise DocumentLoadError(f"Could not read CSV '{path.name}': {exc}") from exc

    if df.empty:
        return []

    columns = list(df.columns)
    blocks: list[tuple[str, int | None]] = []
    for start in range(0, len(df), CSV_ROWS_PER_BLOCK):
        block_df = df.iloc[start : start + CSV_ROWS_PER_BLOCK]
        lines = [", ".join(columns)]
        lines.extend(", ".join(str(row[col]) for col in columns) for _, row in block_df.iterrows())
        blocks.append(("\n".join(lines), None))
    return blocks


_LOADERS = {
    ".pdf": _load_pdf,
    ".txt": _load_txt,
    ".csv": _load_csv,
}


def load_and_chunk(
    file_path: str | Path, source_type: str = "document", doc_id: str | None = None
) -> list[DocumentChunk]:
    """
    Load a single source file and split it into overlapping chunks.

    Args:
        file_path: Path to a .pdf, .txt, or .csv file (data/uploads/ or data/documents/**).
        source_type: Label stored in chunk metadata, e.g. "government", "faq", "upload".
            Callers ingesting data/documents/<category>/ typically pass the folder name.
        doc_id: Optional caller-supplied id (e.g. the upload's generated UUID, matching
            the source file's name on disk). If omitted, one is generated here.

    Returns:
        List of DocumentChunk. All chunks from one file share the same doc_id.

    Raises:
        DocumentLoadError: file missing, unsupported extension, or unreadable content.
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        raise DocumentLoadError(f"File not found: {file_path}")

    extension = path.suffix.lower()
    loader = _LOADERS.get(extension)
    if loader is None:
        raise DocumentLoadError(
            f"Unsupported file type '{extension}' for '{path.name}'. "
            f"Supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    sections = loader(path)
    if not sections:
        logger.warning("No extractable text found in '%s'", path.name)
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )

    doc_id = doc_id or _new_doc_id()
    ingested_at = _now_iso()
    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for section_text, page_number in sections:
        for piece in splitter.split_text(section_text):
            if not piece.strip():
                continue
            chunks.append(
                DocumentChunk(
                    doc_id=doc_id,
                    filename=path.name,
                    chunk_index=chunk_index,
                    text=piece,
                    page_number=page_number,
                    source_type=source_type,
                    ingested_at=ingested_at,
                )
            )
            chunk_index += 1

    logger.info("Loaded '%s' -> %d chunks (doc_id=%s)", path.name, len(chunks), doc_id)
    return chunks


def load_directory(directory: str | Path, source_type: str | None = None) -> list[DocumentChunk]:
    """
    Recursively load and chunk every supported file under a directory.

    Intended for bulk-ingesting curated data/documents/<category>/ folders, where each
    subfolder (government/, business/, finance/, faq/) becomes its own source_type when
    one isn't explicitly given — matching §1's "add a subfolder, no code change required".

    Args:
        directory: Root folder to walk, e.g. data/documents/ or data/uploads/.
        source_type: If given, applied to every file found. If None, each file's
            immediate parent folder name is used instead.

    Returns:
        Combined list of DocumentChunk across every file found. Unreadable files are
        logged and skipped rather than aborting the whole batch.

    Raises:
        DocumentLoadError: the directory itself does not exist.
    """
    root = Path(directory)
    if not root.exists() or not root.is_dir():
        raise DocumentLoadError(f"Directory not found: {directory}")

    all_chunks: list[DocumentChunk] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        file_source_type = source_type or path.parent.name
        try:
            all_chunks.extend(load_and_chunk(path, source_type=file_source_type))
        except DocumentLoadError as exc:
            logger.warning("Skipping '%s': %s", path, exc)
            continue

    return all_chunks


def ingest(file_path: str | Path, doc_id: str | None = None, source_type: str = "document") -> dict:
    """
    End-to-end ingestion: load + chunk a single file, embed every chunk, and
    persist the embeddings into ChromaDB. This is the glue function
    app/routes.py's POST /api/knowledge/upload calls — it ties together
    load_and_chunk() (this module), rag/embeddings.py, and rag/vector_store.py
    so the caller only has to deal with one function and a plain path.

    Args:
        file_path: Path to the already-saved upload (data/uploads/<doc_id>.<ext>).
        doc_id: The id the caller already generated for this upload (used as the
            saved filename's stem). Reused as every chunk's doc_id so deletion
            and citation stay consistent with app/routes.py's knowledge_base_index.
        source_type: Label stored in chunk metadata (routes.py passes the file
            extension without the dot, e.g. "pdf", "txt", "csv").

    Returns:
        {"doc_id": str, "chunk_count": int} — chunk_count may be 0 if the file
        contained no extractable text (not an error, just nothing to index).

    Raises:
        DocumentLoadError: file missing, unsupported extension, or unreadable content.
        EmbeddingError / VectorStoreError: propagated on embedding or Chroma failure.
    """
    from rag.embeddings import get_embedding_model
    from rag.vector_store import get_vector_store

    chunks = load_and_chunk(file_path, source_type=source_type, doc_id=doc_id)
    if not chunks:
        return {"doc_id": doc_id or "", "chunk_count": 0}

    texts = [chunk.text for chunk in chunks]
    embeddings = get_embedding_model().embed_texts(texts)
    added = get_vector_store().add_chunks(chunks, embeddings)

    return {"doc_id": chunks[0].doc_id, "chunk_count": added}