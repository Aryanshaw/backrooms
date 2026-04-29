<!-- backrooms-start -->
## Backrooms — Shared Memory Layer

Backrooms is an MCP server that gives you persistent, cross-session memory.
Every AI tool connected to this server shares the same room context — so when
you switch from Cursor to Claude Code to OpenCode, nothing is lost.

MCP server: http://127.0.0.1:8000/mcp/

### Rules (follow strictly)

- If `.backroom.json` exists in cwd, ALWAYS call `join_room` at the start of every session before doing anything else
- If no `.backroom.json` exists and this is a new project, call `init_room` first
- Call `get_current_room` to confirm active room and members before starting work
- When you make an important decision, discover something non-obvious, or finish a meaningful unit of work — call `push_context` to save it to the room

### Available tools

- `init_room(name)` — initialize a new room for this directory
- `join_room(room_id)` — join or switch to a room
- `get_current_room()` — check active room and members
- `list_rooms()` — see all your rooms
- `exit_room()` — leave the current room
- `push_context(content, tags?)` — save context to the room
- `pull_context()` — load recent context from the room
<!-- backrooms-end -->