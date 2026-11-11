# Issues & Changelog

This document tracks known issues, bugs, and pending fixes in the Get-Placed project.

---

## Issue #001 — Incorrect LinkedIn GEO ID for Mumbai

**Status:** `FIXED`  
**Reported:** November 11  
**Affected File:** `database/queries/linkedinQueries.json`

### Description
The LinkedIn job-search queries may or may not be using an incorrect GEO ID for Mumbai.

This could result in job searches returning incorrect locations, missing relevant Mumbai-based opportunities, or retrieving jobs from unintended regions.

### Expected Resolution
- Verify the currently configured GEO ID whethers its wrong or actaully correct.
- Cross-check it against LinkedIn's actual geographic location data.
- Replace it with the correct Mumbai GEO ID, if necessary.

### Resolution
Verified live against LinkedIn's `typeaheadHits?typeaheadType=GEO&query=Mumbai` API: the 14 Mumbai queries previously used `location=Mumbai` (no `geoId`), while 29 fallback/remote queries used `geoId=102713980` (All of India), returning 85–100% non-Mumbai cities. LinkedIn's official Geo IDs are `106164952` (`Mumbai, Maharashtra, India`) and `90009639` (`Mumbai Metropolitan Region`, covering Mumbai, Navi Mumbai, and Thane). Replaced `location=Mumbai` and removed `geoId=102713980` queries in `database/queries/linkedinQueries.json`, scoping all 22 retained queries to `geoId=90009639`. Verified live: 273/273 (100%) of returned LinkedIn jobs are in the Mumbai Metropolitan Region. Fixed on November 11.

---

## Issue #002 — FreeHire Missing Seniority-Level Metadata

**Status:** `FIXED`  
**Reported:** November 11  
**Affected File:** `database/queries/freehireQueries.json`

### Description
FreeHire job postings may not always include a seniority-level field in their responses.

Currently, restricting queries to junior-level positions could unintentionally exclude relevant opportunities where the seniority level is simply missing or not specified in the job posting.

This means potentially good fresher and entry-level opportunities could be missed even when their actual requirements are suitable for the user.

### Expected Resolution
- Review how seniority-level filters are applied to FreeHire queries.
- Avoid relying exclusively on the seniority-level metadata when filtering results.
- Consider retrieving a broader range of listings and evaluating their experience requirements using the job description itself.
- Ensure that genuinely senior-level positions are still filtered out during post-retrieval job evaluation.

**Important:** A missing seniority-level field should not automatically disqualify an otherwise relevant job posting.

### Resolution
Updated all non-intern queries in `database/queries/freehireQueries.json` to combine `seniority=intern,junior&seniority_include_unspecified=true` with `experience_years_max=2&experience_include_unspecified=true` (keeping postings whose `seniority` or `experience` fields are unset while excluding `>2` yr and `senior`/`lead` roles at the API level). Verified live across all 23 FreeHire queries: `exp > 2` results dropped from 798/2,436 (32.8%) to 2/1,047 (0.2%), while preserving entry-level roles with unset seniority metadata. Fixed on November 11.

---

## Issue #003 — Scraper Execution Attempted in Cloud/Sandbox Environments

**Status:** `FIXED`  
**Reported:** November 11  
**Affected File:** `.agents/skills/find-jobs/SKILL.md`

### Description
When running the `find-jobs` skill, execution was sometimes attempted in an isolated cloud sandbox, remote container, or cloud subagent rather than directly in the user's local host environment. External job boards like FreeHire and LinkedIn block cloud and datacenter IP addresses, resulting in HTTP 403 Forbidden errors or anti-bot blocks.

### Root Cause
The `find-jobs` skill documentation (`.agents/skills/find-jobs/SKILL.md`) did not explicitly instruct agents to execute `scripts/fetch_jobs.py` directly on the local host machine, nor did it caution against running in cloud sandboxes or containers.

### Expected Resolution
- Update `.agents/skills/find-jobs/SKILL.md` to explicitly state that `scripts/fetch_jobs.py` must run directly on the user's local system via host terminal/command execution.
- Emphasize that cloud sandboxes, remote environments, and datacenter subagents must not be used because target services block datacenter IPs.

### Resolution
Updated `.agents/skills/find-jobs/SKILL.md` in Step 2 and the Rules section to explicitly require running `scripts/fetch_jobs.py` directly on the host machine in the user's local shell environment. Added prominent notices specifying that cloud sandboxes, remote containers, and datacenter subagents must never be used because target services block datacenter IPs. Fixed on November 11.

---

## Issue #004 — Sequential Scraper Execution Latency and Lack of Exponential Backoff

**Status:** `FIXED`  
**Reported:** November 11  
**Affected File:** `.agents/skills/find-jobs/scripts/fetch_jobs.py`

### Description
The scraping script executes all 86 queries (43 FreeHire + 43 LinkedIn) sequentially one-by-one with pagination and delay sleeps. This creates over 200 sequential HTTP requests, causing execution to take 10 to 15+ minutes. Furthermore, retries rely on simple linear delays without exponential backoff or jitter, and do not handle HTTP 403 rate-limiting responses.

### Root Cause
`fetch_jobs.py` processes each query and page synchronously in a single thread loop. Network request retries in `http_get()` use linear scaling (`2 * (attempt + 1)`) without exponential backoff or randomized jitter, and do not back off on 403 responses.

### Expected Resolution
- Introduce controlled multi-threading via `concurrent.futures.ThreadPoolExecutor` to process queries concurrently while keeping memory and socket usage safe and standard-library only.
- Implement domain-specific concurrency limits / pacing to prevent triggering HTTP 403 rate limits or IP blocks.
- Refactor `http_get()` to use true exponential backoff with randomized jitter on transient HTTP errors (429, 403, 5xx) and network/socket exceptions.
- Ensure thread-safe logging and stats aggregation.
- Verify execution time improves significantly while queries still return valid results without 403 errors.

### Resolution
Refactored `.agents/skills/find-jobs/scripts/fetch_jobs.py` using standard-library `concurrent.futures.ThreadPoolExecutor`:
1. Introduced domain-aware concurrency (`--freehire-workers 4`, `--linkedin-workers 3` or configurable via `--workers`) with inter-request delays and jitter to prevent triggering rate-limit blocks.
2. Updated `http_get()` to implement true exponential backoff with randomized jitter on HTTP 403, 429, 5xx, and network errors, respecting `Retry-After` response headers.
3. Added thread-safe output logging and stats aggregation preserving query ordering.
4. Verified with a full live test across all 86 queries: total execution time dropped from 10+ minutes to ~28 seconds, successfully fetching 1,054 unique jobs with 0 failed queries. Fixed on November 11.

---

## Issue #005 — Unwanted Remote and All-India Queries Violate Mumbai-Only Preference

**Status:** `FIXED`  
**Reported:** November 11  
**Affected Files:** `database/queries/freehireQueries.json`, `database/queries/linkedinQueries.json`, `database/user/userProfile.json`

### Description
`database/user/userPrefs.json` specifies `"location_preference": "Mumbai, India"` and `"open_to_remote": false`. However, a full `/find-jobs` run on November 11 fetched 2,436 unique jobs where **1,888 (77.5%)** were outside Mumbai (including global remote jobs outside India) and **695 (28.5%)** were `remote`, resulting in a ~90.7% false-positive rate.

### Root Cause
1. `database/user/userProfile.json` still listed `"Remote"` in `preferences.preferred_locations` (`["Mumbai, India", "Remote"]`), conflicting with `userPrefs.json` (`open_to_remote: false`).
2. 65 of 86 queries (36/43 FreeHire, 29/43 LinkedIn) used `work_mode=remote`, `countries=IN`, `f_WT=2`, or `geoId=102713980` (All of India) instead of scoping to Mumbai (`FH02`, `FH03`, `FH05`–`FH11`, `FH13`–`FH17`, `FH19`–`FH22`, `FH24`–`FH32`, `FH34`–`FH37`, `FH39`–`FH43`, and `LN02`, `LN03`, `LN05`, `LN06`, `LN08`, `LN10`, `LN12`–`LN15`, `LN17`, `LN18`, `LN20`, `LN22`–`LN27`, `LN29`, `LN30`, `LN32`, `LN34`, `LN36`, `LN37`, `LN39`–`LN41`, `LN43`).
3. Live testing also showed FreeHire treats combining `cities=Mumbai` with `countries=IN` as a widening OR filter (returning 8,163 all-India jobs across Hyderabad, Chennai, Gurugram, and Delhi).

### Expected Resolution
- Remove `"Remote"` from `preferences.preferred_locations` in `database/user/userProfile.json`.
- Remove all `work_mode=remote` and `countries=IN` queries from `database/queries/freehireQueries.json`, replacing all retained target roles with Mumbai-metro queries (`cities=Mumbai,Navi%20Mumbai,Thane` without `countries=IN` or `work_mode=remote`).
- Remove all `f_WT=2` (remote) and all-India `geoId=102713980` queries from `database/queries/linkedinQueries.json`, scoping every query to Mumbai Metropolitan Region (`geoId=90009639`) with `f_WT=1,3` (onsite + hybrid).
- Verify all queries return predominantly Mumbai-area, non-remote jobs.

### Resolution
Removed `"Remote"` from `preferences.preferred_locations` in `database/user/userProfile.json` (`["Mumbai, India", "Remote"]` → `["Mumbai, India"]`), removed all remote and all-India queries from `freehireQueries.json` (43 → 23 Mumbai Metro queries using `cities=Mumbai,Navi%20Mumbai,Thane` with no `countries=IN` or `work_mode=remote`) and `linkedinQueries.json` (43 → 22 Mumbai Metro queries using `geoId=90009639&f_WT=1,3`). Verified with a live full run: Mumbai location match jumped from 22.5% to 94.0% (`984/1,047`) and `remote` dropped from 28.5% to 5.2% (`54/1,047`). Fixed on November 11.

---

## Issue #006 — FreeHire Substring Keyword Bugs (`q=intern`, `q=c++`) & Missing Category/Experience Caps

**Status:** `FIXED`  
**Reported:** November 11  
**Affected File:** `database/queries/freehireQueries.json`

### Description
Even within Mumbai-targeted FreeHire queries, 71.2% (299/420) of results failed basic relevance checks on November 11:
- `FH38` (`q=intern&q_fields=title&cities=Mumbai`) had **88% false positives** (`53/60`), returning *International Voice Customer Support*, *Chartered Accountant - Internal Audit*, *Head - Human Resource* (13 yrs), and *Physics Teacher for International Curriculum*.
- `FH18` (`q=c++&q_fields=title&cities=Mumbai`) had **78% false positives** (`47/60`), returning *P&C Insurance Operations Specialist*, *EY Manager (C&I)*, and *Chartered Accountant*.
- `FH04` (`skills=python&cities=Mumbai`) had **82% false positives** (`49/60`, with `42/60` requiring >2 yrs experience), and `FH01`, `FH12`, `FH23`, `FH33` allowed senior (`3–15+` yrs) and non-tech roles through.

### Root Cause
1. `FH38` used raw keyword `q=intern` without a tech `category`, matching `"Internal"` and `"International"` across unrelated fields.
2. `FH18` used `q=c++` (FreeHire strips `++`, effectively searching `q=c` and matching any `C` token like `P&C`, `C&I`, `Chartered`).
3. `FH04`, `FH18`, and `FH33` lacked `experience_years_max=2&experience_include_unspecified=true` and `seniority` filters, while `FH01`, `FH12`, and `FH23` used `seniority_include_unspecified=true` without `experience_years_max=2` (allowing high-experience postings lacking seniority tags).

### Expected Resolution
- Replace `q=intern` in internship queries with `seniority=intern` plus explicit tech `category` filters.
- Replace `q=c++` with `skills=cpp` plus tech `category=backend,software_engineering`.
- Add `experience_years_max=2&experience_include_unspecified=true` (paired with `seniority=intern,junior&seniority_include_unspecified=true` and tech `category` filters where missing) across Mumbai FreeHire queries so entries lacking seniority metadata remain included (per Issue #002) while `>2` yr postings are filtered out.
- Re-run live tests to verify `exp > 2` and non-tech noise drop sharply.

### Resolution
Replaced `q=intern` with `seniority=intern` + tech `category` filters (`FH07`, `FH14`, `FH17`, `FH20`), replaced `q=c++` with `skills=cpp&category=backend,software_engineering` (`FH11`), scoped `skills=python` to tech categories (`FH02`), and added `experience_years_max=2&experience_include_unspecified=true` across Mumbai FreeHire queries. Verified live: `FH20` (tech internships) improved from 12% to 81% pass rate (`48/59`), `FH11` (C++) improved from 22% to 59% (`16/27`), `FH02` (Python) improved from 18% to 72% (`43/60`), and non-tech noise across all 1,047 jobs dropped to 2.4%. Fixed on November 11.

---

## Issue #007 — LinkedIn Pagination Stops at Page 1 (`LINKEDIN_PAGE_SIZE = 25`) & Senior Roles Leak Through `f_E=2,3`

**Status:** `FIXED`  
**Reported:** November 11  
**Affected Files:** `.agents/skills/find-jobs/scripts/fetch_jobs.py`, `database/queries/linkedinQueries.json`

### Description
Every LinkedIn query returned at most 10 jobs (`pages: 1`) despite `--linkedin-pages 2` being the default, and Mumbai LinkedIn queries like `LN04` (80% senior titles), `LN11` (70%), `LN21` (70%), `LN28` (60%), and `LN42` (60%) returned mostly senior, Lead, VP, and Software Engineer II postings.

### Root Cause
1. LinkedIn's `seeMoreJobPostings/search` guest endpoint returns **10** cards per page, whereas `LINKEDIN_PAGE_SIZE` in `fetch_jobs.py` was hardcoded to `25`, causing `if len(cards) < LINKEDIN_PAGE_SIZE: break` to terminate pagination after page 1. Live testing of `start=0` (10 jobs) vs `start=10` (10 jobs) showed 0 overlap and valid page-2 results.
2. `linkedinQueries.json` used `f_E=2,3` (Entry level + Associate) with no negative title keywords, and LinkedIn's search index classifies many `Senior`/`Lead`/`Mid-Senior`/`Not Applicable` roles under `f_E=2,3` (confirmed live on job `4482996029` and `4481273790`).

### Expected Resolution
- Update `LINKEDIN_PAGE_SIZE = 10` in `.agents/skills/find-jobs/scripts/fetch_jobs.py`.
- Tighten `linkedinQueries.json` from `f_E=2,3` to `f_E=1,2` (and `f_E=1&f_JT=I` for internships) and add live-verified `NOT Senior NOT Lead NOT Principal NOT Manager` keyword exclusions where LinkedIn's parser supports them cleanly.
- Verify LinkedIn queries fetch 2 pages (`start=0`, `start=10`) with markedly fewer senior titles.

### Resolution
Updated `LINKEDIN_PAGE_SIZE` from `25` to `10` in `.agents/skills/find-jobs/scripts/fetch_jobs.py`, and updated `linkedinQueries.json` to use `f_E=1,2` (and `f_E=1&f_JT=I` for internships) plus `NOT Senior NOT Lead NOT Principal NOT Manager` exclusions where supported. Verified with a full live run: all 22 LinkedIn queries fetched 2 pages (`start=0` and `start=10`), yielding 273 unique jobs with `228/273` (83.5%) passing basic Mumbai + non-senior checks (and 0 warnings/errors). Fixed on November 11.

---

## Issue #008 — AI Roles Requiring Model Building, Fine-Tuning, or Custom ML Not Excluded

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected Files:** `database/user/userPrefs.json`, `.agents/skills/find-jobs/scripts/filter_jobs.py`, `.agents/skills/find-jobs/SKILL.md`

### Description
The `/find-jobs` run surfaced AI/ML postings requiring model training, fine-tuning, reinforcement learning, or custom ML research (e.g., `CashFlo — AI Engineer` listing `fine-tuning`, alongside `ML Engineer`, `LLMOps`, and model-training postings). The user only has experience using chatbots, LLM APIs, and building small agents, with no fine-tuning or custom ML training background.

### Root Cause
`database/user/userPrefs.json` did not distinguish applied LLM/chatbot/agent API integration from ML model training or fine-tuning, and the filtering workflow had no rule excluding fine-tuning, custom ML model development, or ML research roles.

### Expected Resolution
- Document the user's AI scope in `database/user/userPrefs.json` (applied chatbots/LLM APIs/small agents only; exclude model building, fine-tuning, custom ML training, RL, MLOps model serving).
- Enforce exclusion rules for model-building/fine-tuning/custom-ML roles in `.agents/skills/find-jobs/scripts/filter_jobs.py` and `.agents/skills/find-jobs/SKILL.md`, while preserving applied LLM/chatbot/agent integration internships.
- Verify against sample AI postings that fine-tuning/training/ML research roles are filtered out while applied LLM/agent internships remain.

---

## Issue #009 — Google Sheet Tracker Consulted and Used to Filter Out Jobs During `/find-jobs`

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected Files:** `AGENTS.md`, `.agents/skills/find-jobs/SKILL.md`, `.agents/skills/find-jobs/scripts/filter_jobs.py`

### Description
During `/find-jobs`, the Google Sheet application tracker (`Mastersheet`) was read and used to drop `ION — Software Developer, 2027 Leadership Development Program` because of a past campus rejection entry. The user wants `/find-jobs` never to read or filter using the Google Sheet; the sheet is solely for explicit tracking requests.

### Root Cause
`AGENTS.md` instructed "Check the sheet to know what the user has already applied to" without scoping it strictly to explicit tracking actions, and `.agents/skills/find-jobs/SKILL.md` lacked an explicit prohibition against consulting the Google Sheet during job scraping and filtering.

### Expected Resolution
- Update `AGENTS.md` under `Application Tracking` so the Google Sheet is only accessed when the user explicitly asks to check or update application tracking, never during `/find-jobs`.
- Add an explicit rule in `.agents/skills/find-jobs/SKILL.md` forbidding any Google Sheet lookup or exclusion during `/find-jobs`.
- Keep `.agents/skills/find-jobs/scripts/filter_jobs.py` strictly local (`userProfile.json`, `userPrefs.json`, `scrapedJobs.json` only).

---

## Issue #010 — Two-Pass LinkedIn Detail Fetch, HTTP 429 Bursts, and Slow Manual Filtering (~12 min Total)

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected Files:** `.agents/skills/find-jobs/scripts/fetch_jobs.py`, `.agents/skills/find-jobs/scripts/filter_jobs.py`, `.agents/skills/find-jobs/SKILL.md`

### Description
A full `/find-jobs` session took ~12 minutes: `fetch_jobs.py` defaulted `--details` off (forcing a second full 45-query pass + 273 detail fetches taking ~3 minutes with 14 HTTP `429` retries), and the remaining ~8 minutes went to repeated ad-hoc manual filtering passes.

### Root Cause
1. `fetch_jobs.py` defaulted `--details` to `False` and `--details-limit` to `40`, requiring a separate second run to inspect LinkedIn job descriptions and experience requirements.
2. In `add_linkedin_details()`, `details_workers = min(linkedin_workers, 3)` sent un-staggered bursts immediately after search with `time.sleep(delay)` only *after* each request and no global rate limiter, triggering 14 HTTP `429` responses across 273 requests. Live testing confirmed 15 sequential `jobPosting/{id}` requests spaced at `1.2s` succeed 15/15 (100%) with 0 HTTP `429`s in `26.2s`.
3. `fetch_jobs.py` fetched details for all 273 LinkedIn results without pre-skipping already-seen (`scrapedJobs.json`) or clearly disqualified titles.
4. `.agents/skills/find-jobs/` lacked a deterministic filtering script, causing repeated manual inspection scripts and inconsistent passes.

### Expected Resolution
- Update `fetch_jobs.py` to fetch LinkedIn descriptions in **one single run** by default (`--no-details` to disable, default `--details-limit 120`), skipping jobs already in `scrapedJobs.json` (unless `--include-seen`) and clearly senior/non-matching titles before calling `jobPosting/{id}`, and enforcing a thread-safe global minimum request interval (`>= 1.2s` + jitter) with post-search cooldown so HTTP `429` bursts do not occur.
- Add `.agents/skills/find-jobs/scripts/filter_jobs.py` to perform fast, deterministic deduplication, rule-based filtering, borderline flagging (preventing silent drops of viable roles), ranking, and optional saving to `scrapedJobs.json`.
- Update `.agents/skills/find-jobs/SKILL.md` to run the single-pass `fetch_jobs.py` + `filter_jobs.py` pipeline.

---

## Issue #011 — Semester-8 Focus (6-Month Internships / Internships with PPO Only) & Excessive Irrelevant Query Noise (873/1,046 Filtered)

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected Files:** `database/user/userPrefs.json`, `database/queries/freehireQueries.json`, `database/queries/linkedinQueries.json`, `.agents/skills/find-jobs/scripts/filter_jobs.py`, `.agents/skills/find-jobs/SKILL.md`, `database/jobs/scrapedJobs.json`

### Description
In the November 11 `/find-jobs` run, 873 of 1,046 fetched jobs (83.5%) were filtered out, and most returned openings were full-time jobs requiring completed degrees or 1–3+ years of experience. The user has finished Semester 7 and needs a **pure 6-month internship** or **internship with PPO** for Semester 8.

### Root Cause
1. Per-query audit of `scrapedJobs.json` showed 19/23 FreeHire queries (`FH01–FH06`, `FH08–FH13`, `FH15–FH16`, `FH18–FH19`, `FH21–FH23`) yielded only `0%–8.5%` shown results (`FH04`, `FH06`, `FH09`, `FH10`, `FH11`, `FH12`, `FH23` yielded `0`), and 18/22 LinkedIn queries lacked internship targeting (`LN03`, `LN09`, `LN11`, `LN14`, `LN17–LN19`, `LN22` each yielded `0/20`).
2. `database/user/userPrefs.json` listed `"experience_level": "Entry-level / Junior"` with no Semester-8 / 6-month internship / PPO constraint.
3. Live probing showed FreeHire `seniority=intern` and `employment_type=internship` each miss 14 valid tech internships caught by the other (59 + 59 -> 73 union across tech categories), plus uncategorized tech-skill internships and `q=pre-placement`/`"6 months"` return additional matches; on LinkedIn, simple `keywords=<Role> Intern` with `f_E=1&f_JT=I` returns clean internships (whereas `OR`/`NOT` operators break `f_JT=I`), and `f_E=1,2` `(Role) AND (Intern OR Internship)` / `(PPO OR "6 months" OR "6-month")` catches startup internships misfiled as Full-time.

### Expected Resolution
- Update `database/user/userPrefs.json` to specify Semester-8 internship-only preference (`6-month internship` or `internship with PPO`).
- Replace noisy full-time queries in `database/queries/freehireQueries.json` and `database/queries/linkedinQueries.json` with live-verified Mumbai Metro internship, 6-month internship, and PPO queries across the user's target domains.
- Enforce internship / PPO / trainee / apprentice eligibility in `.agents/skills/find-jobs/scripts/filter_jobs.py` and `.agents/skills/find-jobs/SKILL.md` (excluding regular full-time graduate/experienced jobs and short 1–3 month summer internships where explicitly shorter than 6 months, while flagging unclear duration for review).
- Empty `database/jobs/scrapedJobs.json` as requested so the user can verify with a fresh `/find-jobs` run, and verify live query run speed, 0 `429` errors, and high internship signal rate (without polluting `scrapedJobs.json` during testing).
