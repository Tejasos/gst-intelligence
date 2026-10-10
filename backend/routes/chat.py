"""
Chat route — Flask blueprint with SSE streaming + direct numeric answers.

RULE: Numeric questions → direct computed answer (no LLM needed).
LLM is ONLY used for explanations, insights, and summarization.
Supports both Ollama and hosted LLM providers through ai_provider.
"""
import json
import logging
from flask import Blueprint, Response, jsonify, request, stream_with_context, g

from store import store
from routes.auth import require_auth
from services.chat_service import (
    build_context, build_prompt, get_direct_answer,
)
from services.ai_provider import ask_ai, stream_ai, get_ai_status

chat_bp = Blueprint("chat", __name__)
logger  = logging.getLogger(__name__)


@chat_bp.get("/ai/status")
def ai_status():
    """Return configured AI provider information and reachability."""
    return jsonify(get_ai_status())


@chat_bp.post("/chat")
@require_auth
def chat():
    data  = request.get_json() or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify(error="Query is required"), 400

    uid = getattr(g, "current_user", {}).get("id", None)
    if not store.has_data(user_id=uid):
        return jsonify(
            answer="No GST document uploaded yet. Please upload a GSTR-1, 3B, 9, or 9C PDF first.",
            sources=[],
            query=query,
            direct=False,
        )

    ctx       = store.get_active_context(user_id=uid)
    extracted = ctx.get("extracted_data") or {}
    analytics = ctx.get("analytics") or {}

    # Try direct numeric answer first (no LLM needed)
    direct_answer = get_direct_answer(query, extracted, analytics)
    if direct_answer:
        store.add_message("user", query, user_id=uid)
        store.add_message("assistant", direct_answer, user_id=uid)
        return jsonify(
            answer=direct_answer,
            sources=["Extracted GST Data", "Computed Analytics"],
            query=query,
            direct=True,
        )

    # Fallback: LLM for explanation/insights
    context = build_context(ctx)
    prompt  = build_prompt(query, context, store.get_chat_history(user_id=uid))
    store.add_message("user", query, user_id=uid)
    answer = ask_ai(prompt)
    store.add_message("assistant", answer, user_id=uid)

    return jsonify(answer=answer, sources=["Extracted GST Data", "Computed Analytics"], query=query, direct=False)


@chat_bp.post("/chat/stream")
@require_auth
def chat_stream():
    data  = request.get_json() or {}
    query = data.get("query", "").strip()

    if not query:
        def no_query():
            yield f"data: {json.dumps({'token': 'Query is required.', 'done': True})}\n\n"
        return Response(stream_with_context(no_query()), mimetype="text/event-stream")

    uid = getattr(g, "current_user", {}).get("id", None)
    if not store.has_data(user_id=uid):
        def no_data():
            msg = "No GST document uploaded yet. Please upload a PDF first."
            yield f"data: {json.dumps({'token': msg, 'done': True})}\n\n"
        return Response(stream_with_context(no_data()), mimetype="text/event-stream")

    ctx       = store.get_active_context(user_id=uid)
    extracted = ctx.get("extracted_data") or {}
    analytics = ctx.get("analytics") or {}

    # Try direct numeric answer first — stream it instantly
    direct_answer = get_direct_answer(query, extracted, analytics)
    if direct_answer:
        def direct_stream():
            store.add_message("user", query, user_id=uid)
            for word in direct_answer.split(" "):
                yield f"data: {json.dumps({'token': word + ' ', 'done': False, 'direct': True})}\n\n"
            store.add_message("assistant", direct_answer, user_id=uid)
            yield f"data: {json.dumps({'token': '', 'done': True, 'direct': True})}\n\n"
        return Response(
            stream_with_context(direct_stream()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # LLM streaming via unified ai_provider
    context = build_context(ctx)
    prompt  = build_prompt(query, context, store.get_chat_history(user_id=uid))
    store.add_message("user", query, user_id=uid)

    def generate():
        full = []
        for token in stream_ai(prompt):
            full.append(token)
            yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"

        store.add_message("assistant", "".join(full), user_id=uid)
        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@chat_bp.get("/chat/history")
@require_auth
def get_history():
    uid = getattr(g, "current_user", {}).get("id", None)
    return jsonify(history=store.get_chat_history(user_id=uid))


@chat_bp.delete("/chat/history")
@require_auth
def clear_history():
    uid = getattr(g, "current_user", {}).get("id", None)
    store.clear_chat(user_id=uid)
    return jsonify(status="cleared")
