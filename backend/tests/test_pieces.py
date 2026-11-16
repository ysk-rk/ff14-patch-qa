"""長いチャンクを、埋め込み用のかけらに分ける処理（split_for_embedding）のテスト。"""

from app.rules import split_for_embedding

HEAD = "[パッチ7.05] バトル関連 > アクション／特性において、以下の調整が行われます。 > ヴァイパー"
ROWS = [f"| スキル{i} | 威力が {i}00 → {i}10 に変更されます。 |" for i in range(1, 11)]
TEXT = "\n".join([HEAD, *ROWS])


def count_lines(text: str) -> int:
    """偽物のトークン数: 1行を10トークンとして数える。"""
    return 10 * len(text.split("\n"))


def test_short_text_is_returned_as_is():
    assert split_for_embedding(TEXT, count_lines, 1000) == [TEXT]


def test_every_piece_starts_with_head_and_fits():
    # 見出しの行と表の行2つで30トークン
    pieces = split_for_embedding(TEXT, count_lines, 30)
    assert len(pieces) == 5
    for piece in pieces:
        assert piece.split("\n")[0] == HEAD
        assert count_lines(piece) <= 30


def test_lines_keep_order_and_none_are_lost():
    pieces = split_for_embedding(TEXT, count_lines, 40)
    body = [line for piece in pieces for line in piece.split("\n")[1:]]
    assert body == ROWS


def test_empty_lines_are_kept():
    text = "\n".join([HEAD, ROWS[0], "", ROWS[1], ROWS[2]])
    pieces = split_for_embedding(text, count_lines, 30)
    body = [line for piece in pieces for line in piece.split("\n")[1:]]
    assert body == [ROWS[0], "", ROWS[1], ROWS[2]]


def test_too_long_line_becomes_its_own_piece_without_cutting():
    long_row = "| 長いスキル | " + "とても長い説明。" * 50 + " |"
    text = "\n".join([HEAD, ROWS[0], long_row, ROWS[1]])

    def count_chars(s: str) -> int:
        return len(s)

    limit = len(HEAD) + 1 + len(ROWS[0]) + 1 + len(ROWS[1])
    pieces = split_for_embedding(text, count_chars, limit)
    assert pieces == [
        "\n".join([HEAD, ROWS[0]]),
        "\n".join([HEAD, long_row]),
        "\n".join([HEAD, ROWS[1]]),
    ]


def test_single_line_text_is_returned_as_is():
    assert split_for_embedding(HEAD, count_lines, 5) == [HEAD]
