# Documentation Index

## Quick Navigation

This project now includes comprehensive documentation. Use this index to find what you need.

### New Documentation Files Created

1. **EXECUTIVE_SUMMARY.md** - High-level overview
   - Project at a glance
   - Architecture diagram
   - Key components explained
   - Best for: Getting started, understanding big picture

2. **ARCHITECTURE.md** - Detailed technical architecture
   - Implementation structure
   - Session tracking mechanisms
   - Complete API endpoint reference
   - Tool calling implementation details
   - Message history management
   - Configuration management
   - File structure and locations
   - Flow diagrams
   - Design patterns
   - Best for: Deep understanding, modification planning

3. **QUICK_REFERENCE.md** - Developer quick reference
   - File locations and line numbers
   - Global state variables
   - Function signatures
   - Data structure examples
   - Request/response examples
   - Common tasks (add tool, change config, debug)
   - Best for: Quick lookups, troubleshooting

### Existing Documentation

- **README.md** - User-facing quick start guide
- **PLATFORM_INTEGRATION.md** - Integration guide for A/B testing platforms

---

## Reading Recommendations

### For Different Audiences

**First Time User:**
1. Start with README.md (5 min)
2. Read EXECUTIVE_SUMMARY.md sections 1-3 (10 min)
3. Try running the app and test scripts (15 min)

**Developer Modifying Code:**
1. Read QUICK_REFERENCE.md (10 min)
2. Read ARCHITECTURE.md section 4 (Tool Calling) (10 min)
3. Read specific section in ARCHITECTURE.md for area you're modifying (varies)

**A/B Testing Platform Integration:**
1. Read PLATFORM_INTEGRATION.md (10 min)
2. Read EXECUTIVE_SUMMARY.md section 3 (API Endpoints) (5 min)
3. Implement using /chat endpoint examples (varies)

**System Administrator:**
1. Read EXECUTIVE_SUMMARY.md section 7 (Storage & State) (5 min)
2. Read ARCHITECTURE.md section 12 (Testing & Debugging) (5 min)
3. Read section 10 (File Structure) for deployment considerations (5 min)

**DevOps/Production Deployment:**
1. Read EXECUTIVE_SUMMARY.md section 13 (Limitations & Improvements) (5 min)
2. Note: Current system is not production-ready (in-memory storage)
3. See suggestions for database persistence and scaling

---

## Quick Lookups

### I need to...

- **Add a new tool**
  - QUICK_REFERENCE.md → "Common Tasks" → "Add New Tool"
  - ARCHITECTURE.md → Section 4 → "Tool Definition Process"

- **Change default configuration**
  - QUICK_REFERENCE.md → "Configuration Defaults"
  - ARCHITECTURE.md → Section 6 → "Configuration Management"

- **Understand how sessions work**
  - EXECUTIVE_SUMMARY.md → Section 2
  - ARCHITECTURE.md → Section 2 + Section 5

- **See all API endpoints**
  - QUICK_REFERENCE.md → "Endpoint Summary"
  - EXECUTIVE_SUMMARY.md → Section 3
  - ARCHITECTURE.md → Section 3

- **Understand tool calling**
  - ARCHITECTURE.md → Section 4 (detailed)
  - EXECUTIVE_SUMMARY.md → Section 4 (high-level)

- **Debug an issue**
  - QUICK_REFERENCE.md → "Debugging" section
  - ARCHITECTURE.md → Section 12
  - Use `/traces` endpoint to see what happened

- **Integrate with platform**
  - PLATFORM_INTEGRATION.md (primary)
  - EXECUTIVE_SUMMARY.md → Section 3 → "Endpoint 2: /chat"

- **Find code location**
  - QUICK_REFERENCE.md → "File Locations"
  - Search by line numbers to find in app.py

---

## Key Concepts

### Sessions (Session IDs)
- Random ID: `sess_abc123`
- One per conversation
- Stores message history
- See: EXECUTIVE_SUMMARY.md Section 2, ARCHITECTURE.md Section 2, 5

### Traces (Trace IDs)
- Unique ID: `trace_xyz`
- One per API request
- Logs everything (messages, tool calls, timestamps, tokens)
- Used for A/B testing analysis
- See: ARCHITECTURE.md Section 4, 8

### Tool Calling
- Agent automatically executes tools when needed
- Max 10 iterations per request (safety limit)
- All iterations visible in trace
- See: ARCHITECTURE.md Section 4, EXECUTIVE_SUMMARY.md Section 4

### Two Endpoints
- `/v1/chat/completions` - OpenAI compatible (for frontend)
- `/chat` - Platform compatible (for A/B testing systems)
- Same backend, different request/response formats
- See: EXECUTIVE_SUMMARY.md Section 3, ARCHITECTURE.md Section 3

### Configuration
- Can be set per request: temperature, top_p, max_tokens, system_prompt
- Overrides defaults
- Included in trace for analysis
- See: ARCHITECTURE.md Section 6

---

## Architecture at a Glance

```
Flask Server (app.py - 814 lines)
    ├── Tools: calculator, web_search
    ├── Sessions: UUID-based, in-memory
    ├── Traces: Comprehensive logging
    ├── Two Endpoints: /v1/chat/completions, /chat
    ├── Tool Loop: _run_completion() - max 10 iterations
    ├── Frontend: Embedded vanilla JS UI
    └── Storage: Python dicts (no database)
```

---

## Common Errors & Solutions

| Error | Likely Cause | Solution |
|-------|--------------|----------|
| `OPENAI_API_KEY not set` | Missing env var | Set `export OPENAI_API_KEY="key"` |
| `Connection refused` | Server not running | Run `python app.py` |
| `Tool not found` | Tool not registered | Check `execute_tool()` has the tool case |
| `Max iterations reached` | Infinite tool loop | Check tool results aren't triggering infinite loops |
| `Trace not found` | Old trace ID | Use `/traces` to see available traces |
| Session not found | Session expired | Sessions only exist for server uptime |

---

## File Organization

```
app.py (814 lines total)
├── Imports & Setup (lines 1-51)
├── Tool Functions (lines 53-102)
├── Session Management (lines 104-142)
├── Chat Endpoints (lines 144-464)
│   ├── /chat endpoint (lines 144-224)
│   ├── _run_completion() core (lines 226-399)
│   └── /v1/chat/completions (lines 402-464)
├── Trace Endpoints (lines 466-477)
├── Frontend HTML/CSS/JS (lines 479-808)
└── Main (lines 810-813)
```

---

## Testing the System

### Quick Test
```bash
# Terminal 1: Start server
python app.py

# Terminal 2: Run test script
./test_chat_endpoint.sh
```

### Detailed Testing
- Use test scripts in repository: `test_agent.sh`, `test_chat_endpoint.sh`
- View traces at: http://localhost:5000/traces
- View session at: http://localhost:5000/session/{session_id}

---

## Performance & Optimization

All metrics captured in trace data:
- `duration_ms`: How long each tool took
- `total_tokens`: Token usage per request
- `timestamp`: When things happened

Use traces to:
- Identify slow tools
- Optimize prompts (token usage)
- Track feature adoption
- A/B test variants

See: ARCHITECTURE.md Section 8

---

## Next Steps

1. Read README.md to understand the basic setup
2. Run the application: `python app.py`
3. Access UI at http://localhost:5000
4. Run test scripts: `./test_chat_endpoint.sh`
5. Read ARCHITECTURE.md for deep understanding
6. Modify code based on your needs

---

## Support & Questions

- Check QUICK_REFERENCE.md for common tasks
- Check ARCHITECTURE.md for detailed explanations
- Check test scripts for usage examples
- Use `/traces` endpoint to debug issues

---

Last Updated: October 18, 2025
Documentation Files Created:
- EXECUTIVE_SUMMARY.md (12 KB)
- ARCHITECTURE.md (19 KB)
- QUICK_REFERENCE.md (6 KB)
- DOCUMENTATION_INDEX.md (this file)
