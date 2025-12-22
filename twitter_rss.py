#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
from feedgenerator import RssFeed
from datetime import datetime, timezone
import sys
import os

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
NITTERS = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.fdn.fr",
    "https://nitter.1d4.us",
]

def fetch_tweets(username):
    for base in NITTERS:
        try:
            url = f"{base}/{username}"
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            tweets = []
            for t in soup.select(".tweet-content")[:10]:
                text = t.get_text(strip=True)
                if len(text) > 10:
                    tweets.append(text)
            if tweets:
                return tweets, base
        except Exception:
            continue
    return [], None

def main():
    if not os.path.exists("users.txt"):
        print("users.txt not found", file=sys.stderr)
        sys.exit(1)

    with open("users.txt") as f:
        users = [u.strip() for u in f if u.strip()]

    feed = RssFeed(
        title="Crypto X KOL Feed",
        link="https://twitter.com",
        description="Multi X KOL RSS via GitHub Actions",
        language="en",
    )

    for user in users:
        tweets, src = fetch_tweets(user)
        if not tweets:
            continue
        for i, text in enumerate(tweets):
            uid = f"{user}-{hash(text)}"
            feed.add_item(
                title=f"@{user}",
                description=text,
                link=f"https://twitter.com/{user}",
                unique_id=uid,
                pubdate=datetime.now(timezone.utc),
            )

    print(feed.writeString("utf-8"))

if __name__ == "__main__":
    main()
