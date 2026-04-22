"use client";

/**
 * app/page.tsx — 메인 대시보드
 * 무한 스크롤 + 파일 업로드 + 중복 감지 패널
 */
import { useState, useEffect, useCallback, useRef } from "react";
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
  created_at: string;
}

interface DupNote { id: string; summary: string; category: string; created_at: string }
interface DupPair {
  note_a: DupNote;
  note_b: DupNote;
  common_keywords: string[];
  score: number;
}

const PAGE_SIZE = 20;

export default function DashboardPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // 모달 상태
  const [showUpload, setShowUpload] = useState(false);
  const [showDup, setShowDup] = useState(false);
  const [dupPairs, setDupPairs] = useState<DupPair[]>([]);
  const [dupLoading, setDupLoading] = useState(false);
  const [mergingId, setMergingId] = useState<string | null>(null);

  const sentinelRef = useRef<HTMLDivElement>(null);
  const offsetRef = useRef(0);

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

            {/* 검색 */}
            <div className="relative flex-1">
              <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 text-sm">🔍</span>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="메모·요약·키워드 검색..."
                className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-200 bg-white text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent shadow-sm"
              />
            </div>

            {/* 파일 업로드 */}
            <button
              onClick={() => setShowUpload(true)}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-indigo-500 hover:border-indigo-300 transition-colors shadow-sm shrink-0 text-base"
              title="파일 업로드 (아이폰 노트 등)"
            >
              📁
            </button>

            {/* 중복 감지 */}
            <button
              onClick={findDuplicates}
              className="p-2.5 rounded-xl border border-slate-200 bg-white text-slate-500 hover:text-amber-500 hover:border-amber-300 transition-colors shadow-sm shrink-0 text-base"
              title="중복 노트 감지"
            >
              🔁
            </button>

            {/* 새로고침 */}
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
            {!loading && <span className="text-xs text-slate-400">{notes.length}개</span>}
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
            {notes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                onDelete={(id) => setNotes((prev) => prev.filter((n) => n.id !== id))}
                onUpdate={(updated) => setNotes((prev) => prev.map((n) => n.id === updated.id ? updated : n))}
              />
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

      {/* 파일 업로드 모달 */}
      {showUpload && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setShowUpload(false); }}
        >
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800">📁 파일 업로드</h2>
              <button onClick={() => setShowUpload(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">✕</button>
            </div>
            <p className="text-sm text-slate-500 mb-4">
              아이폰 메모·텍스트 파일을 업로드하면 Claude AI가 자동 분류하여 저장합니다.
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
