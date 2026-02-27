import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, ColorType, LineStyle, CandlestickSeries, LineSeries } from "lightweight-charts";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface SetupChartProps {
    symbol: string;
    entry: number;
    stop: number;
    target: number;
    direction: "long" | "short";
}

interface Candle {
    time: string;
    open: number;
    high: number;
    low: number;
    close: number;
}

interface SmaPoint {
    time: string;
    value: number;
}

export function SetupChart({ symbol, entry, stop, target, direction }: SetupChartProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!containerRef.current) return;

        const container = containerRef.current;

        const chart = createChart(container, {
            layout: {
                background: { type: ColorType.Solid, color: "#131722" },
                textColor: "#787B86",
                fontFamily: "'Inter', sans-serif",
                fontSize: 12,
            },
            grid: {
                vertLines: { color: "#1E222D" },
                horzLines: { color: "#1E222D" },
            },
            crosshair: {
                vertLine: { color: "#4C525E", width: 1, style: LineStyle.Dashed },
                horzLine: { color: "#4C525E", width: 1, style: LineStyle.Dashed },
            },
            rightPriceScale: {
                borderColor: "#2A2E39",
                scaleMargins: { top: 0.1, bottom: 0.1 },
            },
            timeScale: {
                borderColor: "#2A2E39",
                timeVisible: false,
            },
            width: container.clientWidth,
            height: 360,
        });

        chartRef.current = chart;

        // v5 API: use addSeries with series type
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: "#26A69A",
            downColor: "#EF5350",
            borderUpColor: "#26A69A",
            borderDownColor: "#EF5350",
            wickUpColor: "#26A69A",
            wickDownColor: "#EF5350",
        });

        const smaLine = chart.addSeries(LineSeries, {
            color: "#FF9800",
            lineWidth: 2,
            priceLineVisible: false,
            crosshairMarkerVisible: false,
            title: "SMA20",
        });

        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const resp = await fetch(
                    `${API_BASE}/chart/${encodeURIComponent(symbol)}?period=6mo&interval=1d`
                );
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();

                const candles: Candle[] = data.candles || [];
                const sma20: SmaPoint[] = data.sma20 || [];

                if (candles.length === 0) {
                    setError("No chart data available");
                    setLoading(false);
                    return;
                }

                candleSeries.setData(candles as any);
                if (sma20.length > 0) {
                    smaLine.setData(sma20 as any);
                }

                // Entry price line (green)
                candleSeries.createPriceLine({
                    price: entry,
                    color: "#26A69A",
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `Entry $${entry.toFixed(2)}`,
                });

                // Stop price line (red)
                candleSeries.createPriceLine({
                    price: stop,
                    color: "#EF5350",
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `Stop $${stop.toFixed(2)}`,
                });

                // Target price line (blue)
                candleSeries.createPriceLine({
                    price: target,
                    color: "#2962FF",
                    lineWidth: 2,
                    lineStyle: LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: `T1 $${target.toFixed(2)}`,
                });

                chart.timeScale().fitContent();
            } catch (err) {
                setError(err instanceof Error ? err.message : "Chart load failed");
            } finally {
                setLoading(false);
            }
        };

        fetchData();

        const handleResize = () => {
            if (containerRef.current) {
                chart.applyOptions({ width: containerRef.current.clientWidth });
            }
        };
        window.addEventListener("resize", handleResize);

        return () => {
            window.removeEventListener("resize", handleResize);
            chart.remove();
            chartRef.current = null;
        };
    }, [symbol, entry, stop, target, direction]);

    const risk = Math.abs(entry - stop);
    const reward = Math.abs(target - entry);
    const rrRatio = risk > 0 ? (reward / risk).toFixed(1) : "—";

    return (
        <div className="chart-wrapper">
            <div className="chart-header">
                <span className="chart-symbol">{symbol}</span>
                <div className="chart-trade-info">
                    <span className="chart-entry">
                        Entry: <strong>${entry.toFixed(2)}</strong>
                    </span>
                    <span className="chart-stop">
                        Stop: <strong>${stop.toFixed(2)}</strong>
                    </span>
                    <span className="chart-target">
                        Target: <strong>${target.toFixed(2)}</strong>
                    </span>
                    <span className="chart-rr">
                        R:R <strong>{rrRatio}</strong>
                    </span>
                    <span className="chart-profit">
                        Potential: <strong>${reward.toFixed(2)}/share</strong>
                    </span>
                </div>
            </div>
            <div className="chart-container" ref={containerRef}>
                {loading && (
                    <div className="chart-loading">
                        <div className="spinner" />
                        <span>Loading chart…</span>
                    </div>
                )}
                {error && <div className="chart-error">{error}</div>}
            </div>
        </div>
    );
}
