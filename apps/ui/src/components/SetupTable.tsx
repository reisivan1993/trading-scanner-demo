import { useState } from "react";
import type { SetupResult } from "../types";
import { SetupDetail } from "./SetupDetail";

interface SetupTableProps {
  results: SetupResult[];
  language?: "en" | "he";
}

type SortField = "rank" | "symbol" | "score" | "rr";

const HEADERS_EN = {
  rank: "Rank",
  symbol: "Symbol",
  direction: "Direction",
  price: "Price",
  entry: "Entry",
  stop: "Stop",
  target: "Target 1",
  rr: "R:R",
  score: "Score",
};

const HEADERS_HE = {
  rank: "דירוג",
  symbol: "סימול",
  direction: "כיוון",
  price: "מחיר",
  entry: "כניסה",
  stop: "סטופ",
  target: "יעד 1",
  rr: "סיכון/סיכוי",
  score: "ציון",
};

const SORTABLE_FIELDS = new Set(["rank", "symbol", "score", "rr"]);

export function SetupTable({ results, language = "en" }: SetupTableProps) {
  const [sortField, setSortField] = useState<SortField>("rank");
  const [sortAsc, setSortAsc] = useState(true);
  const [expandedRank, setExpandedRank] = useState<number | null>(null);
  const [filter, setFilter] = useState("");

  const headers = language === "he" ? HEADERS_HE : HEADERS_EN;

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const filtered = results.filter(
    (r) =>
      r.symbol.toLowerCase().includes(filter.toLowerCase()) ||
      r.direction.toLowerCase().includes(filter.toLowerCase())
  );

  const sorted = [...filtered].sort((a, b) => {
    let cmp = 0;
    switch (sortField) {
      case "rank":
        cmp = a.rank - b.rank;
        break;
      case "symbol":
        cmp = a.symbol.localeCompare(b.symbol);
        break;
      case "score":
        cmp = a.score.total - b.score.total;
        break;
      case "rr":
        cmp = a.setup.rr_ratio - b.setup.rr_ratio;
        break;
    }
    return sortAsc ? cmp : -cmp;
  });

  return (
    <div>
      <div className="table-header-bar">
        <input
          type="text"
          className="filter-input"
          placeholder="Filter by symbol or direction…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="table-result-count">
          {sorted.length} of {results.length} setups
        </span>
      </div>
      <table
        className="setup-table"
        style={{ direction: language === "he" ? "rtl" : "ltr" }}
      >
        <thead>
          <tr>
            {Object.entries(headers).map(([key, label]) => {
              const is_sortable = SORTABLE_FIELDS.has(key);
              const is_active = sortField === key;
              const className = [
                is_sortable ? "sortable" : "",
                is_active ? "active-sort" : "",
              ]
                .filter(Boolean)
                .join(" ");

              return (
                <th
                  key={key}
                  className={className}
                  onClick={() => is_sortable && handleSort(key as SortField)}
                >
                  {label} {is_active ? (sortAsc ? "▲" : "▼") : ""}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <>
              <tr
                key={r.rank}
                onClick={() => setExpandedRank(expandedRank === r.rank ? null : r.rank)}
              >
                <td>{r.rank}</td>
                <td className="symbol-cell">{r.symbol}</td>
                <td>
                  <span className={`direction-badge ${r.direction}`}>
                    {r.direction.toUpperCase()}
                  </span>
                </td>
                <td className="price-cell">
                  {r.current_price ? `$${r.current_price}` : "—"}
                </td>
                <td className="price-cell">${r.setup.entry}</td>
                <td className="price-cell">${r.setup.stop}</td>
                <td className="price-cell">${r.setup.target_1}</td>
                <td className="price-cell">{r.setup.rr_ratio.toFixed(1)}</td>
                <td className="score-cell">{r.score.total.toFixed(1)}</td>
              </tr>
              {expandedRank === r.rank && (
                <SetupDetail key={`detail-${r.rank}`} result={r} />
              )}
            </>
          ))}
          {sorted.length === 0 && (
            <tr className="empty-row">
              <td colSpan={9}>No setups to display</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
