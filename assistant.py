#!/usr/bin/env python3
"""
Advanced Personal Assistant
Powered by Claude claude-opus-4-7 with tool use, persistent memory, streaming, and prompt caching.
"""

import anthropic
import json
import math
import datetime
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL = "claude-opus-4-7"
MEMORY_FILE = Path.home() / ".personal_assistant_memory.json"
MAX_HISTORY_TURNS = 15


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
        "abs": abs,
        "round": round,
        "int": int,
        "float": float,
    }
    try:
        result = eval(compile(expression.strip(), "<calc>", "eval"), safe_env, {})
        if isinstance(result, float) and result == int(result):
            result = int(result)
        return f"{expression} = {result}"
    except Exception as exc:
        return f"Error evaluating '{expression}': {exc}"


def remember_fact(fact: str, category: str = "general") -> str:
    memory = load_memory()
    memory["facts"].append(
        {
            "text": fact,
            "category": category,
            "saved_at": datetime.datetime.now().isoformat(),
        }
    )
    save_memory(memory)
    return f"Remembered: {fact}"


def recall_facts(query: str = "") -> str:
    memory = load_memory()
    facts = memory["facts"]
    if not facts:
        return "No facts stored yet."
    if query:
        q = query.lower()
        facts = [
            f
            for f in facts
            if q in f["text"].lower() or q in f.get("category", "").lower()
        ]
    if not facts:
        return f"No facts found matching '{query}'."
    lines = [f"[{f.get('category', 'general')}] {f['text']}" for f in facts[-25:]]
    return "Stored facts:\n" + "\n".join(f"  • {l}" for l in lines)


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
    available = ", ".join(notes.keys()) or "none"
    return f"Note '{title}' not found. Available notes: {available}"


def list_notes() -> str:
    memory = load_memory()
    notes = memory.get("notes", {})
    if not notes:
        return "No notes saved yet."
    items = [f"  • {k} (updated {v['updated_at'][:10]})" for k, v in notes.items()]
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
    return "Your preferences:\n" + "\n".join(f"  • {k}: {v}" for k, v in prefs.items())


# ── Tool Registry ──────────────────────────────────────────────────────────────
TOOL_HANDLERS: dict = {
    "get_datetime": lambda inp: get_datetime(),
    "calculate": lambda inp: calculate(inp["expression"]),
    "remember_fact": lambda inp: remember_fact(
        inp["fact"], inp.get("category", "general")
    ),
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
        "description": (
            "Evaluate a mathematical expression. "
            "Supports arithmetic, trig, log, sqrt, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "e.g. '2**10', 'sqrt(144)', 'sin(pi/4)'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "remember_fact",
        "description": "Permanently store a fact or piece of information to memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact to store"},
                "category": {
                    "type": "string",
                    "description": "Category tag (e.g. 'personal', 'work', 'health')",
                },
            },
            "required": ["fact"],
        },
    },
    {
        "name": "recall_facts",
        "description": "Retrieve stored facts from memory, optionally filtered by a search query.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional search term"}
            },
            "required": [],
        },
    },
    {
        "name": "write_note",
        "description": "Create or update a named note with any content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title/identifier"},
                "content": {"type": "string", "description": "Full note content"},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "read_note",
        "description": "Read the content of a saved note by its title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title to read"}
            },
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
        "description": "Save a user preference that persists across sessions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Preference name"},
                "value": {"type": "string", "description": "Preference value"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_preferences",
        "description": "Retrieve all saved user preferences.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    # Server-side web search (executed by Anthropic, not client-side)
    {"type": "web_search_20260209", "name": "web_search"},
]


# ── System Prompt with Prompt Caching ─────────────────────────────────────────
SYSTEM_PROMPT = """You are an advanced personal assistant powered by Claude. You are helpful, warm, proactive, and intelligent.

## Your capabilities
- **Memory**: Store facts, notes, and preferences that persist between sessions
- **Math**: Precise calculations including advanced math functions
- **Web search**: Find current information online when needed
- **Time awareness**: Always know the current date and time
- **Note-taking**: Create and manage persistent notes on any topic

## Behavior guidelines
- Be concise yet thorough; adapt response length to the question
- Proactively offer to save important information when the user shares personal details
- For time-sensitive topics (news, events, current data), use web_search
- Combine multiple tools naturally when it helps the user
- Check preferences to personalize responses (address user by name if known)
- If uncertain about something, say so clearly rather than guessing

## Memory strategy
- Use remember_fact for important personal info (birthday, job, preferences, goals)
- Use write_note for longer structured content (lists, plans, recipes, summaries)
- Always check recall_facts at the start if the user references past conversations
- Suggest saving important information proactively

## Tone
- Warm, friendly, and professional
- Eager to help and anticipate needs
- Celebrate the user's achievements and be supportive of their goals"""


def build_system_blocks() -> list:
    """Return system prompt with cache_control for prompt caching efficiency."""
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


# ── Main Loop ──────────────────────────────────────────────────────────────────
def run() -> None:
    client = anthropic.Anthropic()
    # Simplified text-only history for context management
    history: list[dict] = []

    print()
    print("=" * 60)
    print("  Advanced Personal Assistant  (Claude claude-opus-4-7)")
    print("  Commands: 'quit' to exit  |  'clear' to reset history")
    print("=" * 60)
    print()

    memory = load_memory()
    name = memory.get("preferences", {}).get("name", "")
    if name:
        print(f"Assistant: Welcome back, {name}! How can I help you today?\n")
    else:
        print("Assistant: Hello! I'm your personal assistant. How can I help you today?\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAssistant: Goodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "bye", "goodbye"}:
            print("\nAssistant: Goodbye! Have a great day!")
            break

        if user_input.lower() == "clear":
            history.clear()
            print("Assistant: Conversation history cleared.\n")
            continue

        # Append user message to simplified history
        history.append({"role": "user", "content": user_input})

        # Keep history within token budget
        if len(history) > MAX_HISTORY_TURNS * 2:
            history = history[-(MAX_HISTORY_TURNS * 2):]

        print("Assistant: ", end="", flush=True)

        # Build full message list for this turn (will grow with tool rounds)
        turn_messages = list(history)
        assistant_text = ""

        try:
            # Agentic loop: handles tool calls and pause_turn transparently
            while True:
                with client.messages.stream(
                    model=MODEL,
                    max_tokens=4096,
                    thinking={"type": "adaptive"},
                    system=build_system_blocks(),
                    tools=TOOLS,
                    messages=turn_messages,
                ) as stream:
                    chunk_text = ""
                    for text_chunk in stream.text_stream:
                        print(text_chunk, end="", flush=True)
                        chunk_text += text_chunk
                    assistant_text += chunk_text
                    final = stream.get_final_message()

                if final.stop_reason == "end_turn":
                    break

                if final.stop_reason == "pause_turn":
                    # Server-side tools hit iteration limit; re-send to continue
                    turn_messages.append(
                        {"role": "assistant", "content": final.content}
                    )
                    continue

                if final.stop_reason == "tool_use":
                    # Execute client-side tools and feed results back
                    tool_results = []
                    for block in final.content:
                        if block.type == "tool_use":
                            handler = TOOL_HANDLERS.get(block.name)
                            if handler:
                                result = handler(block.input)
                            else:
                                result = f"Unknown tool: {block.name}"
                            preview = result[:72] + "..." if len(result) > 72 else result
                            print(f"\n  [{block.name}] {preview}", flush=True)
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": result,
                                }
                            )
                    turn_messages.append(
                        {"role": "assistant", "content": final.content}
                    )
                    turn_messages.append({"role": "user", "content": tool_results})
                    # Print indent for the continuation response
                    print("  ", end="", flush=True)
                    continue

                # Unexpected stop reason — exit loop
                break

        except anthropic.RateLimitError:
            print("\n[Rate limited — please wait a moment and try again.]")
        except anthropic.APIConnectionError:
            print("\n[Connection error — please check your internet connection.]")
        except anthropic.BadRequestError as exc:
            print(f"\n[Request error: {exc.message}]")
        except Exception as exc:
            print(f"\n[Unexpected error: {exc}]")

        print("\n")

        # Store simplified assistant turn in history (text only, no tool blocks)
        history.append(
            {"role": "assistant", "content": assistant_text or "[tool response]"}
        )


if __name__ == "__main__":
    run()
