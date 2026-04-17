/**
 * NoteCard.tsx — 노트 카드 컴포넌트 (리디자인)
 */
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

export default function NoteCard({ note }: NoteCardProps) {
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
      className={`bg-white rounded-xl border border-slate-200 border-l-4 ${accentClass} p-5 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200`}
    >
      {/* 상단: 소스·카테고리·날짜 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">{icon}</span>
          <span className="text-xs text-slate-400">{sourceLabel}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${badgeClass}`}>
            {note.category}
          </span>
        </div>
        <time className="text-xs text-slate-400 shrink-0">{date}</time>
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
        <div className="flex flex-wrap gap-1.5">
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
    </article>
  );
}
