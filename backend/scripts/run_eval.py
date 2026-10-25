"""評価用データの質問を順に流し、検索と回答を採点する。

使い方:
  python scripts\\run_eval.py                                  いつもどおり（混雑時は予備のモデル）
  python scripts\\run_eval.py --model gemini-3.5-flash-lite    使うモデルを1つに固定する
  python scripts\\run_eval.py --prompt auto                    使うプロンプトを選ぶ
  python scripts\\run_eval.py --search hybrid                  検索のしかたを選ぶ（vector / hybrid）
  python scripts\\run_eval.py --search hybrid --search-only    AI を使わずに検索だけを測る
  python scripts\\run_eval.py --questions ..\\eval\\test_questions.jsonl   使う質問のファイルを選ぶ
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.rag import (  # noqa: E402
    DEFAULT_PROMPT,
    DEFAULT_SEARCH,
    PROMPTS,
    SEARCH_MODES,
    TOP_K,
    LLMUnavailableError,
    answer,
    search,
)
from grading import evidence_ranks, grade, is_pvp_hit, recall_at  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"

# 無料枠の回数制限にかからないよう、1問ごとにあける秒数
WAIT_SECONDS = 5

# 混雑していたときに待つ秒数と、試す回数
RETRY_WAIT_SECONDS = 30
RETRIES = 3

# 検索の再現率を測る順位（上位何件までに入っていれば合格とするか）
RECALL_AT = (3, TOP_K)


def ask_with_retry(question: str, models: list[str] | None, prompt: str, search_mode: str) -> dict:
    """混雑していたら待って再試行する。"""
    for attempt in range(1, RETRIES + 1):
        try:
            return answer(question, models, prompt, search_mode)
        except LLMUnavailableError as e:
            if attempt == RETRIES:
                raise
            print(f"        混雑のため {RETRY_WAIT_SECONDS} 秒待って再試行します（{e}）")
            time.sleep(RETRY_WAIT_SECONDS)
    raise AssertionError("ここには来ない")


def mark(value: bool | None) -> str:
    return {True: "◯", False: "✕", None: "－"}[value]


def percent(value: float | None) -> str:
    return "  － " if value is None else f"{value * 100:>3.0f}％"


def format_ranks(ranks: dict[str, int | None] | None) -> str:
    if ranks is None:
        return "－"
    return ",".join(str(r) if r is not None else "×" for r in ranks.values())


def average(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def summarize(records: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["kind"]].append(r)
    groups["全体"] = records

    headers = "  ".join(f"検索@{k}" for k in RECALL_AT)
    print(f"\n種類                問題数  回答の正解      {headers}")
    for kind, rows in groups.items():
        graded = [r for r in rows if r["correct"] is not None]
        correct = sum(r["correct"] for r in graded)
        rate = correct / len(graded) if graded else None
        recalls = "  ".join(
            percent(average([recall_at(r["ranks"], k) for r in rows])) for k in RECALL_AT
        )
        print(f"{kind:<18}  {len(rows):>4}  {correct:>2}/{len(graded):<2} {percent(rate)}     {recalls}")

    models: dict[str, int] = defaultdict(int)
    for r in records:
        models[r["model"] or "なし"] += 1
    print("\n回答したモデル: " + "、".join(f"{m} {n}問" for m, n in models.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="使うモデルを1つに固定する")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT, choices=sorted(PROMPTS), help="使うプロンプト")
    parser.add_argument("--search", default=DEFAULT_SEARCH, choices=SEARCH_MODES, help="検索のしかた")
    parser.add_argument("--search-only", action="store_true", help="AI を使わずに検索だけを測る")
    parser.add_argument("--questions", default=str(QUESTIONS), help="使う質問のファイル")
    args = parser.parse_args()
    models = [args.model] if args.model else None

    questions_path = Path(args.questions)
    with questions_path.open(encoding="utf-8") as f:
        questions = [json.loads(line) for line in f if line.strip()]
    records = []

    for i, q in enumerate(questions, start=1):
        hits = search(q["question"], args.search)
        ranks = evidence_ranks(q, hits)

        text, model, error, correct = "", None, None, None
        if not args.search_only:
            try:
                result = ask_with_retry(q["question"], models, args.prompt, args.search)
                text, model = result["answer"], result["model"]
                correct = grade(q, text)
            except LLMUnavailableError as e:
                error = str(e)

        ranked = sorted(hits, key=lambda h: h["rank"])
        records.append(
            {
                "id": q["id"],
                "kind": q["kind"],
                "mode": q["mode"],
                "question": q["question"],
                "expected": q["expected"],
                "model": model,
                "prompt": None if args.search_only else args.prompt,
                "search": args.search,
                "correct": correct,
                "ranks": ranks,
                "retrieved": [
                    f"{h['rank']}:{h['version']}({'PvP' if is_pvp_hit(h) else 'PvE'})" for h in ranked
                ],
                "answer": text,
                "error": error,
            }
        )

        answer_label = "" if args.search_only else f"回答 {mark(correct)}  "
        model_label = "" if args.search_only else f"  {model or 'エラー'}"
        print(
            f"[{i:>2}/{len(questions)}] {q['id']}  {answer_label}正解の順位 {format_ranks(ranks):<6}"
            f"{model_label}  {q['question']}"
        )
        if not args.search_only and i < len(questions):
            time.sleep(WAIT_SECONDS)

    print(f"\n質問: {questions_path.name}  検索: {args.search}" + ("" if args.search_only else f"  プロンプト: {args.prompt}"))
    summarize(records)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    # いつもの20問以外を使ったときは、ファイル名の先頭に質問のファイル名を付ける
    prefix = "" if questions_path.resolve() == QUESTIONS.resolve() else f"{questions_path.stem}_"
    if args.search_only:
        label = f"search-only_{args.search}"
    else:
        label = f"{args.model or 'default'}_{args.prompt}_{args.search}"
    output = RESULTS_DIR / f"{stamp}_{prefix}{label}.jsonl"
    with output.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n結果を保存しました: {output}")


if __name__ == "__main__":
    main()