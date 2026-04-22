"use client";

/**
 * app/stats/page.tsx — 대시보드 통계 페이지
 */
import { useState, useEffect } from "react";
import Link from "next/link";

interface CategoryStat { name: string; count: number }
interface SourceStat { name: string; count: number }
interface DailyTrend { date: string; count: number }

interface Stats {
  total: number;
  today: number;
  this_week: number;
  by_category: CategoryStat[];
  by_source: SourceStat[];
  daily_trend: DailyTrend[];
}

const SOURCE_LABEL: Record<string, string> = {
  telegram: "텔레그램",
  rss: "RSS",
  youtube: "유튜브",
  manual: "직접입력",
  upload: "파일업로드",
  kakao: "카카오",
};

const CATEGORY_COLORS = [
  "bg-indigo-500", "bg-emerald-500", "bg-amber-500",
  "bg-red-500", "bg-purple-500", "bg-sky-500", "bg-pink-500", "bg-slate-400",
];

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: Stats) => setStats(data))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="min-h-screen bg-slate-50">
        <header className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-4">
          <Link href="/" className="text-slate-400 hover:text-indigo-500 transition-colors">← 대시보드</Link>
          <h1 className="text-lg font-bold text-slate-800">📊 통계</h1>
        </header>
        <div className="flex flex-col items-center justify-center py-32 text-center">
          <p className="text-4xl mb-4">⚠️</p>
          <p className="text-slate-600 font-medium mb-1">통계를 불러오지 못했습니다</p>
          <p className="text-slate-400 text-sm mb-6">{error || "백엔드 연결을 확인해주세요"}</p>
          <button
            onClick={() => { setError(""); setLoading(true); fetch("/api/stats").then(r => r.json()).then(setStats).catch(e => setError(String(e))).finally(() => setLoading(false)); }}
            className="px-4 py-2 bg-indigo-500 text-white rounded-xl text-sm hover:bg-indigo-600 transition-colors"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  const maxDaily = stats.daily_trend.length > 0
    ? Math.max(...stats.daily_trend.map((d) => d.count), 1)
    : 1;

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 bg-white border-b border-slate-200 px-6 py-4 flex items-center gap-4">
        <Link href="/" className="text-slate-400 hover:text-indigo-500 transition-colors">
          ← 대시보드
        </Link>
        <h1 className="text-lg font-bold text-slate-800">📊 통계</h1>
      </header>

      <div className="max-w-3xl mx-auto px-4 sm:px-8 py-6 space-y-6">
        {/* 요약 카드 */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "전체 노트", value: stats.total, icon: "📝" },
            { label: "오늘", value: stats.today, icon: "📅" },
            { label: "이번 주", value: stats.this_week, icon: "📆" },
          ].map((item) => (
            <div key={item.label} className="bg-white rounded-2xl border border-slate-200 p-4 text-center shadow-sm">
              <div className="text-2xl mb-1">{item.icon}</div>
              <div className="text-2xl font-bold text-slate-800">{item.value}</div>
              <div className="text-xs text-slate-500 mt-0.5">{item.label}</div>
            </div>
          ))}
        </div>

        {/* 일별 추이 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">최근 7일 추이</h2>
          <div className="flex items-end gap-2 h-28">
            {stats.daily_trend.map((d) => {
              const pct = Math.round((d.count / maxDaily) * 100);
              return (
                <div key={d.date} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs text-slate-500 font-medium">{d.count > 0 ? d.count : ""}</span>
                  <div
                    className="w-full rounded-t-md bg-indigo-400 transition-all"
                    style={{ height: `${Math.max(pct, d.count > 0 ? 8 : 2)}%` }}
                  />
                  <span className="text-[10px] text-slate-400">{d.date}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 카테고리 분포 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">카테고리 분포</h2>
          <div className="space-y-3">
            {stats.by_category.map((c, i) => {
              const pct = stats.total > 0 ? Math.round((c.count / stats.total) * 100) : 0;
              return (
                <div key={c.name}>
                  <div className="flex justify-between text-xs text-slate-600 mb-1">
                    <span>{c.name}</span>
                    <span>{c.count}개 ({pct}%)</span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${CATEGORY_COLORS[i % CATEGORY_COLORS.length]}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 소스 분포 */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">소스별 분포</h2>
          <div className="flex flex-wrap gap-2">
            {stats.by_source.map((s) => (
              <div key={s.name} className="flex items-center gap-2 bg-slate-50 rounded-xl px-3 py-2 border border-slate-200">
                <span className="text-sm font-medium text-slate-700">
                  {SOURCE_LABEL[s.name] ?? s.name}
                </span>
                <span className="text-xs bg-indigo-100 text-indigo-700 rounded-full px-2 py-0.5 font-semibold">
                  {s.count}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
