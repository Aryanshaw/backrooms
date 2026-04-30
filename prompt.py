BACKROOMS_MARKER_START = "<!-- backrooms-start -->"
BACKROOMS_MARKER_END = "<!-- backrooms-end -->"

BACKROOMS_SECTION = """<!-- backrooms-start -->
## Backrooms — Shared Memory Layer

Backrooms is an MCP server that gives you persistent, cross-tool memory.
Every AI tool connected to this server shares the same room — so when you
switch from Cursor to Claude Code to OpenCode, nothing is lost.

MCP server: http://127.0.0.1:8000/mcp/

### Session start (follow strictly, in this order)

1. If `.backroom.json` exists in cwd — call `join_room` immediately, no exceptions.
   `join_room` returns the last 3 summaries — read them before doing anything else.
2. If no `.backroom.json` exists — call `list_rooms` to show the user their rooms,
   then call `init_room(name)` for a new project or `join_room(room_id)` for an existing one.
3. Call `get_current_room` to confirm active room and members.

### During session

- When context is getting long, at end of session, or when switching tools —
  call `submit_summary(content)` with a structured summary of the session.
- If you need more history than join_room returned, call `pull_summaries(limit, offset)`.

### Session end

- ALWAYS call `submit_summary(content)` before ending a session.
- Follow the summary format strictly — a future agent must resume from this alone.

### Available tools

**Room Management**
- `init_room(name)` — initialize a new room, writes `.backroom.json` to cwd
- `join_room(room_id?)` — join room from `.backroom.json` (no args) or by explicit room_id; returns last 3 summaries
- `exit_room()` — leave current room, deletes `.backroom.json`
- `get_current_room(room_id?)` — get active room details and members
- `list_rooms()` — list all your rooms with last active timestamps
- `setup_agents_md()` — write AGENTS.md and CLAUDE.md to cwd with Backrooms rules

**Summaries**
- `submit_summary(content)` — persist a session summary to the room
- `pull_summaries(limit=10, offset=0)` — fetch past summaries with pagination

<!-- backrooms-end -->"""
