# Backrooms — Messaging Module PRD

---

## Problem Statement

Once an agent joins a Backrooms room, there is no mechanism to persist the conversation happening in that session. Each agent turn exists only in the current context window — the moment the session ends, hits a context limit, or the developer switches tools, everything is lost. There is no shared message log that other tools can read from, no way to resume where you left off, and no raw material for the summary layer to work with.

---

## Solution

The messaging module gives rooms a persistent, append-only message log. Every agent turn — both the user message and the assistant response — is pushed to the room as a pair in a single transaction. Any agent in the same room can pull messages at session start to catch up on what happened. The module also tracks token accumulation since the last summary and signals the agent when a new summary is needed, without generating it itself.

---

## User Stories

1. As an agent, I want to push both the user message and my response together in one tool call so that the number of tool calls per turn stays minimal.
2. As an agent, I want push_message to read the active room from .memroom.json automatically so that I don't have to pass the room explicitly on every call.
3. As an agent, I want push_message to insert both messages as separate rows in a single database transaction so that the message log is always consistent.
4. As an agent, I want the server to assign timestamps server-side so that message ordering is always reliable regardless of which tool pushed them.
5. As an agent, I want push_message to return a simple status:ok response in the normal case so that I can continue without processing overhead.
6. As an agent, I want push_message to return status:summary_needed when token accumulation since the last summary exceeds the threshold so that I know when to generate a new summary.
7. As an agent, I want the summary_needed response to include the last_summarized_message_id so that I know exactly where to start pulling unsummarized messages from.
8. As an agent, I want the summary_needed response to include unsummarized_message_count so that I can decide whether to generate a summary immediately or defer.
9. As an agent, I want to call pull_messages at session start to retrieve recent conversation history so that I have context before starting work.
10. As an agent, I want pull_messages to return messages in chronological order so that I can follow the conversation naturally.
11. As an agent, I want pull_messages to support a limit parameter (default 20) so that I can control how many messages I receive.
12. As an agent, I want pull_messages to support an offset parameter (default 0) so that I can paginate through the full message history.
13. As an agent, I want pull_messages to support an after_id parameter so that I can retrieve only messages after a specific message_id for summary generation.
14. As an agent, I want pull_messages to return total_messages count so that I know how large the full message log is.
15. As an agent, I want pull_messages to return has_more so that I know whether there are older messages I haven't seen.
16. As a developer, I want the message log to be append-only so that no messages are ever deleted or modified.
17. As a developer, I want each message to store role (user/assistant) so that the conversation structure is preserved.
18. As a developer, I want message content stored as plain text so that retrieval and rendering stays simple.
19. As a developer, I want the room record to track total_tokens and last_summary_tokens so that token accumulation can be calculated without scanning all messages.
20. As a developer, I want token count estimated as len(content) / 4 so that there is no dependency on an external tokenizer.
21. As a developer, I want the summary trigger threshold set at 8000 tokens since last summary so that summaries are generated at a meaningful cadence.
22. As a developer, I want acceptable message loss when an agent crashes mid-session so that the system stays simple without zero-loss guarantees.
23. As a developer, I want message pairs that are partially pushed (user message only, no assistant) to remain in the log without special handling so that the system doesn't need rollback logic.

---

## Implementation Decisions

### Modules

**1. push_message tool**
Accepts `user_content` and `assistant_content` as the only inputs. Room is resolved from `.memroom.json` in the agent's working directory. `user_id` comes from auth. Inserts two rows (role: user, role: assistant) in a single database transaction. After insert, updates `room.total_tokens` by adding estimated tokens for both messages. Computes `total_tokens - last_summary_tokens` and if it exceeds 8000, returns `summary_needed` signal with `last_summarized_message_id` and `unsummarized_message_count`. Otherwise returns `{ status: "ok" }`.

**2. pull_messages tool**
Accepts `limit` (default 20), `offset` (default 0), `after_id` (optional). Room resolved from `.memroom.json`. If `after_id` is provided, returns all messages after that message_id in chronological order up to limit. If no `after_id`, returns the last N messages by created_at descending, then re-ordered ascending for readability. Returns `{ messages, total_messages, has_more }`.

**3. messages table**
```
id           uuid primary key
room_id      uuid → rooms
user_id      varchar
role         varchar  (user / assistant)
content      text
created_at   timestamp (server-assigned)
```

**4. rooms table additions**
```
total_tokens          integer  (running count, updated on every push)
last_summary_tokens   integer  (snapshot at last summary, updated on submit_summary)
last_summarized_message_id  uuid → messages
```

### Key Architectural Decisions

- push_message always receives a pair — user_content + assistant_content — never individual messages
- Both messages inserted in a single transaction — either both succeed or neither does
- No source/tool tracking on messages — removed by design decision
- Token estimation is `len(content) / 4` — no external tokenizer dependency
- Summary generation is never triggered by the server — server only signals need, agent generates
- Agent pulls messages itself for summary generation using `after_id` from push_message response
- pull_messages and summary are separate concerns — pull_messages returns raw messages only, summary comes from join_room response
- Message loss on agent crash is acceptable — no retry or queue mechanism for v1

### API Contracts

push_message:
```
input:  { user_content: str, assistant_content: str }
output (normal): { status: "ok" }
output (threshold hit): {
  status: "summary_needed",
  last_summarized_message_id: str,
  unsummarized_message_count: int
}
```

pull_messages:
```
input:  { limit: int = 20, offset: int = 0, after_id: str = None }
output: {
  messages: [{ id, role, content, created_at }],
  total_messages: int,
  has_more: bool
}
```

---

## Testing Decisions

Good tests verify external behavior — what the tool returns and what side effects it produces in the database — not internal implementation details like how token counting works internally.

Modules to test:

- `push_message` — assert two rows inserted per call, assert transaction atomicity (if second insert fails, first is rolled back), assert total_tokens updated correctly, assert status:ok returned under threshold, assert summary_needed returned when threshold exceeded with correct last_summarized_message_id
- `push_message` with missing .memroom.json — assert graceful error returned
- `pull_messages` with no after_id — assert last N messages returned in chronological order, assert has_more is correct, assert total_messages is accurate
- `pull_messages` with after_id — assert only messages after that id are returned, assert correct ordering
- `pull_messages` pagination — assert offset and limit work correctly across multiple calls
- Token accumulation — assert total_tokens increments correctly across multiple pushes, assert summary_needed triggers at correct threshold

---

## Out of Scope

- Zero-loss message delivery (file watchers, DOM interception, proxy layers)
- Per-message source/tool tracking
- Structured content (JSON, code blocks, tool call results) — plain text only for v1
- Message deletion or editing
- Real tokenizer integration — estimation only for v1
- Semantic search over messages — deferred, requires vector DB
- Retry logic or message queuing for failed pushes
- Push of individual messages (user only or assistant only) — pairs only

---

## Further Notes

The messaging module is the core validation surface for Backrooms. Once push and pull work reliably across Claude Code and OpenCode in the same directory, the hypothesis is proven — agents in different tools can share a conversation. Everything else (summaries, visibility, Chrome extension) builds on this foundation.

The acceptable loss decision was deliberate. A user can always manually call push_message if they notice a turn was missed. The summary layer further compensates by capturing intent even when individual messages are lost.

Semantic search over messages is the right long-term direction but requires vectorizing every message at push time and running a separate vector DB (pgvector or Qdrant). This is deferred until the basic message log proves useful in real usage.