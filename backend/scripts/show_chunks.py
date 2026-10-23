"""キーワードを含むチャンクを表示する（確認用）。

使い方: python scripts\\show_chunks.py キーワード [パッチ番号]
"""

import json
import sys
from pathlib import Path

CHUNKS = Path(__file__).resolve().parents[2] / "data" / "processed" / "chunks.jsonl"


def main() -> None:
    keyword = sys.argv[1]
    version = sys.argv[2] if len(sys.argv) > 2 else None

    shown = 0
    with CHUNKS.open(encoding="utf-8") as f:
        for line in f:
            chunk = json.loads(line)
            if version and chunk["version"] != version:
                continue
            if keyword not in chunk["text"]:
                continue
            print(f"===== {chunk['id']}  表あり: {chunk['has_table']}  {len(chunk['text'])} 文字")
            print(chunk["text"])
            print()
            shown += 1
            if shown >= 2:
                break

    if shown == 0:
        print("見つかりませんでした")


if __name__ == "__main__":
    main()