"use client";

/**
 * app/page.tsx — 메인 대시보드 (사이드바 + 노트 목록)
 * 모바일 최적화: 사이드바 드로어, 햄버거 메뉴, 반응형 패딩
 */
import { useState, useEffect, useCallback } from "react";
import NoteCard from "@/components/NoteCard";
import Sidebar from "@/components/Sidebar";

interface Note {
  id: string;
  source: string;
  raw_content: string;
  summary: string;
  keywords: string[];
  category: string;
  content_type: string;
  url: string | null;
  created_at: string;
}

export default function DashboardPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    params.set("limit", "50");

    const res = await fetch(`/api/notes?${params.toString()}`);
    if (res.ok) {
      const data: Note[] = await res.json();
      setNotes(data);
    }
    setLoading(false);
  }, [query, category]);

  useEffect(() => {
    const timer = setTimeout(fetchNotes, 300);
    return () => clearTimeout(timer);
  }, [fetchNotes]);

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* 사이드바 */}
      <Sidebar
        selected={category}
        onSelect={setCategory}
        noteCount={notes.length}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* 메인 콘텐츠: 데스크탑은 사이드바 너비만큼 margin, 모바일은 0 */}
      <main className="flex-1 min-h-screen sm:ml-60">
        {/* 상단 헤더 */}
        <header className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm border-b border-slate-200 px-4 sm:px-8 py-3 sm:py-4">
          <div className="max-w-3xl mx-auto flex items-center gap-3">
            {/* 햄버거 버튼 (모바일 전용) */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="sm:hidden p-2 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm shrink-0"
              aria-label="메뉴 열기"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            {/* 검색바 */}
            <div className="relative flex-1">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm">
                🔍
              </span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="메모·요약·키워드 검색..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent shadow-sm"
              />
            </div>

            {/* 새로고침 */}
            <button
              onClick={fetchNotes}
              disabled={loading}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm disabled:opacity-50 shrink-0"
              title="새로고침"
            >
              <svg
                className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                />
              </svg>
            </button>
          </div>
        </header>

        {/* 노트 목록 */}
        <div className="max-w-3xl mx-auto px-4 sm:px-8 py-5 sm:py-6">
          {/* 상태 표시 */}
          <div className="flex items-center justify-between mb-4 sm:mb-5">
            <h2 className="text-slate-700 font-semibold text-base">
              {category ? `${category}` : "전체 노트"}
            </h2>
            {!loading && (
              <span className="text-xs text-slate-400">
                {notes.length}개
              </span>
            )}
          </div>

          {/* 로딩 */}
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-slate-400 text-sm">불러오는 중...</p>
              </div>
            </div>
          )}

          {/* 빈 상태 */}
          {!loading && notes.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="text-5xl mb-4">📭</div>
              <p className="text-slate-500 font-medium mb-1">
                {query ? "검색 결과가 없습니다" : "저장된 노트가 없습니다"}
              </p>
              <p className="text-slate-400 text-sm">
                {query
                  ? "다른 키워드로 검색해보세요"
                  : "텔레그램 봇으로 메모를 보내보세요!"}
              </p>
            </div>
          )}

          {/* 노트 카드 목록 */}
          {!loading && notes.length > 0 && (
            <div className="space-y-3">
              {notes.map((note) => (
                <NoteCard
                  key={note.id}
                  note={note}
                  onDelete={(id) => setNotes((prev) => prev.filter((n) => n.id !== id))}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
