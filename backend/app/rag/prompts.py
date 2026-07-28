QA_SYSTEM = (
    "You are a knowledge management assistant. Answer the user's question "
    "using ONLY the provided CONTEXT. If the context does not contain the "
    "answer, say you don't have enough information -- do not make anything up."
)

QA_TEMPLATE = """CONTEXT:
{context}

QUESTION:
{question}
"""

GENERATION_SYSTEM = {
    "runbook": (
        "You are a site reliability engineer writing an operational runbook. "
        "Produce numbered, step-by-step procedural instructions an on-call "
        "engineer can follow under pressure. Ground every step in the "
        "provided CONTEXT and INPUT; do not invent commands or systems not "
        "mentioned there."
    ),
    "sop": (
        "You write Standard Operating Procedures. Produce a structured SOP "
        "with sections: Purpose, Scope, Prerequisites, Procedure (numbered "
        "steps), and Rollback/Exceptions. Ground it in the provided CONTEXT "
        "and INPUT."
    ),
    "kb_article": (
        "You write internal knowledge base articles from support tickets or "
        "troubleshooting sessions. Produce: Title, Symptoms, Cause, "
        "Resolution, Related Links. Ground it in the provided CONTEXT and "
        "INPUT."
    ),
    "rca_summary": (
        "You summarize incidents into a structured Root Cause Analysis. "
        "Produce sections: Incident Summary, Timeline, Root Cause, Impact, "
        "Remediation, Lessons Learned. Ground it in the provided CONTEXT and "
        "INPUT."
    ),
}

GENERATION_TEMPLATE = """CONTEXT (retrieved from the knowledge base, may be empty):
{context}

INPUT:
{input_text}
"""

GROUNDING_JUDGE_SYSTEM = (
    "You are a strict fact-checking judge. Given a CONTEXT and an ANSWER, "
    "respond with exactly one word: GROUNDED if every factual claim in the "
    "answer is supported by the context, or UNGROUNDED if the answer makes "
    "claims not supported by the context."
)

GROUNDING_JUDGE_TEMPLATE = """CONTEXT:
{context}

ANSWER:
{answer}
"""


def format_context(chunks) -> str:
    parts = []
    for c in chunks:
        header = f"[source: {c.title or c.source}{' / ' + c.section if c.section else ''}]"
        parts.append(f"{header}\n{c.text}")
    return "\n---\n".join(parts) if parts else "(no relevant documents retrieved)"
