#!/usr/bin/env python3
"""
WhatsApp Personal Assistant Bot
Connects the personal assistant to WhatsApp via Twilio webhook.
Run alongside ngrok to receive messages.
"""

import os
import json
import math
import datetime
from pathlib import Path

import anthropic
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL = "claude-opus-4-7"
MEMORY_FILE = Path.home() / ".personal_assistant_memory.json"
MAX_HISTORY_TURNS = 15
WHATSAPP_MAX_LENGTH = 1500  # WhatsApp / Twilio message limit

# ── Memory ─────────────────────────────────────────────────────────────────────
def _empty_memory() -> dict:
    return {"facts": [], "notes": {}, "preferences": {}}


def load_memory() -> dict:
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return _empty_memory()
    return _empty_memory()


def save_memory(memory: dict) -> None:
    MEMORY_FILE.write_text(
        json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Tool Implementations ────────────────────────────────────────────────────────
def get_datetime() -> str:
    now = datetime.datetime.now()
    return f"Current date/time: {now.strftime('%A, %B %d, %Y at %H:%M:%S')}"


def calculate(expression: str) -> str:
    safe_env = {
        "__builtins__": {},
        **{k: getattr(math, k) for k in dir(math) if not k.startswith("_")},
        "abs": abs, "round": round, "int": int, "float": float,
    }
    try:
        result = eval(compile(expression.strip(), "<calc>", "eval"), safe_env, {})
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"{expression} = {result}"
    except Exception as exc:
        return f"Error: {exc}"


def remember_fact(fact: str, category: str = "general") -> str:
    memory = load_memory()
    memory["facts"].append({
        "text": fact,
        "category": category,
        "saved_at": datetime.datetime.now().isoformat(),
    })
    save_memory(memory)
    return f"Remembered: {fact}"


def recall_facts(query: str = "") -> str:
    memory = load_memory()
    facts = memory["facts"]
    if not facts:
        return "No facts stored yet."
    if query:
        q = query.lower()
        facts = [f for f in facts if q in f["text"].lower() or q in f.get("category", "").lower()]
    if not facts:
        return f"No facts found matching '{query}'."
    lines = [f"[{f.get('category','general')}] {f['text']}" for f in facts[-25:]]
    return "Stored facts:\n" + "\n".join(f"• {l}" for l in lines)


def write_note(title: str, content: str) -> str:
    memory = load_memory()
    memory["notes"][title] = {
        "content": content,
        "updated_at": datetime.datetime.now().isoformat(),
    }
    save_memory(memory)
    return f"Note '{title}' saved."


def read_note(title: str) -> str:
    memory = load_memory()
    notes = memory.get("notes", {})
    if title in notes:
        n = notes[title]
        return f"=== {title} ===\n{n['content']}\n(updated: {n['updated_at'][:10]})"
    matches = [k for k in notes if title.lower() in k.lower()]
    if matches:
        return f"Note '{title}' not found. Similar: {', '.join(matches)}"
    return f"Note '{title}' not found. Available: {', '.join(notes.keys()) or 'none'}"


def list_notes() -> str:
    memory = load_memory()
    notes = memory.get("notes", {})
    if not notes:
        return "No notes saved yet."
    items = [f"• {k} (updated {v['updated_at'][:10]})" for k, v in notes.items()]
    return "Your notes:\n" + "\n".join(items)


def set_preference(key: str, value: str) -> str:
    memory = load_memory()
    memory.setdefault("preferences", {})[key] = value
    save_memory(memory)
    return f"Preference saved: {key} = {value}"


def get_preferences() -> str:
    memory = load_memory()
    prefs = memory.get("preferences", {})
    if not prefs:
        return "No preferences saved yet."
    return "Your preferences:\n" + "\n".join(f"• {k}: {v}" for k, v in prefs.items())


# ── Tool Registry ──────────────────────────────────────────────────────────────
TOOL_HANDLERS: dict = {
    "get_datetime": lambda inp: get_datetime(),
    "calculate": lambda inp: calculate(inp["expression"]),
    "remember_fact": lambda inp: remember_fact(inp["fact"], inp.get("category", "general")),
    "recall_facts": lambda inp: recall_facts(inp.get("query", "")),
    "write_note": lambda inp: write_note(inp["title"], inp["content"]),
    "read_note": lambda inp: read_note(inp["title"]),
    "list_notes": lambda inp: list_notes(),
    "set_preference": lambda inp: set_preference(inp["key"], inp["value"]),
    "get_preferences": lambda inp: get_preferences(),
}

TOOLS = [
    {
        "name": "get_datetime",
        "description": "Get the current date and time.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate",
        "description": "Evaluate a mathematical expression (arithmetic, trig, log, sqrt, etc.)",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
    {
        "name": "remember_fact",
        "description": "Permanently store a fact to memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall_facts",
        "description": "Retrieve stored facts from memory.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": [],
        },
    },
    {
        "name": "write_note",
        "description": "Create or update a named note.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_note",
        "description": "Read a saved note by title.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "list_notes",
        "description": "List all saved notes.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "set_preference",
        "description": "Save a user preference.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_preferences",
        "description": "Retrieve all saved user preferences.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {"type": "web_search_20260209", "name": "web_search"},
]

SYSTEM_PROMPT = """You are an advanced personal assistant on WhatsApp. Be helpful, warm, and concise.
Keep responses SHORT and clear — WhatsApp users prefer brief answers.
Use memory tools to remember important info about the user.
For current info use web_search. For math use calculate. Always know the time with get_datetime.
Respond in the same language the user writes in."""

# ── Assistant Logic ────────────────────────────────────────────────────────────
anthropic_client = anthropic.Anthropic()


def get_assistant_response(messages: list) -> str:
    """Run the full agentic loop and return the final text response."""
    turn_messages = list(messages)

    while True:
        response = anthropic_client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            tools=TOOLS,
            messages=turn_messages,
        )

        if response.stop_reason == "end_turn":
            return next(
                (b.text for b in response.content if b.type == "text"), ""
            )

        if response.stop_reason == "pause_turn":
            turn_messages.append({"role": "assistant", "content": response.content})
            continue

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    handler = TOOL_HANDLERS.get(block.name)
                    result = handler(block.input) if handler else f"Unknown tool: {block.name}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            turn_messages.append({"role": "assistant", "content": response.content})
            turn_messages.append({"role": "user", "content": tool_results})
            continue

        break

    return "Sorry, I encountered an issue. Please try again."


# ── Flask App ──────────────────────────────────────────────────────────────────
app = Flask(__name__)

# Per-phone-number conversation history (in memory)
conversations: dict[str, list] = {}


@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")

    if not body:
        return "", 204

    print(f"[{from_number}] {body}")

    # Get or create conversation history for this user
    history = conversations.setdefault(from_number, [])
    history.append({"role": "user", "content": body})

    # Trim history
    if len(history) > MAX_HISTORY_TURNS * 2:
        conversations[from_number] = history[-(MAX_HISTORY_TURNS * 2):]

    # Get response
    try:
        reply = get_assistant_response(list(conversations[from_number]))
    except Exception as exc:
        print(f"Error: {exc}")
        reply = "Sorry, I ran into an error. Please try again."

    # Truncate if too long for WhatsApp
    if len(reply) > WHATSAPP_MAX_LENGTH:
        reply = reply[:WHATSAPP_MAX_LENGTH] + "..."

    print(f"[Assistant] {reply[:80]}{'...' if len(reply) > 80 else ''}")

    conversations[from_number].append({"role": "assistant", "content": reply})

    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)


@app.route("/", methods=["GET"])
def health():
    return "WhatsApp Assistant is running!", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting WhatsApp bot on port {port}...")
    app.run(debug=False, host="0.0.0.0", port=port)
