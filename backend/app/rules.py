"""AI やデータに依存しない、決まった処理。自動テスト（tests/test_rules.py）の対象。"""

import re

# 質問や見出しにこれらの言葉が入っていれば PvP として扱う
PVP_WORDS = re.compile(r"PvP|フロントライン|クリスタルコンフリクト")

# auto のとき、これらの言葉が入った質問は「何が変わったか」「いつ変わったか」の質問として v1 で答える
HISTORY_WORDS = re.compile(r"何が変わ|どう変わ|どう調整|変更点|変更内容|どのパッチ|いつ")

# 【今の値】と【変更の経緯】の行
CURRENT_MARK = "【今の値】"
CHANGE_LINE = re.compile(r"^\s*[-・*]\s*パッチ\s*([\d.]+)\s*[:：]\s*(.+?)\s*→\s*(.+?)\s*$")


def is_pvp_text(text: str) -> bool:
    """質問や見出しが PvP に関するものか。"""
    return bool(PVP_WORDS.search(text))


def bigrams(text: str) -> list[str]:
    """日本語は単語の区切りがないため、2文字ずつに区切ってキーワード検索に使う。"""
    text = re.sub(r"\s+", "", text)
    return [text[i : i + 2] for i in range(len(text) - 1)]


def choose_prompt(question: str) -> str:
    """auto のときに使うプロンプトを、質問の言葉から決める。"""
    return "v1" if HISTORY_WORDS.search(question) else "v2"


def fix_current_value(text: str) -> str:
    """【変更の経緯】の中で一番新しいパッチの「変更後」を、【今の値】に入れ直す。

    AI が正しい経緯を書いたのに、今の値だけを間違えることがあるため、
    最後の一歩はコードで決める。経緯が書かれていなければ、そのまま返す。
    """
    lines = text.splitlines()
    changes = [m for line in lines if (m := CHANGE_LINE.match(line.replace("**", "")))]
    if not changes:
        return text

    latest = max(changes, key=lambda m: float(m.group(1)))
    current = f"{CURRENT_MARK}{latest.group(3)}（根拠: パッチ{latest.group(1)}）"

    for i, line in enumerate(lines):
        if CURRENT_MARK in line:
            lines[i] = current
            return "\n".join(lines)
    return "\n".join([current, *lines])