import { useEffect, useState } from "react";
import { Banner } from "./components/Banner";
import { SetupTable } from "./components/SetupTable";
import type { ScanResponse } from "./types";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8001";

type TabId = "adhoc" | "swing" | "position";

const TABS: { id: TabId; label: string; description: string }[] = [
  { id: "adhoc", label: "Ad-Hoc", description: "Single ticker or full universe scan" },
  { id: "swing", label: "Short-Term Swing", description: "Mean reversion: extended from MA20" },
  { id: "position", label: "Long Position Entry", description: "Trend following: near SMA150" },
];

function App() {
  const [activeTab, setActiveTab] = useState<TabId>("adhoc");
  const [data, setData] = useState<ScanResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");

  const fetchLatest = async (tab?: TabId) => {
    const current = tab ?? activeTab;
    setLoading(true);
    setError(null);
    try {
      const url =
        current === "adhoc"
          ? `${API_BASE}/scan/latest`
          : `${API_BASE}/scan/strategy/${current}/latest`;
      const resp = await fetch(url);
      if (resp.status === 404) {
        setData(null);
        setError("No scan results yet. Run a scan first.");
        return;
      }
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const json = await resp.json();
      setData(json);
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
      const url =
        activeTab === "adhoc"
          ? `${API_BASE}/scan/run`
          : `${API_BASE}/scan/strategy/${activeTab}`;
      const resp = await fetch(url, { method: "POST" });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchLatest();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger scan");
      setLoading(false);
    }
  };

  const scanTicker = async () => {
    const symbol = ticker.trim();
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/scan/ticker/${encodeURIComponent(symbol)}`, {
        method: "POST",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      await fetchLatest();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to scan ${symbol}`);
      setLoading(false);
    }
  };

  const handleTickerKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      scanTicker();
    }
  };

  const handleTabChange = (tab: TabId) => {
    setActiveTab(tab);
    setData(null);
    setError(null);
    fetchLatest(tab);
  };

  useEffect(() => {
    fetchLatest();
  }, []);

  const scanButtonLabel =
    activeTab === "adhoc"
      ? "Run Full Scan"
      : activeTab === "swing"
        ? "Run Swing Scan"
        : "Run Position Scan";

  return (
    <div>
      <header className="app-header">
        <h1 className="app-title">
          Cold <span>Trader</span> Scanner
        </h1>
        <div className="header-controls">
          <div className="ticker-input-group">
            <input
              type="text"
              className="ticker-input"
              placeholder="e.g. AAPL"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              onKeyDown={handleTickerKeyDown}
              disabled={loading}
            />
            <button
              className="btn btn-scan-ticker"
              onClick={scanTicker}
              disabled={loading || !ticker.trim()}
            >
              Scan Ticker
            </button>
          </div>
          <button className="btn btn-secondary" onClick={() => fetchLatest()} disabled={loading}>
            Refresh
          </button>
          <button className="btn btn-primary" onClick={triggerScan} disabled={loading}>
            {loading ? "Scanning..." : scanButtonLabel}
          </button>
        </div>
      </header>

      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={`tab-btn ${activeTab === tab.id ? "tab-active" : ""}`}
            onClick={() => handleTabChange(tab.id)}
            title={tab.description}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="app-content">
        {loading && (
          <div className="loading-overlay">
            <div className="spinner" />
            <span>Scanning...</span>
          </div>
        )}

        {error && !loading && <div className="error-banner">{error}</div>}

        {data && !loading && (
          <>
            <Banner visible={data.cash_is_position} message={data.banner_message} />

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

            <SetupTable results={data.results} />
          </>
        )}
      </main>
    </div>
  );
}

export default App;
