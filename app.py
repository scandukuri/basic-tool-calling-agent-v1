from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from openai import OpenAI
import json
import os
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import math
import uuid

app = Flask(__name__)
CORS(app)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Platform URL for integration
PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://localhost:8000")

# Tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information using DuckDuckGo",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "num_results": {"type": "integer", "description": "Number of results (default 5)", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate mathematical expressions safely",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression to evaluate"}
                },
                "required": ["expression"]
            }
        }
    }
]

def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo HTML scraping."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code != 200:
            return f"Search failed with status {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        for result in soup.find_all('div', class_='result')[:num_results]:
            title_elem = result.find('a', class_='result__a')
            snippet_elem = result.find('a', class_='result__snippet')

            if title_elem:
                title = title_elem.get_text(strip=True)
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                results.append(f"{title}: {snippet}")

        return "\n\n".join(results) if results else "No results found"
    except Exception as e:
        return f"Search error: {str(e)}"

def calculator(expression: str) -> str:
    """Evaluate mathematical expressions safely."""
    try:
        safe_dict = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "pi": math.pi, "e": math.e,
            "log": math.log, "log10": math.log10, "exp": math.exp,
            "floor": math.floor, "ceil": math.ceil,
        }
        result = eval(expression, {"__builtins__": {}}, safe_dict)
        return str(result)
    except Exception as e:
        return f"Calculation error: {str(e)}"

def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool and return results."""
    if tool_name == "web_search":
        return web_search(arguments.get("query", ""), arguments.get("num_results", 5))
    elif tool_name == "calculator":
        return calculator(arguments.get("expression", ""))
    else:
        return f"Error: Unknown tool '{tool_name}'"

def get_platform_session(session_id: str):
    """
    GET request to Platform to fetch session config and message history.

    Returns:
        {
            "config": {
                "system_prompt": "...",
                "temperature": 0.7,
                "top_p": 1.0,
                "max_tokens": 2048
            },
            "messages": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    """
    try:
        response = requests.get(
            f"{PLATFORM_URL}/api/sessions/{session_id}?experiment_id={os.environ.get('EXPERIMENT_ID').strip()}",
            timeout=30
        )
        if response.status_code == 404:
            print(f"  ↳ Status 404 (new session) - using defaults")
            # New session - return defaults
            return {
                "config": {
                    "system_prompt": "You are a helpful assistant with access to web search and calculator tools.",
                    "temperature": 0.7,
                    "top_p": 1.0,
                    "max_tokens": 2048
                },
                "messages": []
            }
        response.raise_for_status()
        print(f"  ↳ Status {response.status_code} - session found")
        return response.json()
    except requests.RequestException as e:
        print(f"  ↳ ⚠️  Platform unavailable ({type(e).__name__}) - using defaults")
        # Fallback to defaults if Platform is unavailable
        return {
            "config": {
                "system_prompt": "You are a helpful assistant with access to web search and calculator tools.",
                "temperature": 0.7,
                "top_p": 1.0,
                "max_tokens": 2048
            },
            "messages": []
        }

def post_platform_session(session_id: str, data: dict):
    """
    POST request to Platform to save session results.

    Sends:
        {
            "session_id": "sess_xxx",
            "messages": [...],  # Full conversation including new turn
            "trace": {...},     # Execution trace
            "timestamp": "..."
        }
    """
    try:
        # PROOF: Print EXACT data object being sent to Platform
        print(f"  ↳ EXACT POST DATA:")
        print(json.dumps(data, indent=2))
        print()

        response = requests.post(
            f"{PLATFORM_URL}/api/sessions/{session_id}?experiment_id={os.environ.get('EXPERIMENT_ID').strip()}",
            json=data,
            timeout=30
        )
        response.raise_for_status()
        print(f"  ↳ Status {response.status_code} - saved to Platform\n")
    except requests.RequestException as e:
        print(f"  ↳ ⚠️  Platform unavailable ({type(e).__name__}) - data not saved\n")

def _run_completion(messages, config):
    """
    Internal function to run completion with tool calling.

    Args:
        messages: List of message dicts (must NOT include system message)
        config: Dict with temperature, top_p, max_tokens, system_prompt

    Returns:
        Tuple of (assistant_content, trace, full_message_history)
    """
    # Configuration
    system_prompt = config.get("system_prompt", "You are a helpful assistant with access to web search and calculator tools.")
    max_tokens = config.get("max_tokens", 2048)
    temperature = config.get("temperature", 0.7)
    top_p = config.get("top_p", 1.0)

    # Prepend system message
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    # Trace data
    trace_id = f"trace_{uuid.uuid4().hex[:8]}"
    trace = {
        "trace_id": trace_id,
        "started_at": datetime.utcnow().isoformat(),
        "turns": [],
        "tool_calls": [],
        "config": {
            "model": "gpt-4o",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p
        }
    }

    # Record user message
    user_message = next((m for m in reversed(messages) if m["role"] == "user"), None)
    if user_message:
        trace["turns"].append({
            "role": "user",
            "content": user_message["content"],
            "timestamp": datetime.utcnow().isoformat()
        })

    # Tool execution loop (max 10 iterations)
    for _ in range(10):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=full_messages,
                tools=TOOLS,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p
            )
        except Exception as e:
            trace["completed_at"] = datetime.utcnow().isoformat()
            trace["error"] = f"OpenAI API error: {str(e)}"
            raise Exception(f"OpenAI API error: {str(e)}")

        assistant_message = response.choices[0].message

        # No tool calls - we're done
        if not assistant_message.tool_calls:
            # Append final assistant response to messages
            full_messages.append({
                "role": "assistant",
                "content": assistant_message.content
            })

            # Record final assistant response in trace
            trace["turns"].append({
                "role": "assistant",
                "content": assistant_message.content,
                "tool_calls": None,
                "timestamp": datetime.utcnow().isoformat()
            })
            trace["completed_at"] = datetime.utcnow().isoformat()
            trace["total_tokens"] = response.usage.total_tokens

            # Return full conversation history (excluding system message)
            return (assistant_message.content, trace, full_messages[1:])

        # Add assistant message with tool calls
        assistant_tool_calls = [
            {
                "id": tc.id,
                "type": tc.type,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in assistant_message.tool_calls
        ]

        full_messages.append({
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": assistant_tool_calls
        })

        # Record assistant message with tool calls in trace
        trace["turns"].append({
            "role": "assistant",
            "content": assistant_message.content or "",
            "tool_calls": [
                {
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                }
                for tc in assistant_tool_calls
            ],
            "timestamp": datetime.utcnow().isoformat()
        })

        # Execute each tool call
        for tool_call in assistant_message.tool_calls:
            tool_start = datetime.utcnow()
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            # Execute tool
            print(f"🔧 Calling tool: {tool_name}({tool_args})")
            tool_result = execute_tool(tool_name, tool_args)
            tool_end = datetime.utcnow()
            tool_duration_ms = (tool_end - tool_start).total_seconds() * 1000
            print(f"✓ Tool result ({tool_duration_ms:.0f}ms): {tool_result[:100]}{'...' if len(tool_result) > 100 else ''}")

            # Log tool call
            trace["tool_calls"].append({
                "name": tool_name,
                "arguments": tool_args,
                "result": tool_result[:200] + "..." if len(tool_result) > 200 else tool_result,
                "full_result_length": len(tool_result),
                "duration_ms": tool_duration_ms,
                "timestamp": tool_start.isoformat()
            })

            # Add tool result to messages
            full_messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

            # Record tool result in trace turns
            trace["turns"].append({
                "role": "tool",
                "name": tool_name,
                "content": tool_result,
                "tool_call_id": tool_call.id,
                "timestamp": tool_end.isoformat()
            })

    # Max iterations reached
    trace["completed_at"] = datetime.utcnow().isoformat()
    trace["error"] = "Max iterations (10) reached"
    raise Exception("Max tool iterations reached")


@app.route("/chat", methods=["POST"])
def chat():
    """
    Simplified chat endpoint that integrates with Platform.

    Flow:
    1. Receive message from frontend with session_id
    2. GET config + message history from Platform
    3. Run agent with that config
    4. POST results back to Platform
    5. Return response to frontend (for streaming)

    Request:
        {
            "session_id": "sess_xxx",
            "message": "What is 2+2?"
        }

    Response:
        {
            "response": "The result is 4.",
            "session_id": "sess_xxx"
        }
    """
    data = request.json
    session_id = data.get("session_id")
    user_message = data.get("message", "")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    try:
        # Step 1: GET config and message history from Platform
        print(f"\n📥 GET {PLATFORM_URL}/api/sessions/{session_id}")
        platform_data = get_platform_session(session_id)
        config = platform_data["config"]
        message_history = platform_data["messages"]
        print(f"✓ Retrieved {len(message_history)} messages from Platform")

        # Step 1.5: Fix tool_calls format (Platform may not include proper structure)
        for i, msg in enumerate(message_history):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                print(f"  ⚠️  Fixing tool_calls in message {i}:")
                print(f"      Before: {json.dumps(msg['tool_calls'], indent=6)}")
                for tc in msg["tool_calls"]:
                    # Add missing 'type' field
                    if "type" not in tc:
                        tc["type"] = "function"

                    # Check if 'function' field exists and has correct structure
                    if "function" not in tc:
                        # Platform might have stored it flat - reconstruct
                        if "name" in tc and "arguments" in tc:
                            tc["function"] = {
                                "name": tc.pop("name"),
                                "arguments": tc.pop("arguments")
                            }
                print(f"      After: {json.dumps(msg['tool_calls'], indent=6)}")

        # Step 2: Append new user message
        message_history.append({"role": "user", "content": user_message})

        # Step 3: Run agent scaffolding
        print(f"🤖 Running agent with {len(message_history)} messages")
        assistant_content, trace, full_conversation = _run_completion(message_history, config)

        # Step 4: POST back to Platform (with FULL conversation including tool calls)
        print(f"📤 POST {PLATFORM_URL}/api/sessions/{session_id}")
        post_platform_session(session_id, {
            "session_id": session_id,
            "messages": full_conversation,  # ← Now includes tool calls!
            "trace": trace,
            "timestamp": datetime.utcnow().isoformat()
        })

        # Step 6: Return response to frontend
        return jsonify({
            "response": assistant_content,
            "session_id": session_id
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({
            "error": str(e),
            "session_id": session_id
        }), 500


@app.route("/end-session", methods=["POST"])
def end_session():
    """
    End session endpoint - notifies Platform that conversation is complete.

    Request:
        {
            "session_id": "sess_xxx"
        }

    Response:
        {
            "session_id": "sess_xxx",
            "status": "ended"
        }
    """
    data = request.json
    session_id = data.get("session_id")

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    try:
        # Notify Platform that session has ended
        print(f"\n🔚 END SESSION: {session_id}")
        response = requests.post(
            f"{PLATFORM_URL}/api/sessions/{session_id}/end?experiment_id={os.environ.get('EXPERIMENT_ID').strip()}",
            json={"session_id": session_id, "ended_at": datetime.utcnow().isoformat()},
            timeout=30
        )
        response.raise_for_status()
        print(f"  ↳ Status {response.status_code} - Platform notified\n")

        return jsonify({
            "session_id": session_id,
            "status": "ended"
        })

    except requests.RequestException as e:
        print(f"  ↳ ⚠️  Platform unavailable ({type(e).__name__}) - session end not recorded\n")
        # Return success anyway - frontend should still end session
        return jsonify({
            "session_id": session_id,
            "status": "ended"
        })


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html>
<head>
    <title>Tool Agent Chat</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            color: #333;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .header {
            background: white;
            padding: 16px 24px;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 20px; font-weight: 600; color: #1a73e8; }
        .session-info { font-size: 12px; color: #666; }
        .session-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #1a73e8;
            color: white;
        }
        .btn-primary:hover { background: #1557b0; }
        .btn-danger {
            background: #dc3545;
            color: white;
        }
        .btn-danger:hover { background: #c82333; }
        .btn:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .main-container {
            flex: 1;
            display: flex;
            max-width: 1400px;
            width: 100%;
            margin: 0 auto;
            overflow: hidden;
        }
        .chat-container {
            flex: 1;
            display: flex;
            flex-direction: column;
            background: white;
        }
        .messages {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        .message {
            display: flex;
            gap: 12px;
            max-width: 80%;
        }
        .message-user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }
        .message-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 14px;
            flex-shrink: 0;
        }
        .avatar-user {
            background: #1a73e8;
            color: white;
        }
        .avatar-assistant {
            background: #34a853;
            color: white;
        }
        .message-content {
            background: #f8f9fa;
            padding: 12px 16px;
            border-radius: 12px;
            line-height: 1.5;
            font-size: 14px;
        }
        .message-user .message-content {
            background: #1a73e8;
            color: white;
        }
        .message-timestamp {
            font-size: 11px;
            color: #999;
            margin-top: 4px;
        }
        .input-area {
            padding: 20px;
            border-top: 1px solid #e0e0e0;
            background: white;
        }
        .input-container {
            display: flex;
            gap: 12px;
            align-items: flex-end;
        }
        #messageInput {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #d0d0d0;
            border-radius: 24px;
            font-size: 14px;
            font-family: inherit;
            resize: none;
            max-height: 120px;
            outline: none;
        }
        #messageInput:focus {
            border-color: #1a73e8;
        }
        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #999;
            text-align: center;
            padding: 40px;
        }
        .empty-state-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>⚡ Chat</h1>
            <div class="session-info" id="sessionInfo"></div>
        </div>
        <div class="session-controls">
            <button class="btn btn-primary" id="startBtn" onclick="startSession()">New Chat</button>
            <button class="btn btn-danger" id="endBtn" onclick="endSession()" style="display:none;">End Chat</button>
        </div>
    </div>

    <div class="main-container">
        <div class="chat-container">
            <div class="messages" id="messages">
                <div class="empty-state">
                    <div class="empty-state-icon">💬</div>
                    <h3>Welcome to Chat</h3>
                    <p>Click "New Chat" to start a conversation</p>
                </div>
            </div>
            <div class="input-area" id="inputArea" style="display:none;">
                <div class="input-container">
                    <textarea
                        id="messageInput"
                        placeholder="Type your message..."
                        rows="1"
                        onkeydown="handleKeyDown(event)"
                    ></textarea>
                    <button class="btn btn-primary" onclick="sendMessage()" id="sendBtn">Send</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentSessionId = null;
        let sessionMessages = [];

        function generateSessionId() {
            return 'sess_' + Math.random().toString(36).substr(2, 9);
        }

        function startSession() {
            // Generate session ID locally
            currentSessionId = generateSessionId();
            sessionMessages = [];

            // Update UI
            document.getElementById('startBtn').style.display = 'none';
            document.getElementById('endBtn').style.display = 'inline-block';
            document.getElementById('inputArea').style.display = 'block';
            document.getElementById('sessionInfo').textContent = `Session: ${currentSessionId}`;

            // Clear messages
            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML = '';

            document.getElementById('messageInput').focus();
        }

        async function endSession() {
            if (!currentSessionId) return;

            const sessionToEnd = currentSessionId;

            // Notify backend (which notifies Platform)
            try {
                await fetch('/end-session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({session_id: sessionToEnd})
                });
            } catch(e) {
                console.error('Failed to notify end session:', e);
            }

            // Clear session
            currentSessionId = null;
            sessionMessages = [];

            // Update UI
            document.getElementById('startBtn').style.display = 'inline-block';
            document.getElementById('endBtn').style.display = 'none';
            document.getElementById('inputArea').style.display = 'none';
            document.getElementById('sessionInfo').textContent = '';

            const messagesDiv = document.getElementById('messages');
            messagesDiv.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">✓</div>
                    <h3>Chat ended</h3>
                    <p>Click "New Chat" to start a new conversation</p>
                </div>
            `;
        }

        function addMessage(role, content) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message message-${role}`;

            const avatar = document.createElement('div');
            avatar.className = `message-avatar avatar-${role}`;
            avatar.textContent = role === 'user' ? 'U' : 'A';

            const contentDiv = document.createElement('div');
            const contentText = document.createElement('div');
            contentText.className = 'message-content';
            contentText.textContent = content;

            const timestamp = document.createElement('div');
            timestamp.className = 'message-timestamp';
            timestamp.textContent = new Date().toLocaleTimeString();

            contentDiv.appendChild(contentText);
            contentDiv.appendChild(timestamp);

            messageDiv.appendChild(avatar);
            messageDiv.appendChild(contentDiv);

            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        async function sendMessage() {
            if (!currentSessionId) return;

            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            if (!message) return;

            const sendBtn = document.getElementById('sendBtn');
            sendBtn.disabled = true;
            input.disabled = true;

            // Add user message to UI
            addMessage('user', message);
            input.value = '';

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        session_id: currentSessionId,
                        message: message
                    })
                });

                const data = await res.json();

                if (data.error) {
                    addMessage('assistant', 'Error: ' + data.error);
                } else {
                    addMessage('assistant', data.response);
                }
            } catch(e) {
                addMessage('assistant', 'Error: ' + e.message);
            } finally {
                sendBtn.disabled = false;
                input.disabled = false;
                input.focus();
            }
        }

        function handleKeyDown(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        }
    </script>
</body>
</html>"""

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set in environment")

    print(f"🔗 Platform URL: {PLATFORM_URL}")
    app.run(debug=True, port=5000)
