"use client";

/**
 * NoteCard.tsx — 노트 카드 컴포넌트 (리디자인)
 */
import { useState } from "react";
interface NoteCardProps {
  note: {
    id: string;
    source: string;
    raw_content: string;
    summary: string;
    keywords: string[];
    category: string;
    content_type: string;
    url: string | null;
    created_at: string;
  };
  onDelete?: (id: string) => void;
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
  telegram: "✈️",
  kakao: "💬",
  youtube: "▶️",
  rss: "📡",
  manual: "✏️",
};

const SOURCE_LABEL: Record<string, string> = {
  telegram: "텔레그램",
  kakao: "카카오",
  youtube: "유튜브",
  rss: "RSS",
  manual: "직접입력",
};

export default function NoteCard({ note, onDelete }: NoteCardProps) {
  const [expanded, setExpanded] = useState(false);

  const handleDelete = async () => {
    if (!confirm("이 노트를 삭제할까요?")) return;
    const res = await fetch(`/api/notes/${note.id}`, { method: "DELETE" });
    if (res.ok && onDelete) onDelete(note.id);
  };
  const badgeClass = CATEGORY_COLORS[note.category] ?? "bg-slate-100 text-slate-600 border-slate-200";
  const accentClass = CATEGORY_ACCENT[note.category] ?? "border-l-slate-300";
  const icon = SOURCE_ICON[note.source] ?? "📌";
  const sourceLabel = SOURCE_LABEL[note.source] ?? note.source;

  const date = new Date(note.created_at).toLocaleDateString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <article
      className={`bg-white rounded-xl border border-slate-200 border-l-4 ${accentClass} p-4 sm:p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200`}
    >
      {/* 상단: 소스·카테고리 / 날짜·삭제 — 모바일에서 두 줄로 자연스럽게 wrap */}
      <div className="flex flex-wrap items-center justify-between gap-y-1.5 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm shrink-0">{icon}</span>
          <span className="text-xs text-slate-400 shrink-0">{sourceLabel}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full border shrink-0 ${badgeClass}`}>
            {note.category}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <time className="text-xs text-slate-400">{date}</time>
          {onDelete && (
            <button
              onClick={handleDelete}
              className="text-slate-300 hover:text-red-400 transition-colors p-0.5 rounded"
              title="삭제"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* 요약 (있을 때만) */}
      {note.summary ? (
        <p className="text-slate-800 text-sm leading-relaxed mb-3 font-medium">
          {note.summary}
        </p>
      ) : (
        <p className="text-slate-500 text-sm leading-relaxed mb-3 italic">
          {note.raw_content.length > 120
            ? note.raw_content.slice(0, 120) + "..."
            : note.raw_content}
        </p>
      )}

      {/* URL */}
      {note.url && (
        <a
          href={note.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-indigo-500 hover:text-indigo-700 hover:underline truncate mb-3 group"
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
              className="text-xs px-2 py-0.5 bg-slate-50 text-slate-500 border border-slate-200 rounded-full"
            >
              #{kw}
            </span>
          ))}
        </div>
      )}

      {/* 원문 펼치기 */}
      {note.raw_content && (
        <div className="border-t border-slate-100 pt-2 mt-1">
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-1"
          >
            <svg
              className={`w-3 h-3 transition-transform ${expanded ? "rotate-90" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {expanded ? "원문 접기" : "원문 보기"}
          </button>
          {expanded && (
            <p className="mt-2 text-xs text-slate-500 leading-relaxed whitespace-pre-wrap bg-slate-50 rounded-lg p-3">
              {note.raw_content}
            </p>
          )}
        </div>
      )}
    </article>
  );
}
