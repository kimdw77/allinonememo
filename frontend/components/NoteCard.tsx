"use client";

/**
 * NoteCard.tsx — 노트 카드 (편집 + 연관 노트 패널 포함)
 */
import { useState } from "react";

interface RelatedLink {
  title: string;
  url: string;
  description?: string;
  published_date?: string;
}

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
    articles?: RelatedLink[];
    images?: string[];
    search_query?: string;
  };
}

interface NoteCardProps {
  note: Note;
  onDelete?: (id: string) => void;
  onUpdate?: (updated: Note) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  "비즈니스": "bg-blue-100 text-blue-700 border-blue-200",
  "기술":     "bg-emerald-100 text-emerald-700 border-emerald-200",
  "무역/수출": "bg-amber-100 text-amber-700 border-amber-200",
  "건강":     "bg-red-100 text-red-700 border-red-200",
  "교육":     "bg-purple-100 text-purple-700 border-purple-200",
  "뉴스":     "bg-sky-100 text-sky-700 border-sky-200",
  "개인메모":  "bg-pink-100 text-pink-700 border-pink-200",
  "기타":     "bg-slate-100 text-slate-600 border-slate-200",
};

const CATEGORY_ACCENT: Record<string, string> = {
  "비즈니스": "border-l-blue-400",
  "기술":     "border-l-emerald-400",
  "무역/수출": "border-l-amber-400",
  "건강":     "border-l-red-400",
  "교육":     "border-l-purple-400",
  "뉴스":     "border-l-sky-400",
  "개인메모":  "border-l-pink-400",
  "기타":     "border-l-slate-300",
};

const SOURCE_ICON: Record<string, string> = {
  telegram: "✈️", kakao: "💬", youtube: "▶️", rss: "📡", manual: "✏️",
};
const SOURCE_LABEL: Record<string, string> = {
  telegram: "텔레그램", kakao: "카카오", youtube: "유튜브", rss: "RSS", manual: "직접입력",
};

const FALLBACK_CATEGORIES = ["비즈니스", "기술", "무역/수출", "건강", "교육", "뉴스", "개인메모", "기타"];

interface RelatedNote {
  id: string;
  summary: string;
  keywords: string[];
  category: string;
}

export default function NoteCard({ note, onDelete, onUpdate }: NoteCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reclassifying, setReclassifying] = useState(false);

  // 편집 폼 상태
  const [editSummary, setEditSummary] = useState(note.summary || "");
  const [editKeywords, setEditKeywords] = useState((note.keywords || []).join(", "));
  const [editCategory, setEditCategory] = useState(note.category || "기타");
  const [categories, setCategories] = useState<string[]>(FALLBACK_CATEGORIES);

  // 연관 노트
  const [related, setRelated] = useState<RelatedNote[]>([]);
  const [relatedLoaded, setRelatedLoaded] = useState(false);
  const [relatedLoading, setRelatedLoading] = useState(false);

  const handleDelete = async () => {
    if (!confirm("이 노트를 삭제할까요?")) return;
    const res = await fetch(`/api/notes/${note.id}`, { method: "DELETE" });
    if (res.ok && onDelete) onDelete(note.id);
  };

  const handleReclassify = async () => {
    if (!confirm("AI로 요약·키워드·카테고리를 다시 분류할까요?")) return;
    setReclassifying(true);
    try {
      const res = await fetch(`/api/notes/${note.id}/reclassify`, { method: "POST" });
      if (res.ok && onUpdate) onUpdate(await res.json());
    } finally {
      setReclassifying(false);
    }
  };

  const handleEditOpen = async () => {
    setEditSummary(note.summary || "");
    setEditKeywords((note.keywords || []).join(", "));
    setEditCategory(note.category || "기타");
    setEditing(true);
    // 편집 시 최신 카테고리 목록을 서버에서 로드
    try {
      const res = await fetch("/api/categories");
      if (res.ok) {
        const data: Array<{ name: string }> = await res.json();
        const names = data.map((d) => d.name);
        if (!names.includes("기타")) names.push("기타");
        setCategories(names);
      }
    } catch { /* 실패 시 fallback 목록 유지 */ }
  };

  const handleSave = async () => {
    setSaving(true);
    const keywords = editKeywords
      .split(",")
      .map((k) => k.trim())
      .filter(Boolean);

    const res = await fetch(`/api/notes/${note.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        summary: editSummary,
        keywords,
        category: editCategory,
      }),
    });

    if (res.ok && onUpdate) {
      const updated = await res.json();
      onUpdate(updated);
    }
    setSaving(false);
    setEditing(false);
  };

  const handleExpand = async () => {
    const next = !expanded;
    setExpanded(next);
    if (next && !relatedLoaded) {
      setRelatedLoading(true);
      try {
        const res = await fetch(`/api/notes/${note.id}/related`);
        if (res.ok) setRelated(await res.json());
      } catch {
        // 연관 노트 로드 실패 시 조용히 무시
      }
      setRelatedLoaded(true);
      setRelatedLoading(false);
    }
  };

  const badgeClass = CATEGORY_COLORS[note.category] ?? "bg-slate-100 text-slate-600 border-slate-200";
  const accentClass = CATEGORY_ACCENT[note.category] ?? "border-l-slate-300";
  const icon = SOURCE_ICON[note.source] ?? "📌";
  const sourceLabel = SOURCE_LABEL[note.source] ?? note.source;
  const date = new Date(note.created_at).toLocaleDateString("ko-KR", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });

  return (
    <article
      className={`bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 border-l-4 ${accentClass} p-4 sm:p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200`}
    >
      {/* 상단: 소스·카테고리 / 날짜·액션 */}
      <div className="flex flex-wrap items-center justify-between gap-y-1.5 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm shrink-0">{icon}</span>
          <span className="text-sm sm:text-xs text-slate-400 dark:text-slate-500 shrink-0">{sourceLabel}</span>
          <span className={`text-sm sm:text-xs font-medium px-2 py-0.5 rounded-full border shrink-0 ${badgeClass}`}>
            {note.category}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <time className="text-sm sm:text-xs text-slate-400 dark:text-slate-500">{date}</time>
          {/* 재분류 버튼 */}
          <button
            onClick={handleReclassify}
            disabled={reclassifying}
            className="text-slate-300 hover:text-emerald-400 disabled:opacity-40 transition-colors p-0.5 rounded"
            title="AI 재분류"
          >
            {reclassifying ? (
              <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            ) : (
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            )}
          </button>
          {/* 편집 버튼 */}
          <button
            onClick={handleEditOpen}
            className="text-slate-300 hover:text-indigo-400 transition-colors p-0.5 rounded"
            title="편집"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
          {onDelete && (
            <button
              onClick={handleDelete}
              className="text-slate-300 hover:text-red-400 transition-colors p-0.5 rounded"
              title="삭제"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* 편집 폼 */}
      {editing ? (
        <div className="mb-3 space-y-2.5 bg-slate-50 dark:bg-slate-700/50 rounded-lg p-3 border border-slate-200 dark:border-slate-600">
          <div>
            <label className="text-sm sm:text-xs text-slate-500 dark:text-slate-400 mb-1 block">요약</label>
            <textarea
              value={editSummary}
              onChange={(e) => setEditSummary(e.target.value)}
              rows={3}
              className="w-full text-sm text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-400 resize-none"
            />
          </div>
          <div>
            <label className="text-sm sm:text-xs text-slate-500 dark:text-slate-400 mb-1 block">키워드 (쉼표로 구분)</label>
            <input
              value={editKeywords}
              onChange={(e) => setEditKeywords(e.target.value)}
              className="w-full text-sm text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-400"
            />
          </div>
          <div>
            <label className="text-sm sm:text-xs text-slate-500 dark:text-slate-400 mb-1 block">카테고리</label>
            <select
              value={editCategory}
              onChange={(e) => setEditCategory(e.target.value)}
              className="w-full text-sm text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-400"
            >
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div className="flex gap-2 justify-end pt-1">
            <button
              onClick={() => setEditing(false)}
              className="text-xs text-slate-500 hover:text-slate-700 px-3 py-1.5 rounded-lg border border-slate-200 bg-white transition-colors"
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-xs text-white bg-indigo-500 hover:bg-indigo-600 disabled:opacity-50 px-3 py-1.5 rounded-lg transition-colors"
            >
              {saving ? "저장 중…" : "저장"}
            </button>
          </div>
        </div>
      ) : (
        <>
          {/* 요약 */}
          {note.summary ? (
            <p className="text-slate-800 dark:text-slate-100 text-base sm:text-sm leading-relaxed mb-3 font-medium">
              {note.summary}
            </p>
          ) : (
            <p className="text-slate-500 dark:text-slate-400 text-base sm:text-sm leading-relaxed mb-3 italic">
              {note.raw_content.length > 120
                ? note.raw_content.slice(0, 120) + "..."
                : note.raw_content}
            </p>
          )}

          {/* 하이라이트 */}
          {note.highlights && note.highlights.length > 0 && (
            <div className="mb-3 space-y-1.5">
              {note.highlights.map((hl, i) => (
                <p
                  key={i}
                  className="text-sm text-slate-700 leading-relaxed px-2 py-1 rounded"
                  style={{ background: "linear-gradient(120deg, #fef08a 0%, #fef9c3 100%)" }}
                >
                  {hl}
                </p>
              ))}
            </div>
          )}

          {/* 원본 미디어 (사진 미리보기 / 음성 플레이어) */}
          {note.file_url && (() => {
            const ct = note.content_type ?? "";
            const isImage = ["image", "newspaper", "article", "photo"].includes(ct);
            const isVoice = ["voice", "audio"].includes(ct);
            if (isImage) return (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={note.file_url!}
                alt="원본 이미지"
                className="w-full max-h-52 object-cover rounded-lg mb-3 border border-slate-100 dark:border-slate-700"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            );
            if (isVoice) return (
              <audio
                controls
                src={note.file_url!}
                className="w-full mb-3 rounded-lg"
              />
            );
            return null;
          })()}

          {/* URL */}
          {note.url && (
            <a
              href={note.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-sm sm:text-xs text-indigo-500 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline truncate mb-3"
            >
              <span>🔗</span>
              <span className="truncate">{note.url}</span>
            </a>
          )}

          {/* 키워드 태그 */}
          {note.keywords && note.keywords.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {note.keywords.map((kw) => (
                <span
                  key={kw}
                  className="text-sm sm:text-xs px-2 py-0.5 bg-slate-50 dark:bg-slate-700 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-600 rounded-full"
                >
                  #{kw}
                </span>
              ))}
            </div>
          )}

          {/* 관련 기사 (신문 OCR) */}
          {note.related_links?.articles && note.related_links.articles.length > 0 && (
            <div className="mb-2 border border-sky-100 dark:border-sky-900 rounded-lg p-2.5 bg-sky-50 dark:bg-sky-900/20">
              <p className="text-sm sm:text-[11px] font-semibold text-sky-600 dark:text-sky-400 mb-1.5">📰 관련 기사</p>
              <div className="space-y-1">
                {note.related_links.articles.slice(0, 3).map((article, i) => (
                  <a
                    key={i}
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-1 text-sm sm:text-xs text-sky-700 dark:text-sky-400 hover:text-sky-900 dark:hover:text-sky-200 hover:underline"
                  >
                    <span className="shrink-0 mt-0.5 text-sky-400">•</span>
                    <span className="line-clamp-1">{article.title}</span>
                  </a>
                ))}
              </div>
              {note.related_links.images && note.related_links.images.length > 0 && (
                <div className="flex gap-1.5 mt-2 overflow-x-auto">
                  {note.related_links.images.slice(0, 3).map((img, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={i}
                      src={img}
                      alt=""
                      className="h-14 w-20 object-cover rounded shrink-0 border border-sky-100 dark:border-sky-900"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* 원문 펼치기 + 연관 노트 */}
      {!editing && note.raw_content && (
        <div className="border-t border-slate-100 dark:border-slate-700 pt-2 mt-1">
          <button
            onClick={handleExpand}
            className="text-sm sm:text-xs text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors flex items-center gap-1"
          >
            <svg
              className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {expanded ? "접기" : "원문 + 연관 노트 보기"}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3">
              {/* 원문 */}
              <p className="text-sm sm:text-xs text-slate-500 dark:text-slate-400 leading-relaxed whitespace-pre-wrap bg-slate-50 dark:bg-slate-700 rounded-lg p-3">
                {note.raw_content}
              </p>

              {/* 연관 노트 */}
              {relatedLoading && (
                <p className="text-xs text-slate-400 dark:text-slate-500 text-center py-2">연관 노트 로딩 중…</p>
              )}
              {!relatedLoading && related.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">🔗 연관 노트</p>
                  <div className="space-y-1.5">
                    {related.map((r) => (
                      <div
                        key={r.id}
                        className="bg-slate-50 dark:bg-slate-700 rounded-lg px-3 py-2 border border-slate-100 dark:border-slate-600"
                      >
                        <p className="text-sm sm:text-xs text-slate-700 dark:text-slate-300 leading-snug line-clamp-2">
                          {r.summary || "(요약 없음)"}
                        </p>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {(r.keywords || []).slice(0, 4).map((kw) => (
                            <span key={kw} className="text-[10px] text-slate-400">#{kw}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {!relatedLoading && relatedLoaded && related.length === 0 && (
                <p className="text-xs text-slate-400 text-center py-1">연관 노트 없음</p>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
