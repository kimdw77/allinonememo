"use client";

/**
 * Sidebar.tsx — 좌측 사이드바: 로고, 카테고리 필터, 관리, 로그아웃
 * 카테고리 목록은 /api/categories에서 동적 로드
 */
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

interface Category {
  id: number;
  name: string;
  icon: string;
  color: string;
}

interface SidebarProps {
  selected: string;
  onSelect: (category: string) => void;
  noteCount: number;
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ selected, onSelect, noteCount, isOpen, onClose }: SidebarProps) {
  const router = useRouter();
  const [categories, setCategories] = useState<Category[]>([]);
  const [managing, setManaging] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIcon, setNewIcon] = useState("📁");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  const fetchCategories = async () => {
    try {
      const res = await fetch("/api/categories");
      if (res.ok) setCategories(await res.json());
    } catch {
      // 조회 실패 시 빈 목록 유지
    }
  };

  useEffect(() => { fetchCategories(); }, []);

  const handleLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  const handleSelect = (value: string) => {
    onSelect(value);
    onClose();
  };

  const handleAdd = async () => {
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    setError("");
    const res = await fetch("/api/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, icon: newIcon, color: "#6366f1" }),
    });
    if (res.ok) {
      setNewName("");
      setNewIcon("📁");
      await fetchCategories();
    } else {
      const data = await res.json().catch(() => ({}));
      setError(data.detail ?? "추가 실패");
    }
    setAdding(false);
  };

  const handleDelete = async (name: string) => {
    const res = await fetch(`/api/categories/${encodeURIComponent(name)}`, { method: "DELETE" });
    if (res.ok) {
      if (selected === name) onSelect("");
      await fetchCategories();
    }
  };

  return (
    <>
      {/* 모바일 오버레이 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 sm:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-screen w-60 bg-slate-900 flex flex-col z-30
          transition-transform duration-300 ease-in-out
          ${isOpen ? "translate-x-0" : "-translate-x-full"}
          sm:translate-x-0
        `}
      >
        {/* 로고 */}
        <div className="px-5 py-6 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center text-sm shadow-lg shadow-indigo-500/30">
                🗄️
              </div>
              <div>
                <h1 className="text-white font-bold text-base leading-none">MyVault</h1>
                <p className="text-slate-500 text-xs mt-0.5">AI 지식저장소</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="sm:hidden text-slate-500 hover:text-slate-300 transition-colors p-1"
              aria-label="사이드바 닫기"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div className="mt-3 text-xs text-slate-600">총 {noteCount}개의 노트</div>
        </div>

        {/* 카테고리 */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <div className="flex items-center justify-between px-2 mb-2">
            <p className="text-xs font-medium text-slate-600 uppercase tracking-wider">카테고리</p>
            <button
              onClick={() => { setManaging((v) => !v); setError(""); }}
              className="text-xs text-slate-500 hover:text-indigo-400 transition-colors"
              title="카테고리 관리"
            >
              {managing ? "완료" : "관리"}
            </button>
          </div>

          {/* 추가 폼 (관리 모드) */}
          {managing && (
            <div className="mb-3 px-1 space-y-1.5">
              <div className="flex gap-1">
                <input
                  value={newIcon}
                  onChange={(e) => setNewIcon(e.target.value)}
                  placeholder="📁"
                  className="w-10 bg-slate-800 text-white text-center text-sm rounded px-1 py-1 outline-none focus:ring-1 focus:ring-indigo-500"
                  maxLength={2}
                />
                <input
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                  placeholder="새 카테고리명"
                  className="flex-1 bg-slate-800 text-white text-sm rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-600"
                  maxLength={30}
                />
                <button
                  onClick={handleAdd}
                  disabled={adding || !newName.trim()}
                  className="text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded px-2 py-1 transition-colors"
                >
                  추가
                </button>
              </div>
              {error && <p className="text-xs text-red-400 px-1">{error}</p>}
            </div>
          )}

          <ul className="space-y-0.5">
            {/* 전체 버튼 */}
            <li>
              <button
                onClick={() => handleSelect("")}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                  selected === ""
                    ? "bg-indigo-500/20 text-indigo-400 font-medium"
                    : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                <span className="text-base w-5 text-center">◈</span>
                <span>전체</span>
              </button>
            </li>

            {categories.map((cat) => (
              <li key={cat.name} className="flex items-center gap-1">
                <button
                  onClick={() => handleSelect(cat.name)}
                  className={`flex-1 flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                    selected === cat.name
                      ? "bg-indigo-500/20 text-indigo-400 font-medium"
                      : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                  }`}
                >
                  <span className="text-base w-5 text-center">{cat.icon}</span>
                  <span>{cat.name}</span>
                </button>

                {/* 삭제 버튼 (관리 모드 + '기타' 제외) */}
                {managing && cat.name !== "기타" && (
                  <button
                    onClick={() => handleDelete(cat.name)}
                    className="text-slate-600 hover:text-red-400 transition-colors p-1 rounded"
                    title={`${cat.name} 삭제`}
                  >
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
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
    </>
  );
}
