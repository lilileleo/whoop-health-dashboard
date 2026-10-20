import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  CloudDownload,
  Database,
  Download,
  FileText,
  Heart,
  LayoutDashboard,
  Leaf,
  Link2,
  LoaderCircle,
  Moon,
  Plus,
  Printer,
  RefreshCw,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  TrendingUp,
  X,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { request, num, hours, local, time, today } from "./api";
import type { Dashboard, Day, Metric, Status } from "./api";
import ActivityCalendar from "./ActivityCalendar";
import Insights from "./Insights";
import TrainingPlan from "./TrainingPlan";
import RecoverySignals from "./RecoverySignals";

const navs = [
  { id: "overview", name: "健康概览", sub: "OVERVIEW", icon: LayoutDashboard },
  { id: "longterm", name: "长期对照", sub: "LONG TERM", icon: TrendingUp },
  { id: "plans", name: "训练计划", sub: "PLAN", icon: CalendarDays },
  { id: "sleep", name: "睡眠分析", sub: "SLEEP", icon: Moon },
  { id: "recovery", name: "恢复与心率", sub: "RECOVERY", icon: Heart },
  { id: "activity", name: "运动与负荷", sub: "ACTIVITY", icon: Activity },
  { id: "reports", name: "健康报表", sub: "REPORTS", icon: FileText },
  { id: "settings", name: "同步与设置", sub: "SETTINGS", icon: Settings },
];
const chartColors = {
  green: "#4c8b64",
  lime: "#c6dd72",
  purple: "#9181ca",
  blue: "#709ec6",
  gray: "#a4aaa5",
};
const short = (v: string) => v.slice(5).replace("-", "/");
const recoveryColor = (v: number | null) =>
  v == null ? "#e3e8e0" : v >= 67 ? "#72a47c" : v >= 34 ? "#e6c66f" : "#d58375";

function Panel({
  title,
  subtitle,
  children,
  aside,
  className = "",
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  aside?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-head">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}
function Empty({ text = "这个时段暂无有效数据" }: { text?: string }) {
  return (
    <div className="empty">
      <Leaf size={26} />
      <p>{text}</p>
    </div>
  );
}
function Stat({
  title,
  metric,
  unit,
  icon,
  tone = "mint",
  digits = 0,
}: {
  title: string;
  metric: Metric;
  unit: string;
  icon: ReactNode;
  tone?: string;
  digits?: number;
}) {
  return (
    <article className={`stat ${tone}`}>
      <div className="stat-top">
        <span>{title}</span>
        <span className="stat-icon">{icon}</span>
      </div>
      <div className="stat-value">
        {num(metric.value, digits)}
        <small>{unit}</small>
      </div>
      <div className="stat-bottom">
        <span className="delta">
          {metric.delta == null ? (
            "无可比数据"
          ) : (
            <>
              {metric.delta >= 0 ? (
                <ArrowUpRight size={14} />
              ) : (
                <ArrowDownRight size={14} />
              )}{" "}
              {Math.abs(metric.delta).toFixed(digits || 1)}
              <span>较前期</span>
            </>
          )}
        </span>
        <span>{metric.n} 天样本</span>
      </div>
    </article>
  );
}
const axis = {
  axisLine: false,
  tickLine: false,
  tick: { fill: "#8b938c", fontSize: 11 },
};
function Tip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: {
    name?: string;
    value?: number;
    dataKey?: string;
    color?: string;
  }[];
  label?: string | number;
}) {
  return active && payload?.length ? (
    <div className="chart-tip">
      <strong>{label}</strong>
      {payload
        .filter((p) => p.value != null)
        .map((p, i) => (
          <div key={i}>
            <span style={{ color: p.color }}>● {p.name}</span>
            <b>{num(Number(p.value), 1)}</b>
          </div>
        ))}
    </div>
  ) : null;
}

function Trend({
  data,
  metric,
  baseline,
  color,
  unit,
  max,
}: {
  data: Day[];
  metric: string;
  baseline?: string;
  color: string;
  unit: string;
  max?: number;
}) {
  return (
    <div className="chart">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={data}
          margin={{ top: 10, right: 12, left: -20, bottom: 0 }}
        >
          <defs>
            <linearGradient
              id={`gradient-${metric}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor={color} stopOpacity={0.17} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid
            vertical={false}
            stroke="#edf0e9"
            strokeDasharray="3 4"
          />
          <XAxis
            dataKey="date"
            tickFormatter={short}
            minTickGap={35}
            {...axis}
          />
          <YAxis
            {...axis}
            domain={max ? [0, max] : ["auto", "auto"]}
            unit={unit}
          />
          <Tooltip content={<Tip />} />
          <Area
            isAnimationActive={false}
            type="monotone"
            dataKey={metric}
            name={
              metric === "recovery"
                ? "恢复分"
                : metric === "hrv"
                  ? "HRV"
                  : "静息心率"
            }
            stroke={color}
            strokeWidth={2.5}
            fill={`url(#gradient-${metric})`}
            connectNulls={false}
            dot={false}
            activeDot={{ r: 5, strokeWidth: 3, stroke: "#fff" }}
          />
          {baseline && (
            <Line
              isAnimationActive={false}
              type="monotone"
              dataKey={baseline}
              name="前28日基线"
              stroke="#a9b49c"
              strokeDasharray="5 5"
              dot={false}
              connectNulls={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState("overview"),
    [data, setData] = useState<Dashboard | null>(null),
    [status, setStatus] = useState<Status | null>(null);
  const [period, setPeriod] = useState("30"),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [range, setRange] = useState("days=30");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [syncing, setSyncing] = useState(false),
    [note, setNote] = useState<{ day: string; text: string } | null>(null),
    [saving, setSaving] = useState(false),
    [busy, setBusy] = useState(false);
  const [calendarRevision, setCalendarRevision] = useState(0);
  const [trainingDay, setTrainingDay] = useState(today());
  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const [d, s] = await Promise.all([
          request<Dashboard>("/api/dashboard?" + range),
          request<Status>("/api/status"),
        ]);
        setData(d);
        setStatus(s);
        setSyncing(s.running);
        setError("");
        setStart(d.range.start);
        setEnd(d.range.end);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setLoading(false);
      }
    },
    [range],
  );
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 5000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!syncing) return;
    const timer = setInterval(async () => {
      try {
        const s = await request<Status>("/api/status");
        setStatus(s);
        if (!s.running) {
          setSyncing(false);
          load(true);
          setToast(s.history[0]?.message || "同步完成");
        }
      } catch (e) {
        setError((e as Error).message);
        setSyncing(false);
      }
    }, 1800);
    return () => clearInterval(timer);
  }, [syncing, load]);
  const mutate = async (url: string, body?: unknown, method = "POST") =>
    request<any>(url, method, body, status?.local_token);
  async function sync(days = 14) {
    setSyncing(true);
    try {
      await mutate("/api/sync", { days });
      setToast("开始同步，历史数据仍可查看");
    } catch (e) {
      setSyncing(false);
      setToast((e as Error).message);
    }
  }
  async function connect() {
    setBusy(true);
    try {
      const result = await mutate("/api/auth/start");
      window.location.assign(result.url);
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function importLocal() {
    setBusy(true);
    try {
      await mutate("/api/import");
      await load(true);
      setToast("本地归档已重新导入");
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function choosePeriod(value: string) {
    setPeriod(value);
    if (value !== "custom") setRange(`days=${value}`);
  }
  async function saveNote() {
    if (!note) return;
    setSaving(true);
    try {
      await mutate("/api/notes/" + note.day, { text: note.text }, "PUT");
      setCalendarRevision((r) => r + 1);
      setNote(null);
      load(true);
      setToast("备注已保存");
    } catch (e) {
      setToast((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  const active = navs.find((n) => n.id === page)!;
  const stale = status?.last_fetch
    ? Math.floor(
        (Date.now() - new Date(status.last_fetch).getTime()) / 86400000,
      )
    : null;
  const go = (id: string) => {
    setPage(id);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const exportUrl = (kind: string) => `/api/export/${kind}?${range}`;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            go("overview");
          }}
        >
          <span className="brand-mark">
            <Activity size={24} />
          </span>
          <div>
            WHOOP<span>个人健康空间</span>
          </div>
        </a>
        <div className="sidebar-label">你的健康，一目了然</div>
        <nav aria-label="主导航">
          {navs.map((n) => (
            <button
              aria-label={n.name}
              title={n.name}
              key={n.id}
              onClick={() => go(n.id)}
              className={page === n.id ? "nav-item active" : "nav-item"}
              aria-current={page === n.id ? "page" : undefined}
            >
              <n.icon size={19} />
              <span>{n.name}</span>
              {page === n.id && <span className="nav-dot" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div className="plant-art">
            <Leaf size={43} />
            <span />
            <span />
          </div>
          <h3>健康，从了解自己开始</h3>
          <p>
            关注长期趋势，
            <br />
            也听听身体今天的声音。
          </p>
          <button onClick={() => go("reports")}>
            查看我的报表 <ArrowRight size={14} />
          </button>
        </div>
        <div className="local-badge">
          <ShieldCheck size={17} />
          <span>
            {status?.server_mode
              ? "私有服务 · 数据由你掌握"
              : "本地运行 · 数据由你掌握"}
            <small>
              {status?.server_mode ? "存储于你的服务器" : "仅在此设备保存"}
            </small>
          </span>
        </div>
        <div className="profile">
          <span className="avatar">我</span>
          <div>
            我的健康档案<small>个人工作空间</small>
          </div>
          <span className="online-dot" />
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="breadcrumb">
            个人空间 <ChevronRight size={13} /> <span>{active.name}</span>
          </div>
          <div className="topbar-right">
            <span className="local-pill">
              <span /> {status?.auth_mode === "tailscale" ? "TAILSCALE ONLY" : status?.server_mode ? "PRIVATE SERVER" : "LOCAL ONLY"}
            </span>
            <span className="today">
              <CalendarDays size={14} />
              {today()}
            </span>
          </div>
        </header>
        <div className="main-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">YOUR HEALTH, IN PERSPECTIVE</div>
              <h1>
                {page === "overview" ? "让每一天，恢复得更好" : active.name}
                <span className="heading-leaf">
                  <Leaf size={23} />
                </span>
              </h1>
              <p>
                {page === "overview"
                  ? "把睡眠、恢复与运动连起来，读懂身体的节奏。"
                  : page === "settings"
                    ? "连接 WHOOP、同步数据，管理你的个人健康档案。"
                    : "从个人数据出发，观察变化，找到自己的节奏。"}
              </p>
            </div>
            <button
              className="button primary"
              onClick={() => sync()}
              disabled={syncing || !status}
            >
              <RefreshCw size={16} className={syncing ? "spin" : ""} />
              {syncing ? "正在同步" : "同步 WHOOP"}
            </button>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              {error}
              <button onClick={() => load()}>重新加载</button>
            </div>
          )}
          {status?.insecure_http && status.auth_mode !== "tailscale" && (
            <div className="error-banner" role="alert">
              HTTP 临时测试：登录密码和健康数据未经加密，请仅短期使用，并尽快升级 HTTPS。网页重新授权已禁用，已有有效令牌仍可同步。
            </div>
          )}
          {status?.auth_mode === "tailscale" && (
            <p className="help-text" role="status">
              Tailscale 专用免登录：允许访问本服务的设备可直接查看和修改数据，请仅授权可信设备。服务器到 WHOOP 仍使用 HTTPS；当前 HTTP 页面不提供重新授权。
            </p>
          )}
          {status && (
            <div
              className={`freshness ${stale != null && stale >= 2 ? "outdated" : ""}`}
            >
              <div>
                <span className="status-dot" />
                {syncing
                  ? "WHOOP 数据同步中"
                  : stale != null && stale >= 2
                    ? `数据已 ${stale} 天未更新`
                    : "本地数据已就绪"}
                <span className="separator">·</span>
                <span>最近同步 {local(status.last_fetch)}</span>
              </div>
              <button onClick={() => go("settings")}>
                同步详情 <ChevronRight size={13} />
              </button>
            </div>
          )}
          {!["settings", "longterm", "plans"].includes(page) && (
            <div className="rangebar">
              <div className="segmented">
                {[
                  ["7", "近7天"],
                  ["30", "近30天"],
                  ["90", "近90天"],
                  ["custom", "自定义"],
                ].map(([v, l]) => (
                  <button
                    className={period === v ? "selected" : ""}
                    key={v}
                    onClick={() => choosePeriod(v)}
                  >
                    {l}
                  </button>
                ))}
              </div>
              {period === "custom" ? (
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setRange(`start=${start}&end=${end}`);
                  }}
                  className="custom-range"
                >
                  <input
                    type="date"
                    aria-label="开始日期"
                    value={start}
                    onChange={(e) => setStart(e.target.value)}
                    required
                  />
                  <span>—</span>
                  <input
                    type="date"
                    aria-label="结束日期"
                    value={end}
                    onChange={(e) => setEnd(e.target.value)}
                    required
                  />
                  <button className="button small" type="submit">
                    应用
                  </button>
                </form>
              ) : (
                <span className="range-label">
                  <CalendarDays size={14} />
                  {data?.range.start} — {data?.range.end}
                  <span className="range-hint">截至最新记录</span>
                </span>
              )}
            </div>
          )}
          {loading && !data ? (
            <div className="loading">
              <LoaderCircle className="spin" size={27} />
              <p>正在整理你的健康数据…</p>
            </div>
          ) : (
            data && (
              <div className={loading ? "content-loading" : ""}>
                {page === "overview" && (
                  <>
                    <ActivityCalendar
                      end={data.available.end}
                      revision={`${status?.last_fetch}-${calendarRevision}`}
                      onNote={setNote}
                    />
                    <div className="overview-grid">
                      <section className="hero">
                        <div className="hero-copy">
                          <span className="hero-tag">
                            <Sun size={14} /> BODY & BALANCE
                          </span>
                          <h2>
                            认识身体的变化，
                            <br />
                            找到适合你的节奏。
                          </h2>
                          <p>
                            本时段收录 {data.coverage} 天健康记录。
                            <br />
                            用持续的观察，让每一次休息更有意义。
                          </p>
                          <button onClick={() => go("recovery")}>
                            探索恢复趋势 <ArrowRight size={15} />
                          </button>
                        </div>
                        <div className="hero-visual">
                          <div className="orbit orbit-one" />
                          <div className="orbit orbit-two" />
                          <div className="recovery-orb">
                            <span>时段平均恢复</span>
                            <strong>{num(data.summary.recovery.value)}</strong>
                            <small>{data.summary.recovery.n} 天有效样本</small>
                          </div>
                          <span className="orbit-point point-one" />
                          <span className="orbit-point point-two" />
                        </div>
                        <span className="hero-foot">
                          SMALL STEPS. BETTER DAYS.
                        </span>
                      </section>
                      <section className="snapshot">
                        <div className="panel-head">
                          <h2>最近一天</h2>
                          <span>{data.latest?.date || "暂无"}</span>
                        </div>
                        {data.latest ? (
                          <>
                            <div className="snapshot-score">
                              <span
                                className="score-ring"
                                style={{
                                  borderColor: recoveryColor(
                                    data.latest.recovery,
                                  ),
                                }}
                              >
                                {num(data.latest.recovery)}
                              </span>
                              <div>
                                <h3>
                                  恢复状态
                                  {data.latest.calibrating ? " · 校准中" : ""}
                                </h3>
                                <p>
                                  {data.latest.recovery == null
                                    ? "暂无恢复读数"
                                    : data.latest.recovery >= 67
                                      ? "绿色区间"
                                      : data.latest.recovery >= 34
                                        ? "黄色区间"
                                        : "红色区间"}
                                  <span
                                    className="mini-dot"
                                    style={{
                                      background: recoveryColor(
                                        data.latest.recovery,
                                      ),
                                    }}
                                  />
                                </p>
                              </div>
                            </div>
                            <div className="snapshot-values">
                              <div>
                                <Moon size={15} />
                                <span>主睡眠</span>
                                <b>{hours(data.latest.sleep)}</b>
                              </div>
                              <div>
                                <Heart size={15} />
                                <span>HRV</span>
                                <b>
                                  {num(data.latest.hrv, 1)} <small>ms</small>
                                </b>
                              </div>
                              <div>
                                <Activity size={15} />
                                <span>周期 Strain</span>
                                <b>{num(data.latest.strain, 1)}</b>
                              </div>
                            </div>
                            <button
                              className="text-button"
                              onClick={() =>
                                setNote({
                                  day: data.latest!.date,
                                  text:
                                    data.daily.find(
                                      (d) => d.date === data.latest?.date,
                                    )?.note || "",
                                })
                              }
                            >
                              <Plus size={14} />
                              记录这一天的感受
                            </button>
                          </>
                        ) : (
                          <Empty />
                        )}
                      </section>
                    </div>
                    <div className="stats">
                      <Stat
                        title="平均恢复"
                        metric={data.summary.recovery}
                        unit="/ 100"
                        icon={<Heart size={18} />}
                      />
                      <Stat
                        title="平均主睡眠"
                        metric={data.summary.sleep}
                        unit="小时"
                        digits={1}
                        tone="purple"
                        icon={<Moon size={18} />}
                      />
                      <Stat
                        title="平均 HRV"
                        metric={data.summary.hrv}
                        unit="ms"
                        digits={1}
                        tone="sand"
                        icon={<Activity size={18} />}
                      />
                      <Stat
                        title="平均周期 Strain"
                        metric={data.summary.strain}
                        unit="/ 21"
                        digits={1}
                        tone="blue"
                        icon={<TrendingUp size={18} />}
                      />
                    </div>
                    <div className="two-columns">
                      <Panel
                        title="恢复的节奏"
                        subtitle="每日恢复分 · 留白表示未收录"
                        aside={<span className="legend-dot green">恢复分</span>}
                      >
                        <Trend
                          data={data.daily}
                          metric="recovery"
                          color={chartColors.green}
                          unit=""
                          max={100}
                        />
                      </Panel>
                      <SleepChart data={data} />
                    </div>
                    <div className="section-title">
                      <div>
                        <Sparkles size={18} />
                        <h2>数据里的小发现</h2>
                      </div>
                      <span>描述性观察 · 非医疗诊断</span>
                    </div>
                    <div className="insights">
                      {data.insights.map((i, n) => (
                        <article className={`insight ${i.tone}`} key={i.title}>
                          <span className="insight-number">0{n + 1}</span>
                          <h3>{i.title}</h3>
                          <p>{i.text}</p>
                        </article>
                      ))}
                    </div>
                    <DailyTable data={data} onNote={setNote} compact />
                  </>
                )}
                {page === "longterm" && (
                  <Insights
                    token={status?.local_token}
                    end={data.available.end}
                    onSaved={() => load(true)}
                    revision={status?.last_fetch || ""}
                    onOpenWeek={(day) => {
                      setTrainingDay(day);
                      go("plans");
                    }}
                  />
                )}
                {page === "plans" && (
                  <TrainingPlan
                    token={status?.local_token}
                    onSaved={() => load(true)}
                    revision={status?.last_fetch || ""}
                    initialDay={trainingDay}
                  />
                )}
                {page === "sleep" && (
                  <>
                    <div className="stats">
                      <Stat
                        title="主睡眠时长"
                        metric={data.summary.sleep}
                        unit="小时"
                        digits={1}
                        tone="purple"
                        icon={<Moon size={18} />}
                      />
                      <Stat
                        title="全天睡眠"
                        metric={data.summary.total_sleep}
                        unit="小时"
                        digits={1}
                        icon={<Sun size={18} />}
                      />
                      <Stat
                        title="睡眠效率"
                        metric={data.summary.efficiency}
                        unit="%"
                        tone="sand"
                        icon={<CheckCircle2 size={18} />}
                      />
                      <Stat
                        title="睡眠一致性"
                        metric={data.summary.consistency}
                        unit="%"
                        tone="blue"
                        icon={<CalendarDays size={18} />}
                      />
                    </div>
                    <div className="two-columns">
                      <SleepChart data={data} />
                      <Panel
                        title="作息一致性"
                        subtitle="WHOOP 原始评分，补觉与作息变化需结合实际"
                      >
                        <div className="chart">
                          <ResponsiveContainer width="100%" height="100%">
                            <LineChart
                              data={data.daily}
                              margin={{ left: -20, right: 12 }}
                            >
                              <CartesianGrid
                                vertical={false}
                                stroke="#edf0e9"
                                strokeDasharray="3 4"
                              />
                              <XAxis
                                dataKey="date"
                                tickFormatter={short}
                                {...axis}
                              />
                              <YAxis domain={[0, 100]} {...axis} />
                              <Tooltip content={<Tip />} />
                              <Line
                                isAnimationActive={false}
                                dataKey="consistency"
                                name="一致性 %"
                                stroke={chartColors.purple}
                                dot={false}
                                strokeWidth={2}
                              />
                              <Line
                                isAnimationActive={false}
                                dataKey="efficiency"
                                name="效率 %"
                                stroke={chartColors.green}
                                dot={false}
                                strokeWidth={2}
                              />
                              <Legend
                                iconType="circle"
                                wrapperStyle={{ fontSize: 11 }}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </Panel>
                    </div>
                    <Panel
                      title="每一段睡眠"
                      subtitle="按睡眠结束日期归日，Nap 保留原始分类；彩条为睡眠阶段估计值"
                      aside={
                        <div className="stage-legend">
                          <span>浅睡</span>
                          <span>深睡</span>
                          <span>REM</span>
                          <span>清醒</span>
                        </div>
                      }
                    >
                      {data.sleeps.length ? (
                        <div className="sleep-list">
                          {data.sleeps.map((s, i) => (
                            <div className="sleep-row" key={s.id || i}>
                              <div className="sleep-date">
                                <strong>{s.date}</strong>
                                <small>
                                  {time(s.start)} — {time(s.end)}
                                </small>
                              </div>
                              <span className={`tag ${s.nap ? "nap" : "main"}`}>
                                {s.nap ? "Nap / 补觉" : "主睡眠"}
                              </span>
                              <div className="stage-bar">
                                {Object.entries(s.stages).map(([key, v]) => (
                                  <span
                                    className={key}
                                    key={key}
                                    style={{ flex: v }}
                                    title={`${key}: ${hours(v)}`}
                                  />
                                ))}
                              </div>
                              <b>{hours(s.hours)}</b>
                              <span className="muted">
                                效率 {num(s.efficiency)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Empty />
                      )}
                    </Panel>
                    <Quality data={data} />
                  </>
                )}
                {page === "recovery" && (
                  <>
                    <RecoverySignals daily={data.daily} />
                    <div className="stats">
                      <Stat
                        title="平均恢复"
                        metric={data.summary.recovery}
                        unit="/ 100"
                        icon={<Heart size={18} />}
                      />
                      <Stat
                        title="HRV · RMSSD"
                        metric={data.summary.hrv}
                        unit="ms"
                        digits={1}
                        tone="purple"
                        icon={<Activity size={18} />}
                      />
                      <Stat
                        title="静息心率"
                        metric={data.summary.rhr}
                        unit="bpm"
                        digits={1}
                        tone="sand"
                        icon={<Heart size={18} />}
                      />
                      <Stat
                        title="夜间 SpO₂"
                        metric={data.summary.spo2}
                        unit="%"
                        digits={1}
                        tone="blue"
                        icon={<Leaf size={18} />}
                      />
                    </div>
                    <Panel
                      title="每日恢复"
                      subtitle="绿色 67–100 · 黄色 34–66 · 红色 0–33；校准期记录仅作观察"
                    >
                      <div className="chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={data.daily}
                            margin={{ left: -20, right: 12 }}
                          >
                            <CartesianGrid vertical={false} stroke="#edf0e9" />
                            <XAxis
                              dataKey="date"
                              tickFormatter={short}
                              minTickGap={30}
                              {...axis}
                            />
                            <YAxis domain={[0, 100]} {...axis} />
                            <Tooltip content={<Tip />} />
                            <Bar
                              isAnimationActive={false}
                              dataKey="recovery"
                              name="恢复分"
                              radius={[4, 4, 0, 0]}
                              maxBarSize={26}
                            >
                              {data.daily.map((d) => (
                                <Cell
                                  key={d.date}
                                  fill={recoveryColor(d.recovery)}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </Panel>
                    <div className="two-columns">
                      <Panel
                        title="HRV 与个人基线"
                        subtitle="虚线为此前 28 天均值，至少 7 个非校准样本"
                      >
                        <Trend
                          data={data.daily}
                          metric="hrv"
                          baseline="hrv_baseline"
                          color={chartColors.purple}
                          unit=""
                        />
                      </Panel>
                      <Panel
                        title="静息心率与个人基线"
                        subtitle="与自己的变化比较，单日高低不代表好坏"
                      >
                        <Trend
                          data={data.daily}
                          metric="rhr"
                          baseline="rhr_baseline"
                          color={chartColors.green}
                          unit=""
                        />
                      </Panel>
                    </div>
                    <Panel
                      title="睡眠与恢复的关联"
                      subtitle="同一天主睡眠时长与恢复分的 Pearson 相关系数"
                    >
                      <div className="correlation">
                        <strong>
                          {data.correlation.r == null
                            ? "样本不足"
                            : num(data.correlation.r, 2)}
                        </strong>
                        <p>
                          有效配对 {data.correlation.n} 天，至少需要 10
                          天。恢复评分本身包含睡眠因素，相关性不代表因果，也不能用来推断某种生活习惯的效果。
                        </p>
                      </div>
                    </Panel>
                    <DailyTable data={data} onNote={setNote} />
                  </>
                )}
                {page === "activity" && (
                  <>
                    <ActivityCalendar
                      end={data.available.end}
                      revision={`${status?.last_fetch}-${calendarRevision}`}
                      onNote={setNote}
                    />
                    <div className="activity-kpis">
                      <div>
                        <Activity />
                        <b>{data.workouts.length}</b>
                        <span>活动记录</span>
                      </div>
                      <div>
                        <TrendingUp />
                        <b>{num(data.summary.strain.value, 1)}</b>
                        <span>平均周期 Strain</span>
                      </div>
                      <div>
                        <CalendarDays />
                        <b>{data.daily.filter((d) => d.workouts > 0).length}</b>
                        <span>有活动的日期</span>
                      </div>
                      <div>
                        <Heart />
                        <b>
                          {Math.round(
                            data.workouts.reduce(
                              (n, w) => n + (w.minutes || 0),
                              0,
                            ),
                          )}
                        </b>
                        <span>活动分钟</span>
                      </div>
                    </div>
                    <Panel
                      title="负荷与恢复"
                      subtitle="周期 Strain 使用右轴；活动分数不相加"
                    >
                      <div className="chart tall">
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart
                            data={data.daily}
                            margin={{ left: -20, right: -10 }}
                          >
                            <CartesianGrid vertical={false} stroke="#edf0e9" />
                            <XAxis
                              dataKey="date"
                              tickFormatter={short}
                              minTickGap={30}
                              {...axis}
                            />
                            <YAxis domain={[0, 100]} {...axis} />
                            <YAxis
                              yAxisId="strain"
                              orientation="right"
                              domain={[0, 21]}
                              {...axis}
                            />
                            <Tooltip content={<Tip />} />
                            <Bar
                              isAnimationActive={false}
                              dataKey="recovery"
                              name="恢复分 /100"
                              fill="#dbe8d7"
                              radius={[3, 3, 0, 0]}
                              maxBarSize={24}
                            />
                            <Line
                              isAnimationActive={false}
                              dataKey="strain"
                              name="Strain /21"
                              yAxisId="strain"
                              stroke={chartColors.purple}
                              strokeWidth={2.5}
                              dot={false}
                            />
                            <Legend
                              iconType="circle"
                              wrapperStyle={{ fontSize: 11 }}
                            />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </div>
                    </Panel>
                    <Panel
                      title="活动明细"
                      subtitle="心率区间显示 WHOOP 原始分区，0–5 级由左至右"
                    >
                      {data.workouts.length ? (
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>日期 / 时间</th>
                                <th>活动</th>
                                <th>时长</th>
                                <th>Strain</th>
                                <th>平均 / 最高心率</th>
                                <th>心率区间分布</th>
                              </tr>
                            </thead>
                            <tbody>
                              {data.workouts.map((w, i) => (
                                <tr key={w.id || i}>
                                  <td>{local(w.start)}</td>
                                  <td>
                                    <span className="activity-name">
                                      <Activity size={14} />
                                      {w.name === "activity"
                                        ? "日常活动"
                                        : w.name}
                                    </span>
                                    {!w.scored && (
                                      <span className="tag nap">待评分</span>
                                    )}
                                  </td>
                                  <td>{num(w.minutes)} 分钟</td>
                                  <td>
                                    <b>{num(w.strain, 1)}</b>
                                  </td>
                                  <td>
                                    {num(w.average_hr)} / {num(w.max_hr)}{" "}
                                    <small>bpm</small>
                                  </td>
                                  <td>
                                    <div className="zones">
                                      {w.zones.map((z, n) => (
                                        <span
                                          key={n}
                                          style={{
                                            flex: z,
                                            background: [
                                              "#d5ded4",
                                              "#acc4a5",
                                              "#7ca47c",
                                              "#d9c36b",
                                              "#d5a06c",
                                              "#c87970",
                                            ][n],
                                          }}
                                          title={`Zone ${n}: ${z.toFixed(1)} 分钟`}
                                        />
                                      ))}
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <Empty />
                      )}
                    </Panel>
                  </>
                )}
                {page === "reports" && (
                  <>
                    <section className="report-banner">
                      <span className="document-icon">
                        <FileText size={34} />
                      </span>
                      <div>
                        <div className="eyebrow">
                          YOUR PERSONAL HEALTH REVIEW
                        </div>
                        <h2>把变化留在报表里</h2>
                        <p>选择时段，查看统计与环比，保存属于你的健康记录。</p>
                      </div>
                      <button
                        className="button primary"
                        onClick={() => window.print()}
                      >
                        <Printer size={16} />
                        打印 / 保存 PDF
                      </button>
                    </section>
                    <div className="report-actions">
                      {[
                        { label: "日报", days: 1 },
                        { label: "近7天", days: 7 },
                        { label: "近30天", days: 30 },
                        { label: "近90天", days: 90 },
                      ].map((p) => (
                        <button
                          className="button"
                          key={p.label}
                          onClick={() => choosePeriod(String(p.days))}
                        >
                          <CalendarDays size={15} />
                          {p.label}
                        </button>
                      ))}
                      <span />
                      <a className="button" href={exportUrl("csv")}>
                        <Download size={15} />
                        CSV 数据
                      </a>
                      <a className="button" href={exportUrl("markdown")}>
                        <FileText size={15} />
                        Markdown 报告
                      </a>
                      <a className="button" href={exportUrl("json")}>
                        <Download size={15} />
                        JSON
                      </a>
                    </div>
                    <Panel
                      title="健康分析报告"
                      subtitle={`${data.range.start} — ${data.range.end} · ${data.coverage}/${data.range.days} 天有记录`}
                      aside={
                        <span className="report-label">
                          LOCAL HEALTH REPORT
                        </span>
                      }
                    >
                      <div className="report-intro">
                        <h3>与上一等长时段相比</h3>
                        <p>
                          对比 {data.range.previous_start} —{" "}
                          {data.range.previous_end}
                          。样本数不同可能影响均值，指标变化不单独代表健康改善或恶化。
                        </p>
                      </div>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>指标</th>
                              <th>本期平均</th>
                              <th>有效样本</th>
                              <th>前期平均</th>
                              <th>变化</th>
                            </tr>
                          </thead>
                          <tbody>
                            {[
                              ["recovery", "恢复分", "分"],
                              ["sleep", "主睡眠", "小时"],
                              ["total_sleep", "全天睡眠", "小时"],
                              ["hrv", "HRV", "ms"],
                              ["rhr", "静息心率", "bpm"],
                              ["consistency", "睡眠一致性", "%"],
                              ["strain", "周期 Strain", ""],
                            ].map(([k, label, unit]) => {
                              const m = data.summary[k];
                              return (
                                <tr key={k}>
                                  <td>{label}</td>
                                  <td>
                                    <b>{num(m.value, 1)}</b> {unit}
                                  </td>
                                  <td>
                                    {m.n} 天 / 前期 {m.previous_n} 天
                                  </td>
                                  <td>
                                    {num(m.previous, 1)} {unit}
                                  </td>
                                  <td>
                                    {m.delta == null
                                      ? "—"
                                      : `${m.delta >= 0 ? "+" : ""}${num(m.delta, 1)} ${unit}`}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                      <div className="report-observations">
                        {data.insights.map((i) => (
                          <div key={i.title}>
                            <h3>{i.title}</h3>
                            <p>{i.text}</p>
                          </div>
                        ))}
                      </div>
                    </Panel>
                    <Quality data={data} />
                    <DailyTable data={data} onNote={setNote} />
                    {!!data.events?.length && (
                      <Panel
                        title="时段内的生活事件"
                        subtitle="与同期指标对照，保留真实生活背景"
                      >
                        <div className="context-weeks">
                          {data.events.map((e) => (
                            <div className="context-event" key={e.id}>
                              <span className="event-tag">{e.category}</span>
                              <small>
                                {e.day} {e.time}
                              </small>
                              <p>{e.text}</p>
                            </div>
                          ))}
                        </div>
                      </Panel>
                    )}
                    <Panel title="统计口径" subtitle="让每一个数字都能追溯">
                      {data.definitions.map((d) => (
                        <p className="definition" key={d}>
                          <Check size={14} />
                          {d}
                        </p>
                      ))}
                    </Panel>
                  </>
                )}
                {page === "settings" && status && (
                  <>
                    <div className="settings-grid">
                      <Panel
                        title="WHOOP 连接"
                        subtitle={
                          status.server_mode
                            ? "授权凭据保存在你的服务器，由后端完成刷新"
                            : "授权凭据保存在本机，由后端完成刷新"
                        }
                        aside={<Link2 size={20} />}
                      >
                        <div className="connection-state">
                          <span
                            className={
                              status.authorized
                                ? "connected-icon"
                                : "disconnected-icon"
                            }
                          >
                            <CheckCircle2 size={26} />
                          </span>
                          <div>
                            <h3>
                              {status.authorized
                                ? "已保存 WHOOP 授权"
                                : "尚未连接 WHOOP"}
                            </h3>
                            <p>
                              {status.configured
                                ? "应用配置已就绪"
                                : "请先在 .env 配置应用凭据"}
                            </p>
                          </div>
                        </div>
                        <button
                          className="button"
                          disabled={busy || syncing || status.insecure_http}
                          onClick={connect}
                        >
                          {busy ? (
                            <LoaderCircle className="spin" size={15} />
                          ) : (
                            <Link2 size={15} />
                          )}{" "}
                          {status.authorized ? "重新授权" : "连接 WHOOP"}
                        </button>
                        <p className="help-text">
                          {status.insecure_http
                            ? "HTTP 临时模式不提供网页授权。已有有效令牌可继续同步；如令牌失效，请升级 HTTPS 后重新连接。"
                            : "已保存授权不代表令牌始终有效；同步时会验证，失效后可重新连接。OAuth 回调为当前服务的 /callback。"}
                        </p>
                      </Panel>
                      <Panel
                        title="个人数据档案"
                        subtitle="SQLite 数据库自动创建，无需单独安装"
                        aside={<Database size={20} />}
                      >
                        <div className="count-grid">
                          {[
                            ["recovery", "恢复"],
                            ["sleep", "睡眠"],
                            ["cycle", "周期"],
                            ["workout", "活动"],
                          ].map(([k, l]) => (
                            <div key={k}>
                              <strong>{status.counts[k] || 0}</strong>
                              <span>{l}记录</span>
                            </div>
                          ))}
                        </div>
                        <button
                          className="button"
                          disabled={busy || syncing}
                          onClick={importLocal}
                        >
                          <RefreshCw size={15} />
                          重新导入本地归档
                        </button>
                        <p className="help-text">
                          原始 JSON
                          继续保留。数据库文件：data/whoop.sqlite；备注和同步日志也存储于此。
                        </p>
                      </Panel>
                    </div>
                    <Panel
                      title="数据同步"
                      subtitle="同步在后台运行；关闭页面后，服务仍会继续处理"
                    >
                      <div className="sync-options">
                        {[14, 90, 365].map((n) => (
                          <button
                            key={n}
                            className="button"
                            disabled={syncing}
                            onClick={() => sync(n)}
                          >
                            <CloudDownload size={16} />
                            {n === 14 ? "同步最近14天" : `回填最近${n}天`}
                          </button>
                        ))}
                      </div>
                      <p className="help-text">
                        每次同步重新拉取所选时间段，按记录 ID 更新，可覆盖 WHOOP
                        的延迟评分和修改。最新记录之外的历史删除暂不自动清理。
                      </p>
                      <p className="help-text">
                        {status.sync_interval_minutes
                          ? `已启用每 ${status.sync_interval_minutes} 分钟自动同步；服务启动一个间隔后首次运行。`
                          : "当前使用手动同步，自动同步未启用。"}
                        时区：Asia/Shanghai。
                      </p>
                    </Panel>
                    <Panel title="同步记录" subtitle="失败不会清空已有数据">
                      {status.history.length ? (
                        <div className="sync-history">
                          {status.history.map((h) => (
                            <div key={h.id}>
                              <span className={`sync-state ${h.state}`}>
                                {h.state === "success" ? (
                                  <CheckCircle2 size={17} />
                                ) : h.state === "running" ? (
                                  <LoaderCircle className="spin" size={17} />
                                ) : (
                                  <CircleHelp size={17} />
                                )}
                              </span>
                              <div>
                                <strong>{h.message}</strong>
                                <p>
                                  {local(h.started_at)}
                                  {h.finished_at
                                    ? ` → ${local(h.finished_at)}`
                                    : ""}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <Empty text="尚未从网页发起同步，可先浏览已导入的数据" />
                      )}
                    </Panel>
                    {status.import_errors.length > 0 && (
                      <div className="error-banner">
                        导入提示：{status.import_errors.join("；")}
                      </div>
                    )}
                    <Panel
                      title="使用与备份"
                      subtitle={
                        status.auth_mode === "tailscale"
                          ? "数据保存在你的服务器，通过获准的 Tailscale 设备直接访问"
                          : status.server_mode
                          ? "数据保存在你的服务器，登录后访问"
                          : "数据在本机保存，前端通过本地服务读取"
                      }
                    >
                      <p className="definition">
                        <ShieldCheck size={16} />
                        {status.auth_mode === "tailscale"
                          ? "当前使用 Tailscale 专用免登录，保留请求来源与操作校验；请保持仅绑定 Tailscale 地址，不对公网开放。"
                          : status.server_mode
                          ? "当前启用服务器模式，访问需要看板密码。凭据不会发送给前端。"
                          : "服务绑定 127.0.0.1，仅本机可访问。凭据不会发送给前端。"}
                      </p>
                      <p className="definition">
                        <Database size={16} />
                        备份前先停止服务，再复制 data/
                        目录；请妥善保管其中的令牌和健康数据。
                      </p>
                      <p className="definition">
                        <FileText size={16} />
                        需要分享时可在报表中心导出指定时段的报告。
                      </p>
                    </Panel>
                  </>
                )}
              </div>
            )
          )}
          <footer>
            <span className="footer-brand">
              <Activity size={14} /> WHOOP <span>PERSONAL INSIGHTS</span>
            </span>
            <span>
              倾听身体，保持自己的节奏。<span className="footer-sep">·</span>
              仅供个人趋势观察
            </span>
          </footer>
        </div>
      </main>
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          {toast}
          <button aria-label="关闭提示" onClick={() => setToast("")}>
            <X size={15} />
          </button>
        </div>
      )}
      {note && (
        <div
          className="modal-backdrop"
          onClick={() => !saving && setNote(null)}
        >
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="note-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="panel-head">
              <div>
                <h2 id="note-title">记录这一天 · {note.day}</h2>
                <p>补充生活背景，让数据更有意义</p>
              </div>
              <button
                className="icon-button"
                aria-label="关闭备注"
                onClick={() => setNote(null)}
              >
                <X size={18} />
              </button>
            </div>
            <div className="note-presets">
              {["聚会", "饮酒", "出差", "补觉", "生病", "高强度训练"].map(
                (t) => (
                  <button
                    key={t}
                    onClick={() =>
                      setNote({
                        ...note,
                        text: note.text ? note.text + " · " + t : t,
                      })
                    }
                  >
                    {t}
                  </button>
                ),
              )}
            </div>
            <textarea
              autoFocus
              value={note.text}
              onChange={(e) => setNote({ ...note, text: e.target.value })}
              placeholder="例如：记录作息变化、午休或训练调整…"
              maxLength={2000}
            />
            <div className="modal-bottom">
              <span>{note.text.length} / 2000 · 清空后保存可删除备注</span>
              <button
                className="button primary"
                disabled={saving}
                onClick={saveNote}
              >
                {saving ? "保存中" : "保存备注"}
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function SleepChart({ data }: { data: Dashboard }) {
  return (
    <Panel
      title="睡眠，每一段都算数"
      subtitle="主睡眠与 Nap 分别展示 · 单位：小时"
      aside={<Moon size={17} className="muted" />}
    >
      <div className="chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data.daily}
            margin={{ top: 10, left: -20, right: 12 }}
          >
            <CartesianGrid
              vertical={false}
              stroke="#edf0e9"
              strokeDasharray="3 4"
            />
            <XAxis
              dataKey="date"
              tickFormatter={short}
              minTickGap={35}
              {...axis}
            />
            <YAxis {...axis} />
            <Tooltip content={<Tip />} />
            <Bar
              isAnimationActive={false}
              dataKey="sleep"
              name="主睡眠"
              fill={chartColors.purple}
              stackId="sleep"
              maxBarSize={20}
              radius={[0, 0, 2, 2]}
            />
            <Bar
              isAnimationActive={false}
              dataKey="naps"
              name="Nap / 补觉"
              fill="#dad2ed"
              stackId="sleep"
              maxBarSize={20}
              radius={[3, 3, 0, 0]}
            />
            <Legend
              iconType="circle"
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Panel>
  );
}
function Quality({ data }: { data: Dashboard }) {
  return (
    <Panel
      title="数据质量与待核对记录"
      subtitle="提示帮助理解数据，不会自动修改 WHOOP 原始记录"
      aside={<CircleHelp size={18} />}
    >
      {data.flags.length ? (
        <div className="quality-list">
          {data.flags.map((f, i) => (
            <div key={i}>
              <span className="quality-dot" />
              <div>
                <h3>
                  {f.type}
                  <small>{f.date}</small>
                </h3>
                <p>{f.text}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="quality-ok">
          <CheckCircle2 size={18} />
          本时段未触发数据质量提示。
        </p>
      )}
    </Panel>
  );
}
function DailyTable({
  data,
  onNote,
  compact = false,
}: {
  data: Dashboard;
  onNote: (note: { day: string; text: string }) => void;
  compact?: boolean;
}) {
  const rows = [...data.daily]
    .reverse()
    .filter(
      (d) => d.recovery != null || d.sleep != null || d.workouts > 0 || d.note,
    );
  return (
    <Panel
      title={compact ? "最近的健康记录" : "每日健康记录"}
      subtitle="日期按北京时间显示 · 点击备注补充当天的生活背景"
      aside={
        <span className="records-count">
          {compact ? Math.min(7, rows.length) : rows.length} 条
        </span>
      }
    >
      {rows.length ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>日期</th>
                <th>恢复</th>
                <th>主睡眠</th>
                <th>
                  HRV <small>ms</small>
                </th>
                <th>静息心率</th>
                <th>Strain</th>
                <th>生活备注</th>
              </tr>
            </thead>
            <tbody>
              {(compact ? rows.slice(0, 7) : rows).map((d) => (
                <tr key={d.date}>
                  <td className="date-cell">
                    {d.date}
                    <small>
                      {new Date(d.date + "T12:00:00+08:00").toLocaleDateString(
                        "zh-CN",
                        { weekday: "short", timeZone: "Asia/Shanghai" },
                      )}
                    </small>
                  </td>
                  <td>
                    <span
                      className="recovery-tag"
                      style={{
                        background: recoveryColor(d.recovery) + "25",
                        color:
                          d.recovery == null
                            ? "#7c857c"
                            : d.recovery >= 67
                              ? "#4c805b"
                              : d.recovery >= 34
                                ? "#a48430"
                                : "#a95c53",
                      }}
                    >
                      <span style={{ background: recoveryColor(d.recovery) }} />
                      {num(d.recovery)}
                    </span>
                    {d.calibrating && <small> 校准</small>}
                  </td>
                  <td>{hours(d.sleep)}</td>
                  <td>{num(d.hrv, 1)}</td>
                  <td>
                    {num(d.rhr)} <small>bpm</small>
                  </td>
                  <td>{num(d.strain, 1)}</td>
                  <td>
                    <button
                      className="note-button"
                      onClick={() =>
                        onNote({ day: d.date, text: d.note || "" })
                      }
                    >
                      {d.note ? (
                        <span className="note-text">{d.note}</span>
                      ) : (
                        <>
                          <Plus size={13} />
                          添加备注
                        </>
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty />
      )}
    </Panel>
  );
}
