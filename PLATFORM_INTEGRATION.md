# Platform Integration Guide

## Summary

The agent now exposes **TWO** endpoints:

1. **`/v1/chat/completions`** - Original OpenAI-compatible endpoint (for frontend)
2. **`/chat`** - New platform-compatible endpoint (for A/B testing platform)

Both endpoints share the same core logic and provide complete trace data.

---

## Endpoint 1: `/chat` (Platform-Compatible)

### Request Format
```json
POST /chat
{
  "messages": [
    {"role": "user", "content": "What is 25 * 47?"}
  ],
  "temperature": 0.7,
  "top_p": 1.0,
  "max_tokens": 2048,
  "session_id": "sess_xxx" (optional - auto-created if not provided)
}
```

### Response Format
```json
{
  "response": "The result of 25 * 47 is 1,175.",
  "session_id": "sess_abc123",
  "trace": {
    "trace_id": "trace_xyz",
    "started_at": "2025-10-18T20:00:00",
    "completed_at": "2025-10-18T20:00:03",
    "total_tokens": 150,
    "config": {
      "model": "gpt-4o",
      "temperature": 0.7,
      "top_p": 1.0,
      "max_tokens": 2048
    },
    "tool_calls": [
      {
        "name": "calculator",
        "arguments": {"expression": "25 * 47"},
        "result": "1175",
        "duration_ms": 0.5,
        "timestamp": "2025-10-18T20:00:01"
      }
    ],
    "turns": [
      {
        "role": "user",
        "content": "What is 25 * 47?",
        "timestamp": "2025-10-18T20:00:00"
      },
      {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "call_xxx", "name": "calculator", ...}],
        "timestamp": "2025-10-18T20:00:01"
      },
      {
        "role": "tool",
        "name": "calculator",
        "content": "1175",
        "tool_call_id": "call_xxx",
        "timestamp": "2025-10-18T20:00:01"
      },
      {
        "role": "assistant",
        "content": "The result of 25 * 47 is 1,175.",
        "tool_calls": null,
        "timestamp": "2025-10-18T20:00:03"
      }
    ]
  }
}
```

### Key Features

✅ **Auto-session creation** - If no `session_id` provided, creates one automatically
✅ **Session persistence** - Pass `session_id` to maintain conversation history
✅ **System prompt extraction** - Extracts from `messages[0]` if `role == "system"`
✅ **Full conversation history** - Platform can pass entire conversation in `messages`
✅ **Complete trace data** - All tool calls, timestamps, durations, turns
✅ **Simple response format** - `{"response": "..."}` for easy parsing

---

## Endpoint 2: `/v1/chat/completions` (OpenAI-Compatible)

### Request Format
```json
POST /v1/chat/completions
{
  "messages": [{"role": "user", "content": "Hello"}],
  "system_prompt": "You are a helpful assistant.",
  "session_id": "sess_xxx" (optional),
  "temperature": 0.7,
  "top_p": 1.0,
  "max_tokens": 1000
}
```

### Response Format
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4o-2024-08-06",
  "choices": [{
    "index": 0,
    "message": {
      "role": "assistant",
      "content": "Hello! How can I help you?"
    },
    "finish_reason": "stop"
  }],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "total_tokens": 18
  },
  "trace_id": "trace_xyz",
  "session_id": "sess_xxx",
  "trace": { /* same as /chat endpoint */ }
}
```

---

## Platform Integration Flow

### First Message
```python
# Platform calls agent
response = requests.post("http://agent-url/chat", json={
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7
})

# Store session_id
session_id = response.json()["session_id"]  # "sess_abc123"

# Display response
user_message = response.json()["response"]

# Store trace for A/B analysis
trace = response.json()["trace"]
```

### Subsequent Messages
```python
# Platform includes full conversation history
response = requests.post("http://agent-url/chat", json={
    "messages": [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "What's 2+2?"}
    ],
    "session_id": session_id,  # ← Pass stored session_id
    "temperature": 0.7
})
```

### Platform sends ENTIRE conversation each time (like OpenAI API)
The agent maintains session state for:
- Frontend display (via `/session/start`, `/session/end`)
- Session-level trace aggregation
- But platform can pass full history in each request

---

## Trace Data for A/B Testing

Every response includes complete trace data:

```python
{
  "trace": {
    "trace_id": "unique_id",
    "started_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    "total_tokens": 150,

    # Model configuration used
    "config": {
      "model": "gpt-4o",
      "temperature": 0.7,
      "top_p": 1.0,
      "max_tokens": 2048
    },

    # All tool executions
    "tool_calls": [
      {
        "name": "calculator",
        "arguments": {"expression": "..."},
        "result": "...",
        "duration_ms": 0.5,  # ← Execution time
        "timestamp": "..."
      }
    ],

    # Complete conversation flow
    "turns": [
      {"role": "user", "content": "...", "timestamp": "..."},
      {"role": "assistant", "tool_calls": [...], "timestamp": "..."},
      {"role": "tool", "content": "...", "timestamp": "..."},
      {"role": "assistant", "content": "...", "timestamp": "..."}
    ]
  }
}
```

---

## Testing

### Test Platform Endpoint
```bash
./test_chat_endpoint.sh
```

Tests:
- ✅ Auto-session creation
- ✅ Session persistence
- ✅ System prompt extraction
- ✅ Full conversation history
- ✅ Tool calling
- ✅ Trace data

### Test Original Endpoint
```bash
./test_agent.sh
```

---

## What Platform Must Do

### Minimal Requirements:
1. **Store `session_id`** after first call
2. **Pass `session_id`** in subsequent calls
3. **Parse `response`** field for display

### For A/B Testing:
1. **Store `trace` data** in experiment database
2. **Analyze** tool calls, durations, turns
3. **Compare** variants using trace metrics

### Example Platform Code:
```python
from fastapi import FastAPI
import requests

app = FastAPI()

AGENT_A_URL = "http://agent-a:5000/chat"
AGENT_B_URL = "http://agent-b:5000/chat"

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # Route to variant
    variant_url = AGENT_A_URL if assign_variant() == "A" else AGENT_B_URL

    # Call agent
    agent_response = requests.post(variant_url, json={
        "messages": request.messages,
        "session_id": request.session_id,
        "temperature": request.temperature
    })

    data = agent_response.json()

    # Store trace for analysis
    store_trace(data["trace"], variant="A")

    # Return to user
    return {
        "response": data["response"],
        "session_id": data["session_id"]
    }
```

---

## Architecture

```
┌─────────┐
│  User   │
└────┬────┘
     │
     ▼
┌─────────────┐
│  Platform   │ ← Routes to A or B
└──┬──────┬───┘
   │      │
   ▼      ▼
┌────┐  ┌────┐
│ A  │  │ B  │ ← Both agents expose /chat endpoint
└────┘  └────┘
   │      │
   └──────┘
      │
      ▼
  Trace DB ← Stores traces for analysis
```

---

## Summary

✅ **Two endpoints** - Platform-compatible `/chat` + OpenAI-compatible `/v1/chat/completions`
✅ **Session management** - Agent maintains state, platform just passes session_id
✅ **Complete tracing** - Every request logs full conversation flow with tool calls
✅ **Platform-ready** - Minimal changes needed (just pass session_id)
✅ **A/B testing ready** - Full trace data for analysis

The agent is now **fully compatible** with your A/B testing platform! 🎉
