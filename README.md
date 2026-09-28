# SentinelAgent

A multi-turn customer support agent built with Python, FastAPI, and Pydantic. It answers order questions using an LLM, validated tool calls, and conversation history scoped to each user and session.

The project is a work in progress. Human review and some reliability controls described below are planned features.

## Overview

Core capabilities:

- An OpenRouter LLM adapter and a deterministic fake client for tests.
- An explicit tool registry with argument validation and order ownership checks.
- Bearer-token authentication mapped to two configured users.
- Conversation memory scoped by user and session, with in-memory and PostgreSQL adapters.
- LLM latency and token-usage logging.

The central design principle is:

> The model proposes an action. Application code validates and authorizes it before execution.

The running application currently uses in-memory storage. The PostgreSQL adapter and Alembic migrations are available, but the adapter is not yet connected to the chat route.

## Request flow

`POST /chat` requires an `Authorization: Bearer <token>` header. The authenticated token determines the user identity; the request body contains only the session ID and message:

```json
{
  "session_id": "session-1",
  "message": "Where is ORD001?"
}
```

Example conversation:

1. User: “Where is ORD001?”
2. The model requests `get_order_status` with an order ID.
3. Application code validates the arguments and checks the authenticated user's ownership.
4. The tool returns the order status, and the model explains it.
5. User: “When will it arrive?” The agent uses the earlier conversation for context.

Relevant files: [main.py](app/main.py), [agent.py](app/agent.py), [llm.py](app/llm.py), [tools.py](app/tools.py), and [model.py](app/model.py).

## Development

Install dependencies using Poetry:

```sh
make install
```

Configure these values in a local `.env` file:

- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL`
- `DATABASE_URL` (a `postgresql+asyncpg://` connection URL)
- `AUTH_USER001_TOKEN`
- `AUTH_USER002_TOKEN`

Use distinct random values for the two authentication tokens. Keep credentials out of source control and logs.

```sh
make run          # Start the API at http://127.0.0.1:8081
make test         # Run tests; PostgreSQL tests require TEST_DATABASE_URL
make lint         # Run Ruff checks
make check        # Check dependencies, lint, formatting, and tests
make help         # List all available commands
```

## Known limitations and planned work

### Authentication and authorization

Authentication currently uses static bearer tokens mapped to `USER001` and `USER002` in [auth.py](app/auth.py).

- [ ] Replace static credentials with a production authentication mechanism.
- [ ] Test that changing request content cannot grant access to another user's order or conversation.

Relevant files: [main.py](app/main.py), [model.py](app/model.py), [tools.py](app/tools.py), and [authorization tests](tests/test_order_authorization.py).

### Conversation history

Both memory adapters trim the oldest whole turns to fit a soft 20-message budget. The latest turn is preserved intact even when it exceeds that budget. The PostgreSQL adapter retains older rows in the database; a retention policy is still needed.

The authorization-denial path records a generic tool error with the matching call ID before returning a denial. A regression test verifies that the next LLM call receives the complete exchange.

- [x] Preserve complete tool-call/result exchanges when trimming history.
- [x] Record a safe matching tool result when authorization is denied.
- [x] Test a follow-up turn after a denied request.
- [x] Test trimming at the boundary of a tool exchange and preservation of an oversized latest turn in both adapters.
- [ ] Connect the PostgreSQL adapter to the application lifecycle.
- [ ] Define database retention and concurrent-request behavior.

In-memory history is lost on process restart and is not shared between application workers.

Relevant files: [memory.py](app/memory.py), [agent.py](app/agent.py), and [memory tests](tests/test_memory.py).

### Human review

The handoff table and PostgreSQL store can create and retrieve pending requests, but `/chat` does not create them yet. Saying “I will contact support” is insufficient unless a review request actually exists.

- [ ] Define handoff triggers, such as a refund requiring approval or an explicit request for a person.
- [ ] Create a review request containing the proposed action, validated arguments, requester, reason, and only the context needed by the reviewer.
- [ ] Implement transitions: `pending → approved/rejected`; an approved action can then become `executed` or `failed`.
- [ ] Require an authorized reviewer to approve or reject the request.
- [ ] Bind approval to the exact proposed action and recheck authorization before execution.
- [ ] Prevent repeated approval or execution from applying the same action twice.
- [ ] Return a review identifier and clear pending status to the user.

Suggested implementation locations: review models in [model.py](app/model.py), orchestration in [agent.py](app/agent.py), review routes in [main.py](app/main.py), and a dedicated review store module.

### Reliability

The current loop permits six tool executions despite `MAX_TOOL_CALLS = 5`.

- [ ] Enforce the intended tool-execution limit and test its boundary.
- [ ] Test malformed JSON, invalid arguments, unknown tools, and tool execution failures.
- [ ] Configure provider and tool timeouts explicitly.
- [ ] Define which transient failures are retryable and bound retries.
- [ ] Avoid retrying side effects without an idempotency strategy.
- [ ] Make fallback responses and stored conversation state consistent.

Relevant files: [agent.py](app/agent.py), [llm.py](app/llm.py), and [tools.py](app/tools.py).

## PostgreSQL memory integration tests

The PostgreSQL memory tests are marked `integration` and are skipped by the
regular `make test` command unless `TEST_DATABASE_URL` is set. Use a dedicated test
database; the tests insert and clean up rows under unique test user/session IDs.
Apply migrations to that database, then run the tests:

```sh
DATABASE_URL='postgresql+asyncpg://sentinelagent:sentinelagent_dev_only@127.0.0.1:5432/sentinelagent_test' make db-upgrade
make integration-test TEST_DATABASE_URL='postgresql+asyncpg://sentinelagent:sentinelagent_dev_only@127.0.0.1:5432/sentinelagent_test'
```

Do not point `TEST_DATABASE_URL` at production or a database containing valuable
data.
