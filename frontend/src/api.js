const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function authHeaders(token) {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle(res) {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function login(username, password) {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  return handle(res);
}

export async function health() {
  const res = await fetch(`${BASE_URL}/health`);
  return handle(res);
}

export async function askQuestion(token, question, topK) {
  const res = await fetch(`${BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ question, top_k: topK ?? null }),
  });
  return handle(res);
}

export async function generateDocument(token, docType, inputText, useRetrieval) {
  const res = await fetch(`${BASE_URL}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ doc_type: docType, input_text: inputText, use_retrieval: useRetrieval }),
  });
  return handle(res);
}

export async function approveAndReingest(token, docType, title, content) {
  const res = await fetch(`${BASE_URL}/generate/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(token) },
    body: JSON.stringify({ doc_type: docType, title, content }),
  });
  return handle(res);
}

export async function ingestFile(token, file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE_URL}/ingest`, {
    method: "POST",
    headers: authHeaders(token),
    body: form,
  });
  return handle(res);
}

export async function listDocuments(token) {
  const res = await fetch(`${BASE_URL}/ingest/documents`, {
    headers: authHeaders(token),
  });
  return handle(res);
}
