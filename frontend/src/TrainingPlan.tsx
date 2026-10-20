import { useEffect, useState } from "react";
import { CheckCircle2, ChevronLeft, ChevronRight, Save } from "lucide-react";
import { request, num, today } from "./api";
import "./insights.css";
type Plan = {
  id: number;
  name: string;
  weekday: number | null;
  kind: string;
  scheduled_day: string | null;
  state: string;
  workout_id: string | null;
  note: string;
  candidates: string[];
};
type Workout = {
  id: string;
  date: string;
  label: string;
  strain: number | null;
  high_minutes: number;
};
type Week = {
  start: string;
  end: string;
  plans: Plan[];
  workouts: Workout[];
  complete: number;
  configured: number;
};
export default function TrainingPlan({
  token,
  onSaved,
  revision,
  initialDay,
}: {
  token?: string;
  onSaved: () => void;
  revision?: string;
  initialDay?: string;
}) {
  const [day, setDay] = useState(initialDay || today()),
    [data, setData] = useState<Week | null>(null),
    [rev, setRev] = useState(0),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    let active = true;
    request<Week>("/api/training-week?day=" + day)
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
  }, [day, rev, revision]);
  function move(n: number) {
    const d = new Date(day + "T12:00:00+08:00");
    d.setDate(d.getDate() + n * 7);
    setDay(d.toLocaleDateString("en-CA", { timeZone: "Asia/Shanghai" }));
  }
  function update(id: number, patch: Partial<Plan>) {
    if (data)
      setData({
        ...data,
        plans: data.plans.map((p) => (p.id === id ? { ...p, ...patch } : p)),
      });
  }
  async function save(plan: Plan, template = false) {
    setBusy(true);
    setMessage("");
    try {
      await request(
        template
          ? `/api/training-templates/${plan.id}`
          : `/api/training-checks/${plan.id}`,
        "PUT",
        template
          ? { name: plan.name, weekday: plan.weekday, kind: plan.kind }
          : {
              week: data!.start,
              state: plan.state,
              workout_id: plan.workout_id || null,
              scheduled_day: plan.scheduled_day || null,
              note: plan.note,
            },
        token,
      );
      setRev((r) => r + 1);
      setMessage(template ? "周模板已更新" : "本周记录已保存");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}
      <section className="panel">
        <div className="panel-head">
          <div>
            <h2>四练计划，对照实际</h2>
            <p>候选活动不等于完成，确认后才计入本周四练</p>
          </div>
          <div className="plan-week-nav">
            <button aria-label="上一训练周" onClick={() => move(-1)}>
              <ChevronLeft size={15} />
            </button>
            <input
              type="date"
              aria-label="训练周日期"
              value={day}
              onChange={(e) => setDay(e.target.value)}
            />
            <button aria-label="下一训练周" onClick={() => move(1)}>
              <ChevronRight size={15} />
            </button>
          </div>
        </div>
        {data && (
          <>
            <div className="plan-summary">
              <strong>
                {data.complete}
                <small>/ 4 已确认完成</small>
              </strong>
              <span>
                {data.start} — {data.end}
                <br />
                {data.configured}/4 练已配置，{4 - data.configured} 练需补充计划
              </span>
            </div>
            <div className="plan-cards">
              {data.plans.map((p) => (
                <article className={`plan-card ${p.state}`} key={p.id}>
                  <div className="plan-card-title">
                    <span>第 {p.id} 练</span>
                    <h3>{p.name}</h3>
                    <span className="plan-state">
                      {p.state === "complete"
                        ? "已确认"
                        : p.state === "skipped"
                          ? "明确跳过"
                          : p.weekday == null
                            ? "待配置"
                            : p.candidates.length
                              ? "有候选，待核对"
                              : p.scheduled_day && p.scheduled_day < today()
                                ? "未匹配，待核对"
                                : "计划中"}
                    </span>
                  </div>
                  <div className="plan-fields">
                    <label>
                      本周安排日期
                      <input
                        type="date"
                        aria-label={`第${p.id}练安排日期`}
                        value={p.scheduled_day || ""}
                        onChange={(e) =>
                          update(p.id, { scheduled_day: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      关联实际活动
                      <select
                        aria-label={`第${p.id}练关联活动`}
                        value={p.workout_id || ""}
                        onChange={(e) =>
                          update(p.id, { workout_id: e.target.value })
                        }
                      >
                        <option value="">不关联活动 / 手动确认</option>
                        {data.workouts.map((w) => (
                          <option key={w.id} value={w.id}>
                            {p.candidates.includes(w.id) ? "★ 候选 · " : ""}
                            {w.date.slice(5)} {w.label} · Strain{" "}
                            {num(w.strain, 1)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      确认状态
                      <select
                        aria-label={`第${p.id}练确认状态`}
                        value={p.state}
                        onChange={(e) =>
                          update(p.id, { state: e.target.value })
                        }
                      >
                        <option value="pending">待核对</option>
                        <option value="complete">已完成（本人确认）</option>
                        <option value="skipped">本周跳过</option>
                      </select>
                    </label>
                    <label className="plan-note">
                      本周备注
                      <input
                        aria-label={`第${p.id}练备注`}
                        value={p.note}
                        onChange={(e) => update(p.id, { note: e.target.value })}
                        maxLength={1000}
                        placeholder="例如：4×4顺延到周六，实际完成4组"
                      />
                    </label>
                  </div>
                  <button
                    className="button"
                    disabled={busy || !token}
                    onClick={() => save(p)}
                  >
                    <CheckCircle2 size={14} />
                    保存本周确认
                  </button>
                </article>
              ))}
            </div>
            <p className="insight-caption">
              功能性训练只能作为力量日候选，不能证明做过深蹲；高强度累计达到10分钟只提示可能的间歇训练，无法确认4×4的组数。没有匹配也不等于没训练。
            </p>
          </>
        )}
      </section>
      {message && (
        <p className="plan-message" role="status">
          {message}
        </p>
      )}
      {data && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>每周训练模板</h2>
              <p>仅预填周一深蹲与周五4×4；另外两练请按你的真实计划补充</p>
            </div>
          </div>
          <div className="plan-template-list">
            {data.plans.map((p) => (
              <form
                key={p.id}
                onSubmit={(e) => {
                  e.preventDefault();
                  save(p, true);
                }}
              >
                <span>第{p.id}练</span>
                <input
                  aria-label={`第${p.id}练名称`}
                  value={p.name}
                  onChange={(e) => update(p.id, { name: e.target.value })}
                  maxLength={100}
                  required
                />
                <select
                  aria-label={`第${p.id}练固定星期`}
                  value={p.weekday ?? ""}
                  onChange={(e) =>
                    update(p.id, {
                      weekday:
                        e.target.value === "" ? null : Number(e.target.value),
                    })
                  }
                >
                  <option value="">未设置</option>
                  {["周一", "周二", "周三", "周四", "周五", "周六", "周日"].map(
                    (s, i) => (
                      <option key={s} value={i}>
                        {s}
                      </option>
                    ),
                  )}
                </select>
                <select
                  aria-label={`第${p.id}练类别`}
                  value={p.kind}
                  onChange={(e) => update(p.id, { kind: e.target.value })}
                >
                  {[
                    ["strength", "力量日"],
                    ["interval", "高强度间歇"],
                    ["easy", "低强度有氧"],
                    ["any", "其他 / 自定义"],
                  ].map(([v, l]) => (
                    <option value={v} key={v}>
                      {l}
                    </option>
                  ))}
                </select>
                <button className="button" disabled={busy || !token}>
                  <Save size={13} />
                  保存模板
                </button>
              </form>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
