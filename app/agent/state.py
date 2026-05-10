from typing import TypedDict, Annotated
import operator

class ComplianceState(TypedDict):
    pdf_bytes: bytes
    user_id: str
    document_id: str
    document_name: str
    full_text: str
    chunks: list[str]
    chunk_results: Annotated[list[dict], operator.add]
    report: dict | None
    errors: Annotated[list[str], operator.add]