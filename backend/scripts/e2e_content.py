"""End-to-end smoke for the content-scoring product against a running API.

Usage: python -m scripts.e2e_content  (API expected at http://127.0.0.1:8000)
"""
from __future__ import annotations

import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx

BASE = "http://127.0.0.1:8000/api"
SAMPLE = (
    "我用3个月把粉丝从0做到1万，方法只有3步。\n"
    "第一，先写结论；第二，用具体数字；第三，结尾提问。\n"
    "你最常用哪一招？评论区告诉我。"
)


def main() -> int:
    email = f"e2e-content-{int(time.time())}@example.com"
    with httpx.Client(timeout=180) as c:
        r = c.post(f"{BASE}/auth/register", json={"email": email, "password": "e2econtent1"})
        r.raise_for_status()
        dev = r.json().get("dev_verify_url")
        if dev:
            token = parse_qs(urlparse(dev).query)["token"][0]
            c.get(f"{BASE}/auth/verify", params={"token": token}).raise_for_status()
        login = c.post(f"{BASE}/auth/login", json={"email": email, "password": "e2econtent1"})
        login.raise_for_status()
        h = {"Authorization": f"Bearer {login.json()['token']}"}

        doc = c.post(
            f"{BASE}/documents",
            headers=h,
            json={"title": "增长复盘", "content": SAMPLE, "platform": "xiaohongshu"},
        )
        doc.raise_for_status()
        did = doc.json()["id"]
        print("DOC", doc.json())

        t0 = time.time()
        card = c.post(f"{BASE}/documents/{did}/analyze?lang=zh", headers=h)
        card.raise_for_status()
        body = card.json()
        print(f"ANALYZE {round(time.time()-t0,1)}s overall={body['overall_score']}")
        for d in body["dimensions"]:
            ev = d["evidence"][0]["quote"] if d["evidence"] else "-"
            print(f"  {d['key']}: band {d['band']} score {d['score']} | {ev[:30]}")

        full = c.post(f"{BASE}/documents/{did}/rewrite?lang=zh", headers=h, json={"kind": "full"})
        full.raise_for_status()
        print("REWRITE chars:", len(full.json()["content"]))

        ex = c.get(f"{BASE}/documents/{did}/export?fmt=md", headers=h)
        ex.raise_for_status()
        print("EXPORT md bytes:", len(ex.content))
    return 0


if __name__ == "__main__":
    sys.exit(main())
