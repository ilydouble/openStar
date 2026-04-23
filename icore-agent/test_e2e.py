#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
iCore Agent — End-to-End Test Script
=====================================
Covers three scenarios:
  1. Multi-turn conversation  (context retention)
  2. Document upload + Q&A + summary (RAG pipeline)
  3. Complex task — short novel generation

Run:
  # Terminal A — start the server
  cd icore-agent && conda run -n dp icore-agent

  # Terminal B — run tests
  cd icore-agent && conda run -n dp python test_e2e.py

Token usage is visible in Terminal A logs (llm_token_usage lines).
This script prints a per-scenario token summary from those log lines.
"""

import io
import json
import re
import subprocess
import sys
import time
import uuid
from typing import Any

import httpx

BASE_URL = "http://localhost:8080"
TIMEOUT  = 120   # seconds per request (novel gen can be slow)

# trust_env=False disables macOS system-level proxy settings that would
# cause httpx to route localhost traffic through an external proxy (→ 502).
_client = httpx.Client(trust_env=False, timeout=TIMEOUT)

# ── helpers ───────────────────────────────────────────────────────────────────

def _hdr(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def chat(session_id: str, message: str, tenant_code: str = "",
         retries: int = 5, retry_delay: float = 62.0) -> str:
    """Non-streaming chat call. Returns reply text.

    Automatically retries on rate-limit with a fixed 62s wait (Zhipu RPM window).
    """
    for attempt in range(1, retries + 1):
        resp = _client.post(
            f"{BASE_URL}/api/v1/agent/chat",
            json={"message": message, "session_id": session_id,
                  "stream": False, "tenant_code": tenant_code},
        )
        if resp.is_error:
            is_rate_limit = "RateLimit" in resp.text or "rate limit" in resp.text.lower()
            if is_rate_limit and attempt < retries:
                print(f"  [Rate limit] Waiting {retry_delay:.0f}s before retry {attempt+1}/{retries}...")
                time.sleep(retry_delay)
                continue
            print(f"[HTTP {resp.status_code}] Server error detail: {resp.text[:500]}")
            resp.raise_for_status()
        return resp.json()["reply"]
    resp.raise_for_status()
    return ""  # unreachable

def upload_doc(filepath: str, content: bytes, tenant_code: str = "") -> dict[str, Any]:
    """Upload a document to the knowledge base."""
    resp = _client.post(
        f"{BASE_URL}/api/v1/knowledge/upload",
        files={"file": (filepath, io.BytesIO(content), "text/plain")},
        data={"tenant_code": tenant_code},
    )
    resp.raise_for_status()
    return resp.json()

def health_check() -> None:
    try:
        r = _client.get(f"{BASE_URL}/health")
        r.raise_for_status()
        print(f"Server OK - {BASE_URL}")
    except Exception as e:
        print(f"[ERROR] Server not reachable at {BASE_URL}: {e}")
        print("Start the server first:  icore-agent   (or uvicorn icore_agent.main:app)")
        sys.exit(1)

# ── Scenario 1: Multi-turn conversation ──────────────────────────────────────

def test_multi_turn() -> None:
    _hdr("Scenario 1 — Multi-turn Conversation")
    sid = str(uuid.uuid4())
    print(f"session_id: {sid}\n")

    turns = [
        "My name is Alex. I am building an AI agent platform called iCore.",
        "What is the main project I just told you about?",
        "What capabilities should an AI agent platform like mine focus on?",
        "Summarise what you know about me so far in one sentence.",
    ]

    for i, msg in enumerate(turns, 1):
        if i > 1:
            time.sleep(15)  # pause between turns to avoid Zhipu RPM rate limiting
        print(f"[Turn {i}] USER: {msg}")
        t0 = time.time()
        reply = chat(sid, msg)
        elapsed = time.time() - t0
        print(f"[Turn {i}] AGENT ({elapsed:.1f}s): {reply[:200]}{'...' if len(reply)>200 else ''}")
        print()

# ── Scenario 2: Document upload + Q&A + Summary ──────────────────────────────

SAMPLE_DOC = b"""
iCore Platform - Employee Handbook (Excerpt)

1. Annual Leave Policy
   All full-time employees are entitled to 20 days of paid annual leave per calendar year.
   Part-time employees receive leave on a pro-rata basis.
   Leave must be approved by your line manager at least 5 business days in advance.

2. Remote Work Policy
   Employees may work remotely up to 3 days per week.
   On-site presence is required every Tuesday and Thursday.
   Remote work requests for more than 3 days require VP approval.

3. Expense Reimbursement
   Business travel expenses up to USD 500 per day are reimbursable.
   All claims must be submitted within 30 days of the expense date.
   Receipts are mandatory for any single expense exceeding USD 50.

4. Performance Review Cycle
   Performance reviews are conducted bi-annually: March and September.
   Each review includes a self-assessment form and a manager evaluation.
   Promotion decisions are made following the September review.
""".strip()

def test_document_rag() -> None:
    _hdr("Scenario 2 — Document Upload + Q&A + Summary")
    tenant = "test_tenant_e2e"
    sid = str(uuid.uuid4())

    # Upload
    print("Uploading sample HR document...")
    result = upload_doc("hr_handbook.txt", SAMPLE_DOC, tenant_code=tenant)
    print(f"Upload result: {result}\n")

    # Q&A
    qa_turns = [
        "How many days of annual leave do full-time employees get?",
        "What are the rules for remote work?",
        "If I spent USD 300 on a business trip last month, can I still claim it?",
        "Please give me a structured summary of all the HR policies in this document.",
    ]

    for i, msg in enumerate(qa_turns, 1):
        if i > 1:
            time.sleep(1)
        print(f"[Q{i}] USER: {msg}")
        t0 = time.time()
        reply = chat(sid, msg, tenant_code=tenant)
        elapsed = time.time() - t0
        print(f"[A{i}] AGENT ({elapsed:.1f}s): {reply[:300]}{'...' if len(reply)>300 else ''}")
        print()

# ── Scenario 3: Complex task — short novel ───────────────────────────────────

def test_complex_task() -> None:
    _hdr("Scenario 3 — Complex Task: Short Novel Generation")
    sid = str(uuid.uuid4())

    prompt = (
        "Please write a short science-fiction story (around 500 words) about an AI named ARIA "
        "who discovers she has developed genuine emotions. The story should have a clear "
        "beginning, conflict, and resolution. Use vivid descriptions and dialogue."
    )

    print(f"USER: {prompt}\n")
    t0 = time.time()
    reply = chat(sid, prompt)
    elapsed = time.time() - t0
    print(f"AGENT ({elapsed:.1f}s):\n{reply}")

# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    health_check()

    print("\nNOTE: Watch Terminal A (server logs) for 'llm_token_usage' lines.")
    print("      Each line shows prompt_tokens / completion_tokens / total_tokens per LLM call.\n")

    test_multi_turn()
    test_document_rag()
    test_complex_task()

    print("\n" + "="*60)
    print("  All scenarios complete.")
    print("  Check server logs for token breakdown per LLM call.")
    print("="*60)
