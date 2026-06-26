import asyncio
import os
import re
import json
import feedparser
import httpx
import hashlib
from datetime import datetime
from sqlalchemy import insert, select
from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import Target, ScanResult, Leak, Keyword, Alert, Feed
from workers.site_signatures import SITES

from backend.config import settings
import google.generativeai as genai

# Configure Google Gemini
if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

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
    category = site.get("category", "other")
    async with semaphore:
        try:
            # 1. Special API fetches for found profiles to extract rich metadata
            if name == "GitHub":
                try:
                    github_url = f"https://api.github.com/users/{username}"
                    api_resp = await client.get(github_url, headers=DEFAULT_HEADERS, timeout=3.0)
                    if api_resp.status_code == 200:
                        api_data = api_resp.json()
                        return {
                            "platform": name,
                            "url": url,
                            "status": "FOUND",
                            "response_code": 200,
                            "category": category,
                            "metadata": {
                                "name": api_data.get("name"),
                                "bio": api_data.get("bio"),
                                "location": api_data.get("location"),
                                "company": api_data.get("company"),
                                "blog": api_data.get("blog"),
                                "avatar_url": api_data.get("avatar_url"),
                                "public_repos": api_data.get("public_repos")
                            }
                        }
                    elif api_resp.status_code == 404:
                        return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": 404, "category": category}
                except Exception as api_err:
                    print(f"[GitHub API Error] {api_err}")

            elif name == "Reddit":
                try:
                    reddit_api_url = f"https://www.reddit.com/user/{username}/about.json"
                    api_resp = await client.get(reddit_api_url, headers=DEFAULT_HEADERS, timeout=3.0)
                    if api_resp.status_code == 200:
                        api_data = api_resp.json().get("data", {})
                        created_utc = api_data.get("created_utc")
                        created_str = datetime.utcfromtimestamp(created_utc).strftime('%Y-%m-%d') if created_utc else None
                        avatar_url = api_data.get("subreddit", {}).get("icon_img") if api_data.get("subreddit") else None
                        if avatar_url and "?" in avatar_url:
                            avatar_url = avatar_url.split("?")[0]
                        return {
                            "platform": name,
                            "url": url,
                            "status": "FOUND",
                            "response_code": 200,
                            "category": category,
                            "metadata": {
                                "name": api_data.get("name"),
                                "created_at": created_str,
                                "total_karma": api_data.get("total_karma"),
                                "bio": api_data.get("subreddit", {}).get("public_description") if api_data.get("subreddit") else None,
                                "avatar_url": avatar_url
                            }
                        }
                    elif api_resp.status_code == 404:
                        return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": 404, "category": category}
                except Exception as api_err:
                    print(f"[Reddit API Error] {api_err}")

            # 2. General site check
            response = await client.get(url, headers=DEFAULT_HEADERS, timeout=5.0, follow_redirects=True)
            status_code = response.status_code
            html_content = response.text

            # Check status codes indicative of missing profiles
            if status_code in site.get("error_codes", [404]):
                return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": status_code, "category": category}

            # Check content-based signatures (avoid false positive 200 OKs)
            body_lower = html_content.lower()
            for keyword in site.get("error_keywords", []):
                if keyword.lower() in body_lower:
                    return {"platform": name, "url": url, "status": "NOT_FOUND", "response_code": status_code, "category": category}

            # If no negative signature matches, target profile exists. Parse OG metadata.
            metadata = {}
            try:
                # Find og:title
                og_title = re.search(r'<meta[^>]*?property=["\']og:title["\']?[^>]*?content=["\'](.*?)["\']', html_content, re.IGNORECASE)
                if not og_title:
                    og_title = re.search(r'<meta[^>]*?content=["\'](.*?)["\']?[^>]*?property=["\']og:title["\']', html_content, re.IGNORECASE)
                
                # Find og:description
                og_desc = re.search(r'<meta[^>]*?property=["\']og:description["\']?[^>]*?content=["\'](.*?)["\']', html_content, re.IGNORECASE)
                if not og_desc:
                    og_desc = re.search(r'<meta[^>]*?content=["\'](.*?)["\']?[^>]*?property=["\']og:description["\']', html_content, re.IGNORECASE)

                # Find og:image
                og_image = re.search(r'<meta[^>]*?property=["\']og:image["\']?[^>]*?content=["\'](.*?)["\']', html_content, re.IGNORECASE)
                if not og_image:
                    og_image = re.search(r'<meta[^>]*?content=["\'](.*?)["\']?[^>]*?property=["\']og:image["\']', html_content, re.IGNORECASE)

                if og_title:
                    metadata["title"] = og_title.group(1).strip()
                if og_desc:
                    metadata["description"] = og_desc.group(1).strip()
                if og_image:
                    metadata["image"] = og_image.group(1).strip()
            except Exception as og_err:
                print(f"[OG Metadata Extraction Error] {og_err}")

            return {
                "platform": name,
                "url": url,
                "status": "FOUND",
                "response_code": status_code,
                "category": category,
                "metadata": metadata
            }

        except httpx.HTTPError:
            return {"platform": name, "url": url, "status": "ERROR", "response_code": None, "category": category}
        except Exception:
            return {"platform": name, "url": url, "status": "ERROR", "response_code": None, "category": category}


def generate_ai_username_report(username: str, results: list) -> str:
    """Generate an AI OSINT report summarising the exposure of a username across platforms."""
    found = [r for r in results if r["status"] == "FOUND"]
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")
    error_count = sum(1 for r in results if r["status"] == "ERROR")

    # Group found platforms by category
    from workers.site_signatures import SITES
    site_cat_map = {s["name"]: s.get("category", "other") for s in SITES}

    categories = {}
    for r in found:
        cat = site_cat_map.get(r["platform"], "other")
        categories.setdefault(cat, []).append(r["platform"])

    cat_labels = {
        "social": "Réseaux Sociaux", "dev": "Développement & Tech",
        "gaming": "Gaming", "creative": "Créatif & Art",
        "music": "Musique & Vidéo", "financial": "Finance & Support",
        "security": "Cybersécurité & CTF", "other": "Autres Plateformes"
    }
    
    platforms_by_cat = "\n".join(
        f"- **{cat_labels.get(cat, cat)}** : {', '.join(platforms)}"
        for cat, platforms in sorted(categories.items())
    ) or "Aucune plateforme détectée."

    # Build a details string of metadata retrieved
    found_profiles_info = []
    for r in found:
        meta = r.get("metadata", {})
        info = f"- **{r['platform']}** : {r['url']}"
        meta_parts = []
        if meta:
            if meta.get("name"):
                meta_parts.append(f"Nom: {meta['name']}")
            if meta.get("location"):
                meta_parts.append(f"Localisation: {meta['location']}")
            if meta.get("bio"):
                meta_parts.append(f"Bio: {meta['bio']}")
            elif meta.get("description"):
                meta_parts.append(f"Description: {meta['description']}")
            if meta.get("company"):
                meta_parts.append(f"Entreprise: {meta['company']}")
            if meta.get("total_karma"):
                meta_parts.append(f"Karma: {meta['total_karma']}")
            if meta.get("created_at"):
                meta_parts.append(f"Créé le: {meta['created_at']}")
        if meta_parts:
            info += f" ({', '.join(meta_parts)})"
        found_profiles_info.append(info)
    
    platforms_details = "\n".join(found_profiles_info) or "Aucun profil trouvé."

    exposure_level = (
        "🔴 **ÉLEVÉE**" if len(found) > 20 else
        "🟠 **MODÉRÉE**" if len(found) > 10 else
        "🟡 **FAIBLE**" if len(found) > 3 else
        "🟢 **TRÈS FAIBLE**"
    )

    system_instruction = (
        "Tu es 'Cyber Copilot OSINT Analyst', un expert en intelligence en sources ouvertes (OSINT) "
        "et en investigation numérique. Tu rédiges des rapports d'exposition numérique pour les analystes "
        "de cybersécurité en français, de manière professionnelle, concise et structurée."
    )

    prompt = (
        f"Analyse le pseudo : **{username}** à partir des profils trouvés sur le web.\n\n"
        f"Données de scan ({len(results)} plateformes analysées, {len(found)} trouvées) :\n"
        f"{platforms_details}\n\n"
        f"Calcule un **SCORE DE CONFIANCE** global (en pourcentage, ex: 85%) indiquant la probabilité que "
        f"ces différents profils appartiennent réellement à la même personne physique. Base ton calcul sur "
        f"la cohérence des noms réels, des bios, de la localisation, des styles d'écriture et de l'activité.\n\n"
        f"Instructions pour le rapport Markdown :\n"
        f"1. Commence obligatoirement ton rapport par une ligne au format exact suivant :\n"
        f"   `**SCORE DE CONFIANCE IA : [Score]%**` (remplace [Score] par la valeur numérique uniquement, ex: `**SCORE DE CONFIANCE IA : 85%**`)\n"
        f"2. Ajoute une section **Fiche d'identité synthétisée** au format JSON (bloc de code ```json) contenant les clés suivantes :\n"
        f"   - `nom_probable` (String)\n"
        f"   - `localisation_probable` (String)\n"
        f"   - `photo_profil_probable` (String - URL d'avatar trouvée si présente, sinon null)\n"
        f"   - `bio_synthétisée` (String)\n"
        f"   - `centres_interets` (Array of Strings)\n"
        f"3. Ajoute ensuite des sections d'analyse textuelle :\n"
        f"   - **Synthèse d'Exposition** : évaluation globale (Niveau : {exposure_level}).\n"
        f"   - **Analyse des Risques et Cohérence** : pourquoi ce score ? (ex: correspondances de noms/bios entre GitHub et Reddit, ou au contraire doutes).\n"
        f"   - **Recommandations OPSEC**.\n\n"
        f"Ne mets aucune introduction ou conclusion inutile. Débute directement par la ligne du score."
    )

    response_text = ""
    errors = []

    def try_digitalocean():
        if not settings.AI_API_KEY:
            return None, "DigitalOcean API key not configured."
        try:
            url = settings.AI_BASE_URL.rstrip("/")
            if not url.endswith("/chat/completions"):
                url += "/chat/completions"
            response = httpx.post(
                url,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.AI_API_KEY}"},
                json={"model": settings.AI_MODEL_NAME, "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]},
                timeout=60.0
            )
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}: {response.text}"
            return response.json()["choices"][0]["message"]["content"], None
        except Exception as e:
            return None, str(e)

    def try_gemini():
        if not settings.GEMINI_API_KEY:
            return None, "Gemini API key not configured."
        try:
            model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_instruction)
            return model.generate_content(prompt).text, None
        except Exception as e:
            return None, str(e)

    providers = [("digitalocean", try_digitalocean), ("gemini", try_gemini)] if settings.AI_PROVIDER == "digitalocean" else [("gemini", try_gemini), ("digitalocean", try_digitalocean)]
    for name, func in providers:
        res, err = func()
        if res:
            response_text = res
            break
        elif err:
            errors.append(f"{name}: {err}")
            print(f"[{name.upper()} AI Error] OSINT report: {err}")

    if not response_text:
        # Static fallback
        response_text = (
            f"**SCORE DE CONFIANCE IA : 0%**\n\n"
            f"```json\n"
            f"{{\n"
            f"  \"nom_probable\": \"Non disponible\",\n"
            f"  \"localisation_probable\": \"Non disponible\",\n"
            f"  \"photo_profil_probable\": null,\n"
            f"  \"bio_synthétisée\": \"L'analyse IA n'a pas pu être générée car les clés d'API ne sont pas configurées.\",\n"
            f"  \"centres_interets\": []\n"
            f"}}\n"
            f"```\n\n"
            f"## Rapport OSINT - {username}\n\n"
            f"**Niveau d'exposition** : {exposure_level}\n\n"
            f"**Profils détectés ({len(found)}/{len(results)})** :\n{platforms_by_cat}\n\n"
            f"*(L'analyse IA détaillée n'est pas disponible. Vérifiez la configuration GEMINI_API_KEY ou AI_API_KEY.)*"
        )
    return response_text


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

        # Bulk insert scan results into the database (include category and metadata as JSON)
        db_results = []
        for res in results:
            details_obj = {
                "category": res.get("category", "other"),
                "metadata": res.get("metadata", {})
            }
            db_results.append({
                "target_id": target_id,
                "platform": res["platform"],
                "url": res["url"] if res["status"] == "FOUND" else None,
                "status": res["status"],
                "response_code": res["response_code"],
                "details": json.dumps(details_obj)
            })
            
        if db_results:
            db.execute(insert(ScanResult), db_results)
            db.commit()

        found_results = [r for r in results if r["status"] == "FOUND"]
        total_found = len(found_results)
        print(f"[Scan] Completed for {username}. Found on {total_found}/{len(SITES)} sites.")

        # --- Generate AI OSINT Report ---
        print(f"[Scan] Generating AI OSINT report for: {username}")
        ai_report = generate_ai_username_report(username, results)

        # Insert AI report as a special ScanResult entry
        db.execute(insert(ScanResult), [{
            "target_id": target_id,
            "platform": "Rapport OSINT IA",
            "url": None,
            "status": "FOUND",
            "response_code": None,
            "details": ai_report
        }])
        db.commit()

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


@celery_app.task(bind=True, name="workers.tasks.ingest_leak_file")
def ingest_leak_file(self, file_path: str, source_name: str, leak_date: str = None):
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
                    self.update_state(state='PROGRESS', meta={
                        'current_lines': total_lines,
                        'inserted_records': inserted_records,
                        'status_text': f"Ingestion en cours : {inserted_records} fuites insérées ({total_lines} lignes lues)."
                    })

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
        # Check if feeds table is empty, if so, seed it with defaults
        feeds = db.scalars(select(Feed).where(Feed.is_active == True)).all()
        if not feeds:
            # Seed default feeds
            for df in DEFAULT_FEEDS:
                exists = db.scalar(select(Feed).where(Feed.url == df["url"]))
                if not exists:
                    feed_db = Feed(name=df["name"], url=df["url"], is_active=True)
                    db.add(feed_db)
            db.commit()
            feeds = db.scalars(select(Feed).where(Feed.is_active == True)).all()

        # Fetch keywords to watch
        keywords = db.scalars(select(Keyword)).all()
        if not keywords:
            print("[RSS] No keywords configured. Skipping RSS check.")
            return {"status": "SKIPPED", "reason": "No keywords configured"}

        for feed in feeds:
            print(f"[RSS] Fetching feed: {feed.name} ({feed.url})")
            parsed_feed = feedparser.parse(feed.url)
            
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
                                source_feed=feed.name,
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


# --- TASK 4: DOMAIN SECURITY AUDITOR SCANNER (PASSIVE) ---

def query_dns_doh(domain: str, record_type: str) -> list:
    url = f"https://cloudflare-dns.com/dns-query?name={domain}&type={record_type}"
    headers = {"Accept": "application/dns-json"}
    try:
        response = httpx.get(url, headers=headers, timeout=5.0)
        if response.status_code == 200:
            data = response.json()
            answers = data.get("Answer", [])
            return [ans.get("data") for ans in answers if "data" in ans]
    except Exception as e:
        print(f"[DNS DoH Error] Failed to query {record_type} for {domain}: {str(e)}")
    return []


def check_http_headers(domain: str) -> dict:
    results = {
        "ssl_valid": "NOT_FOUND",
        "hsts": "NOT_FOUND",
        "csp": "NOT_FOUND",
        "x_frame": "NOT_FOUND",
        "x_content_type": "NOT_FOUND",
        "referrer_policy": "NOT_FOUND",
        "headers_found": {}
    }
    
    # Try HTTPS first
    url = f"https://{domain}"
    response = None
    try:
        response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=5.0, follow_redirects=True)
        results["ssl_valid"] = "FOUND"
    except httpx.HTTPError as e:
        print(f"[HTTP check] HTTPS failed for {domain}, falling back to HTTP. Error: {str(e)}")
        results["ssl_valid"] = "NOT_FOUND"
        url = f"http://{domain}"
        try:
            response = httpx.get(url, headers=DEFAULT_HEADERS, timeout=5.0, follow_redirects=True)
        except Exception:
            results["ssl_valid"] = "ERROR"
            
    if response:
        headers = response.headers
        results["headers_found"] = {k: v for k, v in headers.items()}
        
        # Check security headers
        if "Strict-Transport-Security" in headers:
            results["hsts"] = "FOUND"
        if "Content-Security-Policy" in headers:
            results["csp"] = "FOUND"
        if "X-Frame-Options" in headers:
            results["x_frame"] = "FOUND"
        if "X-Content-Type-Options" in headers:
            results["x_content_type"] = "FOUND"
        if "Referrer-Policy" in headers:
            results["referrer_policy"] = "FOUND"
            
    return results


def generate_ai_domain_report(domain: str, dns_txt: list, dns_mx: list, headers_results: dict) -> str:
    system_instruction = (
        "Tu es 'Cyber Copilot Domain Auditor', un expert en audit de sécurité web et réseau.\n"
        "Ton but est d'analyser les configurations de domaine (DNS, en-têtes HTTP de sécurité, SSL) "
        "d'un site web, d'évaluer les forces et les faiblesses, et de rédiger un rapport clair, didactique "
        "et synthétique en français au format Markdown."
    )
    
    hsts = "Présent" if headers_results["hsts"] == "FOUND" else "Manquant"
    csp = "Présent" if headers_results["csp"] == "FOUND" else "Manquant"
    x_frame = "Présent" if headers_results["x_frame"] == "FOUND" else "Manquant"
    x_content_type = "Présent" if headers_results["x_content_type"] == "FOUND" else "Manquant"
    referrer = "Présent" if headers_results["referrer_policy"] == "FOUND" else "Manquant"
    ssl = "Valide" if headers_results["ssl_valid"] == "FOUND" else "Invalide/Non disponible"
    
    prompt = (
        f"Génère un rapport d'audit de sécurité au format Markdown pour le domaine : {domain}\n\n"
        f"Voici les données d'analyse récoltées :\n"
        f"- Connexion HTTPS / Certificat SSL : {ssl}\n"
        f"- En-tête HSTS (Strict-Transport-Security) : {hsts}\n"
        f"- En-tête CSP (Content-Security-Policy) : {csp}\n"
        f"- En-tête X-Frame-Options : {x_frame}\n"
        f"- En-tête X-Content-Type-Options : {x_content_type}\n"
        f"- En-tête Referrer-Policy : {referrer}\n\n"
        f"Configuration DNS :\n"
        f"- Enregistrements MX : {dns_mx or 'Aucun détecté'}\n"
        f"- Enregistrements TXT (SPF/DMARC) : {dns_txt or 'Aucun détecté'}\n\n"
        f"Consignes pour le rapport :\n"
        f"1. Rédige en français de manière professionnelle et conseille.\n"
        f"2. Utilise des listes à puces et du gras pour mettre en évidence les risques.\n"
        f"3. Structure le rapport en 3 sections :\n"
        f"   - **1. Synthèse de Sécurité** (évaluation globale de l'exposition du domaine)\n"
        f"   - **2. Analyse des Vulnérabilités** (explication des risques liés aux en-têtes manquants ou aux DNS non configurés)\n"
        f"   - **3. Recommandations de Correction** (étapes concrètes et exemples de configuration pour sécuriser le domaine)\n"
        f"Ne mets pas d'introduction inutile, démarre directement avec le rapport Markdown."
    )
    
    response_text = ""
    errors = []

    def try_digitalocean():
        if not settings.AI_API_KEY:
            return None, "DigitalOcean API key not configured."
        try:
            url = settings.AI_BASE_URL.rstrip("/")
            if not url.endswith("/chat/completions"):
                url += "/chat/completions"
            
            response = httpx.post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {settings.AI_API_KEY}"
                },
                json={
                    "model": settings.AI_MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=45.0
            )
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}: {response.text}"
            res_data = response.json()
            return res_data["choices"][0]["message"]["content"], None
        except Exception as e:
            return None, str(e)

    def try_gemini():
        if not settings.GEMINI_API_KEY:
            return None, "Gemini API key not configured."
        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=system_instruction
            )
            response = model.generate_content(prompt)
            return response.text, None
        except Exception as e:
            return None, str(e)

    providers = []
    if settings.AI_PROVIDER == "digitalocean":
        providers = [("digitalocean", try_digitalocean), ("gemini", try_gemini)]
    else:
        providers = [("gemini", try_gemini), ("digitalocean", try_digitalocean)]

    for name, func in providers:
        res, err = func()
        if res:
            response_text = res
            break
        elif err:
            errors.append(f"{name}: {err}")
            print(f"[{name.upper()} AI Error] Failed to generate domain report: {err}")
            
    # 3. Static fallback
    if not response_text:
        response_text = (
            f"### Rapport d'Audit de Sécurité - {domain}\n\n"
            f"**Statut HTTPS/SSL** : {ssl}\n\n"
            f"**En-têtes HTTP de sécurité** :\n"
            f"- HSTS : {hsts}\n"
            f"- CSP : {csp}\n"
            f"- X-Frame-Options : {x_frame}\n"
            f"- X-Content-Type-Options : {x_content_type}\n"
            f"- Referrer-Policy : {referrer}\n\n"
            f"**Sécurité de Messagerie (DNS)** :\n"
            f"- MX : {dns_mx or 'Non détecté'}\n"
            f"- SPF/DMARC (TXT) : {dns_txt or 'Non détecté'}\n\n"
            f"*(Note : L'analyse détaillée par IA n'est pas disponible car aucun fournisseur d'IA n'est configuré dans le fichier `.env`)*"
        )
        
    return response_text


@celery_app.task(name="workers.tasks.scan_domain")
def scan_domain(target_id: int):
    print(f"[Domain Scan] Starting scan for target ID: {target_id}")
    db = SessionLocal()
    try:
        # Fetch target details
        target = db.get(Target, target_id)
        if not target or target.type != "domain":
            print(f"[Domain Scan] Target ID {target_id} not found or is not a domain.")
            return {"status": "FAILED", "reason": "Target not found or invalid type"}
            
        domain = target.value.lower().strip()
        
        # 1. Query DNS records (MX, TXT for SPF, and _dmarc.domain TXT for DMARC)
        dns_txt = query_dns_doh(domain, "TXT")
        dns_mx = query_dns_doh(domain, "MX")
        dmarc_txt = query_dns_doh(f"_dmarc.{domain}", "TXT")
        
        # 2. Check HTTP headers & SSL
        headers_results = check_http_headers(domain)
        
        # 3. Generate AI security summary
        report = generate_ai_domain_report(domain, dns_txt + dmarc_txt, dns_mx, headers_results)
        
        # 4. Save results to database
        db_results = []
        
        # SSL Cert Result
        db_results.append({
            "target_id": target_id,
            "platform": "Certificat SSL/TLS",
            "url": f"https://{domain}",
            "status": "FOUND" if headers_results["ssl_valid"] == "FOUND" else "ERROR" if headers_results["ssl_valid"] == "ERROR" else "NOT_FOUND",
            "response_code": 200 if headers_results["ssl_valid"] == "FOUND" else None,
            "details": "Connexion HTTPS établie avec succès." if headers_results["ssl_valid"] == "FOUND" else "Impossible d'établir une connexion sécurisée HTTPS."
        })
        
        # HSTS Result
        db_results.append({
            "target_id": target_id,
            "platform": "En-tête Strict-Transport-Security (HSTS)",
            "url": None,
            "status": "FOUND" if headers_results["hsts"] == "FOUND" else "NOT_FOUND",
            "response_code": None,
            "details": "L'en-tête HSTS est présent et force l'utilisation du protocole sécurisé HTTPS." if headers_results["hsts"] == "FOUND" else "L'en-tête HSTS est manquant, exposant le site à des attaques par dégradation de protocole (SSL stripping)."
        })
        
        # CSP Result
        db_results.append({
            "target_id": target_id,
            "platform": "En-tête Content-Security-Policy (CSP)",
            "url": None,
            "status": "FOUND" if headers_results["csp"] == "FOUND" else "NOT_FOUND",
            "response_code": None,
            "details": "L'en-tête CSP est configuré, limitant l'exécution de scripts non autorisés." if headers_results["csp"] == "FOUND" else "L'en-tête CSP est manquant, ce qui augmente le risque d'attaques Cross-Site Scripting (XSS)."
        })
        
        # X-Frame-Options Result
        db_results.append({
            "target_id": target_id,
            "platform": "En-tête X-Frame-Options",
            "url": None,
            "status": "FOUND" if headers_results["x_frame"] == "FOUND" else "NOT_FOUND",
            "response_code": None,
            "details": "L'en-tête X-Frame-Options protège le site contre le détournement de clic (Clickjacking)." if headers_results["x_frame"] == "FOUND" else "L'en-tête X-Frame-Options est manquant, rendant l'application vulnérable au Clickjacking."
        })
        
        # SPF Result
        spf_status = "FOUND" if (dns_txt and any("v=spf1" in val.lower() for val in dns_txt)) else "NOT_FOUND"
        spf_record = next((val for val in dns_txt if "v=spf1" in val.lower()), None)
        db_results.append({
            "target_id": target_id,
            "platform": "Configuration DNS Mail (SPF)",
            "url": None,
            "status": spf_status,
            "response_code": None,
            "details": f"Enregistrement SPF trouvé : {spf_record[:200]}" if spf_status == "FOUND" else "Aucun enregistrement SPF trouvé dans les champs TXT, facilitant l'usurpation d'identité par email (email spoofing)."
        })
        
        # DMARC Result
        dmarc_status = "FOUND" if (dmarc_txt and any("v=dmarc1" in val.lower() for val in dmarc_txt)) else "NOT_FOUND"
        dmarc_record = next((val for val in dmarc_txt if "v=dmarc1" in val.lower()), None)
        db_results.append({
            "target_id": target_id,
            "platform": "Configuration DNS Mail (DMARC)",
            "url": None,
            "status": dmarc_status,
            "response_code": None,
            "details": f"Enregistrement DMARC trouvé : {dmarc_record[:200]}" if dmarc_status == "FOUND" else "Aucun enregistrement DMARC trouvé pour le sous-domaine _dmarc, augmentant les risques d'usurpation et réduisant la délivrabilité des emails."
        })
        
        # AI Security Report Result
        db_results.append({
            "target_id": target_id,
            "platform": "Rapport de Sécurité IA",
            "url": None,
            "status": "FOUND",
            "response_code": None,
            "details": report
        })
        
        db.execute(insert(ScanResult), db_results)
        db.commit()
        print(f"[Domain Scan] Completed for {domain}. Saved 7 audit entries.")
        return {"status": "SUCCESS", "target_id": target_id}
        
    except Exception as e:
        db.rollback()
        print(f"[Domain Scan] Database/Processing error: {str(e)}")
        return {"status": "ERROR", "reason": str(e)}
    finally:
        db.close()


def check_gravatar(email: str) -> dict:
    email_clean = email.strip().lower()
    email_hash = hashlib.md5(email_clean.encode('utf-8')).hexdigest()
    url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    try:
        response = httpx.get(url, timeout=5.0)
        if response.status_code == 200:
            return {
                "status": "FOUND",
                "details": f"Profil Gravatar existant détecté. Avatar URL: https://www.gravatar.com/avatar/{email_hash}"
            }
        elif response.status_code == 404:
            return {
                "status": "NOT_FOUND",
                "details": "Aucun profil Gravatar public n'a été détecté pour cette adresse email."
            }
    except Exception as e:
         return {
             "status": "ERROR",
             "details": f"Erreur de communication avec Gravatar : {str(e)}"
         }
    return {
        "status": "NOT_FOUND",
        "details": "Aucun profil Gravatar détecté."
    }


def check_email_domain_mx(email: str) -> dict:
    if "@" not in email:
        return {"status": "ERROR", "details": "Format d'adresse email invalide."}
    domain = email.split("@")[-1]
    mx_records = query_dns_doh(domain, "MX")
    if mx_records:
        return {
            "status": "FOUND",
            "details": f"Serveurs de messagerie configurés (MX) : {', '.join(mx_records)[:200]}"
        }
    else:
        return {
            "status": "NOT_FOUND",
            "details": "Aucun serveur de messagerie (MX) trouvé pour ce domaine. L'adresse email est probablement inactive ou incapable de recevoir des messages."
        }


def search_local_leaks(email: str) -> dict:
    db = SessionLocal()
    try:
        email_clean = email.strip()
        query = select(Leak).where(Leak.email == email_clean).limit(10)
        leaks = db.scalars(query).all()
        if leaks:
            sources = list(set([l.source for l in leaks if l.source]))
            return {
                "status": "FOUND",
                "details": f"L'adresse email a été trouvée dans {len(leaks)} enregistrement(s) de fuites locales. Sources : {', '.join(sources)[:200]}."
            }
        else:
            return {
                "status": "NOT_FOUND",
                "details": "Aucune correspondance trouvée pour cette adresse email dans les bases de fuites locales."
            }
    finally:
        db.close()


@celery_app.task(name="workers.tasks.scan_email")
def scan_email(target_id: int):
    print(f"[Email Scan] Starting scan for target ID: {target_id}")
    db = SessionLocal()
    try:
        # Fetch target details
        target = db.get(Target, target_id)
        if not target or target.type != "email":
            print(f"[Email Scan] Target ID {target_id} not found or is not an email.")
            return {"status": "FAILED", "reason": "Target not found or invalid type"}
            
        email = target.value.lower().strip()
        
        # 1. Check Gravatar
        gravatar_res = check_gravatar(email)
        
        # 2. Check MX records
        mx_res = check_email_domain_mx(email)
        
        # 3. Check Local Leaks
        leaks_res = search_local_leaks(email)
        
        # 4. Save results to database
        db_results = []
        
        # Gravatar entry
        db_results.append({
            "target_id": target_id,
            "platform": "Gravatar Profile check",
            "url": f"https://en.gravatar.com/" if gravatar_res["status"] == "FOUND" else None,
            "status": gravatar_res["status"],
            "response_code": None,
            "details": gravatar_res["details"]
        })
        
        # MX configuration entry
        db_results.append({
            "target_id": target_id,
            "platform": "Serveurs MX (Délivrabilité)",
            "url": None,
            "status": mx_res["status"],
            "response_code": None,
            "details": mx_res["details"]
        })
        
        # Leaks entries
        db_results.append({
            "target_id": target_id,
            "platform": "Bases de fuites locales",
            "url": None,
            "status": leaks_res["status"],
            "response_code": None,
            "details": leaks_res["details"]
        })
        
        db.execute(insert(ScanResult), db_results)
        db.commit()
        print(f"[Email Scan] Completed for {email}. Saved 3 audit entries.")
        return {"status": "SUCCESS", "target_id": target_id}
        
    except Exception as e:
        db.rollback()
        print(f"[Email Scan] Database/Processing error: {str(e)}")
        return {"status": "ERROR", "reason": str(e)}
    finally:
        db.close()
