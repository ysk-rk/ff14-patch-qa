"""拡張パッケージの境目で今の値を控える（EXPANSION_GUARD）の対象になりうる評価用の問題を数える。AI も検索も呼ばない。

対象: 今の値の質問（choose_prompt が "v1" でない）で、質問にジョブ名が1つあるもの（job_of が None でない）。
そのうち、正解の資料の版（evidence_versions）が、今のデータの最新の拡張パッケージより前のものも数える。
rag.py は読み込むと索引や埋め込みのモデルを用意するので import しない。その代わり、rag.py と同じ関数・同じ式を使う。
評価用の問題（eval/questions.jsonl）だけを読む。テスト用の問題は読まない。
8.0 の取り込みの手順書で、控える問題の数を数えるときに使う。

使い方: python scripts\\count_expansion_guard.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.rules import choose_prompt, job_names_from_headings, job_of, jobs_in  # noqa: E402

CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
QUESTIONS = ROOT / "eval" / "questions.jsonl"  # 評価用の問題だけ。テスト用の問題は読まない


def major(version: str) -> int:
    """版の先頭の数（"7.57" → 7）。"""
    return int(version.split(".")[0])


def main() -> None:
    out: list[str] = []
    p = out.append

    chunks = [json.loads(line) for line in CHUNKS.open(encoding="utf-8")]
    qs = [json.loads(line) for line in QUESTIONS.open(encoding="utf-8")]

    # rag.build_chunk_jobs と同じ
    job_names = job_names_from_headings([c["headings"] for c in chunks])

    versions = sorted({c["version"] for c in chunks}, key=float)
    latest_expansion = max(major(v) for v in versions)

    p("=" * 70)
    p("改善14：拡張パッケージの境目で今の値を控える、の前に数えたこと")
    p("=" * 70)
    p("(a) 今の値の質問: rag.pick_prompt と同じ。choose_prompt(question) が \"v1\" でなければ AUTO_CURRENT_PROMPT（v5）")
    p("(b) 質問にジョブ名がある: rag.search の JOB_BONUS と同じ。job_of(question, job_names) が None でない")
    p("    （job_of は名前が1つだけのときに返す。参考として、名前が2つ以上ある問題も別に出す）")
    p(f"評価用の問題: {len(qs)}問")
    p(f"取り込んだ版: {len(versions)}個 {versions}")
    p(f"今のデータでの最新の拡張パッケージ（版の先頭の数で一番大きいもの）: {latest_expansion}")

    rows = []
    for q in qs:
        current = choose_prompt(q["question"]) != "v1"
        job = job_of(q["question"], job_names)
        rows.append((q, current, job))

    a = [q["id"] for q, cur, _ in rows if cur]
    b = [q["id"] for q, _, job in rows if job]
    ab = [(q, job) for q, cur, job in rows if cur and job]
    multi = [q["id"] for q in qs if len(jobs_in(q["question"], job_names)) >= 2]

    p(f"\n(a) 今の値の質問: {len(a)}問")
    p(f"(b) 質問にジョブ名がある（1つ）: {len(b)}問")
    p(f"参考：質問にジョブ名が2つ以上ある: {len(multi)}問 {multi}")
    p(f"\n(a)(b) の両方に当たる: {len(ab)}問")
    p(f"    {[q['id'] for q, _ in ab]}")
    for q, job in ab:
        p(f"    {q['id']}  {q['mode']}  ジョブ: {job}  evidence_versions={q['evidence_versions']}  {q['question']}")

    older = [(q, job) for q, job in ab if any(major(v) < latest_expansion for v in q["evidence_versions"])]
    p(f"\n(a)(b) のうち、evidence_versions の版の先頭の数が最新の拡張パッケージ（{latest_expansion}）より小さいもの: {len(older)}問")
    for q, job in older:
        p(f"    {q['id']}  evidence_versions={q['evidence_versions']}")

    print("\n".join(out))


if __name__ == "__main__":
    main()
