import io
import logging
import tempfile
import os
import pdfplumber
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,
    chunk_overlap=150,
    length_function=len,
    separators=["\n\n", "\n", ".", " ", ""],
)

def extract_text_from_bytes(pdf_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        tmp_path = tmp.name
        
    try:
        text_parts = []
        with pdfplumber.open(tmp_path) as pdf:
            logger.info("Extracting text from %d pages", len(pdf.pages))
            for page_num, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {page_num}]\n{page_text}")
                else:
                    logger.debug("Page %d had no extractable text (may be a scan)", page_num)
 
        full_text = "\n\n".join(text_parts)
        logger.info("Extracted %d characters total", len(full_text))
        return full_text
    
    finally:
        os.unlink(tmp_path)

def split_into_chunks(text: str) -> list[str]:
    chunks = _splitter.split_text(text)
 
    meaningful_chunks = [c.strip() for c in chunks if len(c.strip()) > 100]
 
    logger.info(
        "Split into %d chunks (from %d raw, %d filtered out)",
        len(meaningful_chunks),
        len(chunks),
        len(chunks) - len(meaningful_chunks),
    )
    return meaningful_chunks

def extract_and_chunk(pdf_bytes: bytes) -> tuple[str, list[str]]:
    full_text = extract_text_from_bytes(pdf_bytes)
    chunks = split_into_chunks(full_text)
    return full_text, chunks