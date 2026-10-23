"""Steam のニュース API から FF14 のパッチノート（7.x）を取得して保存する。"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

APP_ID = 39210  # FINAL FANTASY XIV Online（Steam版）
API_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/"

# 「Patch 7.57 Notes」のようなタイトルだけを対象にする
PATCH_TITLE = re.compile(r"Patch\s+(7\.\d+[a-z]?)\s+Notes", re.IGNORECASE)

# 黄金のレガシー（7.0）より前の記事まで来たら取得をやめる
CUTOFF = datetime(2024, 6, 1, tzinfo=timezone.utc)

OUTPUT = Path(__file__).resolve().parents[2] / "data" / "raw" / "patch_notes.json"


def fetch_page(enddate: int | None) -> list[dict]:
    """enddate（UNIX時刻）より前の記事を最大100件取得する。"""
    params = {
        "appid": APP_ID,
        "count": 100,
        "maxlength": 0,  # 0 = 本文を省略せずに全文取得
        "format": "json",
        "feeds": "steam_community_announcements",  # 公式のお知らせだけ
    }
    if enddate is not None:
        params["enddate"] = enddate

    res = requests.get(API_URL, params=params, timeout=30)
    res.raise_for_status()
    return res.json().get("appnews", {}).get("newsitems", [])


def main() -> None:
    notes: list[dict] = []
    seen: set[str] = set()
    enddate: int | None = None

    while True:
        items = fetch_page(enddate)
        if not items:
            break

        for item in items:
            if item["gid"] in seen:
                continue
            seen.add(item["gid"])

            published = datetime.fromtimestamp(item["date"], tz=timezone.utc)
            match = PATCH_TITLE.search(item["title"])
            if match and published >= CUTOFF:
                notes.append(
                    {
                        "id": item["gid"],
                        "version": match.group(1),
                        "title": item["title"],
                        "date": published.date().isoformat(),
                        "url": item["url"],
                        "contents": item["contents"],
                    }
                )

        oldest = min(item["date"] for item in items)
        if datetime.fromtimestamp(oldest, tz=timezone.utc) < CUTOFF:
            break

        enddate = oldest - 1
        time.sleep(1)  # APIに負荷をかけないよう間隔をあける

    notes.sort(key=lambda n: n["date"])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{len(notes)} 件のパッチノートを保存しました: {OUTPUT}")
    for n in notes:
        print(f"  {n['date']}  {n['version']:<6}  {len(n['contents']):>7} 文字  {n['title']}")


if __name__ == "__main__":
    main()