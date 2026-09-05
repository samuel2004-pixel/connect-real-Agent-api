"""
streamlit_app.py — a plain Streamlit chatbot UI for the YWAM AI agent.

This is self-contained: it runs the same Groq tool-calling loop as
main.py, directly in Streamlit, so you don't need to run the FastAPI
backend separately just to use the chat. (main.py/tools.py's TOOLS and
dispatch_tool are reused here — no logic duplicated.)

Run locally:
    streamlit run streamlit_app.py

Deploy on Railway: set the Start Command to
    streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
(Railway will still read the same env vars from .env.example.)
"""
import json

import streamlit as st
from groq import Groq

from tools import TOOLS, dispatch_tool

st.set_page_config(page_title="YWAM Systems Agent", page_icon="🤖")

client = Groq(api_key=st.secrets.get("GROQ_API_KEY", None) or __import__("os").environ["GROQ_API_KEY"])
MODEL = __import__("os").environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

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
"""

st.title("YWAM Systems Agent")
st.caption("One prompt, both systems — YWAMMUT + Tailoring Centre")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Render prior turns (skip the system prompt)
for msg in st.session_state.messages[1:]:
    if msg["role"] in ("user", "assistant") and isinstance(msg.get("content"), str):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])


def run_agent_turn(user_text: str):
    st.session_state.messages.append({"role": "user", "content": user_text})
    files = []

    for _ in range(6):  # cap the tool-use loop
        response = client.chat.completions.create(
            model=MODEL,
            messages=st.session_state.messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=1500,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:
            st.session_state.messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content or "", files

        st.session_state.messages.append({
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
            result = dispatch_tool(name, args)

            if isinstance(result, dict) and "pdf_base64" in result:
                files.append({"filename": result.get("filename", "certificate.pdf"), "base64": result["pdf_base64"]})
                result = {k: v for k, v in result.items() if k != "pdf_base64"}

            st.session_state.messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

    return "That took too many steps — try breaking it into smaller requests.", files


prompt = st.chat_input("e.g. Register a new tailoring student named Priya, mobile 9876543210, course Basic Tailoring")
if prompt:
    with st.chat_message("user"):
        st.write(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Working on it…"):
            reply, files = run_agent_turn(prompt)
        st.write(reply)
        for f in files:
            import base64
            st.download_button(
                label=f"⬇ Download {f['filename']}",
                data=base64.b64decode(f["base64"]),
                file_name=f["filename"],
                mime="application/pdf",
            )
