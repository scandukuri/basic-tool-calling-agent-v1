# Tool-Calling Agent Architecture Analysis

## Project Overview

**Name:** Minimal Tool-Calling Agent (Chat Interface)
**Location:** `/Users/scandukuri/basic-tool-calling-agent-v1`
**Stack:** Python Flask backend with vanilla JS frontend
**Model:** GPT-4o
**Architecture:** Single-file monolithic application

---

## 1. CURRENT AGENT IMPLEMENTATION STRUCTURE

### Backend Implementation

**Main File:** `/Users/scandukuri/basic-tool-calling-agent-v1/app.py` (814 lines)

#### Technology Stack:
- **Framework:** Flask 3.0.0
- **CORS:** flask-cors 4.0.0
- **AI Client:** OpenAI SDK (>=1.12.0)
- **HTTP:** requests 2.31.0
- **Web Scraping:** BeautifulSoup 4.12.3
- **Environment:** Python 3.12

#### Architecture Pattern:
- **Monolithic:** All logic in single `app.py` file
- **In-Memory Storage:** No database; uses Python dictionaries
- **Synchronous:** Blocking API calls (no async)
- **CORS Enabled:** Cross-origin requests allowed

### Frontend Implementation

**Location:** Embedded in `app.py` (lines 479-808)

#### Technology:
- **Framework:** Vanilla JavaScript (no frameworks)
- **HTML/CSS:** Embedded in Flask route (`/` endpoint)
- **Styling:** CSS Grid + Flexbox
- **DOM API:** Pure vanilla JS (no jQuery/frameworks)

#### UI Components:
- Chat message display
- Message input textarea
- Session controls (Start/End buttons)
- Auto-scrolling message feed
- Timestamps for messages

---

## 2. SESSION TRACKING

### Session Storage

**Location:** `app.py` lines 49-51
```python
# In-memory storage
traces = []
sessions = {}
```

### Session Management

**Session Structure:**
```python
{
    "session_id": "sess_abc123",
    "started_at": "ISO timestamp",
    "ended_at": "ISO timestamp (optional)",
    "status": "completed|active",
    "messages": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ],
    "traces": ["trace_id_1", "trace_id_2"]
}
```

### Session Endpoints

1. **Start Session** (Lines 104-117)
   - Endpoint: `POST /session/start`
   - Creates new session ID: `sess_{uuid.hex[:8]}`
   - Returns: `{session_id, started_at}`

2. **End Session** (Lines 119-135)
   - Endpoint: `POST /session/end`
   - Marks session as "completed"
   - Records end timestamp and message count
   - Returns: `{session_id, message_count, ended_at}`

3. **Get Session** (Lines 137-142)
   - Endpoint: `GET /session/<session_id>`
   - Returns full session object with all messages

### Session Lifecycle

```
1. Frontend calls /session/start → Creates session
2. Frontend stores session_id locally
3. Each message includes session_id in request
4. Backend appends messages to session.messages
5. Frontend calls /session/end → Completes session
```

---

## 3. EXISTING API ENDPOINTS

### Endpoint Summary

| Endpoint | Method | Purpose | Input | Output |
|----------|--------|---------|-------|--------|
| `/` | GET | HTML chat UI | - | Embedded HTML/CSS/JS |
| `/session/start` | POST | Create session | {} | {session_id, started_at} |
| `/session/end` | POST | End session | {session_id} | {session_id, message_count, ended_at} |
| `/session/<id>` | GET | Get session data | - | Full session object |
| `/v1/chat/completions` | POST | OpenAI-compatible | {messages, session_id, config} | OpenAI-compatible response |
| `/chat` | POST | Platform-compatible | {messages, session_id, config} | {response, session_id, trace} |
| `/traces` | GET | Get all traces | - | {traces: [], count: int} |
| `/traces/<id>` | GET | Get trace by ID | - | Single trace object |

### Main Chat Endpoints

#### 1. `/v1/chat/completions` - OpenAI Compatible (Lines 402-464)

**Request Format:**
```json
{
  "messages": [{"role": "user", "content": "Hello"}],
  "system_prompt": "You are a helpful assistant.",
  "session_id": "sess_xxx" (optional),
  "temperature": 0.7,
  "top_p": 1.0,
  "max_tokens": 1000
}
```

**Response Format:**
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4o-2024-08-06",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "..."},
    "finish_reason": "stop"
  }],
  "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
  "trace_id": "trace_xyz",
  "session_id": "sess_xxx",
  "trace": { /* trace data */ }
}
```

**Flow:**
1. Extracts config parameters (temperature, top_p, max_tokens, system_prompt)
2. Handles system message from messages array
3. Calls `_run_completion()` internal function
4. Returns OpenAI-format response with trace data

#### 2. `/chat` - Platform Compatible (Lines 144-224)

**Request Format:**
```json
{
  "messages": [
    {"role": "system", "content": "..."} (optional),
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "temperature": 0.7,
  "top_p": 1.0,
  "max_tokens": 2048,
  "session_id": "sess_xxx" (optional - auto-created if missing)
}
```

**Response Format:**
```json
{
  "response": "Assistant's message",
  "session_id": "sess_xxx",
  "trace": {
    "trace_id": "trace_xyz",
    "started_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    "tool_calls": [...],
    "turns": [...],
    "config": {...},
    "total_tokens": 150
  }
}
```

**Key Features:**
- Auto-creates session if no `session_id` provided
- Extracts system prompt from `messages[0]` if role="system"
- Session persistence: appends new messages to existing session history
- Returns simplified response with trace data for A/B testing

---

## 4. AGENT SCAFFOLDING / TOOL CALLING IMPLEMENTATION

### Tool Definitions

**Location:** `app.py` lines 17-47

**Defined Tools:**
1. **web_search**
   - Function: Search web via DuckDuckGo HTML scraping
   - Parameters: `query` (required, string), `num_results` (optional, int, default 5)
   - Location: `app.py` lines 53-77

2. **calculator**
   - Function: Evaluate math expressions safely
   - Parameters: `expression` (required, string)
   - Location: `app.py` lines 79-93
   - Safe Math Functions: abs, round, min, max, sum, pow, sqrt, sin, cos, tan, pi, e, log, log10, exp, floor, ceil
   - Security: Uses eval with restricted namespace (`__builtins__: {}`)

### Tool Execution

**Tool Dispatcher Function:** `execute_tool()` (Lines 95-102)
```python
def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool and return results."""
```

Routes tool calls to appropriate handler functions.

### Tool Calling Loop

**Main Function:** `_run_completion()` (Lines 226-399)

**Algorithm:**
1. Build full message history with system prompt
2. Create trace object with unique trace_id
3. Loop up to 10 iterations (max tool calls):
   - Call OpenAI API with tools enabled
   - If no tool_calls: break (done)
   - If tool_calls: execute each tool
   - Append tool results to messages
   - Continue loop for next iteration
4. Return final assistant content with trace

**Tool Call Handling:**
- **Lines 357-393:** Execute each tool call
  - Parse tool arguments from JSON
  - Call tool executor
  - Record duration in milliseconds
  - Log result to trace
  - Format tool result message for next API call

**Error Handling:**
- OpenAI API errors caught and logged to trace
- Max iterations protection (10 loops)
- Tool execution errors captured in result strings

### Trace Data Collection

**Trace Structure:**
```python
{
    "trace_id": "trace_xyz",
    "started_at": "ISO timestamp",
    "completed_at": "ISO timestamp",
    "turns": [
        {
            "role": "user|assistant|tool",
            "content": "...",
            "tool_calls": [...] (if assistant),
            "tool_call_id": "call_xxx" (if tool),
            "timestamp": "ISO timestamp"
        }
    ],
    "tool_calls": [
        {
            "name": "calculator",
            "arguments": {"expression": "25*47"},
            "result": "1175",
            "full_result_length": 4,
            "duration_ms": 0.5,
            "timestamp": "ISO timestamp"
        }
    ],
    "config": {
        "model": "gpt-4o",
        "max_tokens": 1000,
        "temperature": 0.7,
        "top_p": 1.0
    },
    "total_tokens": 150 (populated from OpenAI response)
}
```

---

## 5. MESSAGE HISTORY MANAGEMENT

### Message Format

**OpenAI Standard Format:**
```python
{
    "role": "system|user|assistant|tool",
    "content": "message text",
    "tool_calls": [...] (if role="assistant" and tool calls made),
    "tool_call_id": "call_xxx" (if role="tool"),
    "name": "tool_name" (if role="tool")
}
```

### Message Flow

**In `/v1/chat/completions` Endpoint (Lines 402-464):**

1. **Input Processing:**
   - Extract messages from request
   - Handle optional system message in messages array
   - Append user's latest message to session history

2. **Conversation Building:**
   ```python
   if session_id and session_id in sessions:
       messages = sessions[session_id]["messages"] + [data.get("messages", [{}])[-1]]
   else:
       messages = data.get("messages", [])
   ```

3. **System Message Handling:**
   ```python
   if messages and messages[0].get("role") == "system":
       config["system_prompt"] = messages[0]["content"]
       messages = messages[1:]  # Remove for processing
   ```

4. **Internal Processing:**
   - Prepends system message in `_run_completion()` (line 245)
   - Creates full message array: `[system_msg] + messages`

5. **Session Storage:**
   - Appends both user and assistant messages to session history
   - Stores trace_id in session.traces

### In `/chat` Endpoint (Lines 144-224):

1. **Platform Provides Full History:**
   - Can pass entire conversation in `messages` array
   - Agent uses full history for context

2. **Session Merge:**
   ```python
   if session_id in sessions:
       conversation_messages = sessions[session_id]["messages"].copy()
       conversation_messages.extend(messages)
   else:
       conversation_messages = messages
   ```

3. **Auto-Persistence:**
   - If session exists, appends new messages to history
   - Updates session with latest turn

---

## 6. CONFIGURATION MANAGEMENT

### Configuration Parameters

**Supported Parameters:**
- `temperature` (default: 0.7, range: 0-2)
- `top_p` (default: 1.0, range: 0-1)
- `max_tokens` (default: 1000, varies by endpoint)
- `system_prompt` (default: helpful assistant prompt)

### Configuration Extraction

**Endpoint-Specific Defaults:**

1. **`/v1/chat/completions` Endpoint:**
   ```python
   config = {
       "system_prompt": data.get("system_prompt", "You are a helpful assistant..."),
       "max_tokens": data.get("max_tokens", 1000),
       "temperature": data.get("temperature", 0.7),
       "top_p": data.get("top_p", 1.0)
   }
   ```

2. **`/chat` Endpoint:**
   ```python
   config = {
       "temperature": data.get("temperature", 0.7),
       "top_p": data.get("top_p", 1.0),
       "max_tokens": data.get("max_tokens", 2048),  # Higher default
       "system_prompt": "You are a helpful assistant with access to web search and calculator tools."
   }
   ```

### System Prompt Handling

1. **Explicit System Prompt:**
   - Passed in request: `"system_prompt"` field

2. **Implicit System Prompt:**
   - First message with `role="system"` extracted from messages array
   - Automatically used as system prompt

3. **Default System Prompt:**
   - Different defaults per endpoint
   - `/v1/chat/completions`: Generic helpful assistant
   - `/chat`: Mentions available tools

### Configuration Flow

```
Request Data
    ↓
Extract config parameters with defaults
    ↓
Extract system prompt from messages[0] if present (override explicit)
    ↓
Pass to _run_completion()
    ↓
Include in trace for analysis
```

---

## 7. FILE STRUCTURE & LOCATIONS

### Project Root
```
/Users/scandukuri/basic-tool-calling-agent-v1/
├── app.py (814 lines) - MAIN APPLICATION
├── app_old.py - Previous version (backup)
├── requirements.txt - Dependencies
├── .env - Environment variables (OPENAI_API_KEY)
├── .env.example - Template
├── PLATFORM_INTEGRATION.md - Integration guide
├── README.md - User documentation
├── test_agent.sh - Test script for /v1/chat/completions
├── test_chat_endpoint.sh - Test script for /chat endpoint
├── .claude/ - Claude IDE settings
└── venv/ - Python virtual environment
```

### Code Organization Within app.py

| Section | Lines | Purpose |
|---------|-------|---------|
| Imports | 1-10 | Dependencies |
| Flask Setup | 12-14 | Initialize app and OpenAI client |
| Tool Definitions | 17-47 | TOOLS array with JSON schema |
| Storage | 50-51 | Global `traces` and `sessions` dicts |
| Tool Functions | 53-93 | `web_search()`, `calculator()` |
| Tool Executor | 95-102 | `execute_tool()` dispatcher |
| Session Endpoints | 104-142 | Start, end, get session |
| Platform Chat | 144-224 | `/chat` endpoint |
| Core Logic | 226-399 | `_run_completion()` function |
| OpenAI Endpoint | 402-464 | `/v1/chat/completions` |
| Trace Endpoints | 466-477 | `/traces`, `/traces/{id}` |
| Frontend HTML | 479-808 | Embedded web UI |
| Main | 810-813 | App startup |

### Frontend Files

**Location:** Embedded in `app.py` lines 479-808

**HTML Elements:**
- Header with session controls
- Messages container (auto-scrolling)
- Input textarea with Enter-to-send
- Send button

**CSS:**
- Grid/Flexbox layout
- Message bubbles with avatars
- Responsive design
- Light mode colors (#1a73e8, #34a853)

**JavaScript:**
- `startSession()` - Creates new session
- `endSession()` - Ends current session
- `addMessage()` - Renders message in UI
- `sendMessage()` - Posts to `/v1/chat/completions`
- `handleKeyDown()` - Enter key handling

---

## 8. CURRENT FLOW DIAGRAMS

### Session-Based Flow (Frontend)

```
User opens http://localhost:5000
    ↓
Frontend loads embedded HTML/CSS/JS
    ↓
User clicks "New Chat"
    ↓
POST /session/start → Creates session, returns session_id
    ↓
User types message → POST /v1/chat/completions with session_id
    ↓
Backend processes with tool calling
    ↓
Response returned → Frontend displays
    ↓
Messages appended to session history
    ↓
User clicks "End Chat"
    ↓
POST /session/end → Marks session complete
```

### Platform Integration Flow

```
Platform sends message via POST /chat
    ↓
Request includes: messages, temperature, session_id (optional)
    ↓
If no session_id:
  - Create new session
  - Return new session_id
Else:
  - Load existing session messages
  - Append new message
    ↓
Extract system prompt (from messages[0] if present)
    ↓
Call _run_completion() with full message history
    ↓
Tool calling loop:
  - OpenAI API call
  - Execute tools if needed
  - Append results
  - Loop until no more tools
    ↓
Return: {response, session_id, trace}
    ↓
Platform stores trace data
Platform passes session_id next request
```

### Tool Calling Loop

```
_run_completion(messages, config)
    ↓
Prepend system message
    ↓
[Loop - max 10 iterations]
    ↓
OpenAI API call with tools enabled
    ↓
Response received
    ↓
If no tool_calls:
  - Record final assistant response
  - Store trace
  - Return
    ↓
If tool_calls:
  - For each tool call:
    - Execute tool function
    - Record duration
    - Format result message
  - Append tool results to messages
  - Continue loop
```

---

## 9. KEY DESIGN PATTERNS

### 1. Tool Calling Pattern
- **OpenAI Tool Use Format:** JSON schema definitions with function descriptors
- **Tool Loop:** Automatic retry until no tool calls needed
- **Error Handling:** Max 10 iterations to prevent infinite loops

### 2. Session Management Pattern
- **Dictionary-Based:** In-memory Python dict for sessions
- **Session ID:** Random UUID-based identifiers
- **Append-Only:** Messages appended but never modified

### 3. Trace Pattern
- **Comprehensive Logging:** Every interaction logged
- **Structured Data:** JSON-compatible trace format
- **Metrics:** Duration tracking, token counting
- **Analysis Ready:** Traces exposed via API for A/B testing

### 4. Dual Endpoint Pattern
- **OpenAI-Compatible:** `/v1/chat/completions` for existing integrations
- **Platform-Compatible:** `/chat` for A/B testing platforms
- **Shared Core:** Both use same `_run_completion()` function

### 5. Frontend Pattern
- **Embedded UI:** Single HTML file within Flask route
- **Vanilla JavaScript:** No framework dependencies
- **State Management:** Session ID stored in JavaScript variable
- **Real-Time Updates:** Direct DOM manipulation for message display

---

## 10. STORAGE & STATE MANAGEMENT

### Storage Type: In-Memory Python Dicts

**Global Variables (Lines 50-51):**
```python
traces = []        # List of all traces (persistent per server run)
sessions = {}      # Dict of active sessions (persistent per server run)
```

### Implications:
- **No Persistence:** Data lost on server restart
- **Single Server Only:** Multiple instances won't share data
- **Suitable For:** Development, demos, A/B testing platforms with their own storage
- **Scalability Limit:** Grows unbounded (no cleanup)

### Session Storage Lifecycle:
1. Session created when `/session/start` called
2. Messages appended on each turn
3. Session marked "completed" on `/session/end`
4. Data still in memory (not deleted)

### Trace Storage Lifecycle:
1. Trace object created at start of `_run_completion()`
2. Appended to `traces` list on completion or error
3. Persists for `/traces` API access
4. No TTL or cleanup mechanism

---

## 11. EXTERNAL DEPENDENCIES

### Python Packages (requirements.txt)
```
flask==3.0.0                 # Web framework
flask-cors==4.0.0            # CORS support
openai>=1.12.0              # OpenAI API client
requests==2.31.0            # HTTP library
beautifulsoup4==4.12.3      # HTML parsing for web search
```

### External APIs
- **OpenAI API:** GPT-4o model calls
- **DuckDuckGo:** Web search via HTML scraping (no API key needed)

### Environment Variables
- `OPENAI_API_KEY` - Required for operation

---

## 12. TESTING & DEBUGGING

### Test Scripts

**File 1:** `test_agent.sh` - Tests `/v1/chat/completions` endpoint
- Start session
- Send messages (calculator tests)
- View traces
- View session data
- End session

**File 2:** `test_chat_endpoint.sh` - Tests `/chat` endpoint
- Auto-session creation
- Session persistence
- System prompt extraction
- Full conversation history
- Tool calling verification
- Trace data validation

### Debug Features:
- Console logging with 🔧 emoji for tool calls
- Trace duration tracking
- Full error messages in responses
- `/traces` endpoint for all traces
- `/traces/{id}` for specific trace details

---

## SUMMARY TABLE

| Aspect | Implementation |
|--------|-----------------|
| **Language** | Python 3.12 |
| **Framework** | Flask 3.0.0 |
| **Frontend** | Vanilla JS (embedded HTML) |
| **Storage** | In-memory Python dicts |
| **Sessions** | UUID-based, append-only messages |
| **Tools** | 2 (web_search, calculator) |
| **Tool Calling** | OpenAI API with auto-loop (max 10) |
| **Tracing** | Comprehensive JSON-based traces |
| **Endpoints** | 8 main endpoints |
| **Main Chat** | `/v1/chat/completions`, `/chat` |
| **Configuration** | Temp, top_p, max_tokens, system_prompt |
| **Message History** | Session-based with merge for platform |
| **Error Handling** | Try-catch with error logging to trace |
| **Deployment** | Single file (`app.py`) on port 5000 |

