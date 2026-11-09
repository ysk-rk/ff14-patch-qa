"""q018 と同じ形の問題の候補を探す。

あるスキルの項目（最大チャージ数など）が最後に変わったパッチより新しいパッチで、
別のジョブの同じ項目が変わっているものを出す。AI は呼ばない。

使い方: python scripts\\find_shared_attrs.py [--mode pvp] [--attr 最大チャージ数] [--include-used] [--show 20]
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rules import is_pvp_text  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
EVAL_DIR = ROOT / "eval"

# 「リキャストタイムが 90秒 → 60秒」の「リキャストタイム」
CHANGED = re.compile(r"^(.+?)が\s*.+?→")
# 「「最大チャージ数：2」 が追加」の「最大チャージ数」
ADDED = re.compile(r"「(.+?)[：:]")
# 威力はほとんどのスキルで変わるので、q018 の形の候補からは外す
SKIP_ATTRS = {"威力"}


def attrs_of(cell: str):
    for piece in cell.split("・"):
        piece = piece.strip()
        if not piece:
            continue
        m = CHANGED.match(piece) or ADDED.search(piece)
        if m:
            yield m.group(1).replace(" ", ""), piece


def load_changes() -> list[dict]:
    rows = []
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            c = json.loads(line)
            if not c.get("has_table") or not c.get("headings"):
                continue
            job = c["headings"][-1]
            mode = "pvp" if is_pvp_text(c["text"]) else "pve"
            for t in c["text"].splitlines():
                if not t.startswith("|"):
                    continue
                cells = [x.strip() for x in t.strip().strip("|").split("|")]
                if len(cells) < 2 or cells[0] == "名称" or set(cells[0]) <= set("-: "):
                    continue
                for attr, piece in attrs_of(cells[-1]):
                    rows.append({
                        "attr": attr,
                        "mode": mode,
                        "order": float(c["order"]),
                        "version": c["version"],
                        "id": c["id"],
                        "job": job,
                        "skill": cells[0],
                        "piece": piece,
                    })
    return rows


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
    p = argparse.ArgumentParser(description="q018 と同じ形の問題の候補を探す")
    p.add_argument("--mode", choices=["pve", "pvp"])
    p.add_argument("--attr", help="この項目だけを見る（例: 最大チャージ数）")
    p.add_argument("--include-used", action="store_true", help="評価やテストで使ったスキルも出す")
    p.add_argument("--show", type=int, default=20, help="表示する件数")
    args = p.parse_args()

    used = used_keywords()
    by_attr = defaultdict(list)
    for r in load_changes():
        by_attr[(r["attr"], r["mode"])].append(r)

    found = []
    for (attr, mode), items in by_attr.items():
        if attr in SKIP_ATTRS:
            continue
        if args.mode and mode != args.mode:
            continue
        if args.attr and attr != args.attr:
            continue
        latest = {}
        for r in items:
            key = (r["job"], r["skill"])
            if key not in latest or r["order"] > latest[key]["order"]:
                latest[key] = r
        for (job, skill), last in latest.items():
            if not args.include_used and skill.replace(" ", "") in used:
                continue
            newer = sorted(
                (r for r in items if r["job"] != job and r["order"] > last["order"]),
                key=lambda r: r["order"],
            )
            if newer:
                found.append((len(items), attr, mode, last, newer))

    found.sort(key=lambda x: (x[0], x[1], x[3]["order"]))
    print(f"候補: {len(found)}件（この項目の変更が少ない順。少ないほど、別のジョブの資料が上位に来やすい）\n")
    for n, attr, mode, last, newer in found[: args.show]:
        print(f"[{attr} / {mode} / この項目の変更 {n}件]")
        print(f"  質問: {last['job']} の {last['skill']}  最後の変更 {last['version']}（{last['id']}）: {last['piece'][:60]}")
        for r in newer[:3]:
            print(f"  新しい別ジョブ: {r['job']} の {r['skill']}  {r['version']}（{r['id']}）: {r['piece'][:60]}")
        if len(newer) > 3:
            print(f"  ほか {len(newer) - 3}件")
        print()


if __name__ == "__main__":
    main()