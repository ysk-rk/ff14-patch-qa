# CLAUDE.md

FF14 パッチノート Q&A（RAG）。黄金のレガシー（7.0〜7.57）のパッチノートに、出典付きで答える。
一番の品質目標は「古い情報を今の情報として答えないこと」。

詳しくは docs/spec.md（仕様書）、docs/design.md（設計書）、docs/notes.md（開発メモ、日付順）を読むこと。

## 作業の進め方

- 方針と完了の条件は、別の場所で決めてから渡す。渡された条件を、結果を見てから変えない
- 1回に1つだけ変える
- 変える前に、完了の条件を docs/notes.md に書く
- 条件を満たさなかった変更は取り消し、試したことと理由を docs/notes.md に残す
- 検索の仕組みを変えるときは、まず効果がない値で入れ、検索だけの結果がすべての問題で前と同じになることを確かめる
- 検索を変えるときは、上位3件だけでなく、上位8件から消えた資料がないかも確かめる
- rag.py やプロンプトを変えたら、git diff で消えた行を確かめる（以前、貼り付けで行が消えたことがある）
- ドキュメントとコメントは日本語。今のファイルの書き方に合わせる

## してはいけないこと

- `backend/.env` と `data/` をコミットしない（API キーと、著作権のあるパッチノートの本文）。コミットの前に必ず `git status` を見る
- API キーを出力やファイルに書かない
- テスト用の問題（eval/test_questions.jsonl）を、改善の形が決まる前に流さない。検索だけのモード（--search-only）でも流さない
- テスト用の問題の結果を見て、コードやプロンプトを直さない。◯✕が出た問題を流し直さない（混雑でエラーになった問題だけは流し直してよい）
- AI を呼ぶ評価（--search-only を付けない run_eval.py）を、頼まれずに流さない。無料枠の回数制限を使うため
- push は頼まれたときだけ

## AI を呼ぶ評価のとき

- モデルは `--model gemini-3.5-flash-lite` に固定する
- 503 が出たら1問目で止める（失敗しても回数制限に数えられることがある）。429 が何問も続いたら止める
- 回数制限は太平洋時間の0時（日本時間17時ごろ）にリセットされる

## よく使うコマンド（backend で、.venv に入ってから）

```powershell
python -m pytest -q
python scripts\run_eval.py --search-only
python scripts\run_eval.py --prompt auto --search hybrid --model gemini-3.5-flash-lite
python scripts\show_context.py "質問"
python scripts\count_other_jobs.py
```

- Windows の PowerShell で日本語を出すときは、先に `$env:PYTHONIOENCODING = "utf-8"` を設定する
- 調べるためだけのスクリプトは `data/debug/` に置く（git に入らない）
- 出力を見せるように頼まれたときは、そのまま data/debug/out.txt にも保存する（前の内容は上書きしてよい）。画面では省略されることがあるため 

## 今の状態（2026-11-17 時点）

- 評価用の問題は68問（eval/questions.jsonl）。AI で測ったのは54問まで（lite 54/54）
- テスト用の問題は r001〜r011（eval/test_questions.jsonl、PvP、11問）。ジョブ名がある質問で、正解がロールや共通の調整にある形の改善の最終形が決まるまで流さない。ほかの改善のテストには使わない
- 検索は hybrid（意味の近さ ＋ BM25 を RRF で合わせ、質問のジョブと合う資料に JOB_BONUS = 1/61 を足す）
- ROLE_SKILL_BOOST（改善12）と ROLE_HEADING_JOBS（改善13）は、どちらも False（試して取り消した。コードは残している）
- 意味の近さの検索は VECTOR_INDEX = "pieces"（512トークンを超えるチャンクを、埋め込みのときだけ分けたもの）。"chunks" に戻せば前の動き
- プロンプトは auto（経緯の質問は v4、今の値の質問は v5）
- EXPANSION_GUARD（拡張パッケージの境目で今の値を控える）と NEW_JOB_ALL_NAMES（新しいジョブの見出しから名前をすべて取る）は、どちらも True（改善14。今のデータでは答えは変わらない）
- 8.0 を取り込むときは、設計書（docs/design.md）の 3.8 の手順書のとおりに進める
- 改善の番号は、次は改善15（改善11 とぶつかって、改善14 に名前を変えたことがあるため）
- 自動テストは93個
