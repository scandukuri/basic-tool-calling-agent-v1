# Tool-Calling Agent - Executive Summary

## Project at a Glance

The project is a **minimal, single-file tool-calling agent** built with Flask that integrates with GPT-4o for intelligent chat interactions with automatic tool calling capabilities.

- **Single File:** `app.py` (814 lines of Python)
- **No Database:** In-memory storage (Python dicts)
- **Two Chat Endpoints:** OpenAI-compatible + Platform-compatible
- **2 Tools:** Calculator and Web Search
- **Frontend:** Embedded vanilla JavaScript UI
- **Status:** Production-ready for A/B testing platforms

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      Flask Server (app.py)              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐         ┌────────────────────┐   │
│  │   Two Endpoints  │         │   Two Tools        │   │
│  │                  │         │                    │   │
│  │ /v1/chat (OpenAI)├─────────┤ web_search         │   │
│  │ /chat (Platform) │         │ calculator         │   │
│  └────────┬─────────┘         └────────────────────┘   │
│           │                                             │
│           v                                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │    _run_completion() - Core Tool Loop            │   │
│  │  (max 10 iterations of tool calling)             │   │
│  └──────────────────────────────────────────────────┘   │
│           │                                             │
│           v                                             │
│  ┌──────────────────────────────────────────────────┐   │
│  │         OpenAI GPT-4o API                        │   │
│  │  (with function calling enabled)                 │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │    Trace Collection                              │   │
│  │  (Every interaction logged with timestamps,      │   │
│  │   tool durations, tokens, full conversation)     │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │    Session Management (In-Memory)                │   │
│  │  sessions = {} → {session_id: session_obj}       │   │
│  │  traces = [] → [trace_obj, trace_obj, ...]       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │    Web UI (Embedded Frontend)                    │   │
│  │  Vanilla JS + HTML/CSS                           │   │
│  │  localhost:5000                                  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Current Implementation Structure

### Backend
- **Framework:** Flask 3.0.0
- **Language:** Python 3.12
- **Location:** Single file `/app.py`
- **Architecture:** Monolithic (no separation of concerns)
- **Storage:** In-memory dictionaries (Python objects)
- **API Style:** RESTful with 8 endpoints

### Frontend
- **Framework:** None (vanilla JavaScript)
- **Style:** Embedded in Flask HTML route
- **UI Framework:** Pure CSS Grid/Flexbox
- **State:** Session ID stored in JS variable
- **Interaction:** Direct DOM manipulation

### Key Statistics
- **814 total lines** in app.py
- **8 API endpoints**
- **2 tools** (calculator, web_search)
- **5 main functions** (start_session, end_session, platform_chat, completions, _run_completion)

---

## 2. Session Tracking

### How Sessions Work

1. **Creation:** Frontend calls `POST /session/start` → Server creates random `sess_abc123`
2. **Usage:** Frontend stores session_id in localStorage concept
3. **Persistence:** Every message appended to `sessions[session_id]["messages"]`
4. **Termination:** Frontend calls `POST /session/end` → Server marks completed

### Session Data Structure
```python
sessions = {
    "sess_abc123": {
        "session_id": "sess_abc123",
        "started_at": "2025-10-18T20:00:00",
        "ended_at": "2025-10-18T20:05:00",
        "status": "completed",
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"}
        ],
        "traces": ["trace_id_1", "trace_id_2"]
    }
}
```

### Session Endpoints
- `POST /session/start` - Creates new session
- `POST /session/end` - Ends session
- `GET /session/{session_id}` - Retrieves full session

---

## 3. API Endpoints

### Summary Table

| Endpoint | Method | Purpose | Key Feature |
|----------|--------|---------|-------------|
| `/` | GET | Web UI | Embedded React-like experience |
| `/session/start` | POST | Create session | Returns session_id |
| `/session/end` | POST | End session | Marks completed |
| `/session/{id}` | GET | Get session | Full history included |
| `/v1/chat/completions` | POST | OpenAI-compatible chat | Standard format |
| `/chat` | POST | Platform-compatible chat | Auto-session creation |
| `/traces` | GET | Get all traces | For debugging |
| `/traces/{id}` | GET | Get specific trace | Detailed metrics |

### Two Main Chat Endpoints

#### Endpoint 1: `/v1/chat/completions` (OpenAI-Compatible)
- **Input:** `{messages, system_prompt, session_id, temperature, max_tokens, top_p}`
- **Output:** Full OpenAI API response + trace data
- **Use Case:** Drop-in replacement for OpenAI API
- **Frontend Uses This**

#### Endpoint 2: `/chat` (Platform-Compatible)
- **Input:** `{messages, temperature, session_id(optional), max_tokens, top_p}`
- **Output:** `{response, session_id, trace}`
- **Auto-Creates Sessions:** No session_id required
- **Use Case:** A/B testing platforms
- **Simpler Response Format**

---

## 4. Tool Calling Implementation

### Tool Definition Process

1. **Define in TOOLS Array** (lines 17-47)
   - JSON Schema format (OpenAI function calling spec)
   - Includes description and parameters

2. **Create Handler Function** (lines 53-93)
   - Pure Python function
   - Returns string result

3. **Register in execute_tool()** (lines 95-102)
   - Router function that dispatches to handler

### Tool Calling Loop (`_run_completion()`)

```python
for iteration in range(10):  # Max 10 iterations
    response = openai_api_call(messages, tools=TOOLS)
    
    if not response.tool_calls:
        # Done - return response
        break
    
    # Execute each tool
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call.name, tool_call.arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        })
    
    # Loop again with new result in messages
```

### Available Tools

**1. web_search**
- Parameters: `query` (required), `num_results` (optional, default 5)
- Implementation: DuckDuckGo HTML scraping
- No API key required

**2. calculator**
- Parameters: `expression` (required)
- Implementation: Safe eval with restricted namespace
- Supported: sqrt, sin, cos, tan, pi, e, log, floor, ceil, etc.

### Tool Execution Tracking

Every tool call is logged with:
- Tool name
- Arguments passed
- Result (truncated to 200 chars in trace)
- Duration in milliseconds
- ISO timestamp

---

## 5. Message History Management

### Message Format (OpenAI Standard)
```python
{
    "role": "system|user|assistant|tool",
    "content": "message text",
    "tool_calls": [...],      # if role="assistant" and called tools
    "tool_call_id": "call_x", # if role="tool"
    "name": "tool_name"       # if role="tool"
}
```

### Message Flow per Endpoint

**In `/v1/chat/completions`:**
1. Extract new message from request
2. Load session history if session_id exists
3. Append new message to history
4. Pass to `_run_completion()` with full history
5. Append response back to session

**In `/chat`:**
1. Platform sends entire conversation history in each request
2. Merge with session stored in backend (if session_id provided)
3. Pass full merged conversation to `_run_completion()`
4. Update session with new messages

### Key Insight
- **Frontend:** Builds message history incrementally
- **Platform:** Sends full history each time (OpenAI API style)
- **Backend:** Always works with complete message arrays

---

## 6. Configuration Management

### Supported Parameters

| Parameter | Default | Range | Notes |
|-----------|---------|-------|-------|
| `temperature` | 0.7 | 0-2 | Randomness (0=deterministic, 2=very random) |
| `top_p` | 1.0 | 0-1 | Nucleus sampling (1.0 = no filtering) |
| `max_tokens` | varies | 1-4096 | Max response length |
| `system_prompt` | varies | string | System instructions |

### Per-Endpoint Defaults

**`/v1/chat/completions`:**
```python
{
    "temperature": 0.7,
    "top_p": 1.0,
    "max_tokens": 1000,
    "system_prompt": "You are a helpful assistant..."
}
```

**`/chat`:**
```python
{
    "temperature": 0.7,
    "top_p": 1.0,
    "max_tokens": 2048,  # Higher default
    "system_prompt": "You are a helpful assistant with access to web search and calculator tools."
}
```

### System Prompt Extraction

**Priority Order:**
1. If `messages[0].role == "system"` → Use that content
2. Else if `system_prompt` field provided → Use that
3. Else → Use endpoint default

This allows platforms to override system prompt per-request.

---

## 7. Storage & State

### In-Memory Storage (Global Variables)

```python
traces = []        # List of trace objects
sessions = {}      # Dict of session_id -> session_obj
```

### Lifecycle

**Traces:**
- Created when request starts
- Appended to `traces` list when complete
- Persists for `/traces` API access
- No automatic cleanup

**Sessions:**
- Created on `/session/start` or auto-created on `/chat` endpoint
- Messages appended on each turn
- Marked "completed" on `/session/end`
- Data still in memory (not deleted)

### Implications
- **Suitable for:** Development, demos, A/B testing platforms with their own storage
- **Not suitable for:** Production with persistence requirements
- **Scalability:** Grows unbounded (no cleanup mechanism)
- **Recovery:** Lost on server restart

---

## 8. Trace Data Collection

### Comprehensive Logging

Every request creates a trace object with:

```python
{
    "trace_id": "trace_xyz",
    "started_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    
    # Turns in conversation
    "turns": [
        {
            "role": "user|assistant|tool",
            "content": "...",
            "timestamp": "ISO",
            "tool_calls": [...] # if assistant
        }
    ],
    
    # All tool executions
    "tool_calls": [
        {
            "name": "calculator",
            "arguments": {"expression": "25*47"},
            "result": "1175",
            "duration_ms": 0.5,
            "timestamp": "ISO"
        }
    ],
    
    # Configuration used
    "config": {
        "model": "gpt-4o",
        "temperature": 0.7,
        "top_p": 1.0,
        "max_tokens": 1000
    },
    
    "total_tokens": 150,
    "error": null  # or error message if failed
}
```

### Use Cases for Trace Data
- **A/B Testing:** Compare variant performance metrics
- **Debugging:** See exactly what happened in conversation
- **Analytics:** Tool usage patterns, token efficiency
- **Audit:** Full conversation history with timestamps

---

## 9. Key Design Patterns

### 1. Automatic Tool Looping
Request → Tool Call → Execute → Result → Request → (repeat)
- Max 10 iterations to prevent infinite loops
- Transparent to caller (automatic)
- All iterations visible in trace

### 2. Dual Endpoint Architecture
- **OpenAI-compatible**: For existing integrations
- **Platform-compatible**: For A/B testing systems
- **Shared Core**: Both use same `_run_completion()`

### 3. Comprehensive Tracing
- Every interaction logged
- Duration tracking for tools
- Token counting
- Exposed via API for analysis

### 4. Session Merging Strategy
- Sessions store incremental history
- Platforms can pass full history per request
- Backend intelligently merges both approaches

### 5. Embedded Frontend
- No separate deployment
- Vanilla JS (minimal dependencies)
- Can be disabled (API-only usage)

---

## 10. File Locations Summary

```
/Users/scandukuri/basic-tool-calling-agent-v1/
├── app.py                          ← Main application (814 lines)
│   ├── TOOLS array (lines 17-47)
│   ├── Tool functions (lines 53-93)
│   ├── Session endpoints (lines 104-142)
│   ├── Chat endpoints (lines 144-464)
│   ├── Frontend HTML/CSS/JS (lines 479-808)
│   └── Main app startup (lines 810-813)
├── requirements.txt                ← Dependencies
├── .env                           ← API key (gitignored)
├── README.md                      ← User guide
├── PLATFORM_INTEGRATION.md        ← Integration guide
├── ARCHITECTURE.md                ← (newly created)
└── QUICK_REFERENCE.md             ← (newly created)
```

---

## 11. External Dependencies

### Python Packages
```
flask==3.0.0             # Web framework
flask-cors==4.0.0        # CORS support
openai>=1.12.0          # OpenAI API client
requests==2.31.0        # HTTP library
beautifulsoup4==4.12.3  # HTML parsing (web_search)
```

### External APIs
- **OpenAI:** GPT-4o model (requires API key)
- **DuckDuckGo:** Web search (no API key needed)

---

## 12. Quick Start for Developers

### Setup
```bash
cd /Users/scandukuri/basic-tool-calling-agent-v1
export OPENAI_API_KEY="your-key-here"
python app.py
```

### Access
- Web UI: http://localhost:5000
- API: http://localhost:5000/chat

### Test Endpoints
```bash
./test_agent.sh              # Test OpenAI-compatible endpoint
./test_chat_endpoint.sh      # Test platform-compatible endpoint
```

---

## 13. Known Limitations & Future Improvements

### Current Limitations
1. **In-Memory Storage:** Data lost on restart
2. **Single Instance:** No multi-server support
3. **No Persistence:** Data not backed up to database
4. **No Authentication:** Any client can access
5. **No Rate Limiting:** Could be abused
6. **10 Tool Call Max:** Could be limiting for complex tasks
7. **Synchronous Only:** No async/concurrent handling

### Potential Improvements
- Add database persistence (PostgreSQL/MongoDB)
- Implement authentication/API keys
- Add rate limiting per session
- Support streaming responses
- Add more tools (code execution, file operations)
- Implement session cleanup/TTL
- Add admin dashboard for viewing traces
- Support multiple LLM models
- Add caching layer

---

## 14. Testing

### Included Test Scripts

**test_agent.sh** - Tests `/v1/chat/completions`
- Session creation
- Multi-turn conversation
- Calculator tool
- Trace inspection

**test_chat_endpoint.sh** - Tests `/chat`
- Auto-session creation
- Session persistence
- System prompt extraction
- Full conversation history
- Trace data validation

### Manual Testing
```bash
# View all traces
curl http://localhost:5000/traces

# View specific trace
curl http://localhost:5000/traces/{trace_id}

# View session
curl http://localhost:5000/session/{session_id}
```

---

## Summary

This is a **well-structured, minimal tool-calling agent** perfect for:
- Learning tool-calling concepts
- Prototyping AI features
- A/B testing different agent behaviors
- Embedding in A/B testing platforms

The single-file architecture keeps it simple while the dual endpoints provide both developer-friendly and platform-integration formats. Comprehensive tracing enables detailed analysis for optimization.

**Key Strengths:**
- Simple, easy to understand
- Complete tool calling implementation
- Production-ready tracing for A/B testing
- Flexible configuration per request
- No external dependencies (Flask + OpenAI SDK only)

**Ready to:**
- Add more tools
- Connect to A/B testing platform
- Extend with persistence
- Deploy behind load balancer

