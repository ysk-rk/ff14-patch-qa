"""本文中の h2 と h3 を、出てくる順にタグ名と class 付きで表示する（調査用）。

使い方: python scripts\\outline.py パッチ番号
"""

import sys
from pathlib import Path

from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "lodestone"


def main() -> None:
    version = sys.argv[1] if len(sys.argv) > 1 else "7.2"
    html = (RAW_DIR / f"{version}.html").read_text(encoding="utf-8")
    wrapper = BeautifulSoup(html, "html.parser").select_one("div.news__detail__wrapper")

    for tag in wrapper.find_all(["h2", "h3"]):
        classes = ".".join(tag.get("class", []))
        name = f"{tag.name}.{classes}" if classes else tag.name
        indent = "" if tag.name == "h2" or "mdl-title__ancher" in classes else "    "
        print(f"{indent}{name:<55} {tag.get_text(strip=True)[:30]}")


if __name__ == "__main__":
    main()