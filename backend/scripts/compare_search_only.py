"""検索だけの結果（eval/results）を、前の結果と比べる（正解の順位 ranks と retrieved）。AI は呼ばない。

使い方: python scripts\\compare_search_only.py 新しい結果のファイル名 前の結果のファイル名 [前の結果のファイル名 ...]
ファイル名は eval/results の中の名前（例: 20261117-1623_search-only_hybrid.jsonl）。
8.0 の取り込みの手順書で、取り込む前と後の検索を比べるときに使う。
"""

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parents[2] / "eval" / "results"


def load(name: str) -> dict:
    return {r["id"]: r for r in map(json.loads, (RESULTS / name).open(encoding="utf-8"))}


def main() -> None:
    new_name = sys.argv[1]
    new = load(new_name)
    for old_name in sys.argv[2:]:
        old = load(old_name)
        diff = [i for i in old if i not in new or (old[i]["ranks"], old[i]["retrieved"]) != (new[i]["ranks"], new[i]["retrieved"])]
        extra = [i for i in new if i not in old]
        print(f"{new_name}（{len(new)}問）と {old_name}（{len(old)}問）")
        print(f"    ranks か retrieved が違う問題: {len(diff)}問 {diff}")
        print(f"    新しいほうにだけある問題: {len(extra)}問 {extra}")


if __name__ == "__main__":
    main()
