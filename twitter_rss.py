#!/usr/bin/env python3
"""
Batch Twitter RSS Generator with Smart Detection
- Read users from users.txt
- Generate/update feeds/{user}.rss only if tweets changed
- Use feeds/state.json for hash storage
"""
import os
import sys
import requests
from bs4 import BeautifulSoup
from feedgenerator import Rss201rev2Feed
from datetime import datetime, timezone
import json
import hashlib

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64)"
TIMEOUT = 15
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    # 添加更多实例如果需要，例如 "https://nitter.cz"
]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
FEEDS_DIR = os.path.join(BASE_DIR, "feeds")
STATE_FILE = os.path.join(FEEDS_DIR, "state.json")

def read_users():
    users = []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip().lstrip("@")
            if u and not u.startswith("#"):
                users.append(u)
    return users

def compute_hash(tweets):
    content = ''.join(tweets) if tweets else "empty"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def fetch_tweets(username):
    for base in NITTER_INSTANCES:
        try:
            url = f"{base}/{username}"
            print(f"🔎 Fetching {url}", file=sys.stderr)
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select(".tweet-content")
            tweets = [it.get_text(strip=True) for it in items[:15] if it.get_text(strip=True)]
            if tweets:
                return tweets, base
        except Exception as e:
            print(f"⚠️ {base} failed: {e}", file=sys.stderr)
    return [], None

def generate_rss(username, tweets, source):
    now = datetime.now(timezone.utc)
    feed = Rss201rev2Feed(
        title=f"X (Twitter) - @{username}",
        link=f"https://twitter.com/{username}",
        description=f"Fetched via Nitter ({source or 'N/A'})",
        language="en",
        lastBuildDate=now,
    )
    if tweets:
        for i, t in enumerate(tweets):
            feed.add_item(
                title=t[:80] + "..." if len(t) > 80 else t,
                link=f"https://twitter.com/{username}",
                description=t,
                pubdate=now,
                unique_id=f"{username}-{i}-{int(now.timestamp())}",
            )
    else:
        feed.add_item(
            title="No tweets fetched",
            link=f"https://twitter.com/{username}",
            description="All Nitter instances failed or user has no public tweets.",
            pubdate=now,
            unique_id=f"{username}-empty-{int(now.timestamp())}",
        )
    return feed.writeString("utf-8")

def main():
    os.makedirs(FEEDS_DIR, exist_ok=True)
    users = read_users()
    print(f"👥 Users: {users}", file=sys.stderr)
    state = load_state()
    new_state = state.copy()
    updated = False

    for user in users:
        tweets, src = fetch_tweets(user)
        if not src:  # Fetch failed completely
            print(f"❌ Failed to fetch for {user}, skipping update.", file=sys.stderr)
            continue

        current_hash = compute_hash(tweets)
        old_hash = state.get(user)

        if current_hash != old_hash:
            rss = generate_rss(user, tweets, src)
            path = os.path.join(FEEDS_DIR, f"{user}.rss")
            with open(path, "w", encoding="utf-8") as f:
                f.write(rss)
            print(f"✅ Updated {path}", file=sys.stderr)
            new_state[user] = current_hash
            updated = True
        else:
            print(f"📄 No change for {user}", file=sys.stderr)

    if updated:
        save_state(new_state)
        print("🔄 State updated.", file=sys.stderr)
    else:
        print("🚫 No updates needed.", file=sys.stderr)

if __name__ == "__main__":
    main()
