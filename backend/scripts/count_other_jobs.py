"""検索の上位8件に、質問とは別のジョブの資料が何件入るかを数える。AI は呼ばない。

使い方: python scripts\\count_other_jobs.py [--bonus 0.01]
テスト用の問題（test_questions.jsonl）には使わないこと。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import rag  # noqa: E402
from app.rules import job_of  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="上位8件の別のジョブの資料を数える")
    p.add_argument("--bonus", type=float, help="JOB_BONUS を一時的にこの値にする")
    p.add_argument("--questions", default=str(ROOT / "eval" / "questions.jsonl"), help="使う質問のファイル")
    args = p.parse_args()

    if args.bonus is not None:
        rag.JOB_BONUS = args.bonus

    asked = 0
    total = 0
    with open(args.questions, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            q = json.loads(line)
            job = job_of(q["question"], rag.job_names)
            if not job:
                continue
            asked += 1
            hits = sorted(rag.search(q["question"]), key=lambda h: h["rank"])
            # ジョブの見出しがない資料（共通の調整や、バトル以外）は数えない
            others = [h for h in hits if rag.chunk_jobs.get(h["id"]) and job not in rag.chunk_jobs[h["id"]]]
            total += len(others)
            detail = "、".join(
                f"{h['rank']}位 {'／'.join(sorted(rag.chunk_jobs[h['id']]))} {h['version']}" for h in others
            )
            print(f"{q['id']}  {job}  別のジョブ {len(others)}件  {detail}")

    print(f"\nJOB_BONUS={rag.JOB_BONUS}  ジョブが決まる問題 {asked}問  上位8件の別のジョブの資料 合計 {total}件")


if __name__ == "__main__":
    main()