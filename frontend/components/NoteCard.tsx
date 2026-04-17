interface NoteCardProps {
  note: {
    id: string;
    source: string;
    summary: string;
    keywords: string[];
    category: string;
    content_type: string;
    url: string | null;
    created_at: string;
  };
}

// 카테고리별 배지 색상
const CATEGORY_COLORS: Record<string, string> = {
  "비즈니스": "bg-blue-100 text-blue-700",
  "기술":     "bg-emerald-100 text-emerald-700",
  "무역/수출": "bg-amber-100 text-amber-700",
  "건강":     "bg-red-100 text-red-700",
  "교육":     "bg-purple-100 text-purple-700",
  "뉴스":     "bg-slate-100 text-slate-600",
  "개인메모":  "bg-pink-100 text-pink-700",
  "기타":     "bg-gray-100 text-gray-600",
};

// 소스 아이콘
const SOURCE_ICON: Record<string, string> = {
  telegram: "✈️",
  kakao: "💬",
  youtube: "▶️",
  rss: "📡",
  manual: "✏️",
};

export default function NoteCard({ note }: NoteCardProps) {
  const badgeClass = CATEGORY_COLORS[note.category] ?? "bg-gray-100 text-gray-600";
  const icon = SOURCE_ICON[note.source] ?? "📌";
  const date = new Date(note.created_at).toLocaleDateString("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <article className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md transition-shadow">
      {/* 상단: 소스·카테고리·날짜 */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base">{icon}</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badgeClass}`}>
            {note.category}
          </span>
        </div>
        <time className="text-xs text-slate-400">{date}</time>
      </div>

      {/* 요약 */}
      {note.summary && (
        <p className="text-slate-800 text-sm leading-relaxed mb-3">
          {note.summary}
        </p>
      )}

      {/* URL */}
      {note.url && (
        <a
          href={note.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-indigo-500 hover:underline truncate block mb-3"
        >
          {note.url}
        </a>
      )}

      {/* 키워드 태그 */}
      {note.keywords && note.keywords.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {note.keywords.map((kw) => (
            <span
              key={kw}
              className="text-xs px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full"
            >
              #{kw}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
