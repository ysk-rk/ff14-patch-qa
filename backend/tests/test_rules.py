"""app/rules.py のテスト。"""

from app.rules import bigrams, choose_prompt, fix_current_value, is_pvp_text


class TestChoosePrompt:
    def test_何が変わったかの質問はv1(self):
        assert choose_prompt("PvPのモンクの夢幻闘舞は何が変わった？") == "v1"

    def test_どのパッチかの質問はv1(self):
        assert choose_prompt("移動しながらマウントを呼び出せるようになったのはどのパッチ？") == "v1"

    def test_今の値の質問はv2(self):
        assert choose_prompt("モンクの万象闘気圏の今の威力は？") == "v2"

    def test_どちらにも当てはまらない質問はv2(self):
        assert choose_prompt("パッチ7.6で追加された内容は？") == "v2"


class TestFixCurrentValue:
    def test_経緯が正しく今の値だけ違うときは直す(self):
        # q011 で実際に起きた失敗: 経緯は正しいのに、7.3 の変更前の値を今の値にした
        text = "\n".join(
            [
                "【今の値】40％（根拠: パッチ7.3）",
                "【変更の経緯】",
                "- パッチ7.2: 50％ → 40％",
                "- パッチ7.3: 40％ → 20％",
            ]
        )
        fixed = fix_current_value(text)
        assert "【今の値】20％（根拠: パッチ7.3）" in fixed
        assert "40％（根拠" not in fixed

    def test_パッチ番号は数値として比べる(self):
        # 文字として比べると "7.25" > "7.3" になってしまう
        text = "\n".join(
            [
                "【今の値】35％（根拠: パッチ7.25）",
                "- パッチ7.3: 35％ → 25％",
                "- パッチ7.25: 50％ → 35％",
            ]
        )
        assert "【今の値】25％（根拠: パッチ7.3）" in fix_current_value(text)

    def test_太字の記号があっても読み取れる(self):
        text = "【今の値】620\n- **パッチ7.4**: 620 → 660"
        assert "【今の値】660（根拠: パッチ7.4）" in fix_current_value(text)

    def test_今の値の行がなければ先頭に足す(self):
        text = "【変更の経緯】\n- パッチ7.5: 460 → 500"
        assert fix_current_value(text).splitlines()[0] == "【今の値】500（根拠: パッチ7.5）"

    def test_経緯がなければそのまま返す(self):
        text = "パッチノートからは分かりませんでした。"
        assert fix_current_value(text) == text


class TestBigrams:
    def test_2文字ずつに区切る(self):
        assert bigrams("ブライヤー") == ["ブラ", "ライ", "イヤ", "ヤー"]

    def test_空白は取り除く(self):
        assert bigrams("威力 は") == ["威力", "力は"]


class TestIsPvpText:
    def test_PvPの言葉が入っていればPvP(self):
        assert is_pvp_text("バトル関連 > PvP全般 > モンク")
        assert is_pvp_text("フロントライン関連")

    def test_入っていなければPvPではない(self):
        assert not is_pvp_text("バトル関連 > アクション／特性 > モンク")