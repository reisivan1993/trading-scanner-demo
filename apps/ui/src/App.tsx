import { useEffect, useState } from "react";
import { Banner } from "./components/Banner";
import { SetupTable } from "./components/SetupTable";
import type { ScanResponse } from "./types";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

function App() {
  const [data, setData] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
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

  const triggerScan = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/scan/run`, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchLatest();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger scan");
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLatest();
  }, []);

  return (
    <div>
      <header className="app-header">
        <h1 className="app-title">
          Cold <span>Trader</span> Scanner
        </h1>
        {data && (
          <button className="btn btn-secondary" onClick={fetchLatest} disabled={loading}>
            ↻ Refresh
          </button>
        )}
      </header>

      <main className="app-content">
        {loading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Scanning universe…</span>
          </div>
        )}

        {error && !loading && <div className="error-banner">{error}</div>}

        {!loading && !data && (
          <div className="hero">
            <p className="hero-subtitle">Scan the universe and surface trade setups</p>
            <button className="btn-google-scan" onClick={triggerScan} disabled={loading}>
              <svg className="scan-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              Scan All Stocks
            </button>
          </div>
        )}

        {data && !loading && (
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
                {data.meta.completed_at && (
                  <div className="meta-item">
                    <span className="meta-label">Completed</span>
                    <span className="meta-value">
                      {new Date(data.meta.completed_at).toLocaleString()}
                    </span>
                  </div>
                )}
              </div>

              <button className="btn-google-scan btn-google-scan--small" onClick={triggerScan} disabled={loading}>
                <svg className="scan-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                Re-scan
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
