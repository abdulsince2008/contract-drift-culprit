# Contract-Drift Culprit Finder

**Find breaking API changes and automatically identify the git commits that introduced them.**

## Problem

API contracts drift over time. When a breaking change slips into production, teams waste hours digging through git history to find *who* changed *what* and *when*. Existing tools (oasdiff, Dredd, Optic) tell you *what* broke — but not *which commit* caused it.

## Why This Is Different

| Tool | Detects Drift | Identifies Culprit Commit |
|------|---------------|---------------------------|
| oasdiff | ✅ | ❌ |
| Dredd | ✅ | ❌ |
| Optic | ✅ | ❌ |
| **This tool** | ✅ (via oasdiff) | ✅ (git blame on route handlers) |

**The unique layer**: After oasdiff finds breaking changes, this tool searches your codebase for route handlers matching the changed endpoints, runs `git log` on those files, and surfaces the most recent commits that touch the relevant code paths.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Old OpenAPI │────▶│   oasdiff    │────▶│ Breaking Changes │────▶│ Git Blame on    │
│ Spec (v1)   │     │  (breaking)  │     │  (path, method,  │     │ Matching Route  │
└─────────────┘     └──────────────┘     │   change type)   │     │ Handlers        │
                                         └──────────────────┘     └────────┬────────┘
                                                                          ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Slack/JSON  │◀────│   Report     │◀────│ Culprit Commits  │◀────│ Ranked by       │
│ Output      │     │  Generator   │     │ (hash, author,   │     │ Recency & Match │
└─────────────┘     └──────────────┘     │  date, message)  │     └─────────────────┘
                                         └──────────────────┘
```

1. **Diff**: Uses `oasdiff` (industry-standard) to compare two OpenAPI specs
2. **Match**: For each breaking change, searches repo for route handlers containing the path/method
3. **Blame**: Runs `git log` on matched files to find recent commits
4. **Report**: Outputs rich CLI table, JSON, or Slack message with suspect commits

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Install oasdiff (one-time)
go install github.com/oasdiff/oasdiff@latest
export PATH=$PATH:$(go env GOPATH)/bin

# 3. Run on sample specs (included)
python -m main samples/openapi_old.yaml samples/openapi_new.yaml \
  --repo-path samples
```

## Example Output

```
$ python -m main samples/openapi_old.yaml samples/openapi_new.yaml --repo-path samples

╭─────────────────────────────────────────────────────────────────╮
│                    🔍 Analyzing                                  │
│  Old spec: samples/openapi_old.yaml                             │
│  New spec: samples/openapi_new.yaml                             │
│  Repo: samples                                                  │
╰─────────────────────────────────────────────────────────────────╯

Total Breaking Changes: 7

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Change #1: GET /posts                                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Field       │ Value                                               │
├─────────────┼─────────────────────────────────────────────────────┤
│ Type        │ new-required-request-parameter                      │
│ Description │ added the new required `query` request parameter    │
│             │ `limit`                                             │
└─────────────┴─────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Suspect Commits                                                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Commit   │ Author      │ Date       │ Message                    │ Files            │
├──────────┼─────────────┼────────────┼────────────────────────────┼──────────────────┤
│ c1cee2fb │ Test User   │ 2026-08-29 │ Initial commit: add route  │ routes/posts.py  │
└──────────┴─────────────┴────────────┴────────────────────────────┴──────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Change #2: GET /users                                            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Field       │ Value                                               │
├─────────────┼─────────────────────────────────────────────────────┤
│ Type        │ response-property-type-changed                      │
│ Description │ the `items/id` response's property `type` changed   │
│             │ from `integer` to `string` for status `200`         │
└─────────────┴─────────────────────────────────────────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Suspect Commits                                                  ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Commit   │ Author      │ Date       │ Message                    │ Files            │
├──────────┼─────────────┼────────────┼────────────────────────────┼──────────────────┤
│ c1cee2fb │ Test User   │ 2026-08-29 │ Initial commit: add route  │ routes/users.py  │
└──────────┴─────────────┴────────────┴────────────────────────────┴──────────────────┘

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Change #3: POST /users                                           ┃
┃ ... (5 more changes: POST/PUT /users, GET/PUT /users/{id})       ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Commands

```bash
# Basic usage
python -m main old.yaml new.yaml --repo-path /path/to/repo

# With custom route patterns (for non-standard project structures)
python -m main old.yaml new.yaml -r . -p "**/controllers/**/*.py" -p "**/api/**/*.ts"

# Save JSON report
python -m main old.yaml new.yaml -r . -o report.json

# Send to Slack (requires SLACK_BOT_TOKEN and SLACK_CHANNEL env vars)
python -m main old.yaml new.yaml -r . --slack --repo-url https://github.com/org/repo

# Use config file
cp config.yaml.example config.yaml
# edit config.yaml
python -m main old.yaml new.yaml -c config.yaml
```

## Configuration

Copy `config.yaml.example` to `config.yaml`:

```yaml
repo_path: "."
oasdiff_path: "oasdiff"
route_patterns:
  - "**/routes/**/*.py"
  - "**/controllers/**/*.py"
  - "**/handlers/**/*.py"
  - "**/api/**/*.py"
  - "**/*.py"  # fallback
slack:
  enabled: false
  token: ""
  channel: ""
  repo_url: ""
```

Environment variables: `SLACK_BOT_TOKEN`, `SLACK_CHANNEL`

## Tech Stack & Libraries Reused

| Library | Purpose | Why Not Custom |
|---------|---------|----------------|
| **oasdiff** | OpenAPI diffing | Gold standard, handles all edge cases (refs, polymorphism, etc.) |
| **GitPython** | Git operations | Mature, handles repo traversal, blame, log |
| **slack-sdk** | Slack API | Official, maintained by Slack |
| **Click** | CLI framework | Standard, composable, well-tested |
| **Rich** | Terminal formatting | Beautiful output, tables, panels |
| **PyYAML** | Config parsing | Standard library |

**Genuinely new code**: The `GitBlameAnalyzer` class that maps OpenAPI paths → route handler files → git commits. This mapping logic (path normalization, pattern matching, commit deduplication) is the unique contribution.

## Known Limitations

1. **Language-agnostic but pattern-based**: Route detection works best for Python (Flask/FastAPI/Django), Express, Spring. Add patterns for your framework.
2. **No semantic analysis**: Matches paths by string containment. May produce false positives for generic paths like `/users`.
3. **Single repo only**: Assumes API spec and implementation live in same repo. For multi-repo setups, run per-repo.
4. **oasdiff required**: Must install Go binary separately (not a Python package).
5. **No CI integration yet**: Designed as CLI; GitHub Action / GitLab CI template would be next.

## What's Next

- [ ] GitHub Action for PR checks
- [ ] Support for GraphQL schemas
- [ ] Semantic matching using AST parsing (tree-sitter)
- [ ] Multi-repo correlation via git submodules or monorepo detection
- [ ] Webhook receiver for automatic spec updates

## License

MIT