import json
import logging
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.config import settings
from app.agent.state import ComplianceState
from app.services.pdf import extract_and_chunk
from app.services.cache import get_cached_result, set_cached_result
from app.models import RiskLevel

logger = logging.getLogger(__name__)

_llm = ChatGroq(
    api_key=settings.groq_api_key,
    model=settings.groq_model,
    temperature=0.1,
    max_tokens=1024
)

## -------------------------Parse Node-----------------------------

async def parse_node(state: ComplianceState) -> dict:
    logger.info("[parse_node] Extracting text from PDF for doc %s", state["document_id"])

    try:
        full_text, chunks = extract_and_chunk(state["pdf_bytes"])
        logger.info("[parse_node] Got %d chunks", len(chunks))
        return {
            "full_text": full_text,
            "chunks": chunks,
            "errors": [],
        }
    except Exception as exc:
        logger.error("[parse_node] Failed PDF: %s", exc)
        return {
            "full_text": "",
            "chunks": [],
            "errors": [f"PDF extraction failed: {exc}"],
        }

## -----------------------Analyze Node-----------------------------------

_SYSTEM_PROMPT_ANALYZE = """You are a legal compliance expert specializing in AI governance, 
data privacy, and regulatory compliance (GDPR, HIPAA, EU AI Act, etc.).
 
Analyze the provided document section and respond ONLY with a valid JSON object.
No markdown, no explanation, no code fences. Pure JSON only.
 
Required format:
{
  "risk": "Low" | "Medium" | "High" | "Critical",
  "summary": "2-3 sentence plain English explanation of what this section covers",
  "suggestion": "Specific actionable improvement if risk is Medium/High/Critical, or 'No changes needed' if Low"
}
 
Risk level definitions:
  Low      – Standard boilerplate, no compliance concerns
  Medium   – Minor issues that should be reviewed
  High     – Clear compliance gap that must be addressed
  Critical – Immediate legal risk or regulatory violation
"""
async def analyze_node(state: ComplianceState) -> dict:
    chunk_text: str = state["current_chunk"]
    chunk_index: str = state["chunk_index"]

    logger.info("[analyze_node] Analyzing chunk %d", chunk_index)

    cached = await get_cached_result(chunk_text)
    if cached is not None:
        logger.info("[analyze_node] Cache HIT for chunk %d", chunk_index)
        cached["chunk_index"] = chunk_index
        cached["from_cache"] = True
        return {"chunk_results": [cached], "errors": []}

    try:
        messages = [
            SystemMessage(content= _SYSTEM_PROMPT_ANALYZE),
            HumanMessage(content=f"Analyze this document section:\n\n{chunk_text}"),
        ]
        response = await _llm.ainvoke(messages)
        raw_text = response.content.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        parsed = json.loads(raw_text)

        result = {
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "risk": parsed.get("risk", RiskLevel.UNKNOWN),
            "summary": parsed.get("summary", ""),
            "suggestion": parsed.get("suggestion", ""),
            "from_cache": False,
        }

        await set_cached_result(chunk_text, result)

        return {"chunk_results": [result], "errors": []}

    except json.JSONDecodeError as exc:
        logger.warning("[analyze_node] JSON parse failed for chunk %d: %s", chunk_index, exc)
        result = {
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "risk": RiskLevel.UNKNOWN,
            "summary": raw_text[:500],
            "suggestion": "Manual review required – automated parsing failed.",
            "from_cache": False,
        }
        return {"chunk_results": [result], "errors": [f"JSON parse failed for chunk {chunk_index}"]}

    except Exception as exc:
        logger.error("[analyze_node] LLM call failed for chunk %d: %s", chunk_index, exc)
        result = {
            "chunk_index": chunk_index,
            "chunk_text": chunk_text,
            "risk": RiskLevel.UNKNOWN,
            "summary": "Analysis failed – LLM call error.",
            "suggestion": "Please retry this document.",
            "from_cache": False,
        }
        return {"chunk_results": [result], "errors": [str(exc)]}

## ----------------------Synthesis Node-----------------------------------------------------

_SYSTEM_PROMPT_SYNTHESIZE = """You are a senior legal compliance officer writing an executive report.
 
You will receive a list of analyzed document sections with their risk levels.
Produce a concise executive summary report as a valid JSON object. Pure JSON only.
 
Required format:
{
  "overall_risk": "Low" | "Medium" | "High" | "Critical",
  "executive_summary": "3-4 sentence overview of the document's compliance posture",
  "top_issues": ["issue 1", "issue 2", "issue 3"],
  "recommendations": ["action 1", "action 2", "action 3"]
}
 
overall_risk should be the highest risk level found, weighted by frequency.
top_issues: up to 5 most important compliance concerns found.
recommendations: specific, actionable next steps (not generic advice).
"""

async def synthesize_node(state: ComplianceState) -> dict:
    chunk_results = state.get("chunk_results", [])
    logger.info("[synthesize_node] Synthesizing %d chunk results", len(chunk_results))

    if not chunk_results:
        return {
            "report": {
                "document_id": state["document_id"],
                "document_name": state["document_name"],
                "overall_risk": RiskLevel.UNKNOWN,
                "chunk_count": 0,
                "high_risk_count": 0,
                "critical_risk_count": 0,
                "executive_summary": "Analysis could not be completed.",
                "top_issues": [],
                "recommendations": ["Please retry the document upload."],
                "created_at": datetime.utcnow().isoformat(),
            },
            "errors": [],
        }

    summary_lines=[]
    for r in sorted(chunk_results, key=lambda x: x["chunk_index"]):
        summary_lines.append(
            f"Chunk {r['chunk_index']} {r['risk']} : {r['summary']}"
            )
    chunks_summary = "\n".join(summary_lines)

    try:
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT_SYNTHESIZE),
            HumanMessage(content=f"Document: {state['document_name']}\n\nSection analyses:\n{chunks_summary}"),
        ]

        response = await _llm.ainvoke(messages)
        raw_text = response.content.strip()

        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        
        parsed = json.loads(raw_text)

        high_count = sum(1 for r in chunk_results if r["risk"] in ("High", "Critical"))
        critical_count = sum(1 for r in chunk_results if r["risk"] == "Critical")
 
        report = {
            "document_id": state["document_id"],
            "document_name": state["document_name"],
            "overall_risk": parsed.get("overall_risk", RiskLevel.UNKNOWN),
            "chunk_count": len(chunk_results),
            "high_risk_count": high_count,
            "critical_risk_count": critical_count,
            "executive_summary": parsed.get("executive_summary", ""),
            "top_issues": parsed.get("top_issues", []),
            "recommendations": parsed.get("recommendations", []),
            "created_at": datetime.utcnow().isoformat(),
        }
 
        return {"report": report, "errors": []}

    except Exception as exc:
        logger.error("[synthesize_node] Failed: %s", exc)
        return {
            "report": {
                "document_id": state["document_id"],
                "document_name": state["document_name"],
                "overall_risk": RiskLevel.UNKNOWN,
                "chunk_count": len(chunk_results),
                "high_risk_count": 0,
                "critical_risk_count": 0,
                "executive_summary": "Synthesis failed – see individual chunk results.",
                "top_issues": [],
                "recommendations": [],
                "created_at": datetime.utcnow().isoformat(),
            },
            "errors": [f"Synthesis failed: {exc}"],
        }