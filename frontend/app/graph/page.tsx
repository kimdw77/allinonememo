"use client";

/**
 * graph/page.tsx — 연관 노트 그래프 시각화 (Canvas 기반 force-directed)
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

interface GraphNode {
  id: string;
  label: string;
  category: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  radius: number;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

interface GraphData {
  nodes: Array<{ id: string; label: string; category: string }>;
  edges: Array<{ source: string; target: string; weight: number }>;
}

const CATEGORY_COLORS: Record<string, string> = {
  "기술": "#6366f1",
  "비즈니스": "#f59e0b",
  "뉴스": "#10b981",
  "건강": "#ec4899",
  "교육": "#3b82f6",
  "무역수출": "#8b5cf6",
  "개인메모": "#64748b",
  "기타": "#475569",
};

function getCategoryColor(category: string): string {
  return CATEGORY_COLORS[category] ?? "#6366f1";
}

export default function GraphPage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);
  const nodesRef = useRef<GraphNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const dragRef = useRef<{ node: GraphNode; offsetX: number; offsetY: number } | null>(null);
  const hoveredRef = useRef<GraphNode | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nodeCount, setNodeCount] = useState(0);
  const [edgeCount, setEdgeCount] = useState(0);
  const router = useRouter();

  const getCanvasPos = (canvas: HTMLCanvasElement, e: MouseEvent | Touch) => {
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  const findNode = (x: number, y: number): GraphNode | null => {
    for (const node of nodesRef.current) {
      const dx = x - node.x;
      const dy = y - node.y;
      if (Math.sqrt(dx * dx + dy * dy) <= node.radius + 4) return node;
    }
    return null;
  };

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 배경
    ctx.fillStyle = "#0f172a";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const hovered = hoveredRef.current;

    // 엣지 그리기
    for (const edge of edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t) continue;

      const isHighlighted = hovered && (hovered.id === edge.source || hovered.id === edge.target);
      ctx.beginPath();
      ctx.moveTo(s.x, s.y);
      ctx.lineTo(t.x, t.y);
      ctx.strokeStyle = isHighlighted ? "rgba(99,102,241,0.7)" : "rgba(99,102,241,0.15)";
      ctx.lineWidth = isHighlighted ? 1.5 : 0.8;
      ctx.stroke();
    }

    // 노드 그리기
    for (const node of nodes) {
      const isHovered = hovered?.id === node.id;
      const color = getCategoryColor(node.category);

      // 글로우 효과 (호버 시)
      if (isHovered) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.radius + 6, 0, Math.PI * 2);
        ctx.fillStyle = `${color}33`;
        ctx.fill();
      }

      // 원
      ctx.beginPath();
      ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
      ctx.fillStyle = isHovered ? color : `${color}99`;
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = isHovered ? 2 : 1;
      ctx.stroke();

      // 레이블
      if (isHovered || node.radius > 8) {
        ctx.fillStyle = isHovered ? "#ffffff" : "rgba(255,255,255,0.7)";
        ctx.font = isHovered ? "bold 12px sans-serif" : "11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const maxLen = 14;
        const label = node.label.length > maxLen ? node.label.slice(0, maxLen) + "…" : node.label;
        ctx.fillText(label, node.x, node.y + node.radius + 12);
      }
    }
  }, []);

  const simulate = useCallback(() => {
    const nodes = nodesRef.current;
    const edges = edgesRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const W = canvas.width;
    const H = canvas.height;
    const alpha = 0.3;

    // 반발력 (노드 간)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const repulse = 1800 / (dist * dist);
        const fx = (dx / dist) * repulse;
        const fy = (dy / dist) * repulse;
        a.vx -= fx * alpha;
        a.vy -= fy * alpha;
        b.vx += fx * alpha;
        b.vy += fy * alpha;
      }
    }

    // 인력 (엣지 스프링)
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    for (const edge of edges) {
      const s = nodeMap.get(edge.source);
      const t = nodeMap.get(edge.target);
      if (!s || !t) continue;
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const target = 120;
      const spring = (dist - target) * 0.04 * alpha;
      const fx = (dx / dist) * spring;
      const fy = (dy / dist) * spring;
      s.vx += fx;
      s.vy += fy;
      t.vx -= fx;
      t.vy -= fy;
    }

    // 중심 인력
    const cx = W / 2;
    const cy = H / 2;
    for (const node of nodes) {
      node.vx += (cx - node.x) * 0.002 * alpha;
      node.vy += (cy - node.y) * 0.002 * alpha;
    }

    // 위치 업데이트 + 마찰 + 경계
    for (const node of nodes) {
      if (dragRef.current?.node === node) continue;
      node.vx *= 0.85;
      node.vy *= 0.85;
      node.x = Math.max(node.radius + 20, Math.min(W - node.radius - 20, node.x + node.vx));
      node.y = Math.max(node.radius + 20, Math.min(H - node.radius - 20, node.y + node.vy));
    }

    draw();
    animRef.current = requestAnimationFrame(simulate);
  }, [draw]);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/notes/graph");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: GraphData = await res.json();

        const canvas = canvasRef.current;
        if (!canvas) return;
        const W = canvas.width;
        const H = canvas.height;

        // 초기 위치 랜덤 배치
        nodesRef.current = data.nodes.map((n) => ({
          ...n,
          x: W / 2 + (Math.random() - 0.5) * W * 0.6,
          y: H / 2 + (Math.random() - 0.5) * H * 0.6,
          vx: 0,
          vy: 0,
          radius: 7,
        }));
        edgesRef.current = data.edges;

        setNodeCount(data.nodes.length);
        setEdgeCount(data.edges.length);
        setLoading(false);

        animRef.current = requestAnimationFrame(simulate);
      } catch (e) {
        setError(String(e));
        setLoading(false);
      }
    }

    load();
    return () => cancelAnimationFrame(animRef.current);
  }, [simulate]);

  // 마우스 이벤트
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const onMouseMove = (e: MouseEvent) => {
      const pos = getCanvasPos(canvas, e);
      hoveredRef.current = findNode(pos.x, pos.y);
      canvas.style.cursor = hoveredRef.current ? "pointer" : "default";
    };

    const onMouseDown = (e: MouseEvent) => {
      const pos = getCanvasPos(canvas, e);
      const node = findNode(pos.x, pos.y);
      if (node) {
        dragRef.current = { node, offsetX: pos.x - node.x, offsetY: pos.y - node.y };
      }
    };

    const onMouseUp = (e: MouseEvent) => {
      if (dragRef.current) {
        // 클릭(거의 이동 없음) → 노트 상세로 이동
        const pos = getCanvasPos(canvas, e);
        const dx = pos.x - (dragRef.current.node.x + dragRef.current.offsetX);
        const dy = pos.y - (dragRef.current.node.y + dragRef.current.offsetY);
        if (Math.sqrt(dx * dx + dy * dy) < 5) {
          router.push(`/?note=${dragRef.current.node.id}`);
        }
        dragRef.current = null;
      }
    };

    const onMouseDrag = (e: MouseEvent) => {
      if (!dragRef.current) return;
      const pos = getCanvasPos(canvas, e);
      dragRef.current.node.x = pos.x - dragRef.current.offsetX;
      dragRef.current.node.y = pos.y - dragRef.current.offsetY;
      dragRef.current.node.vx = 0;
      dragRef.current.node.vy = 0;
    };

    canvas.addEventListener("mousemove", onMouseMove);
    canvas.addEventListener("mousemove", onMouseDrag);
    canvas.addEventListener("mousedown", onMouseDown);
    canvas.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("mouseleave", () => {
      hoveredRef.current = null;
      dragRef.current = null;
    });

    return () => {
      canvas.removeEventListener("mousemove", onMouseMove);
      canvas.removeEventListener("mousemove", onMouseDrag);
      canvas.removeEventListener("mousedown", onMouseDown);
      canvas.removeEventListener("mouseup", onMouseUp);
    };
  }, [router]);

  // Canvas 크기 반응형
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    observer.observe(canvas);
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    return () => observer.disconnect();
  }, []);

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-white">
      {/* 헤더 */}
      <header className="flex items-center justify-between px-5 py-3 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push("/")}
            className="text-slate-400 hover:text-white transition-colors text-sm flex items-center gap-1.5"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            대시보드
          </button>
          <span className="text-slate-700">/</span>
          <h1 className="text-white font-semibold text-base">노트 그래프</h1>
        </div>
        {!loading && !error && (
          <div className="text-xs text-slate-500">
            노드 {nodeCount}개 · 연결 {edgeCount}개
          </div>
        )}
      </header>

      {/* 범례 */}
      {!loading && !error && (
        <div className="flex flex-wrap gap-3 px-5 py-2 border-b border-slate-800/50 shrink-0">
          {Object.entries(CATEGORY_COLORS).map(([cat, color]) => (
            <div key={cat} className="flex items-center gap-1.5 text-xs text-slate-400">
              <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />
              {cat}
            </div>
          ))}
        </div>
      )}

      {/* Canvas */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center text-slate-500 text-sm">
            그래프 로딩 중…
          </div>
        )}
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-red-400 text-sm">
            {error}
          </div>
        )}
        {!loading && nodeCount === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-slate-500 text-sm">
            <span className="text-3xl">🕸️</span>
            <p>연결된 노트가 없습니다</p>
            <p className="text-xs text-slate-600">공통 키워드가 2개 이상인 노트 쌍이 생기면 표시됩니다</p>
          </div>
        )}
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{ display: loading || error ? "none" : "block" }}
        />
      </div>

      {/* 하단 도움말 */}
      <div className="px-5 py-2 border-t border-slate-800/50 shrink-0">
        <p className="text-xs text-slate-600 text-center">
          노드를 드래그하여 이동 · 클릭하면 해당 노트로 이동
        </p>
      </div>
    </div>
  );
}
