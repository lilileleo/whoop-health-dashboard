import { useEffect, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Day } from "./api";
import { num } from "./api";
import "./insights.css";
const specs = [
  { key: "hrv", label: "HRV", unit: "ms", color: "#9073be" },
  { key: "rhr", label: "静息心率", unit: "bpm", color: "#669cc0" },
  { key: "sleep", label: "主睡眠时长", unit: "小时", color: "#68976c" },
  {
    key: "respiratory",
    label: "睡眠呼吸率",
    unit: "次/分钟",
    color: "#b18c58",
  },
];
export default function RecoverySignals({ daily }: { daily: Day[] }) {
  const valid = daily.filter((d) => d.recovery != null);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    setSelected((old) =>
      valid.some((d) => d.date === old)
        ? old
        : [...valid].reverse().find((d) => d.recovery! <= 33)?.date ||
          valid.at(-1)?.date ||
          "",
    );
  }, [daily]);
  const row = valid.find((d) => d.date === selected);
  if (!row) return null;
  const preceding = daily.filter((d) => d.date <= selected).slice(-28);
  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>低恢复日，分别看哪些信号变化</h2>
          <p>
            对照此前28天个人基线；不还原 WHOOP 私有权重，也不把同期变化当作原因
          </p>
        </div>
        <select
          className="insight-select"
          aria-label="恢复信号日期"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {[...valid].reverse().map((d) => (
            <option key={d.date} value={d.date}>
              {d.date} · 恢复{d.recovery}
            </option>
          ))}
        </select>
      </div>
      <div className="signal-selected">
        {row.date} <strong>恢复 {num(row.recovery)} / 100</strong>
        {row.calibrating && <span>校准期，谨慎对照</span>}
      </div>
      <div className="signal-grid">
        {specs.map((s) => {
          const value = row[s.key as keyof Day] as number | null;
          const base = row[(s.key + "_baseline") as keyof Day] as number | null;
          const delta = value != null && base != null ? value - base : null;
          return (
            <article key={s.key}>
              <h3 style={{ color: s.color }}>{s.label}</h3>
              <strong>
                {num(value, 1)} <small>{s.unit}</small>
              </strong>
              <p>
                此前基线 {num(base, 1)}{" "}
                {delta == null
                  ? "· 样本不足"
                  : `· ${delta >= 0 ? "高" : "低"} ${Math.abs(delta).toFixed(1)}`}
              </p>
              <div className="signal-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={preceding}
                    margin={{ left: 0, right: 0, top: 10, bottom: 0 }}
                  >
                    <XAxis dataKey="date" hide />
                    <YAxis hide domain={["auto", "auto"]} />
                    <Tooltip
                      formatter={(v) => `${Number(v).toFixed(1)} ${s.unit}`}
                    />
                    <Line
                      dataKey={s.key}
                      name={s.label}
                      stroke={s.color}
                      strokeWidth={2}
                      dot={false}
                      isAnimationActive={false}
                      connectNulls={false}
                    />
                    <Line
                      dataKey={s.key + "_baseline"}
                      name="此前28天基线"
                      stroke="#bbc5b2"
                      strokeDasharray="3 3"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </article>
          );
        })}
      </div>
      <p className="insight-caption">
        只显示所选日期之前、当前筛选范围内的趋势。基线至少需要7个非校准样本；睡眠、呼吸率缺失时留空。指标和事件共同帮助提出问题，不能精确解释总分下降了多少。
      </p>
    </section>
  );
}
