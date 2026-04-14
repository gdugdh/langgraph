# Support Bot MVP

Minimal corporate support bot prototype built with `langgraph`.

What is implemented:
- one shared state object
- 6 graph nodes
- structured LLM classification without heuristic fallback
- taxonomy loaded from a repository-backed JSON file
- file-backed KB search through an MCP-shaped adapter
- KB search queries are generated in Russian
- one `issues.json` file for incident storage
- heuristic deduplication first
- optional LLM refinement for borderline duplicate cases
- clarification loop is split into `classify_ticket` and `clarify_ticket` with up to 3 questions
- `messages` is the source of truth for request context

Files:
- `support_bot.py` - entrypoint and graph wiring
- `service/` - application services
- `repo/` - repository abstractions and file-based implementations
- `data/taxonomy.json` - categories and priorities for classification
- `issues.json` - persistent incident registry
- `kb/` - sample knowledge base files searched by the bot

Run:

```bash
python project/support_bot.py
```

Make targets from `project/`:

```bash
make install
make run
make test
make benchmark
```

Tests:

```bash
python -m unittest discover -s tests -v
python tests/run_duplicate_similarity_benchmark.py
```

Optional env vars:

```bash
export OPENROUTER_API_KEY="..."
export OPENROUTER_MODEL="openai/gpt-4o-mini"
export SUPPORT_BOT_CLASSIFIER_MODEL="openai/gpt-4o-mini"
export SUPPORT_BOT_ENABLE_LLM_DEDUP="1"
export SUPPORT_BOT_KB_DIR="/path/to/kb"
export SUPPORT_BOT_ISSUES_PATH="/path/to/issues.json"
export SUPPORT_BOT_TAXONOMY_PATH="/path/to/taxonomy.json"
```

Notes:
- There is no real MCP server configured in this workspace. The current MVP uses
  a file search adapter with an MCP-like interface, so the graph and state model
  stay stable when a real MCP client is added later.
- The classifier is mandatory in this version. If no classifier LLM is configured,
  the bot stops with an explicit error instead of falling back to heuristics.
- The classifier behaves like first-line triage. It decides whether the issue is
  described well enough to continue based on location, reproduction, and version details.
- `issues.json` is updated in place. Re-running the bot with similar tickets will
  increment `frequency` instead of creating a new issue when heuristic matching
  considers them duplicates.
