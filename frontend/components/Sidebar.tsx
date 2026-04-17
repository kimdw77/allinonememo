"use client";

/**
 * Sidebar.tsx — 좌측 사이드바: 로고, 카테고리 필터, 로그아웃
 */
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

interface SidebarProps {
  selected: string;
  onSelect: (category: string) => void;
  noteCount: number;
}

const CATEGORIES = [
  { label: "전체", value: "", icon: "◈" },
  { label: "비즈니스", value: "비즈니스", icon: "💼" },
  { label: "기술", value: "기술", icon: "⚙️" },
  { label: "무역/수출", value: "무역/수출", icon: "🚢" },
  { label: "건강", value: "건강", icon: "🩺" },
  { label: "교육", value: "교육", icon: "📚" },
  { label: "뉴스", value: "뉴스", icon: "📰" },
  { label: "개인메모", value: "개인메모", icon: "✏️" },
  { label: "기타", value: "기타", icon: "📌" },
];

export default function Sidebar({ selected, onSelect, noteCount }: SidebarProps) {
  const router = useRouter();

  const handleLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  return (
    <aside className="fixed top-0 left-0 h-screen w-60 bg-slate-900 flex flex-col z-10">
      {/* 로고 */}
      <div className="px-5 py-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center text-sm shadow-lg shadow-indigo-500/30">
            🗄️
          </div>
          <div>
            <h1 className="text-white font-bold text-base leading-none">MyVault</h1>
            <p className="text-slate-500 text-xs mt-0.5">AI 지식저장소</p>
          </div>
        </div>
        <div className="mt-3 text-xs text-slate-600">
          총 {noteCount}개의 노트
        </div>
      </div>

      {/* 카테고리 */}
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        <p className="text-xs font-medium text-slate-600 uppercase tracking-wider px-2 mb-2">
          카테고리
        </p>
        <ul className="space-y-0.5">
          {CATEGORIES.map((cat) => (
            <li key={cat.value}>
              <button
                onClick={() => onSelect(cat.value)}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                  selected === cat.value
                    ? "bg-indigo-500/20 text-indigo-400 font-medium"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                <span className="text-base w-5 text-center">{cat.icon}</span>
                <span>{cat.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {/* 로그아웃 */}
      <div className="px-3 py-4 border-t border-slate-800">
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors"
        >
          <span className="text-base w-5 text-center">🚪</span>
          <span>로그아웃</span>
        </button>
      </div>
    </aside>
  );
}
