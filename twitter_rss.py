#!/usr/bin/env python3
"""
Batch Twitter RSS Generator via Nitter
- Read users from users.txt
- Generate one RSS per user into feeds/
"""

import os
import sys
import requests
from bs4 import BeautifulSoup
from feedgenerator import RssFeed
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64)"
TIMEOUT = 15

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.fdn.fr",
    "https://nitter.1d4.us",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.txt")
FEEDS_DIR = os.path.join(BASE_DIR, "feeds")


def read_users():
    if not os.path.exists(USERS_FILE):
        print("❌ users.txt not found", file=sys.stderr)
        sys.exit(1)

    users = []
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            u = line.strip().lstrip("@")
            if u and not u.startswith("#"):
                users.append(u)

    return users


def fetch_tweets(username):
    for base in NITTER_INSTANCES:
        try:
            url = f"{base}/{username}"
            print(f"🔎 Fetching {url}", file=sys.stderr)
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            r.raise_for_status()

            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.select(".tweet-content")

            tweets = []
            for it in items[:15]:
                text = it.get_text(strip=True)
                if text:
                    tweets.append(text)

            if tweets:
                return tweets, base
        except Exception as e:
            print(f"⚠️ {base} failed: {e}", file=sys.stderr)

    return [], None


def generate_rss(username, tweets, source):
    feed = RssFeed(
        title=f"X (Twitter) - @{username}",
        link=f"https://twitter.com/{username}",
        description=f"Fetched via Nitter ({source})",
        language="en",
    )

    now = datetime.now(timezone.utc)

    if tweets:
        for i, t in enumerate(tweets):
            feed.add_item(
                title=t[:60],
                link=f"https://twitter.com/{username}/status/{i}",
                description=t,
                pubdate=now,
                unique_id=f"{username}-{i}-{int(now.timestamp())}",
            )
    else:
        feed.add_item(
            title="No tweets fetched",
            link=f"https://twitter.com/{username}",
            description="All Nitter instances failed or no public tweets.",
            pubdate=now,
            unique_id=f"{username}-empty-{int(now.timestamp())}",
        )

    return feed.writeString("utf-8")


def main():
    os.makedirs(FEEDS_DIR, exist_ok=True)

    users = read_users()
    print(f"👥 Users: {users}", file=sys.stderr)

    for user in users:
        tweets, src = fetch_tweets(user)
        rss = generate_rss(user, tweets, src or "N/A")

        path = os.path.join(FEEDS_DIR, f"{user}.rss")
        with open(path, "w", encoding="utf-8") as f:
            f.write(rss)

        print(f"✅ Generated {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
