"use client";

/**
 * app/tasks/page.tsx — 할일 대시보드
 * tasks 테이블의 태스크를 status 필터로 조회·수정·삭제
 */
import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

interface Task {
  id: string;
  title: string;
  description: string;
  status: "todo" | "in_progress" | "done";
  priority: "high" | "medium" | "low";
  project: string;
  source: string;
  note_id: string | null;
  created_at: string;
}

const STATUS_LABEL: Record<Task["status"], string> = {
  todo: "할 일",
  in_progress: "진행 중",
  done: "완료",
};

const STATUS_NEXT: Record<Task["status"], Task["status"]> = {
  todo: "in_progress",
  in_progress: "done",
  done: "todo",
};

const STATUS_COLOR: Record<Task["status"], string> = {
  todo: "bg-slate-100 text-slate-600",
  in_progress: "bg-blue-100 text-blue-700",
  done: "bg-emerald-100 text-emerald-700",
};

const PRIORITY_COLOR: Record<Task["priority"], string> = {
  high: "bg-red-100 text-red-600 border-red-200",
  medium: "bg-amber-100 text-amber-600 border-amber-200",
  low: "bg-slate-100 text-slate-500 border-slate-200",
};

const PRIORITY_LABEL: Record<Task["priority"], string> = {
  high: "🔴 높음",
  medium: "🟡 보통",
  low: "🟢 낮음",
};

type FilterStatus = "all" | Task["status"];

const FILTER_TABS: { key: FilterStatus; label: string }[] = [
  { key: "all", label: "전체" },
  { key: "todo", label: "할 일" },
  { key: "in_progress", label: "진행 중" },
  { key: "done", label: "완료" },
];

function formatDate(iso: string) {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchTasks = useCallback(async (status: FilterStatus) => {
    setLoading(true);
    setError("");
    try {
      const qs = status !== "all" ? `?status=${status}&limit=100` : "?limit=100";
      const res = await fetch(`/api/tasks${qs}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Task[] = await res.json();
      setTasks(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks(filter);
  }, [filter, fetchTasks]);

  const cycleStatus = async (task: Task) => {
    const nextStatus = STATUS_NEXT[task.status];
    setUpdatingId(task.id);
    try {
      const res = await fetch(`/api/tasks/${task.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (res.ok) {
        setTasks((prev) =>
          prev.map((t) => (t.id === task.id ? { ...t, status: nextStatus } : t))
        );
      }
    } catch { /* ignore */ }
    setUpdatingId(null);
  };

  const deleteTask = async (id: string) => {
    if (!confirm("이 태스크를 삭제하시겠습니까?")) return;
    setDeletingId(id);
    try {
      const res = await fetch(`/api/tasks/${id}`, { method: "DELETE" });
      if (res.ok) setTasks((prev) => prev.filter((t) => t.id !== id));
    } catch { /* ignore */ }
    setDeletingId(null);
  };

  const counts = {
    all: tasks.length,
    todo: tasks.filter((t) => t.status === "todo").length,
    in_progress: tasks.filter((t) => t.status === "in_progress").length,
    done: tasks.filter((t) => t.status === "done").length,
  };

  const displayed = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);

  // 우선순위 정렬: high → medium → low, 같은 우선순위 내 최신순
  const sorted = [...displayed].sort((a, b) => {
    const pri = { high: 0, medium: 1, low: 2 };
    if (pri[a.priority] !== pri[b.priority]) return pri[a.priority] - pri[b.priority];
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200 px-4 sm:px-8 py-4 flex items-center gap-3">
        <Link
          href="/"
          className="text-slate-400 hover:text-indigo-500 transition-colors text-sm"
        >
          ← 대시보드
        </Link>
        <h1 className="text-lg font-bold text-slate-800">☑️ 할일</h1>
        <span className="ml-auto text-xs text-slate-400">{tasks.length}개</span>
        <button
          onClick={() => fetchTasks(filter)}
          className="p-2 rounded-xl border border-slate-200 text-slate-400 hover:text-indigo-500 hover:border-indigo-300 transition-colors text-sm"
          title="새로고침"
        >
          🔄
        </button>
      </header>

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-5 space-y-4">
        {/* 요약 카드 */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: "할 일", count: counts.todo, color: "text-slate-700", bg: "bg-slate-50" },
            { label: "진행 중", count: counts.in_progress, color: "text-blue-600", bg: "bg-blue-50" },
            { label: "완료", count: counts.done, color: "text-emerald-600", bg: "bg-emerald-50" },
          ].map((item) => (
            <div
              key={item.label}
              className={`${item.bg} rounded-2xl border border-slate-200 p-4 text-center shadow-sm`}
            >
              <div className={`text-2xl font-bold ${item.color}`}>{item.count}</div>
              <div className="text-xs text-slate-500 mt-0.5">{item.label}</div>
            </div>
          ))}
        </div>

        {/* 필터 탭 */}
        <div className="flex gap-1.5 bg-white rounded-2xl border border-slate-200 p-1.5 shadow-sm">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`flex-1 py-2 px-3 rounded-xl text-xs font-medium transition-colors ${
                filter === tab.key
                  ? "bg-indigo-500 text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-700 hover:bg-slate-50"
              }`}
            >
              {tab.label}
              {tab.key !== "all" && (
                <span className={`ml-1 ${filter === tab.key ? "text-indigo-200" : "text-slate-400"}`}>
                  {counts[tab.key]}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* 로딩 */}
        {loading && (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {/* 에러 */}
        {!loading && error && (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">⚠️</p>
            <p className="text-slate-500 text-sm">{error}</p>
            <button
              onClick={() => fetchTasks(filter)}
              className="mt-4 px-4 py-2 bg-indigo-500 text-white rounded-xl text-sm hover:bg-indigo-600 transition-colors"
            >
              다시 시도
            </button>
          </div>
        )}

        {/* 빈 상태 */}
        {!loading && !error && sorted.length === 0 && (
          <div className="text-center py-20">
            <p className="text-5xl mb-4">📋</p>
            <p className="text-slate-500 text-sm font-medium">
              {filter === "all" ? "아직 태스크가 없습니다" : `${STATUS_LABEL[filter as Task["status"]]} 태스크가 없습니다`}
            </p>
            <p className="text-slate-400 text-xs mt-2">
              텔레그램에서 할 일이 포함된 메시지를 보내거나 /task 명령어를 사용하세요
            </p>
          </div>
        )}

        {/* 태스크 목록 */}
        {!loading && !error && sorted.length > 0 && (
          <div className="space-y-2.5">
            {sorted.map((task) => (
              <div
                key={task.id}
                className={`bg-white rounded-2xl border shadow-sm transition-opacity ${
                  task.status === "done" ? "border-slate-100 opacity-60" : "border-slate-200"
                }`}
              >
                <div className="p-4">
                  {/* 상단: 제목 + 배지들 */}
                  <div className="flex items-start gap-3">
                    {/* 상태 토글 버튼 */}
                    <button
                      onClick={() => cycleStatus(task)}
                      disabled={updatingId === task.id}
                      className={`mt-0.5 w-5 h-5 rounded-full border-2 shrink-0 transition-all ${
                        task.status === "done"
                          ? "bg-emerald-400 border-emerald-400"
                          : task.status === "in_progress"
                          ? "bg-blue-400 border-blue-400"
                          : "border-slate-300 hover:border-indigo-400"
                      } ${updatingId === task.id ? "opacity-50" : ""}`}
                      title={`다음 상태로: ${STATUS_LABEL[STATUS_NEXT[task.status]]}`}
                    >
                      {task.status === "done" && (
                        <svg className="w-3 h-3 text-white m-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>

                    {/* 제목 */}
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm font-medium leading-snug ${task.status === "done" ? "line-through text-slate-400" : "text-slate-800"}`}>
                        {task.title}
                      </p>
                      {task.description && (
                        <p className="text-xs text-slate-400 mt-1 leading-relaxed line-clamp-2">
                          {task.description}
                        </p>
                      )}
                    </div>

                    {/* 삭제 버튼 */}
                    <button
                      onClick={() => deleteTask(task.id)}
                      disabled={deletingId === task.id}
                      className="shrink-0 text-slate-300 hover:text-red-400 transition-colors text-lg leading-none disabled:opacity-40"
                      title="삭제"
                    >
                      ×
                    </button>
                  </div>

                  {/* 하단: 메타 정보 */}
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${STATUS_COLOR[task.status]}`}>
                      {STATUS_LABEL[task.status]}
                    </span>
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full border ${PRIORITY_COLOR[task.priority]}`}>
                      {PRIORITY_LABEL[task.priority]}
                    </span>
                    {task.project && (
                      <span className="text-[11px] text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-200">
                        📁 {task.project}
                      </span>
                    )}
                    <span className="text-[11px] text-slate-400 ml-auto">
                      {formatDate(task.created_at)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 안내 */}
        {!loading && !error && sorted.length > 0 && (
          <p className="text-center text-xs text-slate-400 py-4">
            원형 버튼을 눌러 상태를 변경하세요 (할 일 → 진행 중 → 완료)
          </p>
        )}
      </div>
    </div>
  );
}
