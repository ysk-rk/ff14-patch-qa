"""保存したパッチノートの HTML から本文と表を取り出し、検索用のチャンクに分けて保存する。"""

import json
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from fetch_lodestone import BASE_URL, PATCH_NOTES

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "lodestone"
OUTPUT = ROOT / "data" / "processed" / "chunks.jsonl"

# 1チャンクの目安の文字数（これを超えたら段落や表の行の区切りで分ける）
MAX_CHARS = 1500

# 見出しの階層の数（大分類・中分類・項目・ジョブ名など・その下）
HEADING_DEPTH = 5
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "dl", "dt", "dd", "section", "br"}
SKIP_TAGS = {"script", "style", "noscript", "img"}


def heading_level(tag: Tag) -> int | None:
    """見出しの階層を返す（0 が一番上）。見出しでなければ None。

    ロードストーンのパッチノートは、タグ名だけでは階層が決まらない。
      0: h3.mdl-title__ancher        大分類（バトル関連、アイテム関連など）
      1: h2                          中分類（PvP全般、クエスト関連など）
      2: その他の h3                  項目（「アクション／特性において…」など）
      3: h4                          ジョブ名など
      4: h5
    """
    if tag.name == "h3":
        return 0 if "mdl-title__ancher" in tag.get("class", []) else 2
    return {"h2": 1, "h4": 3, "h5": 4}.get(tag.name)


@dataclass
class Block:
    headings: tuple[str, ...]
    kind: str  # "text" または "table"
    content: str


def table_to_markdown(table: Tag) -> str:
    """HTML の表を Markdown の表に変換する。"""
    rows = []
    for tr in table.find_all("tr"):
        cells = [c.get_text(" ", strip=True).replace("|", "／") for c in tr.find_all(["th", "td"])]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""

    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]

    # 矢印の画像だけが入った列のように、すべての行が空の列は消す
    keep = [i for i in range(width) if any(r[i] for r in rows)]
    rows = [[r[i] for i in keep] for r in rows]

    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join("---" for _ in keep) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


class Walker:
    """本文を先頭から順に読み、見出しの階層を記録しながら段落と表に分ける。"""

    def __init__(self) -> None:
        self.path = [""] * HEADING_DEPTH
        self.blocks: list[Block] = []
        self.buffer: list[str] = []

    def headings(self) -> tuple[str, ...]:
        return tuple(h for h in self.path if h)

    def flush(self) -> None:
        text = " ".join(self.buffer).strip()
        self.buffer = []
        if text:
            self.blocks.append(Block(self.headings(), "text", text))

    def walk(self, node: Tag) -> None:
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    self.buffer.append(text)
                continue
            if not isinstance(child, Tag) or child.name in SKIP_TAGS:
                continue

            level = heading_level(child)
            if level is not None:
                self.flush()
                self.path[level] = child.get_text(" ", strip=True)
                # 自分より下の階層の見出しは、新しい見出しが来たらリセットする
                for i in range(level + 1, HEADING_DEPTH):
                    self.path[i] = ""
            elif child.name == "table":
                self.flush()
                markdown = table_to_markdown(child)
                if markdown:
                    self.blocks.append(Block(self.headings(), "table", markdown))
            else:
                is_block = child.name in BLOCK_TAGS
                if is_block:
                    self.flush()
                if child.name == "li":
                    self.buffer.append("-")
                self.walk(child)
                if is_block:
                    self.flush()


def split_table(markdown: str) -> list[str]:
    """長すぎる表を行の区切りで分ける。分けたそれぞれに見出しの行を付け直す。"""
    lines = markdown.split("\n")
    header, rows = lines[:2], lines[2:]
    parts: list[str] = []
    current: list[str] = []
    for row in rows:
        if current and len("\n".join(header + current + [row])) > MAX_CHARS:
            parts.append("\n".join(header + current))
            current = []
        current.append(row)
    if current:
        parts.append("\n".join(header + current))
    return parts or [markdown]


def make_chunks(blocks: list[Block]):
    """同じ見出しの下にある段落と表を、MAX_CHARS を目安にまとめる。"""
    sections: list[tuple[tuple[str, ...], list[Block]]] = []
    for block in blocks:
        if sections and sections[-1][0] == block.headings:
            sections[-1][1].append(block)
        else:
            sections.append((block.headings, [block]))

    for headings, items in sections:
        pieces: list[tuple[str, str]] = []
        for block in items:
            if block.kind == "table" and len(block.content) > MAX_CHARS:
                pieces += [("table", part) for part in split_table(block.content)]
            else:
                pieces.append((block.kind, block.content))

        current: list[str] = []
        has_table = False
        for kind, text in pieces:
            if current and len("\n\n".join(current + [text])) > MAX_CHARS:
                yield headings, "\n\n".join(current), has_table
                current, has_table = [], False
            current.append(text)
            has_table |= kind == "table"
        if current:
            yield headings, "\n\n".join(current), has_table


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    total = 0

    with OUTPUT.open("w", encoding="utf-8") as f:
        for version, path in PATCH_NOTES.items():
            html = (RAW_DIR / f"{version}.html").read_text(encoding="utf-8")
            wrapper = BeautifulSoup(html, "html.parser").select_one("div.news__detail__wrapper")
            if wrapper is None:
                print(f"  {version:<5}  本文が見つかりません（スキップ）")
                continue

            walker = Walker()
            walker.walk(wrapper)
            walker.flush()

            count = tables = longest = 0
            for i, (headings, text, has_table) in enumerate(make_chunks(walker.blocks)):
                record = {
                    "id": f"{version}-{i:04d}",
                    "version": version,
                    "order": float(version),  # 7.05 < 7.1 < 7.11 < 7.2 の順に並ぶ
                    "headings": list(headings),
                    "has_table": has_table,
                    "url": BASE_URL + path,
                    # 検索のときに文脈が伝わるよう、パッチ番号と見出しを先頭に付ける
                    "text": f"[パッチ{version}] {' > '.join(headings)}\n{text}",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
                tables += has_table
                longest = max(longest, len(text))

            print(f"  {version:<5}  {count:>4} チャンク（表あり {tables:>3}）  最長 {longest:>5} 文字")
            total += count

    print(f"完了: {total} チャンク → {OUTPUT}")


if __name__ == "__main__":
    main()