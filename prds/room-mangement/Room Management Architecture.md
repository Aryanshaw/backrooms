# MemRoom — Room Management Architecture

---

## High Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DEVELOPER MACHINE                        │
│                                                                 │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐   │
│  │  Claude Code │   │    Cursor    │   │  Codex / Others  │   │
│  │  (plugin)    │   │  (MCP client)│   │  (MCP client)    │   │
│  └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘   │
│         │                  │                     │             │
│         └──────────────────┼─────────────────────┘             │
│                            │ MCP tool calls                    │
│                            ▼                                   │
│              ┌─────────────────────────┐                       │
│              │      .backroom.json      │  ← local anchor       │
│              │  { room: "melina",      │    per directory      │
│              │    owner: "github-id" } │                       │
│              └─────────────┬───────────┘                       │
│                            │ read on every tool call           │
│                            ▼                                   │
│              ┌─────────────────────────┐                       │
│              │   AGENTS.md / CLAUDE.md │  ← instruction layer  │
│              │   "always call          │    tells agents when  │
│              │    get_current_room     │    to use MemRoom     │
│              │    at session start"    │                       │
│              └─────────────────────────┘                       │
│                                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTPS / MCP protocol
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                       MEMROOM SERVER                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                FastMCP — Room Tools                     │   │
│  │                                                         │   │
│  │  init_room(name)        → create room + write json      │   │
│  │  join_room(name, mode)  → register member + summary     │   │
│  │  list_rooms()           → all rooms for user            │   │
│  │  get_current_room()     → read json + confirm server    │   │
│  │  switch_room(name)      → overwrite json + rereg        │   │
│  │  exit_room()            → delete json + dereg           │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                   │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │                GitHub OAuth                             │   │
│  │         user_id derived from GitHub account             │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                   │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │                   PostgreSQL                            │   │
│  │                                                         │   │
│  │  rooms          room_members                            │   │
│  │  ─────────      ─────────────────                       │   │
│  │  id             room_id → rooms                         │   │
│  │  name           user_id                                 │   │
│  │  owner_id       tool (cursor/claude-code/codex)         │   │
│  │  created_at     joined_at                               │   │
│  │  last_active                                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Room Lifecycle State Machine

```
  [ Directory ]
       │
       │ /memroom init <name>
       ▼
  [ .backroom.json written ]
       │
       │ agent session starts
       ▼
  [ join_room called ]  ◄────────────────────────────────┐
       │                                                  │
       ├── linked join → .backroom.json written            │
       │                                                  │
       └── floating join → session state only             │
       │                                                  │
       ▼                                                  │
  [ ACTIVE IN ROOM ] ────── switch_room(name) ───────────┘
       │
       │ exit_room()
       ▼
  [ .backroom.json deleted ]
       │
       ▼
  [ Uninitialized — back to start ]
```

---

## Missing `.backroom.json` Decision Flow

```
  Agent session starts
         │
         ▼
  .backroom.json exists?
    │           │
   YES          NO
    │           │
    ▼           ▼
  join_room   Present options:
  (auto)      ┌─────────────────────────────────┐
              │ 1. init new room here            │
              │ 2. join existing (linked)        │
              │ 3. join existing (floating)      │
              │ 4. list rooms                    │
              └─────────────────────────────────┘
                         │
              user picks → agent calls tool
```

---

## Multi-Directory Same Room

```
~/projects/
├── melina-frontend/
│   └── .backroom.json  ──────────┐
├── melina-backend/              ├──► room: "melina-studio" (server)
│   └── .backroom.json  ──────────┤
└── melina-infra/                │
    └── .backroom.json  ──────────┘

All three dirs push/pull from the same room.
Same mental model as multiple git clones → same remote.
```

---

## Tool Surface per Client

```
┌──────────────────┬───────────────────┬──────────────────────────┐
│ Tool             │ Interface         │ How room rules enforced  │
├──────────────────┼───────────────────┼──────────────────────────┤
│ Claude Code      │ /memroom plugin   │ CLAUDE.md + AGENTS.md    │
│ Cursor           │ MCP tools         │ AGENTS.md                │
│ Codex            │ MCP tools         │ AGENTS.md                │
│ Antigravity      │ AGENTS.md only*   │ AGENTS.md + GEMINI.md    │
│ Claude.ai browser│ Chrome extension  │ Manual (popup UI)        │
└──────────────────┴───────────────────┴──────────────────────────┘

* Antigravity has no MCP support in v1 — room join via AGENTS.md
  instruction only, actual tool calls deferred to v2
```
