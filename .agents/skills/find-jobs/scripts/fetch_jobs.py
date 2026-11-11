#!/usr/bin/env python3
"""
fetch_jobs.py - Get-Placed job fetcher (used by the find-jobs skill).

Loads database/queries/freehireQueries.json and linkedinQueries.json, calls every
query, normalizes the results into one common format, de-duplicates jobs found by
several queries and prints a single JSON document.

This script is READ-ONLY with respect to the project: it never writes to
database/. The agent decides what to keep and saves to scrapedJobs.json itself.

Usage:
    python3 fetch_jobs.py                      # JSON to stdout, progress on stderr
    python3 fetch_jobs.py --out /tmp/jobs.json # JSON to a file instead
    python3 fetch_jobs.py --details            # also fetch LinkedIn job descriptions
    python3 fetch_jobs.py --root /path/to/Get-Placed

Concurrency & Backoff options:
    --freehire-workers N  (default 4)
    --linkedin-workers N  (default 3)
    --workers N           (override concurrency for all sources)
    --delay S             (seconds between requests per worker, default 1.0)
    --retries N           (retries with exponential backoff on 403/429/5xx, default 4)

Output shape:
    {
      "fetched_at": "...",
      "stats":    [ {query_id, source, description, fetched, reported_total, pages, error}, ... ],
      "warnings": [ "human readable problem", ... ],
      "totals":   {"raw": N, "unique": N, "by_source": {...}},
      "jobs":     [ {normalized job}, ... ]
    }

Only the Python standard library is used.
"""

import argparse
import html
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
LINKEDIN_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
LINKEDIN_PAGE_SIZE = 25
SUMMARY_CHARS = 500

_log_lock = threading.Lock()


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #

def log(msg):
    with _log_lock:
        print(msg, file=sys.stderr, flush=True)


class FetchError(Exception):
    pass


def find_root(explicit):
    """Locate the project root (the folder that contains database/queries)."""
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if not (root / "database" / "queries").is_dir():
            sys.exit(f"error: {root} has no database/queries folder")
        return root
    here = Path(__file__).resolve()
    for p in [here.parent, *here.parents]:
        if (p / "database" / "queries").is_dir():
            return p
    cwd = Path.cwd().resolve()
    for p in [cwd, *cwd.parents]:
        if (p / "database" / "queries").is_dir():
            return p
    sys.exit("error: could not find the project root (use --root)")


def load_queries(path):
    """Return the list of queries in a query file, or raise FetchError."""
    if not path.is_file():
        raise FetchError(f"missing query file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise FetchError(f"invalid JSON in {path.name}: {e}")
    queries = data.get("queries") if isinstance(data, dict) else None
    if not isinstance(queries, list):
        raise FetchError(f"{path.name} has no 'queries' list")
    good = []
    for q in queries:
        if isinstance(q, dict) and q.get("query_id") and q.get("query_url"):
            good.append(q)
        else:
            log(f"  skipping malformed query entry in {path.name}: {q!r}")
    return good


def http_get(url, retries=4, timeout=25, base_delay=1.5):
    """GET a URL and return the body as text.
    Retries on 403, 429, 5xx and network errors using exponential backoff with jitter.
    """
    last = None
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
    }
    for attempt in range(retries):
        req = Request(url, headers=headers)
        try:
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            last = f"HTTP {e.code}"
            # 429 Too Many Requests, 403 Forbidden / burst rate-limit, 5xx Server Errors
            if e.code in (403, 429, 500, 502, 503, 504) and attempt < retries - 1:
                retry_after = getattr(e, "headers", {}).get("Retry-After") if getattr(e, "headers", None) else None
                if retry_after and retry_after.isdigit():
                    sleep_time = float(retry_after) + random.uniform(0.5, 1.5)
                else:
                    multiplier = 2.0 if e.code in (403, 429) else 1.5
                    sleep_time = (base_delay * multiplier * (2 ** attempt)) + random.uniform(0.3, 1.2)
                log(f"    [retry {attempt + 1}/{retries}] HTTP {e.code} for {url[:75]}... backing off {sleep_time:.2f}s")
                time.sleep(sleep_time)
                continue
            break
        except (URLError, TimeoutError, OSError) as e:
            last = f"network error: {e}"
            if attempt < retries - 1:
                sleep_time = (base_delay * (2 ** attempt)) + random.uniform(0.3, 1.2)
                log(f"    [retry {attempt + 1}/{retries}] Network error ({e}) for {url[:75]}... backing off {sleep_time:.2f}s")
                time.sleep(sleep_time)
                continue
            break
    raise FetchError(last or "unknown error")


def html_to_text(s):
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|li|div|h\d|ul|ol)>", "\n", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(html.unescape(s))  # some sources are double-escaped
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s)
    return s.strip()


def one_line(s, limit):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= limit else s[: limit - 1].rstrip() + "…"


def clean_url(url):
    """Remove tracking parameters so the same job always has the same URL."""
    if not url:
        return ""
    parts = urlsplit(url)
    kept = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


def set_query_param(url, key, value):
    parts = urlsplit(url)
    items = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != key]
    items.append((key, str(value)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(items), parts.fragment))


def guess_min_years(text):
    """Rough 'N years' hint from free text. Only a hint, the agent should read the JD."""
    nums = []
    for m in re.finditer(r"(\d{1,2})\s*(?:\+|\s*-\s*\d{1,2}|\s*to\s*\d{1,2})?\s*(?:years?|yrs?)\b", text or "", re.I):
        n = int(m.group(1))
        if 0 <= n <= 20:
            nums.append(n)
    return min(nums) if nums else None


# --------------------------------------------------------------------------- #
# Freehire
# --------------------------------------------------------------------------- #

def normalize_freehire(item, query_id):
    enr = item.get("enrichment") or {}
    real = item.get("reality") or {}
    desc_text = html_to_text(item.get("description") or "")
    salary = None
    if enr.get("salary_min") or enr.get("salary_max"):
        salary = {
            "min": enr.get("salary_min"),
            "max": enr.get("salary_max"),
            "currency": enr.get("salary_currency"),
            "period": enr.get("salary_period"),
        }
    return {
        "source": "freehire",
        "origin": item.get("source"),  # where Freehire got it (naukri, shine, workable, ...)
        "job_id": f"freehire:{item.get('source')}:{item.get('external_id')}",
        "url": clean_url(item.get("url")),
        "title": (item.get("title") or "").strip(),
        "company": (item.get("company") or "").strip(),
        "location": (item.get("location") or "").strip(),
        "cities": item.get("cities") or [],
        "work_mode": item.get("work_mode"),
        "posted_at": item.get("posted_at"),
        "experience_years_min": enr.get("experience_years_min"),
        "employment_type": enr.get("employment_type"),
        "salary": salary,
        "skills": (item.get("skills") or [])[:15],
        "via_recruiter": bool(item.get("via_recruiter")),
        "company_type": enr.get("company_type"),
        "reality": {
            "class": real.get("class"),
            "age_days": real.get("age_days"),
            "repost_count": real.get("repost_count"),
            "mass_posting_count": real.get("mass_posting_count"),
            "fake_freshness": real.get("fake_freshness"),
        },
        "summary": enr.get("summary") or one_line(desc_text, SUMMARY_CHARS),
        "query_ids": [query_id],
    }


def fetch_freehire(query, max_pages, delay, retries=4):
    """Page through a Freehire query using limit/offset. Returns (jobs, stat)."""
    qid = query["query_id"]
    stat = {"query_id": qid, "source": "freehire", "description": query.get("query_description", ""),
            "fetched": 0, "reported_total": None, "pages": 0, "error": None}
    jobs, offset = [], 0
    for page in range(max_pages):
        url = set_query_param(query["query_url"], "offset", offset)
        try:
            payload = json.loads(http_get(url, retries=retries, base_delay=delay))
        except (FetchError, json.JSONDecodeError) as e:
            stat["error"] = f"page {page + 1}: {e}"
            break
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            stat["error"] = f"page {page + 1}: unexpected response shape"
            break
        meta = payload.get("meta") or {}
        stat["reported_total"] = meta.get("total", stat["reported_total"])
        stat["pages"] += 1
        jobs.extend(normalize_freehire(item, qid) for item in data)
        offset += len(data)
        total = stat["reported_total"]
        if not data or (isinstance(total, int) and offset >= total):
            break
        if page < max_pages - 1:
            time.sleep(delay + random.uniform(0.1, 0.3))
    stat["fetched"] = len(jobs)
    return jobs, stat


# --------------------------------------------------------------------------- #
# LinkedIn (public guest endpoint, HTML)
# --------------------------------------------------------------------------- #

def linkedin_page_url(query_url, start):
    """Turn a public /jobs/search URL into the guest endpoint that returns job cards."""
    query = urlsplit(query_url).query
    query = re.sub(r"(^|&)start=\d+", "", query).lstrip("&")
    return f"{LINKEDIN_SEARCH}?{query}&start={start}"


def parse_linkedin_cards(page, query_id):
    jobs = []
    for m in re.finditer(r"<li[^>]*>(.*?)</li>", page, re.S):
        chunk = m.group(1)
        if "base-search-card" not in chunk and "base-card" not in chunk:
            continue
        urn = re.search(r"jobPosting:(\d+)", chunk)
        link_tag = re.search(r"<a[^>]*base-card__full-link[^>]*>", chunk)
        href = None
        if link_tag:
            h = re.search(r'href="([^"]+)"', link_tag.group(0))
            href = html.unescape(h.group(1)) if h else None
        job_num = urn.group(1) if urn else None
        if not job_num and href:
            tail = re.search(r"-(\d{6,})(?:\?|$)", href.split("?")[0] + ("?" if "?" not in href else ""))
            job_num = tail.group(1) if tail else None
        if not job_num and not href:
            continue

        def grab(pattern):
            r = re.search(pattern, chunk, re.S)
            return html_to_text(r.group(1)) if r else ""

        title = grab(r"base-search-card__title[^>]*>(.*?)</h3>")
        company = grab(r"base-search-card__subtitle[^>]*>(.*?)</h4>")
        location = grab(r"job-search-card__location[^>]*>(.*?)</span>")
        dt = re.search(r'<time[^>]*datetime="([^"]+)"', chunk)

        jobs.append({
            "source": "linkedin",
            "origin": "linkedin",
            "job_id": f"linkedin:{job_num}" if job_num else f"linkedin:{clean_url(href)}",
            "url": f"https://www.linkedin.com/jobs/view/{job_num}" if job_num else clean_url(href),
            "title": title,
            "company": company,
            "location": location,
            "cities": [],
            "work_mode": None,
            "posted_at": dt.group(1) if dt else None,
            "experience_years_min": None,
            "employment_type": None,
            "salary": None,
            "skills": [],
            "via_recruiter": False,
            "company_type": None,
            "reality": None,
            "summary": "",
            "query_ids": [query_id],
        })
    return jobs


def fetch_linkedin(query, max_pages, delay, retries=4):
    qid = query["query_id"]
    stat = {"query_id": qid, "source": "linkedin", "description": query.get("query_description", ""),
            "fetched": 0, "reported_total": None, "pages": 0, "error": None}
    jobs = []
    for page in range(max_pages):
        url = linkedin_page_url(query["query_url"], page * LINKEDIN_PAGE_SIZE)
        try:
            body = http_get(url, retries=retries, base_delay=delay)
        except FetchError as e:
            stat["error"] = f"page {page + 1}: {e}"
            break
        cards = parse_linkedin_cards(body, qid)
        stat["pages"] += 1
        if not cards:
            if page == 0 and body.strip() and "base-search-card" not in body:
                stat["error"] = "page 1: response had no job cards (blocked, empty or markup changed)"
            break
        jobs.extend(cards)
        if len(cards) < LINKEDIN_PAGE_SIZE:
            break
        if page < max_pages - 1:
            time.sleep(delay + random.uniform(0.1, 0.3))
    stat["fetched"] = len(jobs)
    return jobs, stat


def add_linkedin_details(job, delay, retries=3):
    """Fetch the full description + criteria for one LinkedIn job."""
    job_num = job["job_id"].split(":", 1)[1]
    if not job_num.isdigit():
        return
    try:
        page = http_get(LINKEDIN_DETAIL.format(job_id=job_num), retries=retries, base_delay=delay)
    except FetchError:
        return
    m = re.search(r"show-more-less-html__markup[^>]*>(.*?)</div>", page, re.S)
    text = html_to_text(m.group(1)) if m else ""
    criteria = [html_to_text(c) for c in re.findall(r"description__job-criteria-text[^>]*>(.*?)</span>", page, re.S)]
    if text:
        job["summary"] = one_line(text, SUMMARY_CHARS)
        job["experience_years_min"] = guess_min_years(text)
        job["experience_years_is_hint"] = True
    if criteria:
        job["seniority_level"] = criteria[0]
        if len(criteria) > 1:
            job["employment_type"] = criteria[1]
    time.sleep(delay + random.uniform(0.1, 0.3))


# --------------------------------------------------------------------------- #
# Concurrency Runner
# --------------------------------------------------------------------------- #

def fetch_source_queries(source_name, queries, fetcher, pages, delay, max_workers, retries=4):
    """Fetch all queries for a given source using a controlled thread pool."""
    log(f"[{source_name}] {len(queries)} queries (concurrency: {max_workers})")
    stats_dict = {}
    jobs_dict = {}

    def run_query(q):
        qid = q["query_id"]
        desc = q.get("query_description", "")
        log(f"  [{source_name}] starting {qid}: {desc}")
        jobs, stat = fetcher(q, pages, delay, retries=retries)
        status_msg = f"{stat['fetched']} jobs" + (f" (ERROR: {stat['error']})" if stat["error"] else "")
        log(f"  [{source_name}] finished {qid} -> {status_msg}")
        return qid, jobs, stat

    if max_workers <= 1:
        for q in queries:
            qid, jobs, stat = run_query(q)
            jobs_dict[qid] = jobs
            stats_dict[qid] = stat
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_qid = {executor.submit(run_query, q): q["query_id"] for q in queries}
            for f in as_completed(future_to_qid):
                qid = future_to_qid[f]
                try:
                    _, jobs, stat = f.result()
                    jobs_dict[qid] = jobs
                    stats_dict[qid] = stat
                except Exception as e:
                    log(f"  [{source_name}] unhandled exception on {qid}: {e}")
                    stats_dict[qid] = {
                        "query_id": qid,
                        "source": source_name,
                        "description": "",
                        "fetched": 0,
                        "reported_total": None,
                        "pages": 0,
                        "error": f"unhandled exception: {e}",
                    }
                    jobs_dict[qid] = []

    # Preserve exact query file ordering for stats and jobs
    ordered_stats = []
    ordered_jobs = []
    for q in queries:
        qid = q["query_id"]
        if qid in stats_dict:
            ordered_stats.append(stats_dict[qid])
        if qid in jobs_dict:
            ordered_jobs.extend(jobs_dict[qid])

    return ordered_jobs, ordered_stats


# --------------------------------------------------------------------------- #
# Merge, sanity warnings, main
# --------------------------------------------------------------------------- #

def dedupe(jobs):
    """Merge jobs that appear in several queries (same URL or job_id)."""
    seen, out = {}, []
    for job in jobs:
        key = job["url"] or job["job_id"]
        if key in seen:
            existing = seen[key]
            for qid in job["query_ids"]:
                if qid not in existing["query_ids"]:
                    existing["query_ids"].append(qid)
        else:
            seen[key] = job
            out.append(job)
    return out


def build_warnings(stats, jobs, min_per_query, min_total):
    warnings = []
    by_source = {}
    for s in stats:
        by_source.setdefault(s["source"], []).append(s)
        if s["error"]:
            warnings.append(f"{s['query_id']} ({s['source']}): {s['error']}")
        if s["fetched"] == 0 and not s["error"]:
            warnings.append(f"{s['query_id']} ({s['source']}): returned 0 jobs")
        elif 0 < s["fetched"] < min_per_query:
            warnings.append(f"{s['query_id']} ({s['source']}): only {s['fetched']} job(s), unusually low")
    for source, items in by_source.items():
        if sum(i["fetched"] for i in items) == 0:
            warnings.append(f"{source}: NO jobs returned from any query")
    if len(jobs) < min_total:
        warnings.append(f"only {len(jobs)} unique job(s) in total, unusually low")
    return warnings


def main():
    ap = argparse.ArgumentParser(description="Fetch jobs for the Get-Placed find-jobs skill.")
    ap.add_argument("--root", help="project root (auto-detected by default)")
    ap.add_argument("--out", help="write JSON to this file instead of stdout")
    ap.add_argument("--freehire-pages", type=int, default=3, help="max pages per Freehire query (default 3)")
    ap.add_argument("--linkedin-pages", type=int, default=2, help="max pages per LinkedIn query (default 2)")
    ap.add_argument("--details", action="store_true", help="also fetch LinkedIn job descriptions (slower)")
    ap.add_argument("--details-limit", type=int, default=40, help="max LinkedIn detail fetches (default 40)")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests per worker (default 1.0)")
    ap.add_argument("--freehire-workers", type=int, default=4, help="concurrency for Freehire queries (default 4)")
    ap.add_argument("--linkedin-workers", type=int, default=3, help="concurrency for LinkedIn queries (default 3)")
    ap.add_argument("--workers", type=int, default=None, help="override worker count for all sources")
    ap.add_argument("--retries", type=int, default=4, help="max retries with exponential backoff on errors (default 4)")
    ap.add_argument("--min-per-query", type=int, default=3, help="warn if a query returns fewer jobs (default 3)")
    ap.add_argument("--min-total", type=int, default=10, help="warn if fewer unique jobs overall (default 10)")
    args = ap.parse_args()

    freehire_workers = args.workers if args.workers is not None else args.freehire_workers
    linkedin_workers = args.workers if args.workers is not None else args.linkedin_workers

    root = find_root(args.root)
    qdir = root / "database" / "queries"
    stats, raw_jobs, warnings = [], [], []

    sources = [
        ("freehire", qdir / "freehireQueries.json", fetch_freehire, args.freehire_pages, freehire_workers),
        ("linkedin", qdir / "linkedinQueries.json", fetch_linkedin, args.linkedin_pages, linkedin_workers),
    ]
    for name, path, fetcher, pages, workers in sources:
        try:
            queries = load_queries(path)
        except FetchError as e:
            warnings.append(f"{name}: {e}")
            continue

        jobs, src_stats = fetch_source_queries(
            name, queries, fetcher, pages, args.delay, workers, retries=args.retries
        )
        stats.extend(src_stats)
        raw_jobs.extend(jobs)

    unique = dedupe(raw_jobs)

    if args.details:
        targets = [j for j in unique if j["source"] == "linkedin"][: args.details_limit]
        details_workers = min(linkedin_workers, 3)
        log(f"[linkedin] fetching details for {len(targets)} jobs (concurrency: {details_workers})")
        with ThreadPoolExecutor(max_workers=details_workers) as executor:
            futures = [executor.submit(add_linkedin_details, j, args.delay, args.retries) for j in targets]
            for f in as_completed(futures):
                pass

    warnings.extend(build_warnings(stats, unique, args.min_per_query, args.min_total))

    by_source = {}
    for j in unique:
        by_source[j["source"]] = by_source.get(j["source"], 0) + 1

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stats": stats,
        "warnings": warnings,
        "totals": {"raw": len(raw_jobs), "unique": len(unique), "by_source": by_source},
        "jobs": unique,
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).expanduser().write_text(text, encoding="utf-8")
        log(f"wrote {args.out}")
    else:
        print(text)

    if not stats:
        sys.exit(1)  # nothing could even be attempted


if __name__ == "__main__":
    main()
