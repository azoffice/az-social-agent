#!/usr/bin/env python3
"""
AZ Office Automation - social posting agent.

Reads a content bank (Google Sheet published as CSV, or local content.csv),
picks the next unposted row, writes an SEO/GEO caption with Gemini,
and posts the image + caption to Telegram, Facebook Page and Instagram.

Zero running cost. Designed for GitHub Actions cron.
"""

import csv
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

STATE_FILE = "posted.json"
LOCAL_CSV = "content.csv"
GRAPH = "https://graph.facebook.com/v21.0"

DRY_RUN = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------- utilities

def http(url, data=None, headers=None, method=None, timeout=60):
    """Minimal HTTP helper. Returns (status, parsed_json_or_text)."""
    body = None
    headers = dict(headers or {})
    if data is not None:
        if isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode()
            headers.setdefault("Content-Type",
                               "application/x-www-form-urlencoded")
        elif isinstance(data, (dict, list)):
            body = json.dumps(data).encode()
            headers.setdefault("Content-Type", "application/json")
        else:
            body = data
    req = urllib.request.Request(url, data=body, headers=headers,
                                 method=method or ("POST" if body else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        status = e.code
    except Exception as e:
        return 0, str(e)
    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw


def post_json(url, payload, timeout=60):
    return http(url, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}, timeout=timeout)


def log(msg):
    print(msg, flush=True)


# ------------------------------------------------------------- content bank

def load_rows():
    """Load content rows from the published Google Sheet CSV, else local CSV."""
    sheet_url = os.environ.get("SHEET_CSV_URL", "").strip()
    text = None

    if sheet_url:
        status, body = http(sheet_url)
        if status == 200 and isinstance(body, str) and body.strip():
            text = body
            log("Content bank: Google Sheet")
        else:
            log(f"Sheet fetch failed ({status}); falling back to {LOCAL_CSV}")

    if text is None:
        if not os.path.exists(LOCAL_CSV):
            sys.exit(f"No content source. Set SHEET_CSV_URL or add {LOCAL_CSV}")
        with open(LOCAL_CSV, encoding="utf-8") as f:
            text = f.read()
        log(f"Content bank: {LOCAL_CSV}")

    rows = []
    for raw in csv.DictReader(io.StringIO(text)):
        row = {(k or "").strip().lower(): (v or "").strip()
               for k, v in raw.items()}
        if not row.get("id"):
            continue
        if row.get("skip", "").lower() in ("y", "yes", "true", "1"):
            continue
        if not row.get("image_url"):
            log(f"Row {row['id']}: no image_url, skipped")
            continue
        rows.append(row)

    if not rows:
        sys.exit("Content bank is empty.")
    return rows


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                s = json.load(f)
            if isinstance(s, dict) and isinstance(s.get("posted"), list):
                return s
        except Exception:
            pass
    return {"posted": [], "history": []}


def save_state(state):
    state["history"] = state.get("history", [])[-200:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def pick_row(rows, state):
    """Oldest unposted row. When the bank is exhausted, start the cycle again."""
    posted = state.get("posted", [])
    for r in rows:
        if r["id"] not in posted:
            return r, state
    log("All content posted once — starting a fresh cycle.")
    state["posted"] = []
    return rows[0], state


# ----------------------------------------------------------------- captions

AREAS = ("Nagasandra, Peenya, Jalahalli, Yeshwanthpur, Dasarahalli, "
         "Rajajinagar, Nelamangala, Tumkur Road")

BASE_TAGS = ("#Bangalore #Photocopier #XeroxMachine #CanonCopier "
             "#PhotocopierRental #TonerSupply #AMC #OfficeAutomation "
             "#Peenya #Nagasandra #Yeshwanthpur #Rajajinagar #BangaloreBusiness")

PROMPT = """You write social media captions for AZ Office Automation, a \
photocopier and IT products sales and service business in Nagasandra, HMT \
Layout, Bangalore.

Business facts you may use:
- Brands: Canon, Xerox, Kyocera, Konica Minolta, Fuji Film, Epson
- New machines (all brands, colour and black & white) and reconditioned \
machines (Canon, Xerox, Kyocera, Konica Minolta only)
- Photocopier rental, AMC and CPC contracts, toner and spares supply, \
on-site repair
- Also IT products: interactive displays, CCTV and surveillance, attendance \
systems, laptops and desktops, networking, servers, IP telephony, projectors
- Serves Bangalore and Karnataka
- Call 8553202432 / 9916922432

Today's post topic: {topic}
Extra notes from the owner: {notes}

Write ONE caption that is:
- Opens with a short question a Bangalore office admin would actually type \
into Google, then answers it directly (Q&A format)
- Naturally includes real search keywords such as photocopier dealer \
Bangalore, xerox machine repair, copier on rent, toner supplier, AMC service
- Mentions two or three of these areas naturally: {areas}
- 90 to 130 words, plain and factual, no hype, no emoji spam (2-3 emoji maximum)
- Ends with: a one-line call to action with the phone numbers, then a blank \
line, then 12-15 hashtags on one line

Output only the caption text. No preamble, no markdown, no quotation marks."""


def fallback_caption(topic, notes):
    return (
        f"Looking for {topic} in Bangalore?\n\n"
        f"AZ Office Automation supplies and services Canon, Xerox, Kyocera, "
        f"Konica Minolta, Fuji Film and Epson machines across {AREAS}. "
        f"New and reconditioned photocopiers, machines on monthly rent, AMC "
        f"and CPC contracts, genuine toner and spares, and same-day on-site "
        f"repair by our own technician.\n"
        f"{(notes + chr(10)) if notes else ''}\n"
        f"Call 8553202432 / 9916922432 for a quote today.\n\n"
        f"{BASE_TAGS}"
    )


def clean_caption(text):
    text = re.sub(r"^```[a-z]*\n?|```$", "", text.strip(), flags=re.M)
    text = text.strip().strip('"').strip()
    return re.sub(r"\n{3,}", "\n\n", text)


def gemini_models(key):
    """Ask Google which models this key can actually use, cheapest first.

    Model names change over time, so never hard-code one. GEMINI_MODEL
    (a repo variable) is tried first if set, then whatever ListModels
    reports, preferring small 'flash'/'lite' models on the free tier.
    """
    forced = os.environ.get("GEMINI_MODEL", "").strip()
    found = []
    for ver in ("v1beta", "v1"):
        status, body = http(f"https://generativelanguage.googleapis.com/"
                            f"{ver}/models?key={urllib.parse.quote(key)}"
                            f"&pageSize=200")
        if status != 200 or not isinstance(body, dict):
            continue
        for m in body.get("models", []):
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            name = m.get("name", "").split("/")[-1]
            if not name or name in found:
                continue
            low = name.lower()
            if any(w in low for w in ("embedding", "aqa", "imagen", "veo",
                                      "vision", "tts", "image", "audio",
                                      "live", "native")):
                continue
            found.append(name)
        if found:
            break

    def rank(n):
        low = n.lower()
        return (0 if "flash" in low else 1,
                0 if ("lite" in low or "8b" in low) else 1,
                0 if "preview" not in low and "exp" not in low else 1,
                len(n))

    found.sort(key=rank)
    order = ([forced] if forced else []) + [m for m in found if m != forced]
    if not order:
        log("Gemini: ListModels returned nothing usable")
    else:
        log(f"Gemini: {len(order)} model(s) available, trying "
            f"{', '.join(order[:3])}")
    return order[:3]


def make_caption(row):
    override = row.get("caption_override", "")
    if override:
        log("Caption: override from content bank")
        return override

    topic = row.get("topic", "photocopier sales and service")
    notes = row.get("notes", "")
    key = os.environ.get("GEMINI_API_KEY", "").strip()

    if not key:
        log("Caption: no GEMINI_API_KEY, using fallback template")
        return fallback_caption(topic, notes)

    payload = {
        "contents": [{"parts": [{"text": PROMPT.format(
            topic=topic, notes=notes or "none", areas=AREAS)}]}],
        "generationConfig": {"temperature": 0.9, "maxOutputTokens": 800},
    }

    for model in gemini_models(key):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:generateContent?key={urllib.parse.quote(key)}")
        for attempt in (1, 2):
            status, body = post_json(url, payload)
            if status == 200 and isinstance(body, dict):
                try:
                    text = body["candidates"][0]["content"]["parts"][0]["text"]
                    if text.strip():
                        log(f"Caption: generated by {model}")
                        return clean_caption(text)
                except (KeyError, IndexError, TypeError):
                    pass
            log(f"Gemini {model} attempt {attempt} failed ({status}): "
                f"{str(body)[:200]}")
            if status == 404:
                break          # wrong model name — try the next model
            if attempt == 1:
                time.sleep(5)  # rate limit or blip — retry the same model

    log("Caption: falling back to template")
    return fallback_caption(topic, notes)


# ---------------------------------------------------------------- platforms

def post_telegram(caption, image_url):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (token and chat):
        return None, "not configured"

    # Telegram photo captions are capped at 1024 characters.
    short = caption if len(caption) <= 1024 else caption[:1015].rstrip() + "…"
    status, body = http(f"https://api.telegram.org/bot{token}/sendPhoto",
                        data={"chat_id": chat, "photo": image_url,
                              "caption": short})
    if status == 200 and isinstance(body, dict) and body.get("ok"):
        return True, "posted"
    return False, f"{status}: {str(body)[:300]}"


def post_facebook(caption, image_url):
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not (page_id and token):
        return None, "not configured"

    status, body = http(f"{GRAPH}/{page_id}/photos",
                        data={"url": image_url, "caption": caption,
                              "published": "true", "access_token": token})
    if status == 200 and isinstance(body, dict) and body.get("id"):
        return True, f"post {body.get('post_id', body['id'])}"
    return False, f"{status}: {str(body)[:300]}"


def post_instagram(caption, image_url):
    ig_id = os.environ.get("IG_USER_ID", "").strip()
    token = os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not (ig_id and token):
        return None, "not configured"

    # Instagram captions are capped at 2200 characters.
    cap = caption if len(caption) <= 2200 else caption[:2190].rstrip() + "…"

    status, body = http(f"{GRAPH}/{ig_id}/media",
                        data={"image_url": image_url, "caption": cap,
                              "access_token": token})
    if status != 200 or not isinstance(body, dict) or not body.get("id"):
        return False, f"container {status}: {str(body)[:300]}"
    container = body["id"]

    # Instagram processes the image asynchronously; wait for FINISHED.
    for _ in range(12):
        time.sleep(5)
        s, b = http(f"{GRAPH}/{container}?fields=status_code"
                    f"&access_token={urllib.parse.quote(token)}")
        state = b.get("status_code") if isinstance(b, dict) else None
        if state == "FINISHED":
            break
        if state == "ERROR":
            return False, f"container error: {str(b)[:300]}"
    else:
        return False, "container never finished processing"

    status, body = http(f"{GRAPH}/{ig_id}/media_publish",
                        data={"creation_id": container, "access_token": token})
    if status == 200 and isinstance(body, dict) and body.get("id"):
        return True, f"media {body['id']}"
    return False, f"publish {status}: {str(body)[:300]}"


PLATFORMS = {
    "telegram": post_telegram,
    "facebook": post_facebook,
    "instagram": post_instagram,
}


# --------------------------------------------------------------------- main

def main():
    rows = load_rows()
    state = load_state()
    row, state = pick_row(rows, state)

    image_url = row["image_url"]
    wanted = [p.strip().lower() for p in
              (row.get("platforms") or "telegram,facebook,instagram").split(",")
              if p.strip()]

    log(f"\nRow id   : {row['id']}")
    log(f"Topic    : {row.get('topic', '(none)')}")
    log(f"Image    : {image_url}")
    log(f"Platforms: {', '.join(wanted)}\n")

    caption = make_caption(row)
    log("-" * 60)
    log(caption)
    log("-" * 60 + "\n")

    if DRY_RUN:
        log("DRY_RUN set — nothing was posted, state not changed.")
        return 0

    results, failures = {}, []
    for name in wanted:
        fn = PLATFORMS.get(name)
        if not fn:
            log(f"{name:10s} unknown platform, skipped")
            continue
        ok, detail = fn(caption, image_url)
        if ok is None:
            log(f"{name:10s} skipped ({detail})")
            results[name] = "skipped"
        elif ok:
            log(f"{name:10s} OK — {detail}")
            results[name] = "ok"
        else:
            log(f"{name:10s} FAILED — {detail}")
            results[name] = "failed"
            failures.append(name)

    if any(v == "ok" for v in results.values()):
        state.setdefault("posted", []).append(row["id"])
        state.setdefault("history", []).append({
            "id": row["id"],
            "topic": row.get("topic", ""),
            "at": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "results": results,
        })
        save_state(state)
        log(f"\nState updated — {row['id']} marked as posted.")
    else:
        log("\nNothing posted anywhere; state unchanged so it retries next run.")
        return 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
