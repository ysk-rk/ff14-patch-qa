"""分かれた表の行を出して、次のテスト用の問題の候補を探す。

extract_chunks.py は長い表を行の区切りで分けるので、同じパッチの同じ見出しに
表のチャンクが2つ以上できる。その各行（スキル名と変更点）を出す。
検索も AI も呼ばず、資料の作りだけを見る。

--skills-only を付けると、ジョブのスキルの表（見出しの一つ上に JOB_SECTION_WORDS が
すべて入っているもの）だけを出し、各行に同じスキルの変更があるパッチを足す。

使い方: python scripts\\find_split_tables.py [--mode pve|pvp] [--skills-only] [--include-used] [--show 30]
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rules import JOB_SECTION_WORDS, is_pvp_text  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
EVAL_DIR = ROOT / "eval"


def load_table_chunks() -> list[dict]:
    """表を含み、見出しのあるチャンクを chunks.jsonl の並びのまま返す。"""
    chunks = []
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if c.get("has_table") and c.get("headings"):
                chunks.append(c)
    return chunks


def make_groups(chunks: list[dict]) -> list[list[dict]]:
    """表のチャンクを (version, headings) ごとにまとめ、2つ以上あるものを返す。"""
    groups = defaultdict(list)
    for c in chunks:
        groups[(c["version"], tuple(c["headings"]))].append(c)
    # chunks.jsonl の並びのままにする（ID の順と同じ）
    return [g for g in groups.values() if len(g) >= 2]


def is_skill_group(group: list[dict]) -> bool:
    """見出しの一つ上に JOB_SECTION_WORDS がすべて入っていれば、ジョブのスキルの表とみなす。"""
    headings = group[0]["headings"]
    return len(headings) >= 2 and all(w in headings[-2] for w in JOB_SECTION_WORDS)


def skill_patches(chunks: list[dict]) -> dict:
    """(mode, スキル名) ごとに、表の1列目にそのスキルがあるパッチを集める。分かれていない表も含む。"""
    patches = defaultdict(dict)
    for c in chunks:
        mode = "pvp" if is_pvp_text(c["text"]) else "pve"
        for skill, _ in table_rows(c["text"]):
            patches[(mode, skill.replace(" ", ""))][c["version"]] = float(c["order"])
    return patches


def table_rows(text: str):
    """表の行から (スキル名, 変更点) を出す。見出しの行と区切りの行は除く。

    見出しの行は「名称」の表だけでなく「アイテム名」などの表もあるので、
    区切りの行（|---|）のすぐ上の行を見出しとみなす。
    """
    rows = []
    for t in text.splitlines():
        if not t.startswith("|"):
            continue
        cells = [x.strip() for x in t.strip().strip("|").split("|")]
        if all(set(x) <= set("-: ") for x in cells):
            if rows:
                rows.pop()  # 区切りの行のすぐ上は見出しの行
            continue
        rows.append(cells)
    for cells in rows:
        if len(cells) >= 2 and cells[0] != "名称":
            yield cells[0], cells[-1]


def used_keywords() -> set[str]:
    words = set()
    for path in EVAL_DIR.glob("*.jsonl"):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    k = json.loads(line).get("keyword")
                    if k:
                        words.add(k.replace(" ", ""))
    return words


def main() -> None:
    p = argparse.ArgumentParser(description="分かれた表の行を出す")
    p.add_argument("--mode", choices=["pve", "pvp"], help="省略時は両方")
    p.add_argument("--skills-only", action="store_true", help="ジョブのスキルの表だけを出す")
    p.add_argument("--include-used", action="store_true", help="評価やテストで使ったスキルも出す")
    p.add_argument("--show", type=int, default=30, help="表示する件数")
    args = p.parse_args()

    used = set() if args.include_used else used_keywords()
    chunks = load_table_chunks()
    groups = make_groups(chunks)
    if args.skills_only:
        groups = [g for g in groups if is_skill_group(g)]
        patches = skill_patches(chunks)
    # チャンク数が多い順、同じならパッチの古い順
    groups.sort(key=lambda g: (-len(g), float(g[0]["order"])))

    found = []
    for g in groups:
        for i, c in enumerate(g, 1):
            mode = "pvp" if is_pvp_text(c["text"]) else "pve"
            if args.mode and mode != args.mode:
                continue
            for skill, change in table_rows(c["text"]):
                if skill.replace(" ", "") in used:
                    continue
                found.append((c, f"{i}/{len(g)}", mode, skill, change))

    print(f"分かれた表: {len(groups)}まとまり / 行: {len(found)}件（チャンク数が多い順、同じならパッチの古い順）\n")
    if args.skills_only:
        for g in groups:
            print(f"{g[0]['version']} / {g[0]['headings'][-1]} / {', '.join(c['id'] for c in g)}")
        print()
    for c, pos, mode, skill, change in found[: args.show]:
        line = f"{c['version']} / {c['headings'][-1]} / {c['id']} {pos} / {mode}  {skill}: {change[:60]}"
        if args.skills_only:
            # 同じスキルの変更があるパッチ（古い順）
            vs = patches[(mode, skill.replace(" ", ""))]
            line += f"  [変更のあるパッチ: {', '.join(sorted(vs, key=vs.get))}]"
        print(line)


if __name__ == "__main__":
    main()
