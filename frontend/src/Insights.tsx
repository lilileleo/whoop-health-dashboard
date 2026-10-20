import { useEffect, useState } from "react";
import {
  Plus,
  Trash2,
  Flag,
  Scale,
  Activity,
  LoaderCircle,
} from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { request, num, today } from "./api";
import "./insights.css";

type Event = {
  id: number;
  day: string;
  time: string;
  category: string;
  text: string;
};
type Week = {
  week: string;
  end: string;
  partial: boolean;
  hrv: number | null;
  rhr: number | null;
  strain: number | null;
  weight: number | null;
  hrv_index: number | null;
  rhr_index: number | null;
  strain_index: number | null;
  weight_index: number | null;
  samples: Record<string, number>;
  zones: number[];
  low_minutes: number;
  high_minutes: number;
  low_percent: number | null;
  high_percent: number | null;
  zone_samples: number;
  coverage: number;
  events: Event[];
  notes: { day: string; text: string }[];
  training_complete: number;
  plan_statuses: {
    id: number;
    name: string;
    configured: boolean;
    state: string;
    candidates: number;
  }[];
};
type Data = {
  start: string;
  end: string;
  weeks: Week[];
  weights: { day: string; kg: number }[];
  events: Event[];
  notes: { day: string; text: string }[];
};
const specs = [
  { key: "weight", name: "体重", unit: "kg", color: "#b18c58" },
  { key: "hrv", name: "HRV", unit: "ms", color: "#9073be" },
  { key: "rhr", name: "静息心率", unit: "bpm", color: "#669cc0" },
  { key: "strain", name: "周平均 Strain", unit: "/21", color: "#68976c" },
];
function WeeklyTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: Week }[];
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="chart-tip compare-tip">
      <strong>
        {row.week} — {row.end}
      </strong>
      {specs.map((s) => (
        <div key={s.key}>
          <span style={{ color: s.color }}>{s.name}</span>
          <b>
            {num(row[s.key as keyof Week] as number | null, 1)} {s.unit}
          </b>
        </div>
      ))}
      {row.events.map((e) => (
        <p key={e.id}>
          ⚑ {e.day.slice(5)} {e.text}
        </p>
      ))}
      {row.notes.map((n) => (
        <p key={n.day}>✎ {n.text}</p>
      ))}
    </div>
  );
}
export default function Insights({
  token,
  end,
  onSaved,
  revision,
  onOpenWeek,
}: {
  token?: string;
  end?: string | null;
  onSaved: () => void;
  revision?: string;
  onOpenWeek?: (day: string) => void;
}) {
  const [data, setData] = useState<Data | null>(null),
    [weeks, setWeeks] = useState(8),
    [rev, setRev] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [weightDay, setWeightDay] = useState(today()),
    [weight, setWeight] = useState("");
  const [eventDay, setEventDay] = useState(today()),
    [eventTime, setEventTime] = useState(""),
    [category, setCategory] = useState("其他"),
    [text, setText] = useState("");
  useEffect(() => {
    let active = true;
    const through = end && end > today() ? end : today();
    request<Data>(`/api/long-term?weeks=${weeks}&end=${through}`)
      .then((d) => {
        if (active) {
          setData(d);
          setError("");
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [weeks, end, rev, revision]);
  async function save(kind: "weight" | "event") {
    setBusy(true);
    setError("");
    try {
      if (kind === "weight") {
        await request(
          `/api/weights/${weightDay}`,
          "PUT",
          { kg: Number(weight) },
          token,
        );
        setWeight("");
      } else {
        await request(
          "/api/events",
          "POST",
          { day: eventDay, time: eventTime, category, text },
          token,
        );
        setText("");
      }
      setRev((r) => r + 1);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove(id: number) {
    setBusy(true);
    try {
      await request(`/api/events/${id}`, "DELETE", undefined, token);
      setRev((r) => r + 1);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function removeWeight(day: string) {
    setBusy(true);
    try {
      await request(`/api/weights/${day}`, "DELETE", undefined, token);
      setRev((r) => r + 1);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="insights-workspace">
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>把体重、恢复与负荷放在一起看</h2>
            <p>每条线首个有效周 = 100 · 悬停查看真实数值与事件</p>
          </div>
          <select
            className="insight-select"
            aria-label="长期对照周数"
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
          >
            {[8, 12, 24].map((n) => (
              <option key={n} value={n}>
                过去{n}周
              </option>
            ))}
          </select>
        </div>
        {data ? (
          <>
            <div className="long-chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={data.weeks}
                  margin={{ top: 24, left: -16, right: 16, bottom: 10 }}
                >
                  <CartesianGrid vertical={false} stroke="#edf0e9" />
                  <XAxis
                    dataKey="week"
                    tickFormatter={(v) => v.slice(5)}
                    tick={{ fontSize: 10, fill: "#96a18e" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 10, fill: "#96a18e" }}
                    axisLine={false}
                    tickLine={false}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip content={<WeeklyTooltip />} />
                  <ReferenceLine
                    y={100}
                    stroke="#c5cdbd"
                    strokeDasharray="4 5"
                  />
                  {specs.map((s) => (
                    <Line
                      key={s.key}
                      dataKey={s.key + "_index"}
                      name={s.name}
                      stroke={s.color}
                      strokeWidth={2.3}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                      connectNulls={false}
                      isAnimationActive={false}
                    />
                  ))}
                  {data.weeks
                    .filter((w) => w.events.length || w.notes.length)
                    .map((w) => (
                      <ReferenceLine
                        key={w.week}
                        x={w.week}
                        stroke="#c7b7d8"
                        strokeDasharray="3 4"
                        label={{
                          value: `⚑ ${w.events.length + w.notes.length}`,
                          position: "insideTop",
                          fill: "#9c87b3",
                          fontSize: 10,
                        }}
                      />
                    ))}
                  <Legend wrapperStyle={{ fontSize: 10 }} iconType="circle" />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="insight-caption">
              {!data.weights.length && (
                <span>
                  体重尚无记录，可在下方添加；不会使用当前体重回填历史。
                </span>
              )}
              <p>
                按北京时间自然周统计；Strain
                使用周期读数的周平均，不能直接相加。指数便于比较方向，不代表相互影响的大小。空值留白，末周可能尚未结束。
              </p>
            </div>
          </>
        ) : (
          <div className="empty">
            <LoaderCircle className="spin" />
            正在整理长期趋势
          </div>
        )}
      </section>
      <div className="insight-forms">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>
                <Scale size={15} /> 记录体重
              </h2>
              <p>同一天重复提交会更新该日记录 · 单位 kg</p>
            </div>
          </div>
          <form
            className="insight-form"
            onSubmit={(e) => {
              e.preventDefault();
              save("weight");
            }}
          >
            <label>
              测量日期
              <input
                aria-label="体重测量日期"
                type="date"
                value={weightDay}
                onChange={(e) => setWeightDay(e.target.value)}
                required
              />
            </label>
            <label>
              体重（kg）
              <input
                aria-label="体重公斤"
                type="number"
                step="0.1"
                min="0.1"
                max="500"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="例如 78.5"
                required
              />
            </label>
            <button className="button primary" disabled={busy || !token}>
              <Plus size={14} />
              保存体重
            </button>
          </form>
          {data && data.weights.length > 0 && (
            <div className="recent-weights">
              {data.weights
                .slice(-5)
                .reverse()
                .map((w) => (
                  <span key={w.day}>
                    {w.day.slice(5)} <b>{w.kg} kg</b>
                    <button
                      aria-label={`删除体重${w.day}`}
                      disabled={busy}
                      onClick={() => removeWeight(w.day)}
                    >
                      <Trash2 size={10} />
                    </button>
                  </span>
                ))}
            </div>
          )}
        </section>
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>
                <Flag size={15} /> 在时间线上标一件事
              </h2>
              <p>饮食、计划调整和生活背景都可以留下</p>
            </div>
          </div>
          <form
            className="insight-form event-form"
            onSubmit={(e) => {
              e.preventDefault();
              save("event");
            }}
          >
            <label>
              日期
              <input
                aria-label="事件日期"
                type="date"
                value={eventDay}
                onChange={(e) => setEventDay(e.target.value)}
                required
              />
            </label>
            <label>
              时间（可选）
              <input
                aria-label="事件时间"
                type="time"
                value={eventTime}
                onChange={(e) => setEventTime(e.target.value)}
              />
            </label>
            <label>
              类别
              <select
                aria-label="事件类别"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                {["饮食", "训练调整", "作息", "身体状态", "其他"].map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
            <label className="event-text">
              事件内容
              <input
                aria-label="事件内容"
                value={text}
                onChange={(e) => setText(e.target.value)}
                maxLength={1000}
                placeholder="例如：作息变化 / 训练调整 / 饮食记录"
                required
              />
            </label>
            <button className="button primary" disabled={busy || !token}>
              <Plus size={14} />
              添加事件
            </button>
          </form>
        </section>
      </div>
      {data && (
        <>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>每周极化比例 · 80 / 20</h2>
                <p>按你的指定口径：Zone 1–2 为低强度，Zone 4–5 为高强度</p>
              </div>
            </div>
            <div className="polarization-list">
              {data.weeks.map((w) => (
                <div className="polarization-row" key={w.week}>
                  <div>
                    <strong>
                      {w.week.slice(5)} — {w.end.slice(5)}
                    </strong>
                    <small>
                      {w.zone_samples} 条区间记录
                      {w.partial ? " · 本周未结束" : ""}
                    </small>
                  </div>
                  <div className="polarization-track">
                    <div
                      className="polarization-fill"
                      style={{ width: `${w.low_percent || 0}%` }}
                    />
                    <span style={{ left: "80%" }} title="目标：低强度80%" />
                  </div>
                  <div className="polarization-numbers">
                    {w.low_percent == null ? (
                      "暂无区间数据"
                    ) : (
                      <>
                        <b>
                          {num(w.low_percent)}% / {num(w.high_percent)}%
                        </b>
                        <small>
                          低 {num(w.low_minutes)}分 · 高 {num(w.high_minutes)}分
                        </small>
                      </>
                    )}
                  </div>
                  <div className="zone-middle">
                    Z3：{num(w.zones[3])}分
                    <small>Z0：{num(w.zones[0])}分</small>
                  </div>
                </div>
              ))}
            </div>
            <div className="insight-caption">
              <p>
                分母仅为 Z1+Z2+Z4+Z5；Z0 与 Z3
                单独展示。低/高比例并非全训练时间占比；还需留意 Z3
                是否过多。WHOOP 分区与其他设备的“Zone
                2”定义可能不同，活动重复时区间汇总也可能重复。
              </p>
            </div>
          </section>
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>{weeks}周生活上下文与训练确认</h2>
                <p>
                  按当前周模板核对每一练，确认记录按周保存；时间先后不等于因果
                </p>
              </div>
            </div>
            <div className="context-weeks">
              {[...data.weeks].reverse().map((w) => (
                <article key={w.week}>
                  <div>
                    <strong>
                      {w.week} — {w.end}
                    </strong>
                    <span>
                      四练确认 {w.training_complete}/4 · 健康记录 {w.coverage}{" "}
                      天
                    </span>
                    {onOpenWeek && (
                      <button
                        className="button small"
                        onClick={() => onOpenWeek(w.week)}
                      >
                        核对这周
                      </button>
                    )}
                  </div>
                  <div className="week-plan-chips">
                    {w.plan_statuses?.map((p) => (
                      <span
                        key={p.id}
                        className={p.state === "complete" ? "done" : ""}
                        title={p.name}
                      >
                        第{p.id}练 · {p.name}：
                        {p.state === "complete"
                          ? "已确认"
                          : p.state === "skipped"
                            ? "跳过"
                            : !p.configured
                              ? "未配置"
                              : p.candidates
                                ? "候选待确认"
                                : "未匹配，待核对"}
                      </span>
                    ))}
                  </div>
                  {w.events.map((e) => (
                    <div className="context-event" key={e.id}>
                      <span className="event-tag">{e.category}</span>
                      <small>
                        {e.day.slice(5)} {e.time}
                      </small>
                      <p>{e.text}</p>
                      <button
                        aria-label={`删除事件${e.id}`}
                        disabled={busy}
                        onClick={() => remove(e.id)}
                      >
                        <Trash2 size={13} />
                      </button>
                    </div>
                  ))}
                  {w.notes.map((n) => (
                    <div className="context-event" key={n.day}>
                      <span className="event-tag">日期备注</span>
                      <small>{n.day.slice(5)}</small>
                      <p>{n.text}</p>
                    </div>
                  ))}
                  {!w.events.length && !w.notes.length && (
                    <p className="context-empty">这周暂未添加事件</p>
                  )}
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
