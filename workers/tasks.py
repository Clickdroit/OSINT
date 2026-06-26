import asyncio
import os
import re
import feedparser
import httpx
from datetime import datetime
from sqlalchemy import insert, select
from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import Target, ScanResult, Leak, Keyword, Alert
from workers.site_signatures import SITES

# Headers to mimic a standard browser request
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

# --- TASK 1: USERNAME SCANNER (ASYNC) ---

async def check_site(client: httpx.AsyncClient, site: dict, username: str, semaphore: asyncio.Semaphore) -> dict:
    url = site["url_template"].format(username)
    name = site["name"]
    async with semaphore:
        try:
            # Most sites work fine with GET. We follow redirects.
            response = await client.get(url, headers=DEFAULT_HEADERS, timeout=5.0, follow_redirects=True)
            status_code = response.status_code
            html_content = response.text

            # Check status codes indicative of missing profiles
            if status_code in site.get("error_codes", [404]):
                return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": status_code}

            # Check content-based signatures (avoid false positive 200 OKs)
            body_lower = html_content.lower()
            for keyword in site.get("error_keywords", []):
                if keyword.lower() in body_lower:
                    return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": status_code}

            # If no negative signature matches, target profile exists
            return {"platform": name, "url": url, "status": "FOUND", "response_code": status_code}

        except httpx.HTTPError as e:
            # Network failures or rate limiting
            return {"platform": name, "url": url, "status": "ERROR", "response_code": None}
        except Exception:
            return {"platform": name, "url": url, "status": "ERROR", "response_code": None}


async def run_username_scan(target_id: int):
    db = SessionLocal()
    try:
        # Fetch target details
        target = db.get(Target, target_id)
        if not target or target.type != "username":
            print(f"[Scan] Target ID {target_id} not found or type is not username.")
            return

        username = target.value
        print(f"[Scan] Starting async social media scan for: {username}")

        # Limit concurrency to 25 simultaneous connections to avoid socket exhaust or blocklists
        sem = asyncio.Semaphore(25)
        
        # Configure client with limits
        limits = httpx.Limits(max_keepalive_connections=5, max_connections=25)
        async with httpx.AsyncClient(limits=limits) as client:
            tasks = [check_site(client, site, username, sem) for site in SITES]
            results = await asyncio.gather(*tasks)

        # Bulk insert scan results into the database
        db_results = []
        for res in results:
            db_results.append({
                "target_id": target_id,
                "platform": res["platform"],
                "url": res["url"] if res["status"] == "FOUND" else None,
                "status": res["status"],
                "response_code": res["response_code"]
            })
            
        if db_results:
            db.execute(insert(ScanResult), db_results)
            db.commit()
            
        print(f"[Scan] Completed for {username}. Found on {sum(1 for r in results if r['status'] == 'FOUND')}/{len(SITES)} sites.")

    finally:
        db.close()


@celery_app.task(name="workers.tasks.scan_username")
def scan_username(target_id: int):
    # Run the asynchronous scan loop inside Celery's synchronous worker thread
    asyncio.run(run_username_scan(target_id))
    return {"status": "SUCCESS", "target_id": target_id}


# --- TASK 2: BREACH & LEAK INGESTOR (STREAMING) ---

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

def parse_leak_line(line: str) -> dict | None:
    # Remove surrounding spaces and line endings
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    # Try common delimiters: colon (:) or semicolon (;) or comma (,) or pipe (|)
    parts = []
    for delimiter in [":", ";", ",", "|"]:
        if delimiter in line:
            parts = [p.strip() for p in line.split(delimiter) if p.strip()]
            break
            
    if not parts:
        parts = [line]

    # Try to map parts based on pattern:
    # Commonly it's email:password, username:password, or email:username:password
    email = None
    username = None
    password_hash = None

    if len(parts) == 1:
        # Just a raw credential or email
        val = parts[0]
        if EMAIL_REGEX.match(val):
            email = val
        else:
            username = val
    elif len(parts) == 2:
        # Could be email:password or username:password
        val1, val2 = parts[0], parts[1]
        if EMAIL_REGEX.match(val1):
            email = val1
        else:
            username = val1
        password_hash = val2
    elif len(parts) >= 3:
        # Could be username:email:password
        val1, val2, val3 = parts[0], parts[1], parts[2]
        if EMAIL_REGEX.match(val2):
            username = val1
            email = val2
            password_hash = val3
        elif EMAIL_REGEX.match(val1):
            email = val1
            username = val2
            password_hash = val3
        else:
            username = val1
            email = val2
            password_hash = val3

    if not email and not username:
        return None

    return {
        "username": username,
        "email": email,
        "password_hash": password_hash
    }


@celery_app.task(name="workers.tasks.ingest_leak_file")
def ingest_leak_file(file_path: str, source_name: str, leak_date: str = None):
    print(f"[Ingest] Starting ingestion of leak file: {file_path} (Source: {source_name})")
    
    if not os.path.exists(file_path):
        print(f"[Ingest] File not found: {file_path}")
        return {"status": "FAILED", "reason": f"File {file_path} not found"}

    db = SessionLocal()
    batch_size = 5000
    batch = []
    total_lines = 0
    inserted_records = 0

    try:
        # Stream the file line-by-line using generators to avoid memory spikes
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                total_lines += 1
                record = parse_leak_line(line)
                if record:
                    record["source"] = source_name
                    record["leak_date"] = leak_date
                    batch.append(record)

                if len(batch) >= batch_size:
                    # Bulk insert
                    db.execute(insert(Leak), batch)
                    db.commit()
                    inserted_records += len(batch)
                    batch.clear()
                    print(f"[Ingest] Processed {total_lines} lines... Inserted {inserted_records} leaks.")

            # Insert any leftovers
            if batch:
                db.execute(insert(Leak), batch)
                db.commit()
                inserted_records += len(batch)
                batch.clear()

        print(f"[Ingest] Completed. Ingested {inserted_records} records out of {total_lines} total lines.")
        return {"status": "SUCCESS", "lines_processed": total_lines, "records_inserted": inserted_records}

    except Exception as e:
        db.rollback()
        print(f"[Ingest] Database error during ingestion: {str(e)}")
        return {"status": "ERROR", "reason": str(e)}
    finally:
        db.close()


# --- TASK 3: CYBER NEWS MONITOR / RSS SCRAPER ---

DEFAULT_FEEDS = [
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
    {"name": "NakedSecurity", "url": "https://nakedsecurity.sophos.com/feed/"},
    {"name": "Reddit Netsec", "url": "https://www.reddit.com/r/netsec/.rss"}
]

@celery_app.task(name="workers.tasks.check_rss_feeds")
def check_rss_feeds():
    print("[RSS] Starting security feed keyword checks.")
    db = SessionLocal()
    alerts_created = 0

    try:
        # Fetch keywords to watch
        keywords = db.scalars(select(Keyword)).all()
        if not keywords:
            print("[RSS] No keywords configured. Skipping RSS check.")
            return {"status": "SKIPPED", "reason": "No keywords configured"}

        for feed in DEFAULT_FEEDS:
            print(f"[RSS] Fetching feed: {feed['name']} ({feed['url']})")
            parsed_feed = feedparser.parse(feed["url"])
            
            for entry in parsed_feed.entries:
                title = entry.get("title", "")
                summary = entry.get("summary", "")
                link = entry.get("link", "")
                
                # Check both title and summary against all keywords
                title_lower = title.lower()
                summary_lower = summary.lower()

                for kw in keywords:
                    kw_lower = kw.value.lower()
                    if kw_lower in title_lower or kw_lower in summary_lower:
                        # Check if alert already exists for this URL and keyword
                        exists = db.scalar(
                            select(Alert).where(Alert.url == link, Alert.keyword_id == kw.id)
                        )
                        if not exists:
                            # Create new alert
                            alert = Alert(
                                keyword_id=kw.id,
                                source_feed=feed["name"],
                                title=title,
                                url=link,
                                summary=summary[:1000] if summary else "", # truncate long summaries
                            )
                            db.add(alert)
                            alerts_created += 1
                            print(f"[RSS] ALERT: Keyword '{kw.value}' matched in article: '{title}'")

        if alerts_created > 0:
            db.commit()
            
        print(f"[RSS] Completed. Generated {alerts_created} new alerts.")
        return {"status": "SUCCESS", "alerts_created": alerts_created}

    except Exception as e:
        db.rollback()
        print(f"[RSS] Error occurred: {str(e)}")
        return {"status": "ERROR", "reason": str(e)}
    finally:
        db.close()
