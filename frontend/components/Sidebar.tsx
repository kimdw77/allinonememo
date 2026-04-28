"use client";

/**
 * Sidebar.tsx — 좌측 사이드바
 * 카테고리: 드래그앤드롭 순서 변경 + 인라인 이름·아이콘 변경 + 삭제
 * 순서는 localStorage에 저장 (DB 변경 없음)
 */
import { useState, useEffect, useRef, DragEvent } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
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

const ORDER_KEY = "myvault_cat_order";

function applyOrder(cats: Category[], order: string[]): Category[] {
  if (!order.length) return cats;
  const map = new Map(cats.map((c) => [c.name, c]));
  const ordered: Category[] = [];
  order.forEach((name) => { if (map.has(name)) { ordered.push(map.get(name)!); map.delete(name); } });
  map.forEach((c) => ordered.push(c));
  return ordered;
}

export default function Sidebar({ selected, onSelect, noteCount, isOpen, onClose }: SidebarProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [categories, setCategories] = useState<Category[]>([]);
  const [managing, setManaging] = useState(false);

  // 추가 폼
  const [newName, setNewName] = useState("");
  const [newIcon, setNewIcon] = useState("📁");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  // 인라인 이름 변경
  const [editingName, setEditingName] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editIcon, setEditIcon] = useState("");
  const editInputRef = useRef<HTMLInputElement>(null);

  // 카테고리 통합 모달
  const [mergeSource, setMergeSource] = useState<string | null>(null);
  const [mergeTarget, setMergeTarget] = useState("");
  const [merging, setMerging] = useState(false);

  // 드래그앤드롭
  const dragOver = useRef<string | null>(null);
  const [dragTarget, setDragTarget] = useState<string | null>(null);

  const fetchCategories = async () => {
    try {
      const res = await fetch("/api/categories");
      if (!res.ok) return;
      const data: Category[] = await res.json();
      const order = JSON.parse(localStorage.getItem(ORDER_KEY) ?? "[]") as string[];
      setCategories(applyOrder(data, order));
    } catch {}
  };

  useEffect(() => { fetchCategories(); }, []);

  // 편집 시작 시 input 포커스
  useEffect(() => {
    if (editingName) editInputRef.current?.focus();
  }, [editingName]);

  const saveOrder = (cats: Category[]) => {
    localStorage.setItem(ORDER_KEY, JSON.stringify(cats.map((c) => c.name)));
  };

  const handleLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  const handleSelect = (value: string) => { onSelect(value); onClose(); };

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
      setNewName(""); setNewIcon("📁");
      await fetchCategories();
    } else {
      const data = await res.json().catch(() => ({}));
      setError(data.detail ?? "추가 실패");
    }
    setAdding(false);
  };

  // 삭제 → 통합 모달 열기 ('/'가 포함된 이름도 body로 처리)
  const handleDelete = (name: string) => {
    const others = categories.filter((c) => c.name !== name);
    setMergeSource(name);
    setMergeTarget(others[0]?.name ?? "기타");
  };

  // 통합 실행: source 노트를 target으로 이동 후 source 삭제
  const handleMerge = async () => {
    if (!mergeSource) return;
    setMerging(true);
    const res = await fetch("/api/categories?action=merge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: mergeSource, target: mergeTarget }),
    });
    if (res.ok) {
      if (selected === mergeSource) onSelect(mergeTarget);
      const order = JSON.parse(localStorage.getItem(ORDER_KEY) ?? "[]") as string[];
      localStorage.setItem(ORDER_KEY, JSON.stringify(order.filter((n) => n !== mergeSource)));
      await fetchCategories();
    }
    setMergeSource(null);
    setMerging(false);
  };

  // ─── 이름 변경 ─────────────────────────────────

  const startEdit = (cat: Category) => {
    setEditingName(cat.name);
    setEditName(cat.name);
    setEditIcon(cat.icon);
  };

  const cancelEdit = () => { setEditingName(null); setEditName(""); setEditIcon(""); };

  const commitEdit = async () => {
    const trimmed = editName.trim();
    if (!trimmed || !editingName) { cancelEdit(); return; }
    if (trimmed === editingName && editIcon === categories.find(c => c.name === editingName)?.icon) {
      cancelEdit(); return;
    }
    // body 기반 POST — '/'가 포함된 이름도 안전하게 처리
    const res = await fetch("/api/categories?action=update", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: editingName, new_name: trimmed, icon: editIcon }),
    });
    if (res.ok) {
      if (selected === editingName) onSelect(trimmed);
      const order = JSON.parse(localStorage.getItem(ORDER_KEY) ?? "[]") as string[];
      const newOrder = order.map((n) => (n === editingName ? trimmed : n));
      localStorage.setItem(ORDER_KEY, JSON.stringify(newOrder));
      await fetchCategories();
    }
    cancelEdit();
  };

  // ─── 드래그앤드롭 순서 변경 ─────────────────────

  const onDragStart = (name: string) => (e: DragEvent) => {
    e.dataTransfer.effectAllowed = "move";
    dragOver.current = name;
  };

  const onDragEnter = (name: string) => () => setDragTarget(name);

  const onDragEnd = () => {
    const from = dragOver.current;
    const to = dragTarget;
    dragOver.current = null;
    setDragTarget(null);
    if (!from || !to || from === to) return;

    setCategories((prev) => {
      const next = [...prev];
      const fi = next.findIndex((c) => c.name === from);
      const ti = next.findIndex((c) => c.name === to);
      if (fi < 0 || ti < 0) return prev;
      const [item] = next.splice(fi, 1);
      next.splice(ti, 0, item);
      saveOrder(next);
      return next;
    });
  };

  return (
    <>
      {isOpen && (
        <div className="fixed inset-0 bg-black/50 z-20 sm:hidden" onClick={onClose} aria-hidden="true" />
      )}

      <aside
        className={`
          fixed top-0 left-0 h-screen w-60 bg-slate-900 flex flex-col z-30
          transition-transform duration-300 ease-in-out
          ${isOpen ? "translate-x-0" : "-translate-x-full"} sm:translate-x-0
        `}
      >
        {/* 로고 */}
        <div className="px-5 py-6 border-b border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-indigo-500 rounded-lg flex items-center justify-center text-sm shadow-lg shadow-indigo-500/30">🗄️</div>
              <div>
                <h1 className="text-white font-bold text-base leading-none">MyVault</h1>
                <p className="text-slate-500 text-xs mt-0.5">AI 지식저장소</p>
              </div>
            </div>
            <button onClick={onClose} className="sm:hidden text-slate-500 hover:text-slate-300 p-1" aria-label="사이드바 닫기">
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
              onClick={() => { setManaging((v) => !v); setError(""); cancelEdit(); }}
              className="text-xs text-slate-500 hover:text-indigo-400 transition-colors"
            >
              {managing ? "완료" : "관리"}
            </button>
          </div>

          {/* 추가 폼 */}
          {managing && (
            <div className="mb-3 px-1 space-y-1.5">
              <div className="flex gap-1">
                <input value={newIcon} onChange={(e) => setNewIcon(e.target.value)} placeholder="📁"
                  className="w-10 bg-slate-800 text-white text-center text-sm rounded px-1 py-1 outline-none focus:ring-1 focus:ring-indigo-500" maxLength={2} />
                <input value={newName} onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAdd()}
                  placeholder="새 카테고리명"
                  className="flex-1 bg-slate-800 text-white text-sm rounded px-2 py-1 outline-none focus:ring-1 focus:ring-indigo-500 placeholder:text-slate-600" maxLength={30} />
                <button onClick={handleAdd} disabled={adding || !newName.trim()}
                  className="text-xs bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white rounded px-2 py-1 transition-colors">
                  추가
                </button>
              </div>
              {managing && <p className="text-[10px] text-slate-600 px-1">드래그로 순서 변경 · ✏️ 클릭으로 이름 변경</p>}
              {error && <p className="text-xs text-red-400 px-1">{error}</p>}
            </div>
          )}

          <ul className="space-y-0.5">
            {/* 전체 */}
            <li>
              <button onClick={() => handleSelect("")}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                  selected === "" ? "bg-indigo-500/20 text-indigo-400 font-medium" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                }`}>
                <span className="text-base w-5 text-center">◈</span>
                <span>전체</span>
              </button>
            </li>

            {categories.map((cat) => (
              <li
                key={cat.name}
                draggable={managing}
                onDragStart={onDragStart(cat.name)}
                onDragEnter={onDragEnter(cat.name)}
                onDragEnd={onDragEnd}
                onDragOver={(e) => e.preventDefault()}
                className={`flex items-center gap-1 rounded-lg transition-all ${
                  managing && dragTarget === cat.name ? "ring-1 ring-indigo-400 bg-slate-800/50" : ""
                }`}
              >
                {/* 드래그 핸들 */}
                {managing && (
                  <span className="text-slate-700 cursor-grab active:cursor-grabbing pl-1 shrink-0 select-none">⠿</span>
                )}

                {/* 인라인 편집 모드 */}
                {managing && editingName === cat.name ? (
                  <div className="flex-1 flex gap-1 pr-1 py-1">
                    <input value={editIcon} onChange={(e) => setEditIcon(e.target.value)}
                      className="w-8 bg-slate-700 text-white text-center text-sm rounded px-1 outline-none focus:ring-1 focus:ring-indigo-500" maxLength={2} />
                    <input ref={editInputRef} value={editName} onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") commitEdit(); if (e.key === "Escape") cancelEdit(); }}
                      className="flex-1 bg-slate-700 text-white text-sm rounded px-2 outline-none focus:ring-1 focus:ring-indigo-500 min-w-0" maxLength={30} />
                    <button onClick={commitEdit} className="text-emerald-400 hover:text-emerald-300 text-xs px-1">✓</button>
                    <button onClick={cancelEdit} className="text-slate-500 hover:text-slate-300 text-xs px-1">✕</button>
                  </div>
                ) : (
                  <>
                    <button onClick={() => handleSelect(cat.name)}
                      className={`flex-1 flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors text-left ${
                        selected === cat.name ? "bg-indigo-500/20 text-indigo-400 font-medium" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
                      }`}>
                      <span className="text-base w-5 text-center">{cat.icon}</span>
                      <span className="truncate">{cat.name}</span>
                    </button>

                    {/* 관리 모드 액션 */}
                    {managing && (
                      <div className="flex items-center shrink-0">
                        {/* 이름 변경 */}
                        <button onClick={() => startEdit(cat)}
                          className="text-slate-600 hover:text-indigo-400 transition-colors p-1 rounded"
                          title="이름 변경">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536M9 13l6.586-6.586a2 2 0 112.828 2.828L11.828 15.828a2 2 0 01-1.414.586H9v-2a2 2 0 01.586-1.414z" />
                          </svg>
                        </button>
                        {/* 통합 및 삭제 ('기타' 제외) */}
                        {cat.name !== "기타" && (
                          <button onClick={() => handleDelete(cat.name)}
                            className="text-slate-600 hover:text-red-400 transition-colors p-1 rounded"
                            title="통합 및 삭제">
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        )}
                      </div>
                    )}
                  </>
                )}
              </li>
            ))}
          </ul>
        </nav>

        {/* 하단 메뉴 */}
        <div className="px-3 pb-2 border-t border-slate-800 pt-3 space-y-0.5">
          <Link href="/graph" onClick={onClose}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === "/graph" ? "bg-indigo-500/20 text-indigo-400 font-medium" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}>
            <span className="text-base w-5 text-center">🕸️</span>
            <span>노트 그래프</span>
          </Link>
          <Link href="/stats" onClick={onClose}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === "/stats" ? "bg-indigo-500/20 text-indigo-400 font-medium" : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
            }`}>
            <span className="text-base w-5 text-center">📊</span>
            <span>통계</span>
          </Link>
        </div>

        {/* 로그아웃 */}
        <div className="px-3 py-4 border-t border-slate-800">
          <button onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition-colors">
            <span className="text-base w-5 text-center">🚪</span>
            <span>로그아웃</span>
          </button>
        </div>
      </aside>

      {/* 카테고리 통합 모달 */}
      {mergeSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
          <div className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-xs p-5 border border-slate-700">
            <h3 className="text-white font-semibold text-sm mb-1">카테고리 통합</h3>
            <p className="text-slate-400 text-xs mb-4">
              <span className="text-indigo-400 font-medium">{mergeSource}</span>의 모든 노트를 아래 카테고리로 이동하고 삭제합니다.
            </p>
            <label className="text-xs text-slate-500 mb-1 block">이동할 카테고리</label>
            <select
              value={mergeTarget}
              onChange={(e) => setMergeTarget(e.target.value)}
              className="w-full bg-slate-700 text-white text-sm rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
            >
              {categories
                .filter((c) => c.name !== mergeSource)
                .map((c) => (
                  <option key={c.name} value={c.name}>{c.icon} {c.name}</option>
                ))}
            </select>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setMergeSource(null)}
                className="text-xs px-3 py-1.5 rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 transition-colors"
              >
                취소
              </button>
              <button
                onClick={handleMerge}
                disabled={merging}
                className="text-xs px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition-colors"
              >
                {merging ? "통합 중…" : "통합 및 삭제"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
