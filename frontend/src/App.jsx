import { useState } from "react";
import "./App.css";

const SAMPLE_NOTE = `line 42 — Metformin 500mg BID, continued on discharge.
line 58 — CT chest ordered 3/2 for persistent cough.
line 61 — Pt tolerating oral intake well, ambulating independently.
`;

const API_URL = "http://localhost:8010/api/summarize";

const SECTION_LABELS = {
  discharge_medications: "Discharge Medications",
  hospital_course: "Hospital Course",
  follow_up_plan: "Follow-up Plan",
};

function SentenceRow({ sentence }) {
  return (
    <div className={`sentence-row ${sentence.entailed ? "ok" : "rejected"}`}>
      <span className="sentence-text">{sentence.text}</span>
      <span className="sentence-meta">
        {sentence.entailed ? "✓" : "✗"} lines {sentence.source_lines.join(", ")}
      </span>
    </div>
  );
}

function CoverageRow({ result }) {
  return (
    <div className={`coverage-row ${result.satisfied ? "ok" : "flagged"}`}>
      <strong>{SECTION_LABELS[result.field] ?? result.field}</strong>
      {result.satisfied ? (
        <span className="badge ok">Cited</span>
      ) : (
        <span className="badge flagged">{result.flag}</span>
      )}
    </div>
  );
}

export default function App() {
  const [note, setNote] = useState(SAMPLE_NOTE);
  const [backend, setBackend] = useState("stub");
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSummarize() {
    setLoading(true);
    setError(null);
    setDraft(null);
    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note, backend }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail ?? `Request failed (${res.status})`);
      }
      setDraft(await res.json());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Clinical Note Summarization — Draft Review</h1>
        <p className="subtitle">
          Draft-only. Nothing here is ever sent, filed, or acted on — every sentence
          is traceable to its source line, and unsupported fields are flagged rather
          than guessed.
        </p>
      </header>

      <section className="input-panel">
        <label htmlFor="note">Source note (line-numbered)</label>
        <textarea
          id="note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={8}
          spellCheck={false}
        />
        <div className="controls">
          <label htmlFor="backend">Backend</label>
          <select id="backend" value={backend} onChange={(e) => setBackend(e.target.value)}>
            <option value="stub">Offline stub (free, deterministic)</option>
            <option value="claude">Claude (live)</option>
            <option value="gemini">Gemini (live)</option>
          </select>
          <button onClick={() => setNote(SAMPLE_NOTE)} disabled={loading}>
            Load sample note
          </button>
          <button className="primary" onClick={handleSummarize} disabled={loading || !note.trim()}>
            {loading ? "Summarizing…" : "Generate draft"}
          </button>
        </div>
      </section>

      {error && <div className="error-banner">Error: {error}</div>}

      {draft && (
        <section className="draft-panel">
          <h2>Draft Summary</h2>
          {Object.entries(draft.sections).map(([section, sentences]) => (
            <div className="section-block" key={section}>
              <h3>{SECTION_LABELS[section] ?? section}</h3>
              {sentences.length === 0 ? (
                <p className="empty">No sentences generated for this section.</p>
              ) : (
                sentences.map((s, i) => <SentenceRow sentence={s} key={i} />)
              )}
            </div>
          ))}

          <div className="section-block">
            <h3>Coverage</h3>
            {draft.coverage.map((c) => (
              <CoverageRow result={c} key={c.field} />
            ))}
          </div>

          <div className="section-block">
            <h3>Open Loops</h3>
            {draft.open_loops.length === 0 ? (
              <p className="empty">None detected.</p>
            ) : (
              draft.open_loops.map((loop, i) => (
                <div className="open-loop-row" key={i}>
                  line {loop.order_line}: {loop.description}
                </div>
              ))
            )}
          </div>
        </section>
      )}
    </div>
  );
}
