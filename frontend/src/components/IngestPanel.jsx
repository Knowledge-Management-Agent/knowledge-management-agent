import { useEffect, useState } from "react";
import { ingestFile, listDocuments } from "../api.js";

export default function IngestPanel({ token }) {
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [docs, setDocs] = useState([]);

  async function refresh() {
    try {
      const r = await listDocuments(token);
      setDocs(r.documents);
    } catch (err) {
      setStatus(`Error listing documents: ${err.message}`);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setStatus("");
    try {
      const r = await ingestFile(token, file);
      setStatus(`Ingested "${r.source}" -> ${r.chunks_ingested} chunks.`);
      setFile(null);
      await refresh();
    } catch (err) {
      setStatus(`Error: ${err.message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>Ingest a document</h2>
      <form onSubmit={handleUpload} className="ingest-row">
        <input
          type="file"
          accept=".pdf,.docx,.html,.htm,.md,.markdown,.txt"
          onChange={(e) => setFile(e.target.files[0] || null)}
        />
        <button type="submit" disabled={busy || !file}>
          {busy ? "Uploading..." : "Ingest"}
        </button>
      </form>
      {status && <p className="muted">{status}</p>}

      <h3>Indexed documents</h3>
      {docs.length === 0 ? (
        <p className="muted">No documents ingested yet.</p>
      ) : (
        <ul className="doc-list">
          {docs.map((d) => (
            <li key={d.source}>
              {d.title} <span className="muted">({d.chunks} chunks)</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
