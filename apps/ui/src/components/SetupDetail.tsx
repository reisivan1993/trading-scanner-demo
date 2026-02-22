import type { SetupResult } from "../types";
import { SetupChart } from "./SetupChart";

interface SetupDetailProps {
  result: SetupResult;
}

export function SetupDetail({ result }: SetupDetailProps) {
  const { score, setup, patterns, checklist, web_intel_notes, basis } = result;

  const entry = parseFloat(setup.entry);
  const stop = parseFloat(setup.stop);
  const target = parseFloat(setup.target_1);

  return (
    <tr className="detail-panel">
      <td colSpan={9}>
        {/* Chart */}
        <SetupChart
          symbol={result.symbol}
          entry={entry}
          stop={stop}
          target={target}
          direction={result.direction}
        />

        {basis && (
          <p style={{ margin: "16px 0 16px", color: "#b0b0c0", fontSize: 13, lineHeight: 1.5 }}>
            <span style={{ color: "#2962FF", fontWeight: 600, marginRight: 6 }}>Basis:</span>
            {basis}
          </p>
        )}
        <div className="detail-grid">
          <div className="detail-section">
            <h4>Score Breakdown</h4>
            <ul>
              <li>
                <span className="label">Confluence</span>
                <span className="value">{score.confluence.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">Invalidation</span>
                <span className="value">{score.invalidation.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">R:R</span>
                <span className="value">{score.rr.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">Momentum</span>
                <span className="value">{score.momentum.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">Volume</span>
                <span className="value">{score.volume.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">Pattern</span>
                <span className="value">{score.pattern.toFixed(1)}</span>
              </li>
              <li>
                <span className="label">Cleanliness</span>
                <span className="value">{score.cleanliness.toFixed(1)}</span>
              </li>
              {score.web_intel_modifier !== 0 && (
                <li>
                  <span className="label">Web Intel</span>
                  <span className="value">
                    {score.web_intel_modifier > 0 ? "+" : ""}
                    {(score.web_intel_modifier * 100).toFixed(1)}
                  </span>
                </li>
              )}
            </ul>
          </div>
          <div className="detail-section">
            <h4>Trade Details</h4>
            <ul>
              <li>
                <span className="label">Shares</span>
                <span className="value">{setup.shares}</span>
              </li>
              <li>
                <span className="label">Dollar Risk</span>
                <span className="value">${setup.dollar_risk}</span>
              </li>
              <li>
                <span className="label">PnL T1</span>
                <span className="value">${setup.dollar_pnl_t1}</span>
              </li>
              {setup.target_2 && (
                <li>
                  <span className="label">Target 2</span>
                  <span className="value">${setup.target_2}</span>
                </li>
              )}
            </ul>
          </div>
          <div className="detail-section">
            <h4>Patterns</h4>
            {patterns.length > 0 ? (
              <ul>
                {patterns.map((p, i) => (
                  <li key={i}>
                    <span className="label">{p.name}</span>
                    <span className="value">{(p.confidence * 100).toFixed(0)}%</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="no-data">No patterns detected</p>
            )}
            {web_intel_notes.length > 0 && (
              <>
                <h4 style={{ marginTop: 16 }}>Web Intel</h4>
                <ul>
                  {web_intel_notes.map((n, i) => (
                    <li key={i}>
                      <span className="label">{n}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <div className="detail-section">
            <h4>20 Checklist</h4>
            {checklist && checklist.length > 0 ? (
              <ul>
                {checklist.map((item, i) => (
                  <li key={i}>
                    <span className="label">
                      <span className={item.passed ? "checklist-pass" : "checklist-fail"}>
                        {item.passed ? "PASS" : "FAIL"}
                      </span>
                      {" "}{item.criterion}
                    </span>
                    <span className="value">{item.value || ""}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="no-data">No checklist data</p>
            )}
          </div>
        </div>
      </td>
    </tr>
  );
}
