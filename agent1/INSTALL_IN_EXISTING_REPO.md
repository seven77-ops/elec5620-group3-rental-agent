# Install or update Agent1 in the existing repository

This package contains only agent1. Keep it beside agent2, agent3, agent4 and integration. No teammate module, root configuration, Git history or PyCharm configuration is included.

## Updating an earlier Agent1 installation

1. Stop the running Agent1 process.
2. Back up your existing agent1 directory outside the repository. This preserves any local changes, model configuration, state database and generated reports.
3. Extract this package and place its clean agent1 directory in the repository root. The entry point must be agent1/main.py, not agent1/agent1/main.py.
4. If you have configured a private .env, copy it back from your backup. The package contains only .env.example.
5. You may also restore state/ if you need your previous sessions. Their original messages and reports retain their original language. Start a new session for the English demonstration.

There is no database schema migration in this release. Review your own source edits before replacing them. Do not copy an old module over the updated source files.

## Run on Windows

From the repository root, using the virtual environment that already works:

```powershell
.\.venv\Scripts\python.exe -m pip install -r agent1/requirements.txt
.\.venv\Scripts\python.exe agent1/main.py --demo
```

The demo no longer depends on the Windows default text encoding. Agent1 specifies UTF-8 for text-file reads and writes. The earlier -X utf8 workaround remains optional.

For manual confirmation:

```powershell
.\.venv\Scripts\python.exe agent1/main.py --manual --tenant Yirui
```

At You >, enter /load examples/demo-draft.json and /review. Check the preview, then use /confirm followed by the displayed token. Run /search to call Agent2, and /export to write the results.

For live extraction, configure agent1/.env and run without --manual or --demo. Live model behavior still needs verification. See README.md for example English input.

## Git workflow

Use your existing feature branch. For a first installation, a possible new branch is feature/agent1-yirui:

```powershell
git status
git switch -c feature/agent1-yirui
```

Do not recreate it if already on that branch. After reviewing and testing your changes:

```powershell
git add agent1
git diff --cached --stat
```

Only stage the intended files. agent1/.gitignore excludes credentials, state, generated reports and caches. Use the actual Jira number in the commit and PR title according to the team workflow. This package does not push or merge anything.

## Language boundary

Agent1-authored UI, documentation, tests and human-readable summaries are English. User input and saved historical records are preserved. Raw Agent2 JSON may still contain another language; changing those source explanations is the responsibility of Agent2. The English Markdown summary is generated entirely inside Agent1.
