# Upgrade to Agent1 1.2.0

1. Exit any running Agent1 terminal with `/quit`.
2. Extract the update archive outside the repository. Copy its `agent1` folder into the repository root and merge folders, replacing files with the same names.
3. Do not delete the existing `agent1` directory. The update contains no `.env`, `state/` or `reports/` files; retain your settings, SQLite database and previous exports.
4. From the repository root, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s agent1/tests -v
.\.venv\Scripts\python.exe agent1/main.py --acceptance-demo
```

Expected: 52 tests pass, and every named check in the acceptance scenario reports `passed`.

The existing database format is unchanged. No new dependency is required. Only Agent1 files are included; keep Agent2 beside Agent1.

For the existing confirmed case from 18 October, you can later resume it:

```powershell
.\.venv\Scripts\python.exe agent1/main.py --manual --case case-677dadaab9614e8ba45405e8133c636b
```

At the `You >` prompt, enter `/history`, `/compare 2`, or `/export` individually. The comparison should use versions 2 and 3 on the original snapshot. Do not paste the `You >` prompt itself.

Use `/recover-confirmed` only for an old session still stuck in ProcessingError with an unchanged confirmed draft. It is not needed for the already recovered version-3 case.

Keep Jira tasks in progress until their remaining acceptance checks and actual team joint testing are complete. The local verification records are not evidence of a Sprint Review.
