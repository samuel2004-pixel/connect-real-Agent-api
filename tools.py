"""
tools.py — tool schemas Claude sees, plus the actual HTTP calls to
YWAMMUT's and Tailoring's internal agent APIs.

Add a new capability by: (1) adding an entry to TOOLS with a clear
description and JSON schema, and (2) adding the matching branch in
dispatch_tool(). Keep each tool narrow and single-purpose — that's what
makes the model's tool choice reliable.
"""
import os
import requests

YWAMMUT_BASE = os.environ["YWAMMUT_BASE_URL"].rstrip("/")       # e.g. https://ywammut.up.railway.app
YWAMMUT_KEY = os.environ["YWAMMUT_API_KEY"]

TAILORING_BASE = os.environ["TAILORING_BASE_URL"].rstrip("/")   # e.g. https://ywamtailoring.up.railway.app
TAILORING_KEY = os.environ["TAILORING_API_KEY"]

TIMEOUT = 20


def _ywammut(method, path, **kwargs):
    r = requests.request(
        method, f"{YWAMMUT_BASE}{path}",
        headers={"x-api-key": YWAMMUT_KEY}, timeout=TIMEOUT, **kwargs,
    )
    r.raise_for_status()
    return r.json()


def _tailoring(method, path, **kwargs):
    r = requests.request(
        method, f"{TAILORING_BASE}{path}",
        headers={"x-api-key": TAILORING_KEY}, timeout=TIMEOUT, **kwargs,
    )
    r.raise_for_status()
    return r.json()


def _tool(name, description, properties, required=None):
    """Groq (OpenAI-compatible) tool schema shape — different from Anthropic's
    flatter input_schema shape, hence this wrapper."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


TOOLS = [
    # ---------------- YWAMMUT ----------------
    _tool("list_members", "List YWAMMUT members, optionally filtered by name search. Returns balances.",
          {"q": {"type": "string", "description": "Optional name search"}}),

    _tool("get_member", "Get full detail for one YWAMMUT member: profile, loans, transactions, balance.",
          {"member_id": {"type": "string"}}, ["member_id"]),

    _tool("create_member", "Create a new YWAMMUT member/missionary record.",
          {
              "name": {"type": "string"},
              "phone": {"type": "string"},
              "email": {"type": "string"},
              "company": {"type": "string"},
              "notes": {"type": "string"},
          }, ["name"]),

    _tool("create_loan", "Create a loan for a YWAMMUT member.",
          {
              "client_id": {"type": "string"},
              "amount": {"type": "number"},
              "due_date": {"type": "string", "description": "YYYY-MM-DD"},
              "date_given": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
              "description": {"type": "string"},
          }, ["client_id", "amount", "due_date"]),

    _tool("record_transaction", "Record a contribution (income) or expense against a YWAMMUT member.",
          {
              "client_id": {"type": "string"},
              "type": {"type": "string", "enum": ["income", "expense"]},
              "amount": {"type": "number"},
              "date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
              "description": {"type": "string"},
              "category": {"type": "string"},
          }, ["client_id", "type", "amount"]),

    # ---------------- Tailoring ----------------
    _tool("list_students", "List Tailoring Centre students, optionally filtered by status, course, or name.",
          {
              "status": {"type": "string"},
              "course": {"type": "string"},
              "q": {"type": "string"},
          }),

    _tool("get_student", "Get full detail for one Tailoring Centre student, including fee history.",
          {"student_id": {"type": "integer"}}, ["student_id"]),

    _tool("create_student", "Register a new Tailoring Centre student.",
          {
              "name": {"type": "string"},
              "mobile": {"type": "string"},
              "email": {"type": "string"},
              "course": {"type": "string"},
              "batch": {"type": "string"},
              "address": {"type": "string"},
              "admission_date": {"type": "string", "description": "YYYY-MM-DD"},
              "start_date": {"type": "string", "description": "YYYY-MM-DD"},
              "duration_months": {"type": "integer"},
              "monthly_fee": {"type": "number"},
          }, ["name", "mobile", "course"]),

    _tool("mark_attendance", "Mark a Tailoring Centre student Present or Absent for a given date.",
          {
              "student_id": {"type": "integer"},
              "date": {"type": "string", "description": "YYYY-MM-DD"},
              "status": {"type": "string", "enum": ["Present", "Absent"]},
          }, ["student_id", "date", "status"]),

    _tool("record_fee_payment", "Record a monthly fee payment for a Tailoring Centre student.",
          {
              "student_id": {"type": "integer"},
              "month": {"type": "string", "description": "e.g. '2026-09'"},
              "amount_paid": {"type": "number"},
              "payment_date": {"type": "string", "description": "YYYY-MM-DD, defaults to today"},
              "mode": {"type": "string", "description": "e.g. Cash, UPI"},
              "remarks": {"type": "string"},
          }, ["student_id", "month", "amount_paid"]),

    _tool("issue_certificate",
          "Generate a course-completion certificate PDF for a Tailoring Centre student. "
          "The student must already have a photo on file.",
          {
              "student_id": {"type": "integer"},
              "course": {"type": "string"},
              "duration_months": {"type": "integer"},
              "start_date": {"type": "string", "description": "YYYY-MM-DD"},
              "end_date": {"type": "string", "description": "YYYY-MM-DD, auto-computed if omitted"},
          }, ["student_id", "start_date"]),
]


def dispatch_tool(name, args):
    try:
        if name == "list_members":
            return _ywammut("GET", "/api/agent/missionary", params={"q": args.get("q")} if args.get("q") else None)
        if name == "get_member":
            return _ywammut("GET", f"/api/agent/missionary/{args['member_id']}")
        if name == "create_member":
            return _ywammut("POST", "/api/agent/missionary", json=args)
        if name == "create_loan":
            return _ywammut("POST", "/api/agent/loans", json=args)
        if name == "record_transaction":
            return _ywammut("POST", "/api/agent/transactions", json=args)

        if name == "list_students":
            return _tailoring("GET", "/api/agent/students", params=args)
        if name == "get_student":
            return _tailoring("GET", f"/api/agent/students/{args['student_id']}")
        if name == "create_student":
            return _tailoring("POST", "/api/agent/students", json=args)
        if name == "mark_attendance":
            return _tailoring("POST", "/api/agent/attendance", json=args)
        if name == "record_fee_payment":
            return _tailoring("POST", "/api/agent/fees", json=args)
        if name == "issue_certificate":
            sid = args.pop("student_id")
            return _tailoring("POST", f"/api/agent/certificate/{sid}/issue", json=args)

        return {"error": f"unknown_tool:{name}"}

    except requests.HTTPError as e:
        try:
            body = e.response.json()
        except Exception:
            body = e.response.text
        return {"error": "http_error", "status": e.response.status_code, "detail": body}
    except requests.RequestException as e:
        return {"error": "request_failed", "detail": str(e)}
