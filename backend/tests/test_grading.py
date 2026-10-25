"""scripts/grading.py のテスト。"""

from grading import contains_value, evidence_ranks, grade, recall_at


class TestContainsValue:
    def test_カンマの有無は区別しない(self):
        assert contains_value("威力は 1000 です", "1,000")
        assert contains_value("威力は 1,000 です", "1000")

    def test_パーセントの全角半角は区別しない(self):
        assert contains_value("75%", "75％")

    def test_パッチ番号の一部には一致しない(self):
        # 「7.2」が「7.25」に一致すると、間違った回答を◯にしてしまう
        assert not contains_value("パッチ7.25で変更", "7.2")
        assert contains_value("パッチ7.2で変更", "7.2")

    def test_長い数字の一部には一致しない(self):
        assert not contains_value("威力は1600", "160")


class TestGrade:
    def test_今の値の行だけを採点する(self):
        # 経緯には正解の 25％ が書かれているが、今の値は 35％ と間違えている
        question = {"kind": "latest", "expected": "25％"}
        text = "【今の値】35％（根拠: パッチ7.25）\n- パッチ7.3: 35％ → 25％"
        assert not grade(question, text)

    def test_今の値の行がなければ回答全体を採点する(self):
        question = {"kind": "latest", "expected": "160"}
        assert grade(question, "今の威力は 160 です（根拠: パッチ7.2）")

    def test_答えられない質問は分からないと答えれば正解(self):
        question = {"kind": "unanswerable", "expected": "分からない"}
        assert grade(question, "パッチノートからは分かりませんでした。")
        assert not grade(question, "パッチ7.6ではヴァイパーが強化されました。")

    def test_変更の流れはパッチ番号がすべてそろえば正解(self):
        question = {"kind": "history", "evidence_versions": ["7.16", "7.25", "7.31"]}
        assert grade(question, "パッチ7.16で…、パッチ7.25で…、パッチ7.31で…")
        assert not grade(question, "パッチ7.16で…、パッチ7.31で…")

    def test_変更の流れで分からないと答えたら不正解(self):
        # v2 の q002 で実際に起きた失敗
        question = {"kind": "history", "evidence_versions": ["7.16"]}
        assert not grade(question, "パッチノートからは分かりませんでした。")


class TestEvidenceRanks:
    def hit(self, version: str, rank: int, text: str, headings: str) -> dict:
        return {"version": version, "rank": rank, "text": text, "headings": headings}

    def test_PvEの質問ではPvPのチャンクを数えない(self):
        question = {"evidence_versions": ["7.2"], "keyword": "夢幻闘舞", "mode": "pve"}
        hits = [
            self.hit("7.2", 1, "夢幻闘舞 …", "バトル関連 > PvP全般 > モンク"),
            self.hit("7.2", 3, "夢幻闘舞 …", "バトル関連 > アクション／特性 > モンク"),
        ]
        assert evidence_ranks(question, hits) == {"7.2": 3}

    def test_キーワードがないチャンクは数えない(self):
        question = {"evidence_versions": ["7.2"], "keyword": "万象闘気圏", "mode": "pve"}
        hits = [self.hit("7.2", 1, "鳳凰の舞 …", "バトル関連 > モンク")]
        assert evidence_ranks(question, hits) == {"7.2": None}

    def test_答えられない質問はNone(self):
        question = {"evidence_versions": [], "keyword": None, "mode": "none"}
        assert evidence_ranks(question, []) is None


class TestRecallAt:
    def test_上位k件に入った割合(self):
        assert recall_at({"7.16": 2, "7.25": 1, "7.31": 5}, 3) == 2 / 3

    def test_拾えなかったパッチは数えない(self):
        assert recall_at({"7.2": None}, 8) == 0

    def test_答えられない質問はNone(self):
        assert recall_at(None, 3) is None