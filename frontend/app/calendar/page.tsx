"use client";

/**
 * calendar/page.tsx — 날짜별 노트 캘린더 뷰
 */
import { useEffect, useState } from "react";
import Link from "next/link";

interface DayNote {
  id: string;
  summary: string;
  category: string;
  content_type: string;
}

type CalendarData = Record<string, DayNote[]>;

const CATEGORY_COLORS: Record<string, string> = {
  "기술":    "#6366f1",
  "Tech":    "#6366f1",
  "비즈니스": "#f59e0b",
  "뉴스":    "#10b981",
  "뉴스스크랩": "#10b981",
  "건강":    "#ec4899",
  "건강/운동": "#ec4899",
  "교육":    "#3b82f6",
  "무역/수출": "#8b5cf6",
  "무역수출":  "#8b5cf6",
  "개인메모":  "#64748b",
  "라이프스타일": "#f97316",
  "투자/금융": "#eab308",
  "기타":    "#475569",
};

function catColor(cat: string) {
  return CATEGORY_COLORS[cat] ?? "#6366f1";
}

const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}
function firstWeekday(year: number, month: number): number {
  return new Date(year, month - 1, 1).getDay(); // 0=Sun
}

export default function CalendarPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [data, setData] = useState<CalendarData>({});
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setSelectedDate(null);
    fetch(`/api/notes/calendar?year=${year}&month=${month}`)
      .then((r) => r.ok ? r.json() : {})
      .then((d: CalendarData) => setData(d))
      .finally(() => setLoading(false));
  }, [year, month]);

  const prevMonth = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12); }
    else setMonth(m => m - 1);
  };
  const nextMonth = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1); }
    else setMonth(m => m + 1);
  };

  const totalDays = daysInMonth(year, month);
  const startDay = firstWeekday(year, month);
  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  // 캘린더 그리드 셀 (빈 칸 + 날짜)
  const cells: (number | null)[] = [
    ...Array(startDay).fill(null),
    ...Array.from({ length: totalDays }, (_, i) => i + 1),
  ];
  // 6행 맞추기
  while (cells.length % 7 !== 0) cells.push(null);

  const selectedNotes = selectedDate ? (data[selectedDate] ?? []) : [];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700 px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center gap-4">
          <Link
            href="/"
            className="text-slate-400 hover:text-indigo-500 transition-colors text-sm flex items-center gap-1"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            대시보드
          </Link>
          <span className="text-slate-300 dark:text-slate-600">/</span>
          <h1 className="font-bold text-slate-800 dark:text-slate-100">📅 캘린더</h1>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        {/* 월 네비게이션 */}
        <div className="flex items-center justify-between bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 px-5 py-3">
          <button
            onClick={prevMonth}
            className="p-2 rounded-lg text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-slate-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="text-center">
            <p className="font-bold text-slate-800 dark:text-slate-100 text-lg">
              {year}년 {MONTHS[month - 1]}
            </p>
            <p className="text-xs text-slate-400">
              {Object.keys(data).length}일에 {Object.values(data).reduce((s, n) => s + n.length, 0)}개 노트
            </p>
          </div>
          <button
            onClick={nextMonth}
            className="p-2 rounded-lg text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 dark:hover:bg-slate-700 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>

        {/* 캘린더 그리드 */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden">
          {/* 요일 헤더 */}
          <div className="grid grid-cols-7 border-b border-slate-100 dark:border-slate-700">
            {WEEKDAYS.map((d, i) => (
              <div
                key={d}
                className={`text-center text-xs font-medium py-2.5 ${
                  i === 0 ? "text-red-400" : i === 6 ? "text-blue-400" : "text-slate-400"
                }`}
              >
                {d}
              </div>
            ))}
          </div>

          {/* 날짜 셀 */}
          {loading ? (
            <div className="flex justify-center items-center h-48">
              <div className="w-7 h-7 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <div className="grid grid-cols-7">
              {cells.map((day, idx) => {
                if (day === null) {
                  return <div key={`empty-${idx}`} className="h-16 sm:h-20 border-b border-r border-slate-50 dark:border-slate-700/50 last:border-r-0" />;
                }
                const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const dayNotes = data[dateStr] ?? [];
                const isToday = dateStr === todayStr;
                const isSelected = dateStr === selectedDate;
                const weekday = (startDay + day - 1) % 7;
                const isSun = weekday === 0;
                const isSat = weekday === 6;

                return (
                  <button
                    key={dateStr}
                    onClick={() => setSelectedDate(isSelected ? null : dateStr)}
                    className={`h-16 sm:h-20 border-b border-r border-slate-50 dark:border-slate-700/50 p-1.5 flex flex-col items-start transition-colors ${
                      isSelected
                        ? "bg-indigo-50 dark:bg-indigo-900/30"
                        : "hover:bg-slate-50 dark:hover:bg-slate-700/40"
                    } ${idx % 7 === 6 ? "border-r-0" : ""}`}
                  >
                    <span
                      className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full mb-1 ${
                        isToday
                          ? "bg-indigo-500 text-white"
                          : isSun
                          ? "text-red-400"
                          : isSat
                          ? "text-blue-400"
                          : "text-slate-600 dark:text-slate-300"
                      }`}
                    >
                      {day}
                    </span>
                    {/* 카테고리 dot 최대 4개 */}
                    {dayNotes.length > 0 && (
                      <div className="flex flex-wrap gap-0.5 mt-auto">
                        {dayNotes.slice(0, 4).map((n, i) => (
                          <span
                            key={i}
                            className="w-1.5 h-1.5 rounded-full"
                            style={{ background: catColor(n.category) }}
                          />
                        ))}
                        {dayNotes.length > 4 && (
                          <span className="text-[9px] text-slate-400 leading-none">+{dayNotes.length - 4}</span>
                        )}
                      </div>
                    )}
                    {dayNotes.length > 0 && (
                      <span className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                        {dayNotes.length}개
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* 선택된 날짜의 노트 목록 */}
        {selectedDate && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                {selectedDate.replace(/-/g, ".")} 노트
              </h2>
              <span className="text-xs text-slate-400">{selectedNotes.length}개</span>
              <button
                onClick={() => setSelectedDate(null)}
                className="ml-auto text-xs text-slate-400 hover:text-slate-600"
              >
                닫기 ✕
              </button>
            </div>

            {selectedNotes.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">이 날 저장된 노트가 없습니다</p>
            ) : (
              <div className="space-y-2">
                {selectedNotes.map((note) => (
                  <div
                    key={note.id}
                    className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3 flex items-start gap-3"
                  >
                    <span
                      className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                      style={{ background: catColor(note.category) }}
                    />
                    <div className="min-w-0">
                      <span
                        className="text-xs font-medium"
                        style={{ color: catColor(note.category) }}
                      >
                        {note.category}
                      </span>
                      <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed mt-0.5">
                        {note.summary || "(요약 없음)"}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
