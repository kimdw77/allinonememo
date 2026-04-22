"use client";

/**
 * FileUpload.tsx — 파일 업로드 드래그앤드롭 컴포넌트
 * 지원 형식: txt, md, pdf, docx
 */
import { useState, useRef, DragEvent, ChangeEvent } from "react";

interface UploadedNote {
  id: string;
  summary: string;
  category: string;
  keywords: string[];
}

interface FileUploadProps {
  onUploaded?: (notes: UploadedNote[]) => void;
}

const ACCEPTED = ".txt,.md,.text,.pdf,.docx,.doc";
const ACCEPTED_EXTS = new Set(["txt", "md", "text", "pdf", "docx", "doc"]);

export default function FileUpload({ onUploaded }: FileUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ ok: number; errors: string[] } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    const valid: File[] = [];
    const errors: string[] = [];
    Array.from(files).forEach((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      if (!ACCEPTED_EXTS.has(ext)) {
        errors.push(`${f.name}: 지원하지 않는 형식`);
      } else if (f.size > 10 * 1024 * 1024) {
        errors.push(`${f.name}: 10MB 초과`);
      } else {
        valid.push(f);
      }
    });

    if (valid.length === 0) {
      setResult({ ok: 0, errors });
      return;
    }

    setUploading(true);
    setResult(null);

    const form = new FormData();
    valid.forEach((f) => form.append("files", f));

    try {
      const res = await fetch("/api/notes/upload", { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "업로드 실패" }));
        setResult({ ok: 0, errors: [...errors, err.detail ?? "서버 오류"] });
        return;
      }
      const notes: UploadedNote[] = await res.json();
      setResult({ ok: notes.length, errors });
      onUploaded?.(notes);
    } catch {
      setResult({ ok: 0, errors: [...errors, "네트워크 오류"] });
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
  };

  const onDragLeave = () => setDragging(false);

  const onChange = (e: ChangeEvent<HTMLInputElement>) => handleFiles(e.target.files);

  return (
    <div className="w-full">
      {/* 드롭존 */}
      <div
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => inputRef.current?.click()}
        className={`
          relative flex flex-col items-center justify-center gap-2
          rounded-xl border-2 border-dashed cursor-pointer transition-colors
          px-4 py-6 text-sm
          ${dragging
            ? "border-indigo-400 bg-indigo-50 text-indigo-600"
            : "border-slate-300 bg-slate-50 text-slate-500 hover:border-indigo-300 hover:bg-indigo-50/50"
          }
          ${uploading ? "opacity-60 pointer-events-none" : ""}
        `}
      >
        <span className="text-2xl">{uploading ? "⏳" : "📁"}</span>
        <span className="font-medium text-center">
          {uploading
            ? "분류 중... (Claude AI 처리)"
            : "파일을 드래그하거나 클릭해서 업로드"}
        </span>
        <span className="text-xs text-slate-400">
          txt · md · pdf · docx 지원 / 최대 10개, 파일당 10MB
        </span>

        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED}
          onChange={onChange}
          className="hidden"
        />
      </div>

      {/* 결과 */}
      {result && (
        <div className="mt-2 space-y-1">
          {result.ok > 0 && (
            <p className="text-sm text-emerald-600 font-medium">
              ✅ {result.ok}개 노트가 저장되었습니다
            </p>
          )}
          {result.errors.map((e, i) => (
            <p key={i} className="text-xs text-red-500">⚠️ {e}</p>
          ))}
        </div>
      )}
    </div>
  );
}
