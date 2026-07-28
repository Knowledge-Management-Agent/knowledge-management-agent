import { useState } from "react";
import { askQuestion } from "../api.js";

export default function Chat({ token }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e) {
    e.preventDefault();
    if (!question.trim()) return;
    const q = question.trim();
    setMessages((m) => [...m, { role: "user", text: q }]);
    setQuestion("");
    setBusy(true);
    setError("");
    try {
      const result = await askQuestion(token, q);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: result.answer,
          citations: result.citations,
          timings: result.timings_ms,
        },
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Ask the knowledge base</h2>
      <div className="chat-log">
        {messages.length === 0 && (
          <p className="muted">Ask a question about an ingested document to get started.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg-${m.role}`}>
            <strong>{m.role === "user" ? "You" : "Assistant"}</strong>
            <p>{m.text}</p>
            {m.citations && m.citations.length > 0 && (
              <div className="citations">
                Sources:{" "}
                {m.citations.map((c, ci) => (
                  <span className="citation-pill" key={ci}>
                    {c.title || c.source}
                  </span>
                ))}
              </div>
            )}
            {m.timings && (
              <div className="muted timing">
                retrieval {m.timings.retrieval}ms · generation {m.timings.generation}ms · total{" "}
                {m.timings.total}ms
              </div>
            )}
          </div>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      <form onSubmit={handleSubmit} className="chat-input-row">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How do I restart the ingestion service?"
        />
        <button type="submit" disabled={busy}>
          {busy ? "Thinking..." : "Ask"}
        </button>
      </form>
    </div>
  );
}
