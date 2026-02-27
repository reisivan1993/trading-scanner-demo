import { useEffect, useState } from "react";
import { Banner } from "./components/Banner";
import { SetupTable } from "./components/SetupTable";
import type { ScanResponse } from "./types";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "";

function App() {
  const [data, setData] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLatest = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/scan/latest`);
      if (resp.status === 404) {
        setData(null);
        return;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setData(await resp.json());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch");
    } finally {
      setLoading(false);
    }
  };

  const streamScan = async () => {
    setStreaming(true);
    setData(null);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/scan/stream`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      if (!resp.body) throw new Error("No response body");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const lines = part.split("\n");
          let eventName = "message";
          let dataLine = "";
          for (const line of lines) {
            if (line.startsWith("event: ")) eventName = line.slice(7).trim();
            if (line.startsWith("data: ")) dataLine = line.slice(6);
          }
          if (eventName === "done") return;
          if (eventName === "error") {
            const parsed = JSON.parse(dataLine);
            setError(parsed.error ?? "Scan failed");
            return;
          }
          if (dataLine) setData(JSON.parse(dataLine));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stream failed");
    } finally {
      setStreaming(false);
    }
  };

  useEffect(() => {
    fetchLatest();
  }, []);

  const isBusy = loading || streaming;
  const scanIcon = (
    <svg className="scan-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );

  return (
    <div>
      <header className="app-header">
        <h1 className="app-title">
          Cold <span>Trader</span> Scanner
        </h1>
        {data && !streaming && (
          <button className="btn btn-secondary" onClick={fetchLatest} disabled={isBusy}>
            ↻ Refresh
          </button>
        )}
      </header>

      <main className="app-content">
        {loading && !streaming && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Loading…</span>
          </div>
        )}

        {error && !isBusy && <div className="error-banner">{error}</div>}

        {!isBusy && !data && (
          <div className="hero">
            <p className="hero-subtitle">Scan the universe and surface trade setups</p>
            <button className="btn-google-scan" onClick={streamScan} disabled={isBusy}>
              {scanIcon}
              Scan All Stocks
            </button>
          </div>
        )}

        {streaming && !data && (
          <div className="hero">
            <div className="spinner" />
            <span style={{ color: "var(--text-muted)", marginTop: "1rem" }}>
              Starting scan…
            </span>
          </div>
        )}

        {data && (
          <>
            <Banner visible={data.cash_is_position} message={data.banner_message} />

            <div className="results-toolbar">
              <div className="meta-bar">
                <div className="meta-item">
                  <span className="meta-label">Run</span>
                  <span className="meta-value">{data.meta.run_id.slice(0, 8)}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Scanned</span>
                  <span className="meta-value">{data.meta.tickers_scanned}</span>
                </div>
                <div className="meta-item">
                  <span className="meta-label">Setups</span>
                  <span className="meta-value">{data.meta.setups_passed_risk}</span>
                </div>
                {data.meta.completed_at && !streaming && (
                  <div className="meta-item">
                    <span className="meta-label">Completed</span>
                    <span className="meta-value">
                      {new Date(data.meta.completed_at).toLocaleString()}
                    </span>
                  </div>
                )}
                {streaming && (
                  <div className="meta-item">
                    <span className="meta-label" style={{ color: "var(--accent)" }}>● Live</span>
                  </div>
                )}
              </div>

              <button className="btn-google-scan btn-google-scan--small" onClick={streamScan} disabled={isBusy}>
                {scanIcon}
                {streaming ? "Scanning…" : "Re-scan"}
              </button>
            </div>

            <SetupTable results={data.results} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
