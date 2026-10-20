export type Day = {
  date: string;
  recovery: number | null;
  hrv: number | null;
  rhr: number | null;
  spo2: number | null;
  sleep: number | null;
  naps: number | null;
  total_sleep: number | null;
  performance: number | null;
  efficiency: number | null;
  consistency: number | null;
  strain: number | null;
  workouts: number;
  hrv_baseline: number | null;
  rhr_baseline: number | null;
  sleep_baseline: number | null;
  respiratory: number | null;
  respiratory_baseline: number | null;
  calibrating: boolean;
  note: string;
};
export type Metric = {
  value: number | null;
  n: number;
  previous: number | null;
  previous_n: number;
  delta: number | null;
};
export type Sleep = {
  id: string;
  date: string;
  start: string;
  end: string;
  nap: boolean;
  hours: number;
  performance: number | null;
  efficiency: number | null;
  consistency: number | null;
  respiratory: number | null;
  stages: { light: number; deep: number; rem: number; awake: number };
};
export type Workout = {
  id: string;
  date: string;
  start: string;
  name: string;
  minutes: number | null;
  strain: number | null;
  average_hr: number | null;
  max_hr: number | null;
  kcal: number | null;
  scored: boolean;
  zones: number[];
};
export type Dashboard = {
  range: {
    start: string;
    end: string;
    days: number;
    previous_start: string;
    previous_end: string;
  };
  available: { start: string | null; end: string | null };
  coverage: number;
  summary: Record<string, Metric>;
  daily: Day[];
  sleeps: Sleep[];
  workouts: Workout[];
  flags: { date: string; type: string; text: string }[];
  insights: { title: string; text: string; tone: string }[];
  latest: Day | null;
  correlation: { n: number; r: number | null };
  definitions: string[];
  events: {
    id: number;
    day: string;
    time: string;
    category: string;
    text: string;
  }[];
};
export type Status = {
  local_token: string;
  last_fetch: string | null;
  configured: boolean;
  authorized: boolean;
  running: boolean;
  timezone: string;
  server_mode: boolean;
  insecure_http: boolean;
  auth_mode: "local" | "basic" | "tailscale";
  sync_interval_minutes: number;
  counts: Record<string, number>;
  import_errors: string[];
  history: {
    id: number;
    started_at: string;
    finished_at: string | null;
    state: string;
    message: string;
  }[];
};

export async function request<T>(
  url: string,
  method = "GET",
  body?: unknown,
  token?: string,
): Promise<T> {
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Local-Token": token } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail || `请求失败 (${response.status})`);
  }
  return response.json();
}
export const num = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined ? "—" : v.toFixed(d);
export const hours = (v: number | null | undefined) =>
  v == null
    ? "—"
    : `${Math.floor(Math.round(v * 60) / 60)}小时${String(Math.round(v * 60) % 60).padStart(2, "0")}分`;
export const local = (v: string | null | undefined) =>
  v
    ? new Date(v).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      })
    : "—";
export const time = (v: string) =>
  new Date(v).toLocaleTimeString("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
export const today = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Shanghai" });
