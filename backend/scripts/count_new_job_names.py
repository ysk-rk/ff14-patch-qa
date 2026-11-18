"""見出しから取ったジョブとクラスの名前の数を、新しいジョブの名前を1つ目だけ取るときと、すべて取るときで比べる。AI も検索も呼ばない。

job_names_from_headings に all_names=False と True を直接渡す（rules.NEW_JOB_ALL_NAMES を書き換えても、引数の初めの値は変わらないため）。
チャンクに付くジョブ名は、rag.build_chunk_jobs と同じ式で作る。rag.py は読み込むと索引や埋め込みのモデルを用意するので import しない。
8.0 の取り込みの手順書で、新しいジョブの名前が見出しから取れたかを確かめるときに使う。

使い方: python scripts\\count_new_job_names.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import rules  # noqa: E402
from app.rules import job_names_from_headings, jobs_in  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"


def main() -> None:
    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    headings_list = [c["headings"] for c in chunks]
    first = job_names_from_headings(headings_list, all_names=False)
    every = job_names_from_headings(headings_list, all_names=True)
    default = job_names_from_headings(headings_list)
    print(f"NEW_JOB_ALL_NAMES = {rules.NEW_JOB_ALL_NAMES}")
    print(f"all_names=False: {len(first)}個、all_names=True: {len(every)}個、引数なし（初めの値）: {len(default)}個、"
          f"False と True で同じ: {first == every}")

    # rag.build_chunk_jobs と同じ式
    jobs_first = {c["id"]: jobs_in(c["headings"][-1], first) if c["headings"] else set() for c in chunks}
    jobs_every = {c["id"]: jobs_in(c["headings"][-1], every) if c["headings"] else set() for c in chunks}
    changed = [i for i in jobs_first if jobs_first[i] != jobs_every[i]]
    print(f"チャンクに付くジョブ名が False と True で変わるチャンク: {len(changed)}件 {changed}")


if __name__ == "__main__":
    main()
