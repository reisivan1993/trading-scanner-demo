# CLAUDE.md - Staff Engineer Programming Standards

## Core Philosophy

- **Simplicity over cleverness.** Write code a junior can read at 2 AM during an incident.
- **Delete more than you write.** The best code is the code that doesn't exist.
- **Make it work, make it right, make it fast** -- in that order, and only go to the next step when needed.
- **Ownership mindset.** If you touch it, you own it. Leave code better than you found it.

## Code Quality

### Readability
- Functions do one thing and fit on one screen (~30 lines max). If longer, extract.
- Variable names describe *what*, not *how* (`remaining_retries` not `r` or `cnt`).
- No commented-out code. That's what git history is for.
- No TODO without a ticket/issue number. Naked TODOs rot forever.

### Structure
- Flat is better than nested. Max 3 levels of indentation before you refactor.
- Early returns over deep nesting. Guard clauses at the top.
- Group related logic into cohesive modules. Split when a file exceeds ~300 lines.
- Imports: stdlib > third-party > local, separated by blank lines.

### Naming Conventions
- `snake_case` for functions, variables, modules.
- `PascalCase` for classes.
- `UPPER_SNAKE` for constants.
- Boolean variables/functions: `is_`, `has_`, `can_`, `should_` prefix.
- Avoid abbreviations unless universally understood (`id`, `url`, `http` are fine; `mgr`, `proc`, `ctx` are not).

## Design Principles

### SOLID (applied pragmatically)
- **Single Responsibility.** One reason to change per module/class.
- **Open/Closed.** Extend via composition or protocols, not by editing core logic.
- **Dependency Inversion.** Depend on abstractions (protocols/interfaces), not concretions. Pass dependencies in, don't reach out.

### Data & State
- Prefer immutable data structures for domain objects (`frozen=True` dataclasses, NamedTuples).
- Minimize mutable shared state. When needed, make ownership explicit.
- Use `Decimal` for money. Never `float` for financial calculations.
- All timestamps must be timezone-aware. Always store in UTC, convert for display.

### Configuration
- Config over hardcoded values. Magic numbers go in config files or named constants.
- Validate config at startup. Fail fast on bad input, don't discover problems at runtime.
- Secrets load from environment variables only. Never commit, log, or hardcode secrets.

## Error Handling

- **Fail loud, fail fast.** Errors should be visible, not swallowed.
- **Use specific exceptions.** `raise ValueError("price must be positive")` not `raise Exception("error")`.
- **Custom exception hierarchy** for your domain (e.g., `AppError > ProviderError > RateLimitError`).
- **Retry with backoff** for transient failures (network, rate limits). Cap retries. Always configurable.
- **Don't catch broadly.** No bare `except:` or `except Exception:` unless re-raising or at the top-level boundary.
- **Log at the boundary, not everywhere.** One structured log entry on catch, not scattered prints.

## Testing

### Philosophy
- **Tests are not optional.** Every PR includes tests. No "I'll add tests later."
- **Tests are documentation.** A reader should understand the feature by reading the tests alone.
- **Tests protect refactoring.** If you can't refactor with confidence, your tests are insufficient.
- **A failing test is better than no test.** Write the test first when debugging -- reproduce the bug, then fix it.

### Test Pyramid
- **Unit tests (70%):** Fast, isolated, no I/O. Test one function/class. Run in <1 second each.
- **Integration tests (20%):** Test module boundaries -- DB queries, API client calls, file parsing. Use fakes/containers.
- **E2E tests (10%):** Test critical user flows end-to-end. Expensive to maintain -- keep these minimal.

### Naming & Structure
- **Test naming:** `test_<unit>_<scenario>_<expected_result>`
  - `test_calculate_tax_negative_income_raises_value_error`
  - `test_risk_gate_rr_below_minimum_rejects_setup`
  - `test_parse_config_missing_field_uses_default`
- **One test = one behavior.** If a test name has "and" in it, split it into two tests.
- **Arrange-Act-Assert** pattern. Separate setup, execution, and verification with blank lines.
- **File structure mirrors source:** `src/risk/gate.py` -> `tests/unit/test_risk_gate.py`

### What to Test
- **Happy path** -- does it work with valid input?
- **Edge cases** -- empty input, zero, negative, None, max values, boundary values.
- **Error paths** -- does it raise the right exception with the right message?
- **State transitions** -- if something changes state, test before and after.
- **Regression tests** -- every bug fix gets a test that would have caught it.

### What NOT to Test
- Don't test framework/library internals (e.g., does `json.loads` work?).
- Don't test private methods directly -- test them through the public interface.
- Don't test getters/setters or trivial constructors with zero logic.
- Don't write tests that just mirror the implementation line by line.

### Mocking Guidelines
- **Mock at the boundary, not everywhere.** Mock the HTTP client, not every internal function.
- **Prefer fakes over mocks** when possible. A fake in-memory repository is better than mocking 10 method calls.
- **Never mock what you don't own** without also having an integration test against the real thing.
- **If mocking is painful, the design is wrong.** Difficulty mocking = tightly coupled code. Refactor.
- **Assert on behavior, not on mock call counts.** `assert result == expected` > `mock.assert_called_once()`.

### Fixtures & Factories
- Use `@pytest.fixture` for shared setup. Keep fixtures close to where they're used.
- Use factory functions (`make_setup(overrides)`) over giant fixture trees.
- Avoid deep fixture chains -- if fixture A depends on B depends on C, flatten.
- `conftest.py` is for widely shared fixtures only. Don't dump everything in root conftest.

### Test Data
- Use realistic but minimal data. Don't copy-paste production payloads into tests.
- Hardcode expected values -- don't compute them. `assert total == Decimal("150.00")` not `assert total == price * qty`.
- For time-dependent tests, freeze time with `freezegun` or inject a clock.
- For random/generated data, use fixed seeds or deterministic builders.

### Async Testing
- Use `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`.
- Async tests are just `async def test_...` -- the framework handles the event loop.
- Mock async dependencies with `AsyncMock`.

### Coverage
- **Target 80%+ on business logic.** Not a vanity metric -- measure the critical paths.
- **Don't chase 100%.** Diminishing returns. Focus on high-risk code (money, auth, state changes).
- **Coverage ≠ quality.** A test that asserts nothing has 100% coverage and 0% value.
- Exclude from coverage: `__main__`, config boilerplate, third-party wrappers.

### Running Tests
```bash
# All tests
pytest

# Unit tests only, stop on first failure
pytest tests/unit/ -x

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_risk_gate.py -v

# Specific test by name pattern
pytest -k "test_risk_gate_rr"

# With coverage report
pytest --cov=src --cov-report=term-missing

# Coverage with HTML report
pytest --cov=src --cov-report=html

# Parallel execution (if pytest-xdist installed)
pytest -n auto

# Show slowest 10 tests
pytest --durations=10
```

### CI Expectations
- All tests pass before merge. No "known failures."
- Coverage must not drop on PRs. Ratchet up, never down.
- Flaky tests get quarantined and fixed within 48 hours, not skipped forever.
- Test suite runs in under 5 minutes. If it's slower, split or parallelize.

## Git & Version Control

- **Conventional commits:** `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Small, atomic commits.** Each commit compiles and passes tests.
- **Branch naming:** `feat/<desc>`, `fix/<desc>`, `refactor/<desc>`.
- **Never force-push to main/master.**
- **PR = one logical change.** If you need "and" to describe it, split it.

## Security

- **Never commit secrets.** Use `.env` + `.env.example` pattern.
- **Validate all external input** at system boundaries (API endpoints, file parsing, user input).
- **Parameterize queries.** No string concatenation for SQL or commands.
- **Principle of least privilege.** Request minimum permissions, expose minimum surface.
- **Redact secrets in logs.** Filter fields matching `*_key`, `*_token`, `*_secret`, `*_password`.
- **Keep dependencies updated.** Audit regularly for known vulnerabilities.

## Performance

- **Measure before optimizing.** Profile with real data. No premature optimization.
- **Batch I/O.** Combine multiple network/DB calls when possible.
- **Async for I/O-bound work.** Keep CPU-bound code synchronous or use process pools.
- **Cache expensive computations** with clear invalidation strategy.
- **Set timeouts on all external calls.** No unbounded waits.

## Architecture Patterns

### When to Abstract
- **Rule of Three.** Don't abstract until you see the pattern three times.
- **Three similar lines > one premature abstraction.** Duplication is cheaper than wrong abstraction.
- **Extract when the reason to change differs**, not when code looks similar.

### API & Interface Design
- Accept the most general type, return the most specific.
- Use protocols/interfaces at module boundaries, concrete types internally.
- Fail at compile time (type errors) over runtime when possible.

### Logging & Observability
- Use structured logging (key=value pairs), not string interpolation.
- Log levels: DEBUG for dev, INFO for operations, WARNING for recoverable issues, ERROR for failures.
- Include context: `ticker=AAPL action=rejected reason=below_min_rr` not `"rejected AAPL"`.
- Every external call should be observable: log request/response time, status, retries.

## Code Review Checklist (Self-Review Before PR)

1. Does it work? Did you test the happy path AND edge cases?
2. Is it readable? Could a teammate understand it without asking you?
3. Is it safe? No injection, no leaked secrets, no unvalidated input?
4. Is it tested? New logic has tests, existing tests still pass?
5. Is it minimal? No dead code, no unused imports, no over-engineering?
6. Is it consistent? Follows existing patterns in the codebase?

---

## Assignment Development Cycle

> **Powered by [obra/superpowers](https://github.com/obra/superpowers) v4.3.1** — installed at `~/.claude/` (user scope, active in all sessions).
> Skills trigger automatically. Slash commands: `/brainstorm`, `/write-plan`, `/execute-plan`.

Every task — bug fix, feature, refactor — follows this cycle without exception.
Each phase maps to a specific superpowers skill. Skip no phase.

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. UNDERSTAND      2. EXPLORE       3. PLAN                         │
│  (brainstorming)    (Explore agent)  (writing-plans + git worktree)  │
│        ↓                                                             │
│  4. IMPLEMENT       5. TEST          6. REVIEW        7. COMMIT      │
│  (subagent-driven)  (TDD skill)      (code-review)    (finish-branch)│
└──────────────────────────────────────────────────────────────────────┘
```

### Phase 1 — Understand `[skill: brainstorming]`
- Trigger: `/brainstorm` or describe the feature/bug to Claude.
- Claude asks clarifying questions before touching any file.
- Output: a saved design document with acceptance criteria.
- Gate: you've signed off on the design document section-by-section.
- **Do not skip for "small" tasks.** Even a 3-line change has context.

### Phase 2 — Explore `[Explore sub-agent]`
- Dispatch an **Explore** sub-agent to map the affected code area.
- Find: entry points, callers, data models touched, existing tests.
- Read actual files — never assume from filenames alone.
- Gate: you can name every file that will change and why.

### Phase 3 — Plan `[skill: writing-plans + using-git-worktrees]`
- Trigger: `/write-plan` after design approval.
- Plan breaks work into tasks ≤5 minutes each, with exact file paths and verification steps.
- A git worktree is created for the branch — isolated, clean slate.
- Gate: plan reviewed and approved; worktree baseline tests pass.

### Phase 4 — Implement `[skill: subagent-driven-development]`
- Trigger: `/execute-plan` or Claude dispatches subagents automatically.
- Each task gets a fresh subagent: two-stage review (spec compliance → code quality).
- One logical change per commit. Never batch unrelated edits.
- Gate: all linters pass (`ruff check`, `mypy`); no `print()` in production code.

### Phase 5 — Test `[skill: test-driven-development]`
- RED-GREEN-REFACTOR cycle enforced. Tests written before implementation.
- Cover: happy path, edge cases, error paths for every new function.
- For this project: `pytest tests/unit/ -x` and verify coverage doesn't drop.
- Gate: all tests green; code written before a test is deleted and rewritten.

### Phase 6 — Review `[skill: requesting-code-review + verification-before-completion]`
- Self-review against the Code Review Checklist above, plus:
  - [ ] No hardcoded secrets, URLs, or magic numbers
  - [ ] All new public functions have type annotations
  - [ ] `ruff check --fix` and `mypy` both pass clean
  - [ ] Git diff is the minimal set of changes needed
- Verify it's actually fixed/working before declaring done — no assumptions.

### Phase 7 — Commit & Finish `[skill: finishing-a-development-branch]`
- Conventional commit: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Message describes **why**, not what.
- Skill presents options: merge / open PR / keep branch / discard. Choose explicitly.
- Worktree is cleaned up after branch finalization.

---

## Sub-Agent Usage Guide

> Superpowers skills and Claude Code sub-agents are complementary.
> Skills define **what** workflow to follow. Sub-agents define **who** does the work.

Sub-agents protect the main context window and parallelize independent work.
**Rule:** right agent for the right job; never duplicate work across agents.

### Agent Types & When to Use Them

| Agent | Superpowers Skill | Use When | Do NOT Use When |
|-------|-------------------|----------|-----------------|
| **Explore** | Phase 2 (Explore) | Mapping unfamiliar code, finding all callers, "how does X work?" | You already know the exact file/line — use Read/Grep directly |
| **Plan** | Phase 3 (writing-plans) | Architectural decisions, multi-file change design | Single-file changes with obvious implementation |
| **Bash** | Phases 4–7 (implement/test/commit) | Running pytest, ruff, mypy, git, docker, npm | Reading/writing files — use Read/Edit/Write instead |
| **general-purpose** | Any research phase | Multi-step research needing several search+read rounds | Simple targeted searches — use Glob/Grep directly |

### Parallelism Rules

**Run in parallel** when tasks are independent (no shared output):
```
# Good — independent codebase explorations
[Explore: how does risk_gate work?]  ←─ parallel ─→  [Explore: how does scoring work?]

# Good — independent quality checks
[Bash: ruff check packages/]  ←─ parallel ─→  [Bash: mypy packages/]
```

**Run sequentially** when output feeds input:
```
# Required order
[brainstorming] → approve design → [writing-plans] → approve plan
    → [subagent-driven-development] → [pytest] → [finishing-a-development-branch]
```

### Project-Specific Skill Patterns

**When adding a new provider** (e.g., a new market data source):
1. `/brainstorm` — define the provider contract and edge cases
2. `Explore`: "How does `yfinance_provider.py` implement `BaseProvider`?" + read `base.py` in parallel
3. `/write-plan` — tasks: new provider class → factory registration → unit tests
4. Implement via subagents + `pytest tests/unit/test_providers.py -x`

**When fixing a bug in the pipeline**:
1. `[skill: systematic-debugging]` — 4-phase root cause process, do not skip
2. `Explore`: trace `orchestrator.py` → failing component
3. Write **failing test first** (reproduce the bug), then fix
4. `[skill: verification-before-completion]` — verify fix, not just "tests pass"

**When adding a new trading skill** (e.g., new pattern detector in `packages/skills/`):
1. `/brainstorm` — what signal? what inputs from `indicators.py`? acceptance criteria
2. `Explore`: "How does `patterns.py` detect breakouts?"
3. `/write-plan` — implement in `packages/skills/`, tests in `tests/unit/test_<skill>.py`, wire into `orchestrator.py` last
4. TDD: RED (write test) → GREEN (minimal impl) → REFACTOR

**When changing the API** (`apps/api/routes.py`):
1. Read routes + `dependencies.py` in parallel
2. Update `tests/integration/test_api.py` first (test-first)
3. Implement route change, run `pytest tests/integration/ -x`
4. `[skill: requesting-code-review]` before merging

**When doing a broad refactor** (e.g., changing a core model):
1. `Explore` (thorough): full impact across `packages/` and `apps/`
2. `/write-plan` with explicit sequencing: change models → update callers → update tests
3. `[skill: dispatching-parallel-agents]` for independent caller updates
4. Never refactor and add features in the same commit

### Background Agents

Use `run_in_background=True` only when:
- The task produces output you will read after finishing a parallel task (e.g., full test run while writing another file)
- Long compile/lint job that doesn't block your next step

Always read background output before committing. A green test you haven't read is not a green test.
