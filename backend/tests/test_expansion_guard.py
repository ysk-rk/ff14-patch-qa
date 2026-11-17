"""改善14: 拡張パッケージの境目で、古い値を今の値として答えないしくみのテスト。

作り物のチャンク（tests/fixtures/）を使う。本文は自分で書いた短い文で、本物のパッチノートは入れていない。
  chunks_7x.jsonl: 7.0（「こちら」だけ）、7.1、7.5 の調整
  chunks_8x.jsonl: 上に加えて、8.0（新しいジョブと「こちら」だけ）、8.01 の調整
答えの文は、AI が返す形をまねて手で書いたもの。auto と同じく fix_current_value のあとに guard_expansion を通す。
"""

import json
from pathlib import Path

import pytest

from app.rules import fix_current_value, guard_expansion, job_names_from_headings, latest_expansion

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> tuple[int, set[str]]:
    """作り物のチャンクから、最新の拡張パッケージとジョブ名を作る（rag.py と同じ作り方）。"""
    chunks = [json.loads(line) for line in (FIXTURES / name).open(encoding="utf-8")]
    return latest_expansion({c["version"] for c in chunks}), job_names_from_headings([c["headings"] for c in chunks])


def run(text: str, question: str, name: str) -> str:
    expansion, names = load(name)
    return guard_expansion(fix_current_value(text), question, expansion, names)


# 7.x の変更しかないスキル（ためし斬り）の答え
SLASH = "\n".join(
    [
        "【今の値】140（根拠: パッチ7.5）",
        "【変更の経緯】",
        "- パッチ7.1: 100 → 120",
        "- パッチ7.5: 120 → 140",
    ]
)
SLASH_QUESTION = "テスト騎士のためし斬りの今の威力は？"


def test_最新の拡張パッケージはデータの版から作る():
    assert load("chunks_7x.jsonl")[0] == 7
    assert load("chunks_8x.jsonl")[0] == 8
    assert latest_expansion(["7.57", "8.0", "8.01", "8.1"]) == 8


def test_8_0があるデータで7_xの変更しかないスキルを聞くと今の値が差し替わる():
    result = run(SLASH, SLASH_QUESTION, "chunks_8x.jsonl")
    lines = result.splitlines()
    assert lines[0] == (
        "【今の値】分かりませんでした（最後の変更はパッチ7.5ですが、そのあと拡張パッケージ8.0で"
        "スキルが作り直された可能性があり、パッチノートだけでは今の値を確かめられません）"
    )
    # 【変更の経緯】はそのまま残す
    assert lines[1:] == SLASH.splitlines()[1:]


@pytest.mark.parametrize("order", [("7.5", "8.01"), ("8.01", "7.5")])
def test_8_xで変更があるスキルは差し替わらず8_xの値になる(order):
    rows = {"7.5": "- パッチ7.5: 200 → 220", "8.01": "- パッチ8.01: 300 → 320"}
    text = "\n".join(["【今の値】220（根拠: パッチ7.5）", "【変更の経緯】", *(rows[v] for v in order)])
    result = run(text, "テスト騎士のためし突きの今の威力は？", "chunks_8x.jsonl")
    assert result.splitlines()[0] == "【今の値】320（根拠: パッチ8.01）"


def test_8_0で変更があるスキルも差し替わらない():
    text = "\n".join(["【今の値】90（根拠: パッチ8.0）", "【変更の経緯】", "- パッチ7.5: 100 → 110", "- パッチ8.0: 110 → 90"])
    result = run(text, "テスト騎士のためし斬りの今の威力は？", "chunks_8x.jsonl")
    assert result.splitlines()[0] == "【今の値】90（根拠: パッチ8.0）"


def test_質問にジョブ名がないと差し替わらない():
    question = "ためし斬りの今の威力は？"
    assert run(SLASH, question, "chunks_8x.jsonl") == fix_current_value(SLASH)


def test_経緯の質問は差し替わらない():
    question = "テスト騎士のためし斬りは何が変わった？"
    assert run(SLASH, question, "chunks_8x.jsonl") == fix_current_value(SLASH)


def test_7_xしかないデータではどの質問も差し替わらない():
    for question in (SLASH_QUESTION, "ためし斬りの今の威力は？", "テスト騎士のためし斬りは何が変わった？"):
        assert run(SLASH, question, "chunks_7x.jsonl") == fix_current_value(SLASH)


def test_経緯がない答えは差し替わらない():
    # 基準の6つの外に足したテスト
    text = "【今の値】分かりませんでした（資料にありません）"
    assert run(text, SLASH_QUESTION, "chunks_8x.jsonl") == text
