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
