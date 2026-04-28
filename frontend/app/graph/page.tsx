"use client";

/**
 * graph/page.tsx — 태그·키워드 브라우저
 * 워드클라우드(빈도 시각화) + 키워드 클릭 시 관련 노트 목록
 */
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

interface KeywordStat {
  keyword: string;
  count: number;
  top_category: string;
}

interface Note {
  id: string;
  summary: string;
  category: string;
  content_type: string;
  keywords: string[];
  created_at: string;
}

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
  "음식/요리": "#f97316",
  "스포츠/레저": "#06b6d4",
  "기타":    "#475569",
};

function catColor(cat: string) {
  return CATEGORY_COLORS[cat] ?? "#6366f1";
}

function scaleFont(count: number, min: number, max: number): string {
  if (max === min) return "1.1rem";
  const t = (count - min) / (max - min);
  const size = 0.82 + t * 2.2; // 0.82rem ~ 3.02rem
  return `${size.toFixed(2)}rem`;
}

export default function TagBrowserPage() {
  const [stats, setStats] = useState<KeywordStat[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [notes, setNotes] = useState<Note[]>([]);
  const [notesLoading, setNotesLoading] = useState(false);
  const [sort, setSort] = useState<"freq" | "alpha">("freq");
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch("/api/notes/keywords/stats?limit=120")
      .then((r) => r.ok ? r.json() : [])
      .then((data: KeywordStat[]) => setStats(data))
      .finally(() => setLoading(false));
  }, []);

  const loadNotes = useCallback(async (kw: string) => {
    setNotesLoading(true);
    setNotes([]);
    const res = await fetch(`/api/notes?keyword=${encodeURIComponent(kw)}&limit=30`);
    if (res.ok) setNotes(await res.json());
    setNotesLoading(false);
  }, []);

  const handleSelect = (kw: string) => {
    if (selected === kw) { setSelected(null); setNotes([]); return; }
    setSelected(kw);
    loadNotes(kw);
  };

  const displayed = stats
    .filter((s) => !search || s.keyword.includes(search))
    .sort((a, b) =>
      sort === "alpha" ? a.keyword.localeCompare(b.keyword, "ko") : b.count - a.count
    );

  const minCount = displayed.length ? Math.min(...displayed.map((s) => s.count)) : 1;
  const maxCount = displayed.length ? Math.max(...displayed.map((s) => s.count)) : 1;

  const totalKeywords = stats.length;
  const totalMentions = stats.reduce((s, k) => s + k.count, 0);

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      {/* 헤더 */}
      <header className="sticky top-0 z-10 bg-slate-50/90 dark:bg-slate-900/90 backdrop-blur-sm border-b border-slate-200 dark:border-slate-700 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center gap-4">
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
          <h1 className="font-bold text-slate-800 dark:text-slate-100">🏷️ 태그 브라우저</h1>
          <span className="ml-auto text-xs text-slate-400">
            키워드 {totalKeywords}개 · 총 {totalMentions}회
          </span>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-6">
        {/* 컨트롤 */}
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="태그 검색…"
            className="flex-1 min-w-40 px-3 py-1.5 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <div className="flex rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden text-xs">
            <button
              onClick={() => setSort("freq")}
              className={`px-3 py-1.5 transition-colors ${sort === "freq" ? "bg-indigo-500 text-white" : "bg-white dark:bg-slate-800 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700"}`}
            >
              빈도순
            </button>
            <button
              onClick={() => setSort("alpha")}
              className={`px-3 py-1.5 transition-colors ${sort === "alpha" ? "bg-indigo-500 text-white" : "bg-white dark:bg-slate-800 text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-700"}`}
            >
              가나다순
            </button>
          </div>
        </div>

        {/* 워드클라우드 */}
        <div className="bg-white dark:bg-slate-800 rounded-2xl border border-slate-200 dark:border-slate-700 p-6 min-h-48">
          {loading ? (
            <div className="flex justify-center items-center h-40">
              <div className="w-7 h-7 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : displayed.length === 0 ? (
            <p className="text-center text-slate-400 py-16">저장된 태그가 없습니다</p>
          ) : (
            <div className="flex flex-wrap gap-x-4 gap-y-3 items-center justify-center leading-loose">
              {displayed.map((s) => (
                <button
                  key={s.keyword}
                  onClick={() => handleSelect(s.keyword)}
                  style={{
                    fontSize: scaleFont(s.count, minCount, maxCount),
                    color: catColor(s.top_category),
                    opacity: selected && selected !== s.keyword ? 0.35 : 1,
                  }}
                  className={`font-medium transition-all hover:opacity-100 hover:scale-110 rounded px-1 ${
                    selected === s.keyword
                      ? "ring-2 ring-offset-1 ring-indigo-400 bg-indigo-50 dark:bg-indigo-900/30"
                      : ""
                  }`}
                  title={`${s.keyword} (${s.count}회)`}
                >
                  {s.keyword}
                  <sup className="text-[0.55em] ml-0.5 opacity-60">{s.count}</sup>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 카테고리 범례 */}
        {!loading && stats.length > 0 && (
          <div className="flex flex-wrap gap-3 text-xs">
            {Object.entries(CATEGORY_COLORS)
              .filter(([cat]) => stats.some((s) => s.top_category === cat))
              .map(([cat, color]) => (
                <span key={cat} className="flex items-center gap-1 text-slate-500 dark:text-slate-400">
                  <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                  {cat}
                </span>
              ))}
          </div>
        )}

        {/* 선택된 태그의 노트 목록 */}
        {selected && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
                <span style={{ color: catColor(stats.find((s) => s.keyword === selected)?.top_category ?? "") }}>
                  #{selected}
                </span>{" "}
                관련 노트
              </h2>
              <span className="text-xs text-slate-400">
                {stats.find((s) => s.keyword === selected)?.count ?? 0}개 저장됨
              </span>
              <button
                onClick={() => { setSelected(null); setNotes([]); }}
                className="ml-auto text-xs text-slate-400 hover:text-slate-600"
              >
                닫기 ✕
              </button>
            </div>

            {notesLoading ? (
              <div className="flex justify-center py-8">
                <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : notes.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-6">노트가 없습니다</p>
            ) : (
              <div className="space-y-2">
                {notes.map((note) => (
                  <div
                    key={note.id}
                    className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 px-4 py-3"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium border"
                        style={{
                          color: catColor(note.category),
                          borderColor: catColor(note.category) + "50",
                          background: catColor(note.category) + "18",
                        }}
                      >
                        {note.category}
                      </span>
                      <span className="text-xs text-slate-400 ml-auto">
                        {new Date(note.created_at).toLocaleDateString("ko-KR", {
                          month: "short", day: "numeric",
                        })}
                      </span>
                    </div>
                    <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                      {note.summary || "(요약 없음)"}
                    </p>
                    {note.keywords?.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {note.keywords.slice(0, 6).map((kw) => (
                          <button
                            key={kw}
                            onClick={() => handleSelect(kw)}
                            className={`text-xs px-1.5 py-0.5 rounded-full border transition-colors ${
                              kw === selected
                                ? "bg-indigo-100 dark:bg-indigo-900/40 text-indigo-600 border-indigo-300"
                                : "border-slate-200 dark:border-slate-600 text-slate-400 hover:text-indigo-500 hover:border-indigo-300"
                            }`}
                          >
                            #{kw}
                          </button>
                        ))}
                      </div>
                    )}
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
