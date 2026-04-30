BACKROOMS_MARKER_START = "<!-- backrooms-start -->"
BACKROOMS_MARKER_END = "<!-- backrooms-end -->"

BACKROOMS_SECTION = """<!-- backrooms-start -->
## Backrooms — Shared Memory Layer

Backrooms is an MCP server that gives you persistent, cross-tool memory.
Every AI tool connected to this server shares the same room — so when you
switch from Cursor to Claude Code to OpenCode, nothing is lost.

MCP server: http://127.0.0.1:8000/mcp/

### Session start (follow strictly, in this order)

1. If `.backroom.json` exists in cwd — call `join_room` immediately, no exceptions
2. If no `.backroom.json` exists — call `list_rooms` to show the user their rooms, then call `init_room(name)` for a new project or `join_room(room_id)` for an existing one. Note: Join room will let you join the room and 
also will return a summary of the previous conversation going on in the room.
3. Call `get_room_info` to confirm active room, members, and latest summary
4. Call `pull_messages(limit=20)` to load recent conversation history

### During session

- After EVERY assistant response, call `push_message(user_content, assistant_content)` with both turns as a pair
- If `push_message` returns `status: summary_needed` — call `pull_messages(after_id=last_summarized_message_id)` to fetch unsummarized messages, generate a summary of them, then call `submit_summary` (coming soon)
- Never push only one side of the pair — always both user and assistant content together

### Available tools

**Room Management**
- `init_room(name)` — initialize a new room, writes `.backroom.json` to cwd
- `join_room(room_id?)` — join room from `.backroom.json` (no args) or by explicit room_id
- `exit_room()` — leave current room, deletes `.backroom.json`
- `get_room_info(room_id?)` — get active room details, members, and latest summary
- `list_rooms()` — list all your rooms with last active timestamps
- `setup_agents_md()` — write AGENTS.md to cwd with Backrooms rules

**Messaging**
- `push_message(user_content, assistant_content)` — push both turns as a pair to the room
- `pull_messages(limit=20, offset=0, after_id=None)` — fetch messages with pagination; use after_id for summary generation
- `submit_summary(content, from_message_id, to_message_id)` — generate and submit a summary of messages between from_message_id and to_message_id

<!-- backrooms-end -->"""