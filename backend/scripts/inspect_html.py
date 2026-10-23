"""保存したパッチノートの HTML の作りを調べる（調査用）。"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "lodestone"


def describe(tag) -> str:
    """タグ名と class を「div.news__detail」のような形で返す。"""
    classes = ".".join(tag.get("class", []))
    return f"{tag.name}.{classes}" if classes else tag.name


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else "7.2"
    html = (RAW_DIR / f"{version}.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table")
    print(f"[{version}] 表の数: {len(tables)}")

    # 最初の表が、どのタグの中に入っているか（本文の入れ物を探す手がかり）
    if tables:
        parents = [describe(p) for p in tables[0].parents if p.name not in ("[document]", "html")]
        print("最初の表の親（内側から順に）:")
        for p in parents[:8]:
            print(f"  {p}")

    # 見出しの数と最初のいくつか
    for level in ("h1", "h2", "h3", "h4"):
        heads = soup.find_all(level)
        print(f"{level} の数: {len(heads)}")
        for h in heads[:5]:
            print(f"  {describe(h)}: {h.get_text(strip=True)[:40]}")

    # 最初の表の中身（先頭の3行）
    if tables:
        print("最初の表の先頭3行:")
        for row in tables[0].find_all("tr")[:3]:
            cells = [c.get_text(" ", strip=True)[:20] for c in row.find_all(["th", "td"])]
            print(f"  {cells}")


if __name__ == "__main__":
    main()