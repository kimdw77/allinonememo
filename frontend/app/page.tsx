"use client";

/**
 * app/page.tsx — 메인 대시보드
 * 무한 스크롤 + 파일 업로드 + 중복 감지 + 핀 고정 + 다중선택 + 자동완성 + 내보내기
 */
import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import NoteCard from "@/components/NoteCard";
import Sidebar from "@/components/Sidebar";
import FileUpload from "@/components/FileUpload";

interface Note {
  id: string;
  source: string;
  raw_content: string;
  summary: string;
  highlights?: string[];
  keywords: string[];
  category: string;
  content_type: string;
  url: string | null;
  file_url?: string | null;
  created_at: string;
  related_links?: {
    articles?: Array<{ title: string; url: string; description?: string }>;
    images?: string[];
  };
}

interface DupNote { id: string; summary: string; category: string; created_at: string }
interface DupPair {
  note_a: DupNote;
  note_b: DupNote;
  common_keywords: string[];
  score: number;
}

const PAGE_SIZE = 20;
const PIN_KEY = "myvault_pinned_ids";

function loadPinnedIds(): Set<string> {
  try {
    const raw = localStorage.getItem(PIN_KEY);
    return raw ? new Set<string>(JSON.parse(raw)) : new Set<string>();
  } catch { return new Set(); }
}

function savePinnedIds(ids: Set<string>) {
  localStorage.setItem(PIN_KEY, JSON.stringify(Array.from(ids)));
}

export default function DashboardPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // 핀 고정
  const [pinnedIds, setPinnedIds] = useState<Set<string>>(new Set());

  // 다중 선택
  const [selectMode, setSelectMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);

  // 검색 자동완성
  const [allKeywords, setAllKeywords] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // 내보내기
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exporting, setExporting] = useState(false);

  // 모달 상태
  const [showUpload, setShowUpload] = useState(false);
  const [showDup, setShowDup] = useState(false);
  const [dupPairs, setDupPairs] = useState<DupPair[]>([]);
  const [dupLoading, setDupLoading] = useState(false);
  const [mergingId, setMergingId] = useState<string | null>(null);
  const [reclassifying, setReclassifying] = useState(false);
  const [reclassifyResult, setReclassifyResult] = useState<string>("");

  const sentinelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef(0);

  // localStorage에서 핀 초기화
  useEffect(() => {
    setPinnedIds(loadPinnedIds());
  }, []);

  // 키워드 자동완성 미리 로드
  useEffect(() => {
    fetch("/api/notes/keywords?limit=100")
      .then((r) => r.ok ? r.json() : [])
      .then((kws: string[]) => setAllKeywords(kws))
      .catch(() => {});
  }, []);

  // 외부 클릭 시 자동완성 닫기
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // ─── 핀 고정 ──────────────────────────────

  const togglePin = (id: string) => {
    setPinnedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      savePinnedIds(next);
      return next;
    });
  };

  // 핀된 노트를 상단으로
  const sortedNotes = [
    ...notes.filter((n) => pinnedIds.has(n.id)),
    ...notes.filter((n) => !pinnedIds.has(n.id)),
  ];

  // ─── 다중 선택 ────────────────────────────

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const exitSelectMode = () => {
    setSelectMode(false);
    setSelectedIds(new Set());
  };

  const bulkDelete = async () => {
    if (selectedIds.size === 0) return;
    if (!confirm(`선택한 ${selectedIds.size}개 노트를 삭제하시겠습니까?`)) return;
    setBulkDeleting(true);
    try {
      const res = await fetch("/api/notes/bulk-delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Array.from(selectedIds)),
      });
      if (res.ok) {
        const ids = new Set(selectedIds);
        setNotes((prev) => prev.filter((n) => !ids.has(n.id)));
        setPinnedIds((prev) => {
          const next = new Set(prev);
          ids.forEach((id) => next.delete(id));
          savePinnedIds(next);
          return next;
        });
        exitSelectMode();
      }
    } catch { /* ignore */ }
    setBulkDeleting(false);
  };

  // ─── 내보내기 ─────────────────────────────

  const doExport = async (fmt: "json" | "markdown") => {
    setExporting(true);
    setShowExportMenu(false);
    try {
      const params = new URLSearchParams({ fmt });
      if (category) params.set("category", category);
      if (selectMode && selectedIds.size > 0) params.set("ids", Array.from(selectedIds).join(","));
      const res = await fetch(`/api/notes/export?${params.toString()}`);
      if (!res.ok) { setExporting(false); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fmt === "markdown" ? "myvault_notes.md" : "myvault_notes.json";
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
    setExporting(false);
  };

  // ─── 데이터 로드 ───────────────────────────────

  const loadNotes = useCallback(async (reset: boolean) => {
    if (loading) return;
    setLoading(true);
    const currentOffset = reset ? 0 : offsetRef.current;

    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(currentOffset));

    const res = await fetch(`/api/notes?${params.toString()}`);
    if (res.ok) {
      const data: Note[] = await res.json();
      setNotes((prev) => reset ? data : [...prev, ...data]);
      offsetRef.current = currentOffset + data.length;
      setHasMore(data.length === PAGE_SIZE);
    }
    setLoading(false);
  }, [query, category]); // eslint-disable-line react-hooks/exhaustive-deps

  // 검색어·카테고리 변경 시 리셋
  useEffect(() => {
    offsetRef.current = 0;
    setHasMore(true);
    const timer = setTimeout(() => loadNotes(true), 300);
    return () => clearTimeout(timer);
  }, [query, category]); // eslint-disable-line react-hooks/exhaustive-deps

  // 무한 스크롤 — sentinel이 뷰포트에 진입하면 다음 페이지 로드
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading) {
          loadNotes(false);
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, loading, loadNotes]);

  // ─── 일괄 재분류 ──────────────────────────────

  const bulkReclassify = async () => {
    setReclassifying(true);
    setReclassifyResult("");
    try {
      const res = await fetch("/api/notes/bulk-reclassify?category_filter=기타&limit=50", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setReclassifyResult(`✅ ${data.reclassified}개 재분류 완료`);
        offsetRef.current = 0;
        setNotes([]);
        setHasMore(true);
        loadNotes(true);
      } else {
        setReclassifyResult("❌ 재분류 실패");
      }
    } catch {
      setReclassifyResult("❌ 네트워크 오류");
    }
    setReclassifying(false);
  };

  // ─── 중복 감지 ────────────────────────────────

  const findDuplicates = async () => {
    setDupLoading(true);
    setShowDup(true);
    const res = await fetch("/api/notes/duplicates?threshold=3");
    if (res.ok) {
      const data = await res.json();
      setDupPairs(data.pairs ?? []);
    }
    setDupLoading(false);
  };

  const mergeNotes = async (keepId: string, removeId: string) => {
    setMergingId(removeId);
    const res = await fetch(`/api/notes/merge?keep_id=${keepId}&remove_id=${removeId}`, {
      method: "POST",
    });
    if (res.ok) {
      setDupPairs((prev) =>
        prev.filter(
          (p) =>
            !(
              (p.note_a.id === keepId && p.note_b.id === removeId) ||
              (p.note_a.id === removeId && p.note_b.id === keepId)
            )
        )
      );
      setNotes((prev) => prev.filter((n) => n.id !== removeId));
    }
    setMergingId(null);
  };

  // 자동완성 필터
  const suggestions = query.length >= 1
    ? allKeywords.filter((k) => k.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  // ─── 렌더링 ──────────────────────────────────

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar
        selected={category}
        onSelect={setCategory}
        noteCount={notes.length}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 min-h-screen sm:ml-60">
        {/* 헤더 */}
        <header className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm border-b border-slate-200 px-4 sm:px-8 py-3 sm:py-4">
          <div className="max-w-3xl mx-auto flex items-center gap-2">
            {/* 햄버거 (모바일) */}
            <button
              onClick={() => setSidebarOpen(true)}
              className="sm:hidden p-2 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm shrink-0"
              aria-label="메뉴 열기"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>

            {/* 검색 + 자동완성 */}
            <div className="relative flex-1" ref={searchRef}>
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => setShowSuggestions(true)}
                placeholder="메모·요약·키워드 검색..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent shadow-sm"
              />
              {/* 자동완성 드롭다운 */}
              {showSuggestions && suggestions.length > 0 && (
                <ul className="absolute top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-20 overflow-hidden">
                  {suggestions.map((kw) => (
                    <li key={kw}>
                      <button
                        onMouseDown={(e) => { e.preventDefault(); setQuery(kw); setShowSuggestions(false); }}
                        className="w-full text-left px-4 py-2 text-sm text-slate-700 hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
                      >
                        <span className="text-slate-400 mr-2">🏷</span>{kw}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* 할일 대시보드 — 클립보드 목록 */}
            <Link
              href="/tasks"
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm shrink-0"
              title="할일 대시보드"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
              </svg>
            </Link>

            {/* 파일 업로드 — 위 방향 화살표 */}
            <button
              onClick={() => setShowUpload(true)}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm shrink-0"
              title="파일·이미지 업로드"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
            </button>

            {/* 내보내기 — 아래 방향 화살표 */}
            <div className="relative shrink-0">
              <button
                onClick={() => setShowExportMenu((v) => !v)}
                disabled={exporting}
                className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-violet-500 hover:border-violet-300 transition-colors shadow-sm disabled:opacity-50"
                title="노트 내보내기"
              >
                {exporting ? (
                  <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                  </svg>
                )}
              </button>
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-xl shadow-lg z-20 overflow-hidden w-40">
                  <button
                    onClick={() => doExport("json")}
                    className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    📄 JSON 내보내기
                  </button>
                  <button
                    onClick={() => doExport("markdown")}
                    className="w-full text-left px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    📝 Markdown 내보내기
                  </button>
                </div>
              )}
            </div>

            {/* 다중 선택 — 4개 격자 (체크박스와 전혀 다른 모양) */}
            <button
              onClick={() => { setSelectMode((v) => !v); setSelectedIds(new Set()); }}
              className={`p-2.5 rounded-xl border transition-colors shadow-sm shrink-0 ${
                selectMode
                  ? "border-indigo-400 bg-indigo-50 text-indigo-600"
                  : "border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300"
              }`}
              title={selectMode ? "선택 모드 종료" : "다중 선택"}
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
              </svg>
            </button>

            {/* 일괄 재분류 — 반짝이(AI) */}
            <button
              onClick={bulkReclassify}
              disabled={reclassifying}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-emerald-500 hover:border-emerald-300 transition-colors shadow-sm shrink-0 disabled:opacity-50"
              title={reclassifyResult || "AI 일괄 재분류"}
            >
              {reclassifying ? (
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                </svg>
              )}
            </button>

            {/* 중복 감지 — 문서 두 장 */}
            <button
              onClick={findDuplicates}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-amber-500 hover:border-amber-300 transition-colors shadow-sm shrink-0"
              title="중복 노트 감지"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75" />
              </svg>
            </button>

            {/* 새로고침 — 회전 화살표 */}
            <button
              onClick={() => { offsetRef.current = 0; setNotes([]); setHasMore(true); loadNotes(true); }}
              disabled={loading}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm disabled:opacity-50 shrink-0"
              title="새로고침"
            >
              <svg className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
        </header>

        {/* 노트 목록 */}
        <div className="max-w-3xl mx-auto px-4 sm:px-8 py-5 sm:py-6">
          <div className="flex items-center justify-between mb-4 sm:mb-5">
            <h2 className="text-slate-700 font-semibold text-base">
              {category ? category : "전체 노트"}
            </h2>
            <div className="flex items-center gap-2">
              {selectMode && selectedIds.size > 0 && (
                <span className="text-xs text-indigo-600 font-medium">{selectedIds.size}개 선택됨</span>
              )}
              {!loading && <span className="text-xs text-slate-400">{notes.length}개</span>}
            </div>
          </div>

          {/* 첫 로딩 스피너 */}
          {loading && notes.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 gap-3">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-400 text-sm">불러오는 중...</p>
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
                {query ? "다른 키워드로 검색해보세요" : "텔레그램이나 📁 파일 업로드로 메모를 추가하세요"}
              </p>
            </div>
          )}

          {/* 카드 목록 */}
          <div className="space-y-3">
            {sortedNotes.map((note) => (
              <div key={note.id} className="relative group">
                {/* 핀 버튼 */}
                <button
                  onClick={() => togglePin(note.id)}
                  className={`absolute -top-1 -right-1 z-10 w-6 h-6 rounded-full flex items-center justify-center text-[11px] transition-all shadow-sm ${
                    pinnedIds.has(note.id)
                      ? "bg-amber-400 text-white opacity-100"
                      : "bg-white border border-slate-200 text-slate-400 opacity-0 group-hover:opacity-100"
                  }`}
                  title={pinnedIds.has(note.id) ? "핀 해제" : "핀 고정"}
                >
                  📌
                </button>

                {/* 선택 체크박스 */}
                {selectMode && (
                  <button
                    onClick={() => toggleSelect(note.id)}
                    className={`absolute top-3 left-3 z-10 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      selectedIds.has(note.id)
                        ? "bg-indigo-500 border-indigo-500 text-white"
                        : "border-slate-300 bg-white"
                    }`}
                  >
                    {selectedIds.has(note.id) && (
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                )}

                <div className={selectMode ? "pl-8" : ""}>
                  <NoteCard
                    note={note}
                    onDelete={(id) => setNotes((prev) => prev.filter((n) => n.id !== id))}
                    onUpdate={(updated) => setNotes((prev) => prev.map((n) => n.id === updated.id ? updated : n))}
                  />
                </div>

                {/* 핀된 노트 표시 */}
                {pinnedIds.has(note.id) && (
                  <div className="absolute top-3 left-3 z-10">
                    <span className="text-[10px] bg-amber-100 text-amber-700 border border-amber-200 rounded-full px-1.5 py-0.5 font-medium">핀</span>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* 무한 스크롤 sentinel */}
          <div ref={sentinelRef} className="h-10" />

          {/* 추가 페이지 로딩 */}
          {loading && notes.length > 0 && (
            <div className="flex justify-center py-4">
              <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!loading && !hasMore && notes.length > 0 && (
            <p className="text-center text-xs text-slate-400 py-4">모든 노트를 불러왔습니다</p>
          )}
        </div>
      </main>

      {/* 다중 선택 액션 바 */}
      {selectMode && (
        <div className="fixed bottom-0 left-0 right-0 z-40 bg-white border-t border-slate-200 shadow-lg sm:left-60">
          <div className="max-w-3xl mx-auto px-4 sm:px-8 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-slate-600">
              <span className="font-medium">{selectedIds.size}개 선택됨</span>
              <button onClick={() => setSelectedIds(new Set<string>(notes.map((n) => n.id)))} className="text-indigo-500 hover:underline text-xs">전체 선택</button>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => doExport("json")}
                disabled={selectedIds.size === 0 || exporting}
                className="text-sm px-3 py-1.5 rounded-lg border border-violet-200 text-violet-600 hover:bg-violet-50 disabled:opacity-40 transition-colors"
              >
                📤 내보내기
              </button>
              <button
                onClick={bulkDelete}
                disabled={selectedIds.size === 0 || bulkDeleting}
                className="text-sm px-3 py-1.5 rounded-lg bg-red-500 text-white hover:bg-red-600 disabled:opacity-40 transition-colors"
              >
                {bulkDeleting ? "삭제 중..." : `🗑 ${selectedIds.size}개 삭제`}
              </button>
              <button onClick={exitSelectMode} className="text-sm px-3 py-1.5 rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 transition-colors">
                취소
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 파일 업로드 모달 */}
      {showUpload && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowUpload(false); }}
        >
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800">📁 파일·이미지 업로드</h2>
              <button onClick={() => setShowUpload(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
            </div>
            <p className="text-sm text-slate-500 mb-4">
              텍스트 파일, PDF, Word, 이미지를 업로드하면 Claude AI가 자동 분류하여 저장합니다. 이미지는 OCR로 텍스트를 추출합니다.
            </p>
            <FileUpload
              onUploaded={(newNotes) => {
                setNotes((prev) => [...(newNotes as unknown as Note[]), ...prev]);
                setTimeout(() => setShowUpload(false), 1500);
              }}
            />
          </div>
        </div>
      )}

      {/* 중복 감지 모달 */}
      {showDup && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 px-0 sm:px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowDup(false); }}
        >
          <div className="bg-white rounded-t-2xl sm:rounded-2xl shadow-2xl w-full sm:max-w-xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200">
              <h2 className="font-bold text-slate-800">🔁 중복 노트 감지</h2>
              <button onClick={() => setShowDup(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
            </div>

            <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
              {dupLoading && (
                <div className="flex justify-center py-8">
                  <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                </div>
              )}

              {!dupLoading && dupPairs.length === 0 && (
                <div className="text-center py-8 text-slate-400">
                  <p className="text-3xl mb-2">✅</p>
                  <p>중복 노트가 없습니다!</p>
                </div>
              )}

              {dupPairs.map((pair, i) => (
                <div key={i} className="border border-amber-200 rounded-xl p-4 bg-amber-50">
                  <div className="flex flex-wrap gap-1 mb-3">
                    {pair.common_keywords.map((kw) => (
                      <span key={kw} className="text-xs bg-amber-200 text-amber-800 rounded-full px-2 py-0.5">{kw}</span>
                    ))}
                    <span className="text-xs text-amber-600 ml-auto">공통 {pair.score}개</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    {([pair.note_a, pair.note_b] as const).map((n, idx) => (
                      <div key={n.id} className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-slate-700 text-xs line-clamp-3">{n.summary || "(요약 없음)"}</p>
                        <p className="text-slate-400 text-[10px] mt-1">
                          {n.category} · {new Date(n.created_at).toLocaleDateString("ko-KR")}
                        </p>
                        <button
                          onClick={() =>
                            idx === 0
                              ? mergeNotes(pair.note_a.id, pair.note_b.id)
                              : mergeNotes(pair.note_b.id, pair.note_a.id)
                          }
                          disabled={mergingId === (idx === 0 ? pair.note_b.id : pair.note_a.id)}
                          className="mt-2 text-[11px] text-red-500 hover:text-red-700 underline disabled:opacity-40"
                        >
                          이쪽 유지 (나머지 삭제)
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
