import { useState } from "react";
import Login from "./components/Login.jsx";
import Chat from "./components/Chat.jsx";
import GenerationForm from "./components/GenerationForm.jsx";
import IngestPanel from "./components/IngestPanel.jsx";

const TABS = {
  qa: "Ask a question",
  generate: "Generate documents",
  ingest: "Ingest & sources",
};

export default function App() {
  const [session, setSession] = useState(null); // { token, role, username }
  const [tab, setTab] = useState("qa");

  if (!session) {
    return (
      <div className="page">
        <h1>Knowledge Management Agent — PoC</h1>
        <Login onLogin={setSession} />
      </div>
    );
  }

  const isAuthor = session.role === "author";
  const visibleTabs = isAuthor ? TABS : { qa: TABS.qa };

  return (
    <div className="page">
      <header className="app-header">
        <h1>Knowledge Management Agent — PoC</h1>
        <div>
          <span className="muted">
            {session.username} ({session.role})
          </span>{" "}
          <button className="link-button" onClick={() => setSession(null)}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="tabs">
        {Object.entries(visibleTabs).map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "tab active" : "tab"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "qa" && <Chat token={session.token} />}
      {tab === "generate" && isAuthor && <GenerationForm token={session.token} />}
      {tab === "ingest" && isAuthor && <IngestPanel token={session.token} />}
    </div>
  );
}
