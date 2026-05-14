from typing import AsyncIterator
import logging

from langgraph.graph import StateGraph, END
from langgraph.constants import Send
from app.agent.state import ComplianceState
from app.agent.node import parse_node, analyze_node, synthesize_node

logger = logging.getLogger(__name__)

def chunk_router(state: ComplianceState) -> list[Send]:
    chunks = state.get("chunks", [])

    if not chunks:
        logger.warning("chunk_router: No chunks to process")
        return []

    logger.info("chunk_router: Spawning %d concurrent analyze tasks", len(chunks))

    return [
        Send("analyze_node", {**state, "current_chunk": chunk, "chunk_index": i})
        for i, chunk in enumerate(chunks)
    ]

def build_graph() -> StateGraph:
    builder = StateGraph(ComplianceState)

    builder.add_node("parse_node", parse_node)
    builder.add_node("analyze_node", analyze_node)
    builder.add_node("synthesize_node", synthesize_node)

    builder.set_entry_point("parse_node")

    builder.add_conditional_edges(
        "parse_node",
        chunk_router,
        ["analyze_node"]
    )

    builder.add_edge("analyze_node", "synthesize_node")
    builder.add_edge("synthesize_node", END)

    return builder.compile()

compliance_graph = build_graph()

async def run_analysis_stream(pdf_bytes: bytes, user_id: str, document_id: str, document_name: str) -> AsyncIterator[dict]:
    initial_state:  ComplianceState = {
        "pdf_bytes": pdf_bytes,
        "user_id": user_id,
        "document_id": document_id,
        "document_name": document_name,
        "full_text": "",
        "chunks": [],
        "chunk_results": [],
        "report": None,
        "errors": [],
    }

    logger.info("Starting analysis stream for document %s", document_id)

    async for node_output in compliance_graph.astream(initial_state):
        node_name = list(node_output.keys())[0]
        node_data = node_output[node_name]

        if node_name == "parse_node":
            chunk_count = len(node_data.get("chunks", []))
            yield {"event": "started", "data": {"chunk_count": chunk_count}}

        elif node_name == "analyze_node":
            new_results = node_data.get("chunk_results", [])
            for result in new_results:
                yield {"event": "chunk_done", "data": result}
        
        elif node_name == "synthesize_node":
            report = node_data.get("report")
            yield {"event": "synthesis_done", "data": report}

            errors = node_data.get("errors", [])
            for err in errors:
                yield {"event": "error", "data": err}

    yield {"event": "done", "data": None}
    logger.info("Analysis stream completed for document %s", document_id)