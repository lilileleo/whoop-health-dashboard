import { useEffect, useRef, useState } from "react";
import {
  Activity,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock3,
  LoaderCircle,
  Plus,
} from "lucide-react";
import { request, num } from "./api";
import "./calendar.css";

type Sport = {
  id: string;
  label: string;
  emoji: string;
  color: string;
  count: number;
};
type Session = {
  id: string;
  sport: string;
  start_minute: number;
  end_minute: number;
  minutes: number;
  strain: number | null;
  average_hr: number | null;
  continues_before: boolean;
  continues_after: boolean;
};
type CalendarDay = {
  events: {
    id: number;
    day: string;
    time: string;
    category: string;
    text: string;
  }[];
  date: string;
  sessions: Session[];
  minutes: number;
  percentage: number;
  recorded: boolean;
  note: string;
  dominant_sport: string | null;
};
type CalendarData = {
  start: string;
  end: string;
  days: CalendarDay[];
  sports: Sport[];
  summary: {
    activities: number;
    active_days: number;
    minutes: number;
    recorded_days: number;
  };
};
const clock = (minutes: number) =>
  `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(Math.floor(minutes % 60)).padStart(2, "0")}`;
const dateName = (day: string) =>
  new Date(day + "T12:00:00+08:00").toLocaleDateString("zh-CN", {
    month: "long",
    day: "numeric",
    weekday: "long",
    timeZone: "Asia/Shanghai",
  });
const shade = (minutes: number) =>
  minutes === 0
    ? "#eeedf3"
    : minutes < 20
      ? "#e2daf1"
      : minutes < 45
        ? "#c9b8e2"
        : minutes < 90
          ? "#ae91d0"
          : minutes < 150
            ? "#8c68b7"
            : "#66468f";

export default function ActivityCalendar({
  end,
  revision,
  onNote,
}: {
  end?: string | null;
  revision: string;
  onNote: (note: { day: string; text: string }) => void;
}) {
  const [months, setMonths] = useState(6),
    [mode, setMode] = useState("type"),
    [filter, setFilter] = useState<string | null>(null);
  const [data, setData] = useState<CalendarData | null>(null),
    [selected, setSelected] = useState(""),
    [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active = true;
    setBusy(true);
    request<CalendarData>(
      `/api/activity-calendar?days=${months === 12 ? 365 : months === 6 ? 182 : 91}${end ? `&end=${end}` : ""}`,
    )
      .then((d) => {
        if (!active) return;
        setData(d);
        setError("");
        setSelected((prev) =>
          d.days.some((x) => x.date === prev)
            ? prev
            : [...d.days].reverse().find((x) => x.sessions.length)?.date ||
              d.end,
        );
      })
      .catch((e) => active && setError(e.message))
      .finally(() => active && setBusy(false));
    return () => {
      active = false;
    };
  }, [months, end, revision]);
  useEffect(() => {
    if (scroller.current)
      scroller.current.scrollLeft = scroller.current.scrollWidth;
  }, [data]);
  useEffect(() => {
    const container = scroller.current;
    if (!container || !selected) return;
    const reveal = () => {
      const cell = container.querySelector<HTMLElement>(
        `[data-date="${selected}"]`,
      );
      if (!cell) return;
      const bounds = container.getBoundingClientRect(),
        rect = cell.getBoundingClientRect();
      if (rect.left < bounds.left || rect.right > bounds.right)
        container.scrollLeft +=
          rect.left - bounds.left - container.clientWidth / 2 + rect.width / 2;
    };
    reveal();
    const observer = new ResizeObserver(reveal);
    observer.observe(container);
    return () => observer.disconnect();
  }, [selected, data]);
  const day = data?.days.find((d) => d.date === selected);
  const sports = new Map(data?.sports.map((s) => [s.id, s]) || []);
  const index = data?.days.findIndex((d) => d.date === selected) ?? -1;
  const padded: (CalendarDay | null)[] = [];
  if (data) {
    const offset =
      (new Date(data.start + "T12:00:00+08:00").getUTCDay() + 6) % 7;
    padded.push(...Array(offset).fill(null), ...data.days);
    while (padded.length % 7) padded.push(null);
  }
  const weeks = padded.length / 7;
  const monthsLabels = Array.from({ length: weeks }, (_, i) => {
    const week = padded.slice(i * 7, i * 7 + 7);
    const first =
      week.find((d) => d?.date.endsWith("-01")) ||
      (i === 0 ? week.find(Boolean) : null);
    return first ? `${Number(first.date.slice(5, 7))}月` : "";
  });
  function cellBackground(d: CalendarDay) {
    if (mode === "duration") return shade(d.minutes);
    if (!d.sessions.length) return "#eeedf3";
    const totals = new Map<string, number>();
    d.sessions.forEach((s) =>
      totals.set(s.sport, (totals.get(s.sport) || 0) + s.minutes),
    );
    const total = Array.from(totals.values()).reduce((a, b) => a + b, 0);
    let position = 0;
    return `linear-gradient(to bottom,${Array.from(totals)
      .map(([sport, min]) => {
        const from = position;
        position += (min / total) * 100;
        return `${sports.get(sport)?.color || "#819c93"} ${from}% ${position}%`;
      })
      .join(",")})`;
  }
  const lanes: number[] = [];
  const sessions =
    day?.sessions.map((s) => {
      let lane = lanes.findIndex((end) => end <= s.start_minute);
      if (lane < 0) {
        lane = lanes.length;
        lanes.push(0);
      }
      lanes[lane] = s.end_minute;
      return { ...s, lane };
    }) || [];
  return (
    <section
      className="activity-calendar panel"
      aria-labelledby="activity-calendar-title"
    >
      <div className="calendar-heading">
        <div>
          <span className="calendar-eyebrow">YOUR DAYS IN MOTION</span>
          <h2 id="activity-calendar-title">
            <Activity size={18} />
            活动足迹
          </h2>
          <p>每个方格是一天，点开看看那天的运动节奏。</p>
        </div>
        <div className="calendar-controls">
          <div className="calendar-tabs" aria-label="日历配色">
            <button
              className={mode === "type" ? "chosen" : ""}
              onClick={() => setMode("type")}
            >
              活动类型
            </button>
            <button
              className={mode === "duration" ? "chosen" : ""}
              onClick={() => setMode("duration")}
            >
              活动时长
            </button>
          </div>
          <select
            aria-label="活动日历时间范围"
            value={months}
            onChange={(e) => setMonths(Number(e.target.value))}
          >
            <option value={3}>近3个月</option>
            <option value={6}>近6个月</option>
            <option value={12}>近1年</option>
          </select>
        </div>
      </div>
      {error ? (
        <div className="calendar-error" role="alert">
          {error}
          <button onClick={() => setMonths(months === 6 ? 3 : 6)}>重试</button>
        </div>
      ) : !data ? (
        <div className="calendar-loading">
          <LoaderCircle className="spin" size={21} />
          正在加载活动日历
        </div>
      ) : (
        <>
          <div className="calendar-summary">
            <span>
              <b>{data.summary.activities}</b> 次活动
            </span>
            <span>
              <b>{data.summary.active_days}</b> 个活动日
            </span>
            <span>
              <b>{Math.round((data.summary.minutes / 60) * 10) / 10}</b>{" "}
              小时运动
            </span>
            <span className="calendar-window">
              {data.start} — {data.end}
              {busy && <LoaderCircle className="spin" size={12} />}
            </span>
          </div>
          <div className="calendar-chart">
            <div className="weekday-labels" aria-hidden="true">
              {["一", "", "三", "", "五", "", "日"].map((s, i) => (
                <span key={i}>{s}</span>
              ))}
            </div>
            <div className="calendar-scroll" ref={scroller}>
              <div
                className="calendar-matrix"
                style={{ minWidth: weeks > 30 ? "650px" : "330px" }}
              >
                <div
                  className="calendar-months"
                  style={{
                    gridTemplateColumns: `repeat(${weeks},minmax(0,1fr))`,
                  }}
                  aria-hidden="true"
                >
                  {monthsLabels.map((m, i) => (
                    <span key={i}>{m}</span>
                  ))}
                </div>
                <div
                  className="calendar-cells"
                  style={{
                    gridTemplateColumns: `repeat(${weeks},minmax(0,1fr))`,
                  }}
                >
                  {padded.map((d, i) =>
                    d ? (
                      <button
                        key={d.date}
                        data-date={d.date}
                        className={`calendar-cell ${d.date === selected ? "is-selected" : ""} ${!d.recorded ? "no-data" : ""} ${filter && !d.sessions.some((s) => s.sport === filter) ? "dimmed" : ""}`}
                        style={{ background: cellBackground(d) }}
                        onClick={() => setSelected(d.date)}
                        aria-label={`${d.date}，${d.recorded ? (d.sessions.length ? `${d.sessions.length}次活动，${Math.round(d.minutes)}分钟` : "没有活动记录") : "暂无设备记录"}`}
                        aria-pressed={d.date === selected}
                        title={`${d.date} · ${d.sessions.length} 次活动 · ${Math.round(d.minutes)} 分钟${d.recorded ? "" : " · 无设备记录"}`}
                      />
                    ) : (
                      <span key={`empty${i}`} className="calendar-padding" />
                    ),
                  )}
                </div>
              </div>
            </div>
          </div>
          <div className="calendar-key">
            <div className="calendar-legend">
              {data.sports.map((s) => (
                <button
                  key={s.id}
                  aria-pressed={filter === s.id}
                  className={filter === s.id ? "highlighted" : ""}
                  onClick={() => setFilter(filter === s.id ? null : s.id)}
                  title={`高亮${s.label}，${s.count}次`}
                >
                  <i style={{ background: s.color }} />
                  <span>{s.emoji}</span>
                  {s.label}
                  <small>{s.count}</small>
                </button>
              ))}
              {!data.sports.length && <span>这个时段没有已收录的活动</span>}
            </div>
            <div className="calendar-scale">
              {mode === "duration" ? (
                <>
                  <span>少</span>
                  {[0, 10, 30, 60, 120, 180].map((m) => (
                    <i key={m} style={{ background: shade(m) }} />
                  ))}
                  <span>多</span>
                </>
              ) : (
                <>
                  <span className="empty-key" /> 无活动
                  <span className="missing-key" /> 无设备记录
                </>
              )}
            </div>
          </div>
          {filter && (
            <button className="clear-highlight" onClick={() => setFilter(null)}>
              已高亮：{sports.get(filter)?.label} · 清除筛选高亮
            </button>
          )}
          {day && (
            <div className="day-detail">
              <div className="day-heading">
                <h3>
                  <CalendarDays size={15} />
                  {dateName(day.date)}
                  <small>{day.date.slice(0, 4)}</small>
                </h3>
                <div className="day-pager">
                  <button
                    aria-label="前一天"
                    disabled={index <= 0}
                    onClick={() => setSelected(data.days[index - 1].date)}
                  >
                    <ChevronLeft size={15} />
                  </button>
                  <button
                    aria-label="后一天"
                    disabled={index >= data.days.length - 1}
                    onClick={() => setSelected(data.days[index + 1].date)}
                  >
                    <ChevronRight size={15} />
                  </button>
                </div>
              </div>
              <div
                className="timeline"
                style={{ height: Math.max(1, lanes.length) * 20 + 4 }}
                role="img"
                aria-label={`${day.date} 24小时活动时间轴，共${Math.round(day.minutes)}分钟`}
              >
                {[0, 360, 720, 1080, 1440].map((t) => (
                  <span
                    className="timeline-gridline"
                    style={{ left: `${(t / 1440) * 100}%` }}
                    key={t}
                  />
                ))}
                {sessions.map((s, i) => {
                  const sport = sports.get(s.sport);
                  return (
                    <span
                      key={`${s.id}-${i}`}
                      className="timeline-event"
                      style={{
                        left: `${(s.start_minute / 1440) * 100}%`,
                        width: `${Math.max(0.25, ((s.end_minute - s.start_minute) / 1440) * 100)}%`,
                        top: s.lane * 20 + 2,
                        background: sport?.color,
                      }}
                      title={`${sport?.label} · ${clock(s.start_minute)}–${clock(s.end_minute)}`}
                    />
                  );
                })}
                {day.events
                  ?.filter((e) => e.time)
                  .map((e) => (
                    <span
                      className="timeline-context"
                      key={e.id}
                      style={{
                        left: `${((Number(e.time.slice(0, 2)) * 60 + Number(e.time.slice(3))) / 1440) * 100}%`,
                      }}
                      title={`${e.time} · ${e.text}`}
                    />
                  ))}
              </div>
              <div className="timeline-ticks" aria-hidden="true">
                {[0, 360, 720, 1080, 1440].map((t) => (
                  <span key={t}>{clock(t)}</span>
                ))}
              </div>
              <div className="timeline-meta">
                <span>
                  <Clock3 size={12} />
                  已记录 <b>{Math.round(day.minutes)}</b> 分钟 · 占全天{" "}
                  {day.percentage}%
                </span>
                <span>24 小时</span>
              </div>
              {day.sessions.length ? (
                <ul className="day-sessions">
                  {day.sessions.map((s, i) => {
                    const sport = sports.get(s.sport);
                    return (
                      <li key={`${s.id}-${i}`}>
                        <span className="session-emoji">{sport?.emoji}</span>
                        <i style={{ background: sport?.color }} />
                        <div>
                          <strong>{sport?.label}</strong>
                          <span>
                            {s.continues_before ? "前日延续 · " : ""}
                            {clock(s.start_minute)}–{clock(s.end_minute)}
                            {s.continues_after ? " · 延续至次日" : ""} ·{" "}
                            {Math.round(s.minutes)} 分钟
                          </span>
                        </div>
                        <span className="session-strain">
                          Strain {num(s.strain, 1)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="day-empty">
                  {day.recorded
                    ? "这一天没有已同步的运动记录。休息也是节奏的一部分。"
                    : "这一天尚未收录设备数据，不能据此判断是否运动。"}
                </p>
              )}
              {day.events?.length > 0 && (
                <div className="day-context-events">
                  {day.events.map((e) => (
                    <div key={e.id}>
                      <span>⚑ {e.category}</span>
                      <small>{e.time}</small>
                      <p>{e.text}</p>
                    </div>
                  ))}
                </div>
              )}
              <button
                className="calendar-note"
                onClick={() => onNote({ day: day.date, text: day.note })}
              >
                <Plus size={13} />
                {day.note || "补充这一天的生活备注，例如聚会、补觉、晚餐"}
              </button>
            </div>
          )}
          <p className="calendar-footnote">
            北京时间 · 按 WHOOP 活动类型配色 · 多种活动按时长分色 ·
            时长不重复计算重叠区间<span>手机可左右滑动日历</span>
          </p>
        </>
      )}
    </section>
  );
}
