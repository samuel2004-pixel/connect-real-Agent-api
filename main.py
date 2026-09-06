"""
main.py — the AI orchestrator's chat endpoint, using Groq's free API
(OpenAI-compatible tool calling) instead of Anthropic.

One prompt in -> the model decides which tool(s) to call -> tools hit
YWAMMUT's and Tailoring's internal agent APIs -> result back to the model
-> final natural-language answer (and, for certificates, a file) out.

Run locally:
    uvicorn main:app --reload --port 8080

Deploy on Railway: point it at this repo, set the env vars in
.env.example — the Procfile already tells Railway how to start it.
"""
import os
import json
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from groq import Groq

from tools import TOOLS, dispatch_tool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

app = FastAPI(title="YWAM Systems Agent")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Any unhandled error (Groq API errors, tool failures, etc.) now comes
    # back as JSON in the same shape as a normal /chat response, so the
    # frontend's res.json() never chokes on a plain-text traceback again.
    logger.exception("Unhandled error in %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "reply": "", "files": []},
    )


@app.get("/")
def ui():
    return FileResponse("static/index.html")


client = Groq(api_key=os.environ["GROQ_API_KEY"])
# Groq deprecated llama-3.3-70b-versatile and llama-3.1-8b-instant
# (announced June 17, 2026). Migrated default to openai/gpt-oss-120b,
# their recommended replacement for general-purpose + tool-calling use.
# You can still override via the GROQ_MODEL env var without a code change.
# Check console.groq.com/docs/models for the current recommended model.
MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are an operations assistant with direct tool access to two
independent systems used by YWAM Trichy:

1. YWAMMUT ("Bahi") — missionary/member contribution and loan management.
2. Tailoring Centre — student registration, attendance, fees, and certificates.

Use the tools to actually create records, fetch information, or generate
certificates — don't just describe what you would do. If a request is
ambiguous about which system it belongs to, infer it from context (e.g.
"student" / "course" / "certificate" -> Tailoring; "member" / "loan" /
"contribution" -> YWAMMUT). If you truly can't tell, ask one short
clarifying question instead of guessing.

When you issue a certificate, tell the user it's ready and mention the
file will be attached/available for download — the actual PDF bytes are
handled outside your response text.
"""


class ChatRequest(BaseModel):
    message: str
    # Optional: pass prior turns as [{"role": "user"/"assistant", "content": "..."}]
    history: list[dict] = []


@app.post("/chat")
def chat(req: ChatRequest):
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + req.history
        + [{"role": "user", "content": req.message}]
    )
    generated_files = []  # collects (filename, base64) from any tool call

    for _ in range(6):  # cap the tool-use loop
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1500,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            return JSONResponse({
                "reply": msg.content or "",
                "files": generated_files,
            })

        # Groq/OpenAI wants the assistant turn (with tool_calls) echoed back,
        # then one "tool" role message per call, matched by tool_call_id.
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            logger.info("Tool call: %s(%s)", name, args)
            result = dispatch_tool(name, args)
            logger.info("Tool result: %s", result)

            # Certificate tool returns pdf_base64 — pull it out so it
            # doesn't get stuffed back into the model's context as a huge
            # base64 blob, and surface it to the caller instead.
            if isinstance(result, dict) and "pdf_base64" in result:
                generated_files.append({
                    "filename": result.get("filename", "certificate.pdf"),
                    "base64": result["pdf_base64"],
                })
                result = {k: v for k, v in result.items() if k != "pdf_base64"}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return JSONResponse({
        "reply": "Sorry, that took too many steps — try breaking it into smaller requests.",
        "files": [],
    })


@app.get("/health")
def health():
    return {"status": "ok"}
