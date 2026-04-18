# Advanced Personal Assistant

A conversational AI assistant powered by Claude claude-opus-4-7 with persistent memory, tool use, streaming responses, and prompt caching.

## Features

| Feature | Description |
|---|---|
| **Persistent Memory** | Remembers facts, notes, and preferences across sessions (`~/.personal_assistant_memory.json`) |
| **Math** | Safe evaluation of arithmetic, trig, logarithms, and other math functions |
| **Web Search** | Real-time web search via Claude's built-in search tool |
| **Notes** | Create and retrieve named notes stored locally |
| **Preferences** | Save and recall personal settings (name, language, etc.) |
| **Streaming** | Responses stream token-by-token for low latency |
| **Prompt Caching** | System prompt is cached, reducing token costs on repeated calls |
| **Adaptive Thinking** | Claude uses extended reasoning on complex queries automatically |

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY=your_key_here

# Run the assistant
python assistant.py
```

## Usage

```
You: What's 15% tip on a $47.50 bill?
You: Remember that my name is Alex and I prefer metric units
You: Search for the latest news on AI research
You: Write a note called "shopping" with eggs, milk, bread
You: Read my shopping note
You: What time is it?
You: quit
```

### Commands

| Command | Action |
|---|---|
| `clear` | Clears conversation history (memory is preserved) |
| `quit` / `exit` / `bye` | Exits the assistant |

## Architecture

```
assistant.py
├── Memory layer      — JSON file at ~/.personal_assistant_memory.json
├── Tool registry     — 9 client-side tools + web_search (server-side)
├── System prompt     — Cached with cache_control: ephemeral
├── Agentic loop      — Handles tool_use, pause_turn, end_turn
└── Conversation history — Trimmed to last 15 turns to manage tokens
```

### Tools

| Tool | Type | Description |
|---|---|---|
| `get_datetime` | client | Current date and time |
| `calculate` | client | Math expression evaluator |
| `remember_fact` | client | Store a fact to persistent memory |
| `recall_facts` | client | Retrieve stored facts |
| `write_note` | client | Create/update a named note |
| `read_note` | client | Read a note by title |
| `list_notes` | client | List all notes |
| `set_preference` | client | Save a user preference |
| `get_preferences` | client | Retrieve all preferences |
| `web_search` | server | Live web search (Anthropic-hosted) |
