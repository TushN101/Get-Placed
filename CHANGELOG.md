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

**Status:** `NOT FIXED`  
**Reported:** November 11  
**Affected File:** `.agents/skills/find-jobs/SKILL.md`

### Description
When running the `find-jobs` skill, execution was sometimes attempted in an isolated cloud sandbox, remote container, or cloud subagent rather than directly in the user's local host environment. External job boards like FreeHire and LinkedIn block cloud and datacenter IP addresses, resulting in HTTP 403 Forbidden errors or anti-bot blocks.

### Root Cause
The `find-jobs` skill documentation (`.agents/skills/find-jobs/SKILL.md`) did not explicitly instruct agents to execute `scripts/fetch_jobs.py` directly on the local host machine, nor did it caution against running in cloud sandboxes or containers.

### Expected Resolution
- Update `.agents/skills/find-jobs/SKILL.md` to explicitly state that `scripts/fetch_jobs.py` must run directly on the user's local system via host terminal/command execution.
- Emphasize that cloud sandboxes, remote environments, and datacenter subagents must not be used because target services block datacenter IPs.

---

## Issue #004 — Sequential Scraper Execution Latency and Lack of Exponential Backoff

**Status:** `NOT FIXED`  
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

