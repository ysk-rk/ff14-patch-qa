import { useState, type FormEvent } from 'react'
import './App.css'

type Source = {
  version: string
  headings: string
  url: string
  score: number
}

type AskResponse = {
  answer: string
  model: string
  sources: Source[]
}

const EXAMPLES = [
  'モンクの万象闘気圏の今の威力は？',
  'PvPのモンクの夢幻闘舞は何が変わった？',
  'ナイトのホーリースピリットの威力は？',
]

// 見出しに PvP 系の言葉が入っているチャンクは PvP として表示する
function isPvP(headings: string): boolean {
  return /PvP|フロントライン|クリスタルコンフリクト/.test(headings)
}

function App() {
  const [question, setQuestion] = useState('')
  const [result, setResult] = useState<AskResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function ask(q: string) {
    if (!q.trim() || loading) return

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        throw new Error(body?.detail ?? `エラーが発生しました（${res.status}）`)
      }
      setResult(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    ask(question)
  }

  function handleExample(q: string) {
    setQuestion(q)
    ask(q)
  }

  // 出典は新しいパッチが上に来るように並べ替える
  const sources = result ? [...result.sources].reverse() : []

  return (
    <main className="container">
      <h1>FF14 パッチノート Q&amp;A</h1>
      <p className="lead">黄金のレガシー（7.0〜7.57）のパッチノートをもとに答えます。</p>

      <form onSubmit={handleSubmit} className="ask-form">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="例：モンクの万象闘気圏の今の威力は？"
          disabled={loading}
        />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? '考え中…' : '質問する'}
        </button>
      </form>

      <div className="examples">
        {EXAMPLES.map((q) => (
          <button key={q} type="button" onClick={() => handleExample(q)} disabled={loading}>
            {q}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <>
          <section className="answer">
            <h2>回答</h2>
            <p>{result.answer}</p>
            <p className="model">回答したモデル：{result.model}</p>
          </section>

          <section className="sources">
            <h2>参考にしたパッチノート</h2>
            <ul>
              {sources.map((s, i) => (
                <li key={`${s.url}-${i}`}>
                  <span className="version">パッチ{s.version}</span>
                  <span className={isPvP(s.headings) ? 'tag pvp' : 'tag pve'}>
                    {isPvP(s.headings) ? 'PvP' : 'PvE'}
                  </span>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    {s.headings}
                  </a>
                  <span className="score">近さ {s.score.toFixed(3)}</span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </main>
  )
}

export default App