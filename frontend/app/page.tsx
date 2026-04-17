"use client";

import { useState, useEffect, useCallback } from "react";
import NoteCard from "@/components/NoteCard";
import SearchBar from "@/components/SearchBar";
import TagFilter from "@/components/TagFilter";

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

const CATEGORIES = [
  "비즈니스", "기술", "무역/수출", "건강", "교육", "뉴스", "개인메모", "기타",
];

export default function DashboardPage() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchNotes = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (category) params.set("category", category);
    params.set("limit", "30");

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
    <main className="max-w-4xl mx-auto px-4 py-8">
      {/* 헤더 */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-slate-900 mb-1">MyVault</h1>
        <p className="text-slate-500 text-sm">나만의 AI 지식저장소</p>
      </div>

      {/* 검색바 */}
      <SearchBar value={query} onChange={setQuery} />

      {/* 카테고리 필터 */}
      <TagFilter
        categories={CATEGORIES}
        selected={category}
        onSelect={setCategory}
      />

      {/* 노트 목록 */}
      <div className="mt-6 space-y-4">
        {loading && (
          <p className="text-center text-slate-400 py-12">불러오는 중...</p>
        )}
        {!loading && notes.length === 0 && (
          <p className="text-center text-slate-400 py-12">
            저장된 노트가 없습니다. 텔레그램 봇으로 메모를 보내보세요!
          </p>
        )}
        {!loading &&
          notes.map((note) => <NoteCard key={note.id} note={note} />)}
      </div>
    </main>
  );
}
