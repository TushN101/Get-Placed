# Issues & Changelog

This document tracks known issues, bugs, and pending fixes in the Get-Placed project.

---

## Issue #001 — Incorrect LinkedIn GEO ID for Mumbai

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected File:** `database/queries/linkedinQueries.json`

### Description
The LinkedIn job-search queries may or may not be using an incorrect GEO ID for Mumbai.

This could result in job searches returning incorrect locations, missing relevant Mumbai-based opportunities, or retrieving jobs from unintended regions.

### Expected Resolution
- Verify the currently configured GEO ID whethers its wrong or actaully correct.
- Cross-check it against LinkedIn's actual geographic location data.
- Replace it with the correct Mumbai GEO ID, if necessary.

---

## Issue #002 — FreeHire Missing Seniority-Level Metadata

**Status:** `NOT FIXED`  
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

**Status:** `NOT FIXED`  
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

---

## Issue #006 — FreeHire Substring Keyword Bugs (`q=intern`, `q=c++`) & Missing Category/Experience Caps

**Status:** `NOT FIXED`  
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

---

## Issue #007 — LinkedIn Pagination Stops at Page 1 (`LINKEDIN_PAGE_SIZE = 25`) & Senior Roles Leak Through `f_E=2,3`

**Status:** `NOT FIXED`  
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
