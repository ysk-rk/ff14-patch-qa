"""評価用の質問の候補を探す。

PvE で2回以上調整され、最後の調整が 7.4 以降のスキルを一覧にする。
「古い情報を今の情報として答えてしまわないか」を試すのに向いている。
"""

import json
import re
from collections import defaultdict
from pathlib import Path

CHUNKS = Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks.jsonl"

PVP = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")
HEADER_CELLS = {"名称", "変更前", "変更点"}

# 最後の調整がこのパッチ以降のものを候補にする
LATEST_FROM = 7.4
MIN_CHANGES = 2
SHOW = 25


def table_rows(text: str):
    """Markdown の表から (1列目, 2列目) を取り出す。見出しの行は飛ばす。"""
    for line in text.splitlines():
        if not line.startswith("| ") or line.startswith("| ---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] not in HEADER_CELLS:
            yield cells[0], cells[1]


def main() -> None:
    history: dict[tuple[str, str], list[tuple[float, str, str, str]]] = defaultdict(list)

    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            headings = chunk["headings"]
            # PvE のアクション調整の表だけを対象にする
            if not headings or PVP.search(" ".join(headings)):
                continue
            if not any("アクション" in h for h in headings):
                continue

            job = headings[-1]
            for skill, change in table_rows(chunk["text"]):
                history[(job, skill)].append(
                    (chunk["order"], chunk["version"], chunk["id"], change)
                )

    candidates = [
        (key, sorted(changes))
        for key, changes in history.items()
        if len(changes) >= MIN_CHANGES and max(c[0] for c in changes) >= LATEST_FROM
    ]
    candidates.sort(key=lambda c: (-len(c[1]), c[0]))

    print(f"候補: {len(candidates)} 件（上位 {SHOW} 件を表示）\n")
    for (job, skill), changes in candidates[:SHOW]:
        versions = " → ".join(c[1] for c in changes)
        print(f"■ {job}：{skill}（{versions}）")
        for _, version, chunk_id, change in changes:
            print(f"    {version:<5} {chunk_id:<10} {change[:60]}")
        print()


if __name__ == "__main__":
    main()