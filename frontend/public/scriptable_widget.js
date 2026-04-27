// MyVault Tasks Widget for Scriptable
// 설치 방법:
// 1. iPhone에 Scriptable 앱 설치 (App Store 무료)
// 2. 이 파일을 Scriptable에 새 스크립트로 붙여넣기
// 3. API_URL, API_KEY 값을 본인 환경에 맞게 수정
// 4. 홈 화면 → 길게 누르기 → 위젯 추가 → Scriptable → 스크립트 선택

const API_URL = "https://allinonememo-production.up.railway.app";
const API_KEY = "여기에_API_SECRET_KEY_입력";
const MAX_TASKS = 5;

// ── 데이터 가져오기 ──────────────────────────────
async function fetchTasks() {
  const req = new Request(`${API_URL}/api/tasks?status=todo&limit=${MAX_TASKS}`);
  req.headers = { "X-API-Key": API_KEY };
  try {
    return await req.loadJSON();
  } catch {
    return [];
  }
}

async function fetchStats() {
  const req = new Request(`${API_URL}/api/notes?limit=1`);
  req.headers = { "X-API-Key": API_KEY };
  try {
    const res = new Request(`${API_URL}/api/stats`);
    res.headers = { "X-API-Key": API_KEY };
    return await res.loadJSON();
  } catch {
    return { today: 0, total: 0 };
  }
}

// ── 위젯 빌드 ────────────────────────────────────
async function buildWidget() {
  const [tasks, stats] = await Promise.all([fetchTasks(), fetchStats()]);

  const widget = new ListWidget();
  widget.backgroundColor = new Color("#1e1b4b"); // 인디고 배경
  widget.setPadding(14, 14, 14, 14);

  // 헤더
  const header = widget.addStack();
  header.layoutHorizontally();
  header.centerAlignContent();

  const titleText = header.addText("MyVault");
  titleText.font = Font.boldSystemFont(14);
  titleText.textColor = new Color("#a5b4fc");

  header.addSpacer();

  const statText = header.addText(`오늘 ${stats.today ?? 0}개`);
  statText.font = Font.systemFont(10);
  statText.textColor = new Color("#6366f1");

  widget.addSpacer(8);

  // 구분선
  const divider = widget.addStack();
  divider.backgroundColor = new Color("#312e81");
  divider.size = new Size(0, 1);
  widget.addSpacer(8);

  // 할일 목록
  if (tasks.length === 0) {
    const empty = widget.addText("✅ 오늘 할 일이 없습니다");
    empty.font = Font.systemFont(12);
    empty.textColor = new Color("#818cf8");
    empty.centerAlignText();
  } else {
    const PRIORITY_ICON = { high: "🔴", medium: "🟡", low: "🟢" };

    for (const task of tasks.slice(0, MAX_TASKS)) {
      const row = widget.addStack();
      row.layoutHorizontally();
      row.centerAlignContent();
      row.spacing = 6;

      const icon = row.addText(PRIORITY_ICON[task.priority] ?? "⚪");
      icon.font = Font.systemFont(10);

      const label = row.addText(task.title ?? "");
      label.font = Font.systemFont(11);
      label.textColor = Color.white();
      label.lineLimit = 1;

      widget.addSpacer(4);
    }
  }

  widget.addSpacer();

  // 업데이트 시간
  const now = new Date();
  const timeStr = now.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" });
  const footer = widget.addText(`업데이트 ${timeStr}`);
  footer.font = Font.systemFont(9);
  footer.textColor = new Color("#4338ca");

  return widget;
}

// ── 실행 ─────────────────────────────────────────
const widget = await buildWidget();

if (config.runsInWidget) {
  Script.setWidget(widget);
} else {
  widget.presentMedium();
}
Script.complete();
