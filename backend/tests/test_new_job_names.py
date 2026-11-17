"""改善14: 新しいジョブの見出しから、名前をすべて取るテスト。

テストでは all_names を直接渡すので、NEW_JOB_ALL_NAMES の値によらず通る。
作り物のチャンク（tests/fixtures/chunks_8x_two_new_jobs.jsonl）は、自分で書いた短い文で、本物のパッチノートは入れていない。
"""

import json
from pathlib import Path

import pytest

from app.rules import job_names_from_headings, new_job_names

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("新たなジョブ「A」「B」が実装されます。", ["A", "B"]),
        ("新たなジョブ「A」と「B」が実装されます。", ["A", "B"]),
        ("新たなジョブ「A」、「B」が実装されます。", ["A", "B"]),
        ("新たなジョブ「A」が実装されます。", ["A"]),
        # 取りすぎない（あとに続く別の「」は取らない）
        ("新たなジョブ「A」が実装されます。クエスト「B」を受けると、使えるようになります。", ["A"]),
        ("リミテッドジョブ「A」", ["A"]),
    ],
)
def test_見出しから新しいジョブの名前をすべて取る(heading, expected):
    assert new_job_names(heading, all_names=True) == expected


def test_作り物の8_0で新しいジョブ2つが調整の見出しなしで名前の一覧に入る():
    chunks = [json.loads(line) for line in (FIXTURES / "chunks_8x_two_new_jobs.jsonl").open(encoding="utf-8")]
    names = job_names_from_headings([c["headings"] for c in chunks], all_names=True)
    assert {"テスト弓士", "テスト槌士"} <= names


def test_all_namesがFalseなら1つ目の名前だけを取る():
    # 基準の7つの外に足したテスト（前の動きが残っていること）
    assert new_job_names("新たなジョブ「A」「B」が実装されます。", all_names=False) == ["A"]
