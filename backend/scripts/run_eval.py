"""評価用データの質問を順に流し、検索と回答を採点する。

使い方:
  python scripts\\run_eval.py                                  いつもどおり（混雑時は予備のモデル）
  python scripts\\run_eval.py --model gemini-3.5-flash-lite    使うモデルを1つに固定する
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.rag import LLMUnavailableError, answer, search  # noqa: E402

QUESTIONS = ROOT / "eval" / "questions.jsonl"
RESULTS_DIR = ROOT / "eval" / "results"

# 無料枠の回数制限にかからないよう、1問ごとにあける秒数
WAIT_SECONDS = 5

PVP = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")
UNKNOWN_PHRASES = (
    "分かりませんでした",
    "わかりませんでした",
    "分からない",
    "わからない",
    "記載がありません",
    "記載されていません",
)


def normalize(text: str) -> str:
    """数字の比べ方をそろえる（「1,000」と「1000」、「%」と「％」を同じにする）。"""
    return text.replace(",", "").replace("，", "").replace("%", "％").replace(" ", "")


def contains_value(text: str, expected: str) -> bool:
    """回答に正解の数字が入っているか。「7.2」が「7.25」に一致しないよう前後も見る。"""
    pattern = rf"(?<![\d.]){re.escape(normalize(expected))}(?!\d)"
    return re.search(pattern, normalize(text)) is not None


def evidence_recall(question: dict, hits: list[dict]) -> float | None:
    """正解に必要なパッチのチャンクを、検索でどれだけ拾えたか（0〜1）。"""
    needed = question["evidence_versions"]
    if not needed:
        return None

    found = set()
    for hit in hits:
        if hit["version"] not in needed or question["keyword"] not in hit["text"]:
            continue
        is_pvp = bool(PVP.search(hit["headings"]))
        if question["mode"] == "pve" and is_pvp:
            continue
        if question["mode"] == "pvp" and not is_pvp:
            continue
        found.add(hit["version"])
    return len(found) / len(needed)


def grade(question: dict, text: str) -> bool | None:
    """回答を採点する。機械で採点できないものは None（手で確認）。"""
    if question["kind"] == "unanswerable":
        return any(p in text for p in UNKNOWN_PHRASES)
    if question["kind"] == "history":
        return None
    return contains_value(text, question["expected"])


def mark(value: bool | None) -> str:
    return {True: "◯", False: "✕", None: "－"}[value]


def percent(value: float | None) -> str:
    return "  － " if value is None else f"{value * 100:>3.0f}％"


def summarize(records: list[dict]) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        groups[r["kind"]].append(r)
    groups["全体"] = records

    print("\n種類                問題数  回答の正解      検索の再現率")
    for kind, rows in groups.items():
        graded = [r for r in rows if r["correct"] is not None]
        correct = sum(r["correct"] for r in graded)
        recalls = [r["recall"] for r in rows if r["recall"] is not None]
        recall = sum(recalls) / len(recalls) if recalls else None
        rate = correct / len(graded) if graded else None
        print(
            f"{kind:<18}  {len(rows):>4}  {correct:>2}/{len(graded):<2} {percent(rate)}"
            f"     {percent(recall)}"
        )

    models: dict[str, int] = defaultdict(int)
    for r in records:
        models[r["model"] or "エラー"] += 1
    print("\n回答したモデル: " + "、".join(f"{m} {n}問" for m, n in models.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", help="使うモデルを1つに固定する")
    args = parser.parse_args()
    models = [args.model] if args.model else None

    questions = [json.loads(line) for line in QUESTIONS.open(encoding="utf-8") if line.strip()]
    records = []

    for i, q in enumerate(questions, start=1):
        hits = search(q["question"])
        recall = evidence_recall(q, hits)

        try:
            result = answer(q["question"], models)
            text, model, error = result["answer"], result["model"], None
            correct = grade(q, text)
        except LLMUnavailableError as e:
            text, model, error, correct = "", None, str(e), None

        records.append(
            {
                "id": q["id"],
                "kind": q["kind"],
                "mode": q["mode"],
                "question": q["question"],
                "expected": q["expected"],
                "model": model,
                "correct": correct,
                "recall": recall,
                "retrieved": [
                    f"{h['version']}({'PvP' if PVP.search(h['headings']) else 'PvE'})" for h in hits
                ],
                "answer": text,
                "error": error,
            }
        )

        print(
            f"[{i:>2}/{len(questions)}] {q['id']}  回答 {mark(correct)}  検索 {percent(recall)}"
            f"  {model or 'エラー'}  {q['question']}"
        )
        if i < len(questions):
            time.sleep(WAIT_SECONDS)

    summarize(records)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    output = RESULTS_DIR / f"{stamp}_{args.model or 'default'}.jsonl"
    with output.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n結果を保存しました: {output}")


if __name__ == "__main__":
    main()