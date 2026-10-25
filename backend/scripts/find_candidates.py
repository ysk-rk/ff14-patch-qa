"""評価用の質問の候補を探す。

使い方:
  python scripts\\find_candidates.py                  PvE で2回以上調整され、最後の調整が 7.4 以降のスキル
  python scripts\\find_candidates.py --mode pvp       PvP で2回以上調整されたスキル
  python scripts\\find_candidates.py --mode general   バトル以外で、数値が2回以上変わった項目（上限値など）

すでに eval/questions.jsonl で使っているスキル（keyword）は除く。
変更の流れがまったく同じスキル（祖霊の蛇【壱】と【弐】など）は、1つにまとめて表示する。
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
QUESTIONS = ROOT / "eval" / "questions.jsonl"

PVP = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")
HEADER_CELLS = {"名称", "変更前", "変更点", "変更後"}

# PvE では、最後の調整がこのパッチ以降のものを候補にする
LATEST_FROM = 7.4
MIN_CHANGES = 2

# 「分解スキルの上限値が 650 → 710 に引き上げられます」のような、数値が変わる文
NUMBER_CHANGE = re.compile(r"([^\s。、「」]+?)が\s*([\d,]+)\s*→\s*([\d,]+)\s*に")


def table_rows(text: str):
    """Markdown の表から (1列目, 2列目) を取り出す。見出しの行は飛ばす。"""
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] not in HEADER_CELLS:
            yield cells[0], cells[1]


def used_keywords() -> set[str]:
    """すでに評価用データで使っているスキルや項目。"""
    if not QUESTIONS.exists():
        return set()
    with QUESTIONS.open(encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    return {q["keyword"] for q in questions if q.get("keyword")}


def collect_skills(chunks: list[dict], pvp: bool) -> dict:
    """アクション調整の表から、ジョブとスキルごとの変更を集める。"""
    history = defaultdict(list)
    for chunk in chunks:
        headings = chunk["headings"]
        if not headings:
            continue
        if bool(PVP.search(" ".join(headings))) != pvp:
            continue
        if not any("アクション" in h for h in headings):
            continue
        job = headings[-1]
        for skill, change in table_rows(chunk["text"]):
            history[(job, skill)].append((chunk["order"], chunk["version"], change))
    return history


def collect_general(chunks: list[dict]) -> dict:
    """バトル以外の文章から、「〇〇が 650 → 710 に」の形の変更を集める。"""
    history = defaultdict(list)
    for chunk in chunks:
        headings = chunk["headings"]
        if PVP.search(" ".join(headings)) or any("アクション" in h for h in headings):
            continue
        # 先頭の行（パッチ番号と見出し）は飛ばして、本文だけを見る
        body = chunk["text"].split("\n", 1)[-1]
        for m in NUMBER_CHANGE.finditer(body):
            history[("", m.group(1))].append((chunk["order"], chunk["version"], m.group(0)))
    return history


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pve", "pvp", "general"], default="pve")
    parser.add_argument("--show", type=int, default=30, help="表示する件数")
    args = parser.parse_args()

    with CHUNKS.open(encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    used = used_keywords()

    if args.mode == "general":
        history = collect_general(chunks)
        latest_from = 0.0
    else:
        history = collect_skills(chunks, pvp=args.mode == "pvp")
        latest_from = LATEST_FROM if args.mode == "pve" else 0.0

    # 変更の流れがまったく同じものは、1つにまとめる
    groups: dict[tuple, list[str]] = defaultdict(list)
    for (job, name), changes in history.items():
        changes = sorted(set(changes))
        if len(changes) < MIN_CHANGES or max(c[0] for c in changes) < latest_from:
            continue
        if any(u in name or name in u for u in used):
            continue
        key = (job, tuple((version, change) for _, version, change in changes))
        groups[key].append(name)

    ordered = sorted(groups.items(), key=lambda g: (-len(g[0][1]), g[0][0]))
    print(f"候補: {len(ordered)} 件（上位 {min(args.show, len(ordered))} 件を表示、使用済みは除外）\n")
    for (job, changes), names in ordered[: args.show]:
        label = f"{job}：" if job else ""
        versions = " → ".join(version for version, _ in changes)
        print(f"■ {label}{'、'.join(names)}（{versions}）")
        for version, change in changes:
            print(f"    {version:<5} {change}")
        print()


if __name__ == "__main__":
    main()