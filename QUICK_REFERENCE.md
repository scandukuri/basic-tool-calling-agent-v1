# Quick Reference Guide

## File Locations

| Component | Location | Lines |
|-----------|----------|-------|
| **App Entry Point** | `/app.py` | - |
| **Tool Definitions** | `/app.py` | 17-47 |
| **Tool Functions** | `/app.py` | 53-93 |
| **Tool Executor** | `/app.py` | 95-102 |
| **Session Management** | `/app.py` | 104-142 |
| **Platform Chat** | `/app.py` | 144-224 |
| **Core Logic** | `/app.py` | 226-399 |
| **OpenAI Endpoint** | `/app.py` | 402-464 |
| **Trace Queries** | `/app.py` | 466-477 |
| **Frontend UI** | `/app.py` | 479-808 |
| **Dependencies** | `/requirements.txt` | - |

## Global State

```python
# Line 49-51 in app.py
traces = []      # List of trace objects
sessions = {}    # Dict mapping session_id -> session object
```

## Key Functions

### Tool Functions
- `web_search(query, num_results)` - Line 53
- `calculator(expression)` - Line 79
- `execute_tool(tool_name, arguments)` - Line 95

### Endpoint Handlers
- `start_session()` - Line 104
- `end_session()` - Line 119
- `get_session(session_id)` - Line 137
- `platform_chat()` - Line 144
- `completions()` - Line 402
- `get_traces()` - Line 466
- `get_trace(trace_id)` - Line 471

### Core Logic
- `_run_completion(messages, config, session_id)` - Line 226

## Data Structures

### Session Object
```python
{
    "session_id": "sess_abc123",
    "started_at": "2025-10-18T20:00:00",
    "ended_at": "2025-10-18T20:05:00" (optional),
    "status": "completed|active",
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "traces": ["trace_id_1", "trace_id_2"]
}
```

### Trace Object
```python
{
    "trace_id": "trace_xyz",
    "started_at": "2025-10-18T20:00:00",
    "completed_at": "2025-10-18T20:00:03",
    "turns": [
        {
            "role": "user|assistant|tool",
            "content": "message text",
            "tool_calls": [...],
            "timestamp": "ISO"
        }
    ],
    "tool_calls": [
        {
            "name": "calculator",
            "arguments": {"expression": "25*47"},
            "result": "1175",
            "duration_ms": 0.5,
            "timestamp": "ISO"
        }
    ],
    "config": {
        "model": "gpt-4o",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 1000
    },
    "total_tokens": 150
}
```

## Request/Response Examples

### Start Session
```bash
POST /session/start
{}

Response:
{
  "session_id": "sess_abc123",
  "started_at": "2025-10-18T20:00:00"
}
```

### Send Message (OpenAI Compatible)
```bash
POST /v1/chat/completions
{
  "messages": [{"role": "user", "content": "What is 25*47?"}],
  "session_id": "sess_abc123",
  "temperature": 0.7
}

Response:
{
  "id": "chatcmpl-xyz",
  "object": "chat.completion",
  "model": "gpt-4o-2024-08-06",
  "choices": [{
    "message": {"role": "assistant", "content": "1,175"},
    "finish_reason": "stop"
  }],
  "usage": {"total_tokens": 18},
  "trace_id": "trace_xyz",
  "session_id": "sess_abc123",
  "trace": { ... }
}
```

### Send Message (Platform Compatible)
```bash
POST /chat
{
  "messages": [{"role": "user", "content": "What is 25*47?"}],
  "session_id": "sess_abc123",
  "temperature": 0.7
}

Response:
{
  "response": "1,175",
  "session_id": "sess_abc123",
  "trace": { ... }
}
```

## Tool Calling Loop

```
1. OpenAI API call with tools
2. If assistant.tool_calls is empty:
   - Return response
3. Else:
   - For each tool_call:
     - Execute tool
     - Add result to messages
   - Go to step 1 (max 10 iterations)
```

## Frontend Functions

| Function | Purpose |
|----------|---------|
| `startSession()` | Create new session |
| `endSession()` | End active session |
| `addMessage(role, content)` | Render message in UI |
| `sendMessage()` | Send message to backend |
| `handleKeyDown(event)` | Handle Enter key |

## Configuration Defaults

### `/v1/chat/completions`
- `temperature`: 0.7
- `top_p`: 1.0
- `max_tokens`: 1000
- `system_prompt`: "You are a helpful assistant..."

### `/chat`
- `temperature`: 0.7
- `top_p`: 1.0
- `max_tokens`: 2048 (higher)
- `system_prompt`: "You are a helpful assistant with access to web search and calculator tools."

## Available Tools

### web_search
```json
{
  "query": "search term (required)",
  "num_results": 5 (optional)
}
```
Returns: Web search results from DuckDuckGo

### calculator
```json
{
  "expression": "math expression (required)"
}
```
Returns: Evaluated result or error message
Supported: abs, round, min, max, sum, pow, sqrt, sin, cos, tan, pi, e, log, log10, exp, floor, ceil

## Common Tasks

### Add New Tool
1. Define in `TOOLS` array (line 17-47)
2. Create handler function
3. Add case in `execute_tool()` (line 95-102)

### Change Default Config
- Line 410-414: `/v1/chat/completions` defaults
- Line 170-175: `/chat` endpoint defaults

### Modify Frontend
- HTML: Lines 645-673
- CSS: Lines 485-642
- JavaScript: Lines 676-806

### Add Session Persistence
- Replace `sessions = {}` dictionary with database
- Update session endpoints to use database

## Debugging

### View All Traces
```bash
curl http://localhost:5000/traces
```

### View Specific Trace
```bash
curl http://localhost:5000/traces/{trace_id}
```

### View Session Details
```bash
curl http://localhost:5000/session/{session_id}
```

### Tool Call Logging
- Lines 363-367: Debug output during tool execution
- Look for "🔧 Calling tool" in console

## Performance Metrics

All captured in trace object:
- `duration_ms`: Tool execution time
- `total_tokens`: Full request token usage
- `timestamp`: When each turn occurred

## Known Limitations

1. **In-Memory Storage:** Data lost on restart
2. **Single Instance:** No multi-server support
3. **No Cleanup:** Session/trace data grows unbounded
4. **10 Tool Call Limit:** Max iterations per request
5. **Synchronous:** Blocking API calls (no async)
6. **No Authentication:** Anyone can access all endpoints

## Environment

- `OPENAI_API_KEY`: Required (from .env file)
- Port: 5000
- CORS: Enabled for all origins

