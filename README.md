# Backrooms 🚪

A shared memory layer across AI coding tools — Claude Code, Cursor, OpenCode — so context from one session is accessible in another. Built on MCP.

---

## Structure

```
backrooms/
├── server.py
├── config/
│   ├── db.py
│   └── logger.py
├── tools/
│   └── room_management/
│       ├── router.py
│       └── handlers.py
├── models/
├── alembic/
│   └── env.py
├── alembic.ini
└── .env
```

---

## Setup

**1. Install dependencies**
```bash
uv sync
```

**2. Configure `.env`**
```properties
DATABASE_URL=postgresql+asyncpg://user:password@host/dbname?ssl=require
BACKROOMS_USER_ID=your_username
```

**3. Run migrations**
```bash
alembic upgrade head
```

**4. Start server**
```bash
uvicorn server:app --host 127.0.0.1 --port 8000 --reload
```

---

## Connect to your tools

**Claude Code**
```bash
claude mcp add backrooms --transport http http://127.0.0.1:8000/mcp/
```

**Cursor** — add to MCP settings:
```json
{ "mcpServers": { "backrooms": { "url": "http://127.0.0.1:8000/mcp/" } } }
```

**OpenCode** — add to `opencode.json`:
```json
{ "mcp": { "backrooms": { "type": "remote", "url": "http://127.0.0.1:8000/mcp/" } } }
```