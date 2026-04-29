# MemRoom — Room Management Module PRD

---

## Problem Statement

AI coding agents (Claude Code, Cursor, Codex, Antigravity) operate in isolated context windows. When a developer switches tools, opens a new terminal, or moves between directories, all prior session context is lost. There is no persistent, shared memory layer that follows the developer's intent across tools and directories.

Existing solutions either extract atomic facts (OpenMemory), operate only on local transcripts (agent-session-resume), or tie memory to a specific directory or git remote — all of which break the moment the developer's workflow crosses a tool or directory boundary.

The developer needs a room — a named, persistent shared space — that any agent can join, push context to, and pull context from, regardless of which tool they're using or which directory they're in.

---

## Solution

MemRoom introduces the concept of a **room** — a named, persistent shared context space tied to a developer's intent, not their filesystem. A room is initialized in a directory via a `.backroom.json` file (analogous to `.git`) and accessible to any agent that reads that file. Agents push every message turn to the room and pull room context on session start, giving every tool a shared, up-to-date view of what's being worked on.

Room management covers the full lifecycle: creating rooms, joining them, switching between them, and exiting them — with explicit user control at every step.

---

## User Stories

1. As a developer, I want to initialize a MemRoom in my project directory so that all agents working in that directory automatically share the same context.
2. As a developer, I want to name my room after my project so that I can identify it easily across tools.
3. As a developer, I want Claude Code to auto-join my room when I start a session in a directory that has a `.backroom.json` so that I don't have to manually join every time.
4. As a developer, I want Cursor to auto-join my room when I open a project directory that has a `.backroom.json` so that context is available immediately.
5. As a developer, I want to see a confirmation message when an agent joins a room so that I know context sync is active.
6. As a developer, I want the agent to tell me what room it joined and show me a brief summary of recent activity so that I'm immediately oriented.
7. As a developer, I want to list all my existing rooms with their last active timestamps so that I can track which projects have active context.
8. As a developer, I want to join an existing room from a directory that has no `.backroom.json` so that I can access context from another project temporarily.
9. As a developer, I want to choose between linking a directory permanently to a room or joining temporarily for a session so that I have control over what gets persisted.
10. As a developer, I want a linked join to create a `.backroom.json` in the current directory so that future sessions auto-join without manual intervention.
11. As a developer, I want a floating join to not create any local files so that my directory stays clean for temporary access.
12. As a developer, I want to switch my current directory's room by running a switch command so that I can redirect context to a different room without leaving my editor.
13. As a developer, I want `.backroom.json` to be updated automatically when I switch rooms so that the change persists across sessions.
14. As a developer, I want to exit a room so that the current directory is unlinked and no further messages are pushed.
15. As a developer, I want `.backroom.json` to be deleted when I exit a room so that the directory returns to an uninitialized state cleanly.
16. As a developer, I want the agent to ask for explicit confirmation before overwriting an existing `.backroom.json` so that I never accidentally switch rooms.
17. As a developer, I want to open the same project on a different machine and have the agent auto-join the correct room because `.backroom.json` is committed to the repo so that my context follows me across machines.
18. As a developer, I want multiple directories to be able to link to the same room so that a monorepo or multi-service project shares one unified context.
19. As a developer, I want the agent to detect a missing `.backroom.json` and present clear options (init, join, list) so that I'm never stuck without guidance.
20. As a developer, I want agents in Cursor and Antigravity to follow room management rules from `AGENTS.md` automatically so that I don't have to instruct them manually every session.
21. As a developer, I want Claude Code to follow room management rules from `CLAUDE.md` so that plugin-based tools are also covered.
22. As a developer, I want the room management tools to work identically across Claude Code, Cursor, Codex, and Antigravity so that switching tools doesn't change my workflow.
23. As a developer, I want room initialization to be done via a plugin command (`/memroom init`) in Claude Code so that it feels native to the tool.
24. As a developer, I want the MCP server to handle room operations for Cursor and other MCP-compatible tools so that no plugin system is required on those tools.
25. As a developer, I want my room membership to be authenticated via GitHub OAuth so that my rooms are private and tied to my identity.

---

## Implementation Decisions

### Modules

**1. `.backroom.json` — Local Room Anchor**
A JSON file written to the project directory root on init or linked join. Acts as the single source of truth for which room a directory belongs to. Read by the MCP server on every tool call to determine active room. Never holds secrets — only room name and owner identifier.

Schema:
```
room: string        — room name
owner: string       — github user id
created_at: string  — ISO timestamp
```

**2. MCP Server — Room Management Tools**
Built with FastMCP (Python). Exposes the following tools:

- `init_room(name)` — creates room on server, writes `.backroom.json` to current working directory, returns confirmation
- `join_room(name?, mode?)` — reads `.backroom.json` if present, or takes explicit name; mode is "linked" (writes file) or "floating" (session only); registers agent session as active member; returns room summary
- `list_rooms()` — returns all rooms owned by authenticated user with last_active and active tool list
- `get_current_room()` — reads `.backroom.json`, confirms server connection, returns room name and summary
- `switch_room(name)` — overwrites `.backroom.json` with new room, deregisters from old room, confirms switch
- `exit_room()` — deletes `.backroom.json`, deregisters session, confirms exit

**3. PostgreSQL — Room Persistence**
Two tables: `rooms` and `room_members`. Room state, ownership, and membership persisted server-side. `.backroom.json` is the local pointer; the server holds the canonical state.

Room schema:
```
id, name, owner_id, created_at, last_active
```

Room members schema:
```
room_id, user_id, tool (cursor/claude-code/codex/claude-browser), joined_at
```

**4. AGENTS.md — Instruction Layer**
Shipped with MemRoom installer. Written to project root alongside `.backroom.json`. Instructs all compatible agents to call `get_current_room` at session start, `join_room` if no room is active, and confirms room before any push. Claude Code reads from `CLAUDE.md`; shared rules live in `AGENTS.md`.

**5. Plugin Interface — Claude Code / Codex**
Slash commands wrapping MCP tool calls:
```
/memroom init <name>
/memroom join [name]
/memroom list
/memroom switch <name>
/memroom exit
```

### Architectural Decisions

- `.backroom.json` is the local anchor — identical mental model to `.git`
- Session state (floating joins) lives in MCP server process memory only; not persisted
- GitHub OAuth is the auth layer; user_id derived from GitHub account
- MCP server reads `.backroom.json` from the `cwd` passed by the client at connection time
- Multiple directories can link to the same room — no 1:1 directory-to-room constraint
- Antigravity excluded from MCP tools for v1 (no MCP support yet); AGENTS.md rules still apply for awareness
- No auto-join based on git remote — all room membership is explicit user intent

### Missing `.backroom.json` Flow

When agent detects no `.backroom.json`:
```
MemRoom not initialized here.
1. Create a new room → /memroom init <name>
2. Join an existing room (linked) → /memroom join <name>
3. Join temporarily (floating) → /memroom join <name> --float
4. List existing rooms → /memroom list
```

### Switch / Exit Confirmation

Switch: agent confirms before overwriting existing `.backroom.json`
Exit: agent confirms before deleting `.backroom.json`
Both: never silent, always acknowledged in chat

---

## Testing Decisions

Good tests verify external behavior — what the tool returns and what side effects it produces (file written, file deleted, server state changed) — not internal implementation details like function signatures.

Modules to test:

- `init_room` — assert `.backroom.json` created with correct schema, assert room created on server, assert duplicate init prompts confirmation
- `join_room` (linked) — assert `.backroom.json` written, assert member registered on server, assert room summary returned
- `join_room` (floating) — assert no file written, assert session state set, assert member registered on server
- `list_rooms` — assert correct rooms returned for authenticated user, assert last_active is accurate
- `get_current_room` — assert reads `.backroom.json` correctly, assert returns summary, assert graceful error when file missing
- `switch_room` — assert `.backroom.json` updated, assert old membership deregistered, assert confirmation returned
- `exit_room` — assert `.backroom.json` deleted, assert membership deregistered, assert confirmation returned
- Missing file flow — assert correct options presented when no `.backroom.json` found

---

## Out of Scope

- Auto-join based on git remote URL
- Room sharing between multiple users (v1 is single-user only)
- Room deletion (exit unlinks directory; room persists on server)
- `.backroom.json` conflict resolution for concurrent writes (deferred to scale)
- Antigravity MCP integration (no MCP support in Antigravity as of April 2026)
- Mobile / Claude.ai browser room join (browser sessions pushed via Chrome extension, not room join flow)

---

## Further Notes

The `.backroom.json` file should be added to `.gitignore` by default for floating joins, but committed for linked joins — this allows teams to share room membership across machines. The installer should ask the user which behavior they prefer and handle `.gitignore` automatically.

The git analogy is the right mental model for communicating this to users: `.backroom.json` is to MemRoom what `.git` is to git. This framing should be used in all documentation and onboarding.
