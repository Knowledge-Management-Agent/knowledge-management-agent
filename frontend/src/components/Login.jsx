import { useState } from "react";
import { login } from "../api.js";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("viewer");
  const [password, setPassword] = useState("viewer123");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await login(username, password);
      onLogin({ token: result.access_token, role: result.role, username });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card login-card">
      <h2>Sign in</h2>
      <p className="muted">
        Demo accounts: <code>viewer / viewer123</code> (Q&amp;A only) or{" "}
        <code>author / author123</code> (Q&amp;A + generation + ingestion).
      </p>
      <form onSubmit={handleSubmit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
