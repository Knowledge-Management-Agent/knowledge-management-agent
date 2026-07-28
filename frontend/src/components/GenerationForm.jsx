import { useState } from "react";
import { approveAndReingest, generateDocument } from "../api.js";

const DOC_TYPES = [
  { value: "runbook", label: "Runbook" },
  { value: "sop", label: "SOP" },
  { value: "kb_article", label: "KB Article" },
  { value: "rca_summary", label: "RCA Summary" },
];

export default function GenerationForm({ token }) {
  const [docType, setDocType] = useState("runbook");
  const [inputText, setInputText] = useState("");
  const [useRetrieval, setUseRetrieval] = useState(true);
  const [result, setResult] = useState(null);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [approveStatus, setApproveStatus] = useState("");
  const [error, setError] = useState("");

  async function handleGenerate(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setApproveStatus("");
    try {
      const r = await generateDocument(token, docType, inputText, useRetrieval);
      setResult(r);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove() {
    if (!result || !title.trim()) {
      setApproveStatus("Enter a title before approving.");
      return;
    }
    setBusy(true);
    try {
      const r = await approveAndReingest(token, docType, title.trim(), result.content);
      setApproveStatus(`Re-ingested as "${r.source}" (${r.chunks_ingested} chunks).`);
    } catch (err) {
      setApproveStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Generate a document</h2>
      <form onSubmit={handleGenerate}>
        <label>
          Document type
          <select value={docType} onChange={(e) => setDocType(e.target.value)}>
            {DOC_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Input (ticket text, incident notes, raw notes...)
          <textarea
            rows={6}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Paste the raw operational input to draft from..."
          />
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={useRetrieval}
            onChange={(e) => setUseRetrieval(e.target.checked)}
          />
          Ground with retrieved knowledge base context
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || !inputText.trim()}>
          {busy ? "Generating..." : "Generate"}
        </button>
      </form>

      {result && (
        <div className="generated-result">
          <h3>Draft ({result.doc_type})</h3>
          <pre className="generated-content">{result.content}</pre>
          {result.citations.length > 0 && (
            <div className="citations">
              Sources:{" "}
              {result.citations.map((c, i) => (
                <span className="citation-pill" key={i}>
                  {c.title || c.source}
                </span>
              ))}
            </div>
          )}
          <div className="approve-row">
            <input
              placeholder="Title for re-ingesting this draft into the KB"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <button type="button" onClick={handleApprove} disabled={busy}>
              Approve &amp; re-ingest
            </button>
          </div>
          {approveStatus && <p className="muted">{approveStatus}</p>}
        </div>
      )}
    </div>
  );
}
