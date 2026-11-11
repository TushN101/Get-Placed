---
name: find-jobs
description: Fetch fresh jobs by running the query script, sanity-check the results, remove jobs the user has already seen, filter out scams and mismatches (wrong location, wrong experience level), rank what is left and present it. Use when the user asks to find, scrape, refresh or show jobs, which is usually the start of a session.
---

# Find Jobs

Run the script, sanity-check what comes back, clean it up, rank it, save it, and show it. Keep it simple: **you do not fetch jobs yourself, the script does.**

## Files

| File | Use |
|---|---|
| `scripts/fetch_jobs.py` (in this skill's folder) | Python script that loads both query files, fetches every query and returns normalized, de-duplicated jobs as JSON. **Run it. Do not write your own fetcher or call the APIs by hand.** |
| `database/queries/freehireQueries.json` | Freehire queries (`FH01`, `FH02`, ...). Each has `query_id`, `query_description`, `query_url`. |
| `database/queries/linkedinQueries.json` | LinkedIn queries (`LN01`, `LN02`, ...), same shape. |
| `database/jobs/scrapedJobs.json` | Every job already seen or filtered. Used to avoid repeats and to save progress. |
| `database/user/userProfile.json` | Who the user is (skills, experience, level). |
| `database/user/userPrefs.json` | What the user wants (roles, locations, level, dealbreakers). |

## Workflow

## If you havent read "AGENTS.md" read that first to understand your role.

### Step 1: Load context

Read `userProfile.json`, `userPrefs.json` and `scrapedJobs.json` first, so you know what a *good* result looks like for this user before you see any results.

### Step 2: Run the script

Run `scripts/fetch_jobs.py` from this skill's folder. It finds the project root by itself, loads `freehireQueries.json` and `linkedinQueries.json`, calls every query, merges jobs found by several queries and prints one JSON document. It is read-only: it never writes to `database/`.

```bash
python3 scripts/fetch_jobs.py --out <scratch path>/jobs.json
```

Write the output to a scratch file and read that file, then delete it in the cleanup at the end. Useful flags: `--details` (also fetch LinkedIn job descriptions, slower, use it when LinkedIn jobs need an experience check), `--freehire-pages N`, `--linkedin-pages N`, `--root <path>`.

The JSON has:
- `jobs`: normalized jobs with `title`, `company`, `location`, `url`, `posted_at`, `work_mode`, `experience_years_min`, `skills`, `summary`, `query_ids` and, for Freehire jobs, a `reality` block (`repost_count`, `mass_posting_count`, `fake_freshness`) that helps spot scams and mass reposts. LinkedIn jobs have fewer fields unless you use `--details`.
- `stats`: per-query counts and errors.
- `warnings`: problems the script already noticed (a query that failed or returned 0 or very few jobs, a source with nothing).
- `totals`: raw and unique counts.

Note which `query_id` each job came from. The query descriptions tell you what each query was *meant* to return (for example `FH02` is a no-city fallback, so expect jobs outside Mumbai from it).

### Step 3: Sanity-check the results. Cancel if something is off.

Before processing anything, check whether the results are trustworthy. **If any of these happens, stop the operation.** Do not filter, do not save anything to `scrapedJobs.json`, do not present jobs. Report to the user instead.

- **The script fails or errors**, a whole source (Freehire or LinkedIn) returns nothing, or `warnings` reports a failed or empty query. Read `warnings` and `stats` first.
- **A suspiciously low count**, for example LinkedIn returning 1 or 2 jobs for queries that normally return dozens, or the whole run returning only a handful of jobs. Use judgment: a tiny result usually means a broken URL, wrong ID, rate limit or over-narrow query, not a real lack of jobs.
- **The jobs are the wrong kind of jobs.** For example most results are a different role or field than the user's profile and prefs (a Python/backend user getting sales, marketing or data-entry roles), or mostly senior roles for a fresher.
- **Results do not match the query's intent**, such as a Mumbai-only query returning mostly other cities.

When you cancel, tell the user:
- What you saw (counts per source or query, plus 2 or 3 example bad results).
- Which `query_id`s look responsible, if you can tell.
- That nothing was saved, and that **they can run `/debug-proj`** to investigate and fix the queries.
- There will always be false positives regardless of how good the queries are , but you shouldnt cancel all the time , only cancel when the number of false positives are more than 60-70% which signals a critical issues , or there is other issues of too less jobs or rate limiting.

Do not try to fix the queries yourself here. That is `/debug-proj`'s job.

### Step 4: Remove jobs the user has already seen

Compare the new jobs with `scrapedJobs.json` and drop any match. Match on the job URL or ID first, then on company + title + location. Also remove duplicates *within* this run (the same job from several queries or from both sources). Keep the best link.

### Step 5: Filter out the bad ones

Even jobs that were fetched by the user's queries can be wrong. Remove:

- **Location mismatches:** the user wants, for example, Mumbai only, but the job is in another city. Check the job's actual location, not just the query that found it. Respect `userPrefs.json` on remote and hybrid.
- **Experience mismatches:** the query was for junior or fresher roles but the job wants several years (for example 5 to 6+), or has senior, lead, staff, principal or manager in the title or requirements.
- **Wrong role:** the title or core duties do not match the user's target roles or skills.
- **Scams and junk:**
  - asks the candidate to pay money for anything, or promises guaranteed placement
  - vague description with unrealistic pay or "earn per day" language
  - contact only through WhatsApp or Telegram or a personal email address
  - no identifiable company, or one that looks fake
  - staffing or "bench" mills and mass reposts with no real client
  - requests for ID or bank details before any interview
- **Dealbreakers** from `userPrefs.json`.

If a job is borderline (probably fine but slightly suspicious), keep it and note the concern in its one-liner instead of dropping it.

### Step 6: Rank

Rank the remaining jobs, best first. Weigh:

1. **Company prestige and reputation:** well-known, strong, reputable companies first.
2. **Fit to the user:** how well the role and stack match `userProfile.json` and `userPrefs.json`.
3. **Freshness and role quality:** newer postings and clearer descriptions rank higher.

If it is a close call, fit to the user wins over brand name.

### Step 7: Save to `scrapedJobs.json` *before* presenting

Do this **now**, before showing anything, so progress survives if the conversation ends abruptly. Append every new job from this run:

- **Shown jobs** with `"status": "shown"`.
- **Filtered-out jobs** with `"status": "filtered"` and a short `"reason"` (for example `"not Mumbai"`, `"requires 5+ years"`, `"scam signals"`), so you do not re-evaluate them next time.

Follow the existing structure of `scrapedJobs.json`. If it is empty, use at least: `url` (or job ID), `company`, `title`, `location`, `source`, `query_id`, `date_seen` (`YYYY-MM-DD`), `status`, `reason`. Keep the JSON valid and never remove existing entries.

### Step 8: Present to the user

Show a compact list, best first, so the user can scan it fast:

| # | Company | Role | One-liner | Link |
|---|---|---|---|---|
| 1 | Company name | Role title | One short line on what the job is (only if useful) | [Apply / read more](url) |

- The one-liner is a quick hint about the actual job or a concern ("Backend on payments, Python/Django" or "Staffing firm, role is vague"). Skip it if the title says it all.
- Add a one-line summary under the table, for example: `Fetched 64 · 38 already seen · 14 filtered (6 wrong location, 5 too senior, 3 scam signals) · 12 shown.`
- If very few good jobs remain, say so honestly. Do not pad the list.

Then ask which jobs they want details on, or whether they want a tailored resume for any of them (`/draft-resume`).

## Rules

- **Run the script. Do not fetch jobs any other way.**
- **If results look wrong or too few, cancel, save nothing and point the user to `/debug-proj`.**
- **Save to `scrapedJobs.json` before presenting.**
- Never remove existing entries from `scrapedJobs.json`.
- Never invent job details. If a field is missing, leave it out.
- Keep the final message short and scannable.
