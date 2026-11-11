---
name: debug-proj
description: Diagnose and fix bugs in the Get-Placed project, most often bad job results caused by wrong or badly tuned queries. Use when the user reports wrong, irrelevant, missing or repeated jobs, a broken query, or anything that looks wrong. Logs each issue in CHANGELOG.md, makes a git checkpoint commit, applies the fix, verifies it, cleans up and reports back.
---

# Debug Project

Find what is wrong, write it down, checkpoint it in git, fix it, verify it, clean up, and tell the user what happened.

The usual cause of bad results is the **queries** in `database/queries/`: too broad (junk and senior roles come through), too narrow (few or no results), or misconfigured (wrong location ID, experience level, time window, keywords). But the bug can be anywhere in the project, so scan before assuming.

## Files this skill touches

| File | Use |
|---|---|
| `CHANGELOG.md` | The log of every issue, its diagnosis and its status. Read it first, write to it, update it last. |
| `database/queries/freehireQueries.json` | Freehire API URLs, one per target role. |
| `database/queries/linkedinQueries.json` | LinkedIn public API URLs, one per target role. |
| `database/user/userProfile.json` | Who the user is. Used to judge whether queries fit them. |
| `database/user/userPrefs.json` | What the user wants (roles, locations, level, dealbreakers). |
| `database/jobs/scrapedJobs.json` | Jobs already shown. Evidence of what the bug looks like. **Do not pollute it with test data.** |

## Workflow

Follow these steps in order. Do not skip the log, the commit or the verification.

### Step 1: Understand the report and read existing issues

1. Read what the user said is wrong. If it is too vague to investigate ("it's broken"), ask **one** short question (what they saw versus what they expected). Otherwise start.
2. Read `CHANGELOG.md`. If the report matches an existing issue, **reuse that issue number** instead of creating a duplicate.
3. Check that the project is a git repository (`git status`). If it is not, tell the user and ask whether to run `git init` before continuing. Do not continue without a way to checkpoint.

### Step 2: Scan and pinpoint the cause

Investigate with evidence, not guesses. Read the files above, then look for the cause.

**For bad job results, check each query against the user's profile and prefs:**
- **Keywords:** too generic (pulls in unrelated roles) or too exact (pulls in almost nothing)? Do they match the user's target roles?
- **Location:** is the location parameter or geo ID the right one for the city the user wants? Do not trust a geo ID from memory. Verify it by checking what the live response actually returns.
- **Experience level:** is the level filter right for the user (fresher or early-career), or are senior roles slipping through?
- **Time window and pagination:** too short a window returns little; no limit returns stale jobs.
- **Work mode, job type and other filters:** do they match `userPrefs.json`?
- **URL health:** does it still return a valid response, or is it broken, expired or rate-limited?
- **Dedupe or storage problems:** repeated jobs usually mean the match logic against `scrapedJobs.json` is wrong, not the query.

**Confirm the cause by testing:** run the suspect query once (read-only) and inspect the results. Look at title, location, seniority and company of a sample, and compare with what the user expects. A suspected cause only counts as an issue once you have evidence for it.

If a suspicion turns out to be fine (for example the geo ID is actually correct), still log it with the result so it is not re-investigated. Mark it `FIXED` with the note "verified correct, no change needed".

### Step 3: Log the issues in `CHANGELOG.md`

Before changing any project file, write every issue found into `CHANGELOG.md`, using the existing format and the next free number (`#001`, `#002`, and so on). Add each new issue at the end, with the status `NOT FIXED`.

```markdown
## Issue #00N — Short, specific title

**Status:** `NOT FIXED`
**Reported:** <Month Day>
**Affected File:** `path/to/file`

### Description
What is wrong, how it shows up for the user, and the evidence you found
(for example: "12 of 20 results for the backend query were senior roles; the query has no experience filter").

### Root Cause
The pinpointed cause, backed by your test.

### Expected Resolution
- Concrete steps to fix it, specific enough to follow without guessing.
- How to verify the fix worked.

---
```

Keep entries factual and short. One issue per distinct root cause. Do not merge unrelated problems.

### Step 4: Checkpoint commit

Create a git commit **before** applying any fix, so the user can roll back.

- Stage only what matters: `CHANGELOG.md` and the files you are about to modify. **Never use `git add -A` or `git add .`** because that would sweep in the user's unrelated work.
- Commit message format, listing the issue numbers being fixed:

  ```
  Fixing the bugs: issue 001, issue 003
  ```

- Do **not** push. Do not change git config or amend or rewrite history.
- If the commit fails (nothing to commit, hooks, identity not set), say what happened and fix the cause or ask the user. Do not continue to Step 5 without a successful checkpoint.
- Note the short commit hash for the final summary.

### Step 5: Apply the fixes from the changelog

Work through the issues you logged, following each issue's **Expected Resolution**.

- Change only the files named in the issue. If you discover a new problem mid-fix, stop, add it to `CHANGELOG.md` as a new issue and handle it properly instead of fixing it silently.
- Keep JSON valid. Preserve the existing structure, key names and ordering of the query files.
- If a fix needs information only the user has (a preference, a target city, a role), ask once, then continue.
- If a fix is large or changes the user's search strategy (for example removing a role from the queries entirely), describe the change and confirm before applying it.

### Step 6: Verify

Do not trust the edit. Prove it worked.

1. **Syntax:** every JSON file you touched parses correctly.
2. **Behavior:** re-run each affected query (read-only) and check the results against the issue's description. Examples: the senior roles are gone, the location is right, the result count is reasonable, the response is valid.
3. **Regression:** spot-check one or two queries you did not change to confirm they still work.
4. If a fix did not work, go back to Step 2 for that issue. Do not mark it fixed. After two failed attempts, mark it `NOT FIXED`, record what you learned and tell the user honestly.

### Step 7: Clean up

Remove everything you created along the way that is not part of the fix:
- Temporary files, scratch scripts, saved test responses and debug output.
- Any test results that ended up in `database/jobs/scrapedJobs.json` during verification. Restore that file to its state before the debugging session if it changed.
- Leftover commented-out or duplicated query entries.

Check with `git status` and `git diff` that the only changes are the intended fixes and the `CHANGELOG.md` update.

### Step 8: Update `CHANGELOG.md`

For each issue, update the entry:
- `**Status:**` set to `FIXED`, or left `NOT FIXED` with a reason.
- Add a **Resolution** section: what was changed (old value to new value where useful), the verification result, and the date.

```markdown
### Resolution
Replaced the Mumbai geo ID in all LinkedIn queries (`<old>` → `<new>`). Re-ran the
queries: all results are now in Mumbai. Fixed on <Month Day>.
```

### Step 9: Deliver the summary

Tell the user, briefly:

- **Issues found and fixed:** one line each, giving the number, the problem and the fix.
- **Issues not fixed** (if any), with the reason.
- **Verification:** what you re-ran and what you saw.
- **Rollback point:** the checkpoint commit hash, and that the fixes are currently uncommitted so the user can review the diff. Offer to commit them if they want.
- A suggestion to re-run `/find-jobs` to see the improved results.

Keep it short. The details are in `CHANGELOG.md`.

## Rules

- **Log before fixing, and commit before fixing.** The order is: log → commit → fix → verify → clean up → update log → report.
- **Evidence over guesses.** Never change a query because it "looks wrong". Show that it is wrong.
- **Never trust remembered IDs or parameters** (geo IDs, experience codes). Verify them against live responses.
- **Smallest safe change.** Fix the cause, not the whole file.
- **No duplicates in the changelog.** Reuse an existing issue number when the problem is the same.
- **Never delete or rewrite user data** (`userProfile.json`, `userPrefs.json`, `scrapedJobs.json`) except where an issue's fix explicitly requires it, and then only with the user's confirmation.
- **No pushing, no history rewriting, no `git add -A`.**
- **Make good use of changelog.md to see what the past bugs where and how was it fixed**
- **Be honest.** If you could not reproduce or fix something, say so and leave the status as `NOT FIXED`.
