# SentinelAgent

A practice project for an SDE II AI live-coding interview: building an order-support agent with tool calling, short-term conversation memory, authorization, and human review.

The project is a work in progress. Human review and some reliability controls described below are practice targets, not completed features.

## Interview focus

The interview guide asks you to demonstrate:

- Tool/function calling: define a schema, parse a result, and handle malformed responses.
- Short-term conversation memory across multiple turns.
- Agent security.
- Human-in-the-loop decisions and handoff.
- Production-readiness checks.

The central principle to explain is:

> The model proposes an action. Application code validates and authorizes it before execution.

Practice both implementing the behavior and explaining your decisions in English.

## Practice scenario

Build an order-support agent that answers order questions and hands refund requests to a human.

Example conversation:

1. User: “Where is ORD001?”
2. The model requests `get_order_status` with an order ID.
3. Application code validates the arguments and checks the authenticated user's ownership.
4. The tool returns the order status, and the model explains it.
5. User: “When will it arrive?” The agent uses the earlier conversation for context.
6. User: “Please refund it.” The application creates a pending review request.
7. An authorized reviewer approves or rejects the request. Only an approved request can proceed to execution.

| Topic | What to demonstrate |
| --- | --- |
| Tool calling | Typed argument schema, JSON parsing, input validation, an allowed tool registry, execution, and a tool result returned to the model. |
| Memory | Follow-up questions, isolation between users, and bounded history that preserves complete tool exchanges. |
| Security | Authenticated identity, ownership checks in application code, and untrusted treatment of model output and tool content. |
| Human review | A persisted review request, explicit status, authorized approval or rejection, and controlled execution. |
| Production readiness | Timeouts, bounded execution, failure handling, useful logs, tests, and secrets supplied through configuration. |

## Current code and practice priorities

Initial observations below are based on code inspection on September 28, 2026. Tests were not run for that review. Update this checklist as implementation changes.

The repository already contains FastAPI routes, an LLM adapter, a tool registry, in-memory conversation storage, order ownership checks, and tests.

### 1. Trace one complete tool call

- [ ] Follow the request through [main.py](app/main.py), [agent.py](app/agent.py), [llm.py](app/llm.py), and [tools.py](app/tools.py).
- [ ] Explain the models in [model.py](app/model.py).
- [ ] Use the fake LLM to demonstrate a tool call followed by a final answer.
- [ ] Explain which failures belong to parsing, validation, authorization, and execution.

### 2. Establish trusted identity

The chat route currently accepts `user_id` from the request body. A caller can therefore claim another user's identity even though the tool checks order ownership.

- [ ] Derive user identity from an authenticated request.
- [ ] Pass that identity to memory and tools independently of model-generated arguments.
- [ ] Test that changing request content cannot grant access to another user's order or conversation.

Relevant files: [main.py](app/main.py), [model.py](app/model.py), [tools.py](app/tools.py), and [authorization tests](tests/test_order_authorization.py).

### 3. Preserve valid conversation history

The memory store currently retains the last 20 individual messages. This can separate a tool call from its result. The PostgreSQL store also has an unfinished method.

The authorization-denial path records an assistant tool call without a matching tool result, leaving an incomplete exchange for a later turn.

- [ ] Preserve complete tool-call/result exchanges when trimming history.
- [ ] Record a safe matching tool result when authorization is denied.
- [ ] Test a follow-up turn after a denied request.
- [ ] Test trimming at the boundary of a tool exchange.
- [ ] Finish or remove the incomplete PostgreSQL stub before running the application.
- [ ] Explain in-memory storage limitations: process restarts, multiple workers, and retention.

Relevant files: [memory.py](app/memory.py), [agent.py](app/agent.py), and [memory tests](tests/test_memory.py).

### 4. Add human review

Human handoff is not implemented yet. Saying “I will contact support” is insufficient unless a review request actually exists.

- [ ] Define handoff triggers, such as a refund requiring approval or an explicit request for a person.
- [ ] Create a review request containing the proposed action, validated arguments, requester, reason, and only the context needed by the reviewer.
- [ ] Implement transitions: `pending → approved/rejected`; an approved action can then become `executed` or `failed`.
- [ ] Require an authorized reviewer to approve or reject the request.
- [ ] Bind approval to the exact proposed action and recheck authorization before execution.
- [ ] Prevent repeated approval or execution from applying the same action twice.
- [ ] Return a review identifier and clear pending status to the user.

Suggested implementation locations: review models in [model.py](app/model.py), orchestration in [agent.py](app/agent.py), review routes in [main.py](app/main.py), and a dedicated review store module.

### 5. Bound execution and handle failures

The current loop permits six tool executions despite `MAX_TOOL_CALLS = 5`.

- [ ] Enforce the intended tool-execution limit and test its boundary.
- [ ] Test malformed JSON, invalid arguments, unknown tools, and tool execution failures.
- [ ] Configure provider and tool timeouts explicitly.
- [ ] Define which transient failures are retryable and bound retries.
- [ ] Avoid retrying side effects without an idempotency strategy.
- [ ] Make fallback responses and stored conversation state consistent.

Relevant files: [agent.py](app/agent.py), [llm.py](app/llm.py), and [tools.py](app/tools.py).

### 6. Prepare the live interview setup

The current adapter uses OpenRouter. The interview guide explicitly lists an AWS Bedrock, OpenAI, or Anthropic API key.

- [ ] Prepare working access through one of the listed providers.
- [ ] Verify a real tool call using the intended model before the interview.
- [ ] Keep API keys out of source control and logs.
- [ ] Keep a deterministic fake LLM available for tests and offline practice.
- [ ] Confirm the project starts and the documented test command works in your environment.
- [ ] Verify the IDE and AI coding assistant are ready.

## A 60-minute mock interview

This is a suggested practice duration, not the confirmed interview format.

| Time | Exercise |
| --- | --- |
| 0–5 minutes | Clarify requirements, identify sensitive actions, and explain the request flow. |
| 5–20 minutes | Implement one successful tool call using typed models and a fake LLM. |
| 20–30 minutes | Add a second conversation turn and user isolation. |
| 30–45 minutes | Handle malformed arguments, unauthorized access, and a minimal human-review flow. |
| 45–55 minutes | Test important failure paths and execution limits. |
| 55–60 minutes | Demonstrate the behavior and explain remaining production work. |

## Questions to rehearse aloud

1. Why must the application validate arguments even when the model receives a schema?
2. What happens when tool arguments are malformed or the tool name is unknown?
3. Where does trusted user identity come from?
4. How do you prevent a prompt or tool response from granting extra permissions?
5. How do you retain useful context without breaking tool-message ordering?
6. Which actions require human review, and what does the reviewer receive?
7. What prevents an approved action from executing twice?
8. What happens when the model times out or repeatedly requests tools?
9. Which tests can run without a live model, and what still needs provider integration testing?
10. What would need to change before deploying multiple application workers?

## Workflow for further practice and code changes

For each topic or question, use this cycle:

1. Explain the concept and why it matters in this project.
2. Inspect the current behavior and identify a concrete gap.
3. Choose one small implementation exercise with observable acceptance criteria.
4. Make the requested code change and review the diff.
5. Run focused checks for the affected behavior, including meaningful failure cases.
6. Explain the result, tradeoffs, and next useful exercise.

When using an AI coding assistant, request small, reviewable changes. Read the generated code, explain why it works, and verify its behavior before continuing.

A useful follow-up prompt is:

> Help me practice [topic] in SentinelAgent. Explain the current behavior, suggest the next exercise and code changes, and tell me how to verify them. If I ask you to implement it, make the change and run the relevant checks.
