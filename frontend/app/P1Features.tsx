"use client";

import { useEffect, useMemo, useState } from "react";
import { DemoModeControl, type AnalysisMode } from "./P2Features";
import type { Mission, TeacherClassResponse } from "../lib/api/contracts";
import type { TeacherSession } from "../lib/api/session";
import { apiErrorMessage } from "../lib/api/adapters";

function PageHeader({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <header className="p1-header">
      <button className="icon-button" onClick={onBack} aria-label="뒤로 가기">←</button>
      <strong>{title}</strong>
      <span />
    </header>
  );
}

export function MissionsPage({ mission, onBack, onScan }: { mission?: Mission | null; onBack: () => void; onScan: () => void }) {
  const missions = [
    ...(mission ? [{ icon: "⚡", title: mission.title, type: mission.type, current: 0, target: mission.condition.find((item) => "count" in item)?.count ?? 1, reward: `+${mission.rewardXp} XP`, active: true }] : []),
    { icon: "🏷️", title: "라벨 구출 작전", type: "행동형", current: 1, target: 2, reward: "XP 2배", active: true },
    { icon: "📸", title: "오늘 3개 관찰하기", type: "개수형", current: 2, target: 3, reward: "+20 XP", active: true },
    { icon: "📦", title: "종이류 탐험", type: "카테고리형", current: 1, target: 3, reward: "탐험가 뱃지", active: false },
    { icon: "↻", title: "다시 찍기 성공", type: "재도전형", current: 1, target: 1, reward: "+30 XP", active: false },
  ];
  return (
    <main className="p1-page">
      <PageHeader title="오늘의 미션" onBack={onBack} />
      <section className="p1-content">
        <div className="p1-hero mission-hero"><div><p className="eyebrow">선택형 보너스</p><h1>오늘도 가볍게<br />한 가지 도전!</h1><p>미션을 하지 않아도 자유 촬영과 도감 수집은 언제나 가능해요.</p></div><span>⚡</span></div>
        <div className="mission-list">
          {missions.map((mission) => {
            const percent = Math.min(100, (mission.current / mission.target) * 100);
            const complete = mission.current >= mission.target;
            return <article className={`mission-detail-card ${complete ? "complete" : ""}`} key={mission.title}>
              <div className="mission-symbol">{complete ? "✓" : mission.icon}</div>
              <div className="mission-copy"><div><small>{mission.type}</small><h2>{mission.title}</h2></div><p>{complete ? "미션 완료! 보상을 받았어요." : `${mission.target - mission.current}번만 더 하면 완료!`}</p><div className="mission-progress"><span style={{ width: `${percent}%` }} /></div><small>{mission.current} / {mission.target}</small></div>
              <div className="mission-reward"><small>보상</small><strong>{mission.reward}</strong>{!complete && <button onClick={onScan}>찍기</button>}</div>
            </article>;
          })}
        </div>
      </section>
    </main>
  );
}

export function CharacterPage({ onBack, onBadges }: { onBack: () => void; onBadges: () => void }) {
  return (
    <main className="p1-page">
      <PageHeader title="나의 봄이" onBack={onBack} />
      <section className="character-page p1-content">
        <div className="character-showcase">
          <div className="stage-label">2단계 · 새싹 봄이</div>
          <div className="big-mascot"><span>🌱</span><b>•ᴗ•</b></div>
          <div className="character-sparkles">✦ ✦ ✦</div>
          <h1>LEVEL 3</h1><p>다음 단계에서는 잎사귀가 더 풍성해져요!</p>
          <div className="level-progress-large"><span style={{ width: "64%" }} /></div><div className="level-caption"><b>180 XP</b><span>다음 레벨 250 XP</span></div>
        </div>
        <div className="growth-panel"><p className="eyebrow">성장 과정</p><h2>함께 자라는 봄이</h2><div className="growth-steps"><div className="passed"><span>🌰</span><b>씨앗 봄이</b><small>처음 만남</small></div><div className="current"><span>🌱</span><b>새싹 봄이</b><small>현재 단계</small></div><div><span>🌳</span><b>푸른 봄이</b><small>LEVEL 7</small></div></div><button className="secondary-button" onClick={onBadges}>내 뱃지 보러가기</button></div>
      </section>
    </main>
  );
}

export function BadgesPage({ onBack }: { onBack: () => void }) {
  const badges = [
    { icon: "🔥", name: "꾸준함", detail: "3일 연속 탐험", progress: "3 / 3", unlocked: true },
    { icon: "↻", name: "다시 도전", detail: "재촬영 성공 5회", progress: "5 / 5", unlocked: true },
    { icon: "🔍", name: "탐험가", detail: "하루에 5종 관찰", progress: "3 / 5", unlocked: false },
    { icon: "✨", name: "완벽주의", detail: "한 품목 10회 완결", progress: "4 / 10", unlocked: false },
    { icon: "💚", name: "충북 지킴이", detail: "지역 카드 모두 수집", progress: "1 / 5", unlocked: false },
  ];
  return <main className="p1-page"><PageHeader title="나의 뱃지" onBack={onBack} /><section className="p1-content"><p className="eyebrow">도전 기록</p><h1 className="p1-title">행동할수록 빛나는<br />나의 환경 뱃지</h1><div className="badge-grid">{badges.map((badge) => <article key={badge.name} className={`badge-card ${badge.unlocked ? "unlocked" : "locked"}`}><div className="badge-medal">{badge.unlocked ? badge.icon : "?"}</div><h2>{badge.name}</h2><p>{badge.detail}</p><div className="badge-progress"><span style={{ width: `${Number(badge.progress.split(" / ")[0]) / Number(badge.progress.split(" / ")[1]) * 100}%` }} /></div><small>{badge.progress}</small>{badge.unlocked && <b>획득 완료</b>}</article>)}</div></section></main>;
}

export function ClassGoalPage({ onBack }: { onBack: () => void }) {
  return <main className="p1-page"><PageHeader title="우리 반 공동 목표" onBack={onBack} /><section className="p1-content"><div className="goal-celebration"><span>🤝</span><p className="eyebrow">4학년 2반</p><h1>우리 반이 함께 모은<br /><em>카드 312장</em></h1><div className="goal-gauge"><span style={{ width: "62.4%" }} /></div><div><b>312장</b><span>목표 500장</span></div><p>188장 더 모으면 목표 달성!</p></div><div className="goal-info-grid"><article><span>🌳</span><h2>목표 보상</h2><p>나무 심기 활동 인증서</p><small>시제품 예시 목표</small></article><article><span>🏆</span><h2>우리 반 기록</h2><p>이번 주 46장 발견</p><small>지난주보다 12장 많아요</small></article><article><span>👫</span><h2>함께한 친구</h2><p>23명이 참여 중</p><small>개인 순위는 표시하지 않아요</small></article></div></section></main>;
}

const questions = [
  { text: "우리 학교 분리수거함은 몇 종류인가요?", options: ["1~2종", "3~4종", "5~6종", "잘 모르겠어요"] },
  { text: "투명 페트병 전용함이 있나요?", options: ["있어요", "없어요", "잘 모르겠어요"] },
  { text: "종이팩을 따로 모으는 곳이 있나요?", options: ["있어요", "없어요", "잘 모르겠어요"] },
  { text: "수거함에 알기 쉬운 안내 그림이 있나요?", options: ["잘 보여요", "조금 있어요", "없어요"] },
  { text: "학교에서 분리배출을 실천하기 쉬운가요?", options: ["쉬워요", "보통이에요", "어려워요"] },
];

export function ChecklistPage({ onBack, onComplete }: { onBack: () => void; onComplete: (answers: string[]) => void }) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<string[]>([]);
  const selected = answers[index];
  const choose = (option: string) => setAnswers((current) => { const next = [...current]; next[index] = option; return next; });
  const next = () => index === questions.length - 1 ? onComplete(answers) : setIndex((value) => value + 1);
  return <main className="checklist-page"><PageHeader title="우리 학교 살펴보기" onBack={onBack} /><section className="checklist-card"><div className="checklist-progress"><span style={{ width: `${(index + 1) / questions.length * 100}%` }} /></div><div className="question-number">질문 {index + 1} / {questions.length}</div><div className="question-icon">🏫</div><h1>{questions[index].text}</h1><p>직접 본 모습과 가장 가까운 답을 골라줘.</p><div className="answer-options">{questions[index].options.map((option) => <button className={selected === option ? "selected" : ""} key={option} onClick={() => choose(option)}><span>{selected === option ? "✓" : ""}</span>{option}</button>)}</div><div className="checklist-actions"><button className="secondary-button" disabled={index === 0} onClick={() => setIndex((value) => value - 1)}>이전</button><button className="primary-button" disabled={!selected} onClick={next}>{index === questions.length - 1 ? "결과 보기" : "다음"}</button></div></section></main>;
}

export function ChecklistResult({ onBack }: { onBack: () => void }) {
  return <main className="p1-page"><PageHeader title="학교 살펴보기 결과" onBack={onBack} /><section className="checklist-result p1-content"><div className="result-school">🏫</div><p className="eyebrow">관찰 완료</p><h1>우리 학교는<br /><em>조금 더 살펴볼 단계</em>예요</h1><p>분리수거함은 있지만 종이팩과 투명 페트병을 따로 모으는 곳이 부족해 보여요.</p><div className="result-stat"><strong>알고 있었나요?</strong><p>서울 74개 학교 조사에서 6종 분리배출을 하는 학교는 16곳뿐이었어요.</p></div><div className="school-actions"><article><span>1</span><div><h2>수거함 안내를 확인해요</h2><p>그림이 흐리거나 없다면 선생님께 이야기해봐요.</p></div></article><article><span>2</span><div><h2>친구와 함께 관찰해요</h2><p>어떤 품목을 따로 모으면 좋을지 찾아봐요.</p></div></article></div><button className="primary-button" onClick={onBack}>홈으로 돌아가기</button></section></main>;
}

export function SettingsPage({ muted, onMutedChange, demoMode, onDemoModeChange, onBack, onTeacher }: { muted: boolean; onMutedChange: (value: boolean) => void; demoMode: AnalysisMode; onDemoModeChange: (value: AnalysisMode) => void; onBack: () => void; onTeacher: () => void }) {
  const [largeText, setLargeText] = useState(false);
  return <main className={`p1-page ${largeText ? "large-text" : ""}`}><PageHeader title="설정" onBack={onBack} /><section className="settings-content p1-content"><p className="eyebrow">사용 환경</p><h1 className="p1-title">나에게 편한 방식으로</h1><div className="settings-list"><label><span>🔊</span><div><strong>음성 안내</strong><small>AI 결과를 소리 내어 읽어요</small></div><input type="checkbox" checked={!muted} onChange={(event) => onMutedChange(!event.target.checked)} /></label><label><span>🔎</span><div><strong>큰 글씨</strong><small>중요한 글자를 더 크게 보여줘요</small></div><input type="checkbox" checked={largeText} onChange={(event) => setLargeText(event.target.checked)} /></label><div><span>🔒</span><div><strong>사진 처리 안내</strong><small>사진은 판정 후 저장하지 않아요</small></div><b>안전</b></div></div><DemoModeControl value={demoMode} onChange={onDemoModeChange} /><button className="teacher-entry" onClick={onTeacher}>교사이신가요? 교사용 화면으로 →</button></section></main>;
}

export function TeacherLogin({ onBack, onLogin }: { onBack: () => void; onLogin: (name: string, email: string) => Promise<void> }) {
  const [name, setName] = useState("김선생");
  const [email, setEmail] = useState("teacher@gmail.com");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await onLogin(name.trim(), email.trim());
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  };
  return <main className="teacher-login-page"><PageHeader title="교사용" onBack={onBack} /><section className="teacher-login-card"><div className="teacher-symbol">🧑‍🏫</div><p className="eyebrow">선생님 전용</p><h1>우리 반의 변화를<br />한눈에 확인하세요</h1><p>공유 API 명세에 맞춰 이름과 이메일로 입장합니다.</p><form onSubmit={submit}><label>이름<input value={name} required onChange={(event) => setName(event.target.value.slice(0, 30))} /></label><label>이메일<input type="email" value={email} required onChange={(event) => setEmail(event.target.value)} /></label>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button" disabled={submitting}>{submitting ? "로그인 중…" : "교사로 로그인"}</button></form></section></main>;
}

export function TeacherDashboard({ teacher, classData, onCreateClass, onRefreshCode, onToggleLock, onLogout }: { teacher?: TeacherSession | null; classData?: TeacherClassResponse | null; onCreateClass?: (input: { school: string; grade: number; className: number; goalTarget: number }) => Promise<void>; onRefreshCode?: () => Promise<string>; onToggleLock?: (locked: boolean) => Promise<void>; onLogout: () => void }) {
  const [tab, setTab] = useState<"overview" | "students" | "content" | "settings">("overview");
  const [joinCode, setJoinCode] = useState("4B7K2M");
  const [locked, setLocked] = useState(false);
  const [notice, setNotice] = useState("");
  const [comparisonEnabled, setComparisonEnabled] = useState(false);
  const [classForm, setClassForm] = useState({ school: "국민초등학교", grade: 6, className: 1, goalTarget: 100 });
  const [creatingClass, setCreatingClass] = useState(false);
  const [contentItems, setContentItems] = useState([
    { id: 1, title: "라벨 구출 작전", type: "행동형 미션", active: true },
    { id: 2, title: "종이류 3개 관찰", type: "카테고리형 미션", active: true },
    { id: 3, title: "영동 포도 상자", type: "충북 특화 카드", active: true },
    { id: 4, title: "괴산 장류 용기", type: "충북 특화 카드", active: false },
  ]);
  useEffect(() => {
    if (!classData) return;
    const timer = window.setTimeout(() => {
      setJoinCode(classData.classCode);
      setLocked(classData.locked ?? false);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [classData]);
  const refreshCode = async () => {
    try {
      const code = await onRefreshCode?.();
      if (code) setJoinCode(code);
      setNotice("현재 참여 코드를 새로 불러왔어요.");
    } catch (reason) {
      setNotice(apiErrorMessage(reason));
    }
  };
  const createClass = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!onCreateClass || creatingClass) return;
    setCreatingClass(true);
    try {
      await onCreateClass(classForm);
      setNotice("새 학급을 만들었어요.");
    } catch (reason) {
      setNotice(apiErrorMessage(reason));
    } finally {
      setCreatingClass(false);
    }
  };
  const toggleLock = async () => {
    const next = !locked;
    try {
      await onToggleLock?.(next);
      setLocked(next);
      setNotice(next ? "학급 참여를 잠갔어요." : "학급 참여 잠금을 해제했어요.");
    } catch (reason) {
      setNotice(apiErrorMessage(reason));
    }
  };
  const students = useMemo(() => [
    ["초록탐험가", "오늘", "18장", "4회"], ["지구수호대", "오늘", "15장", "3회"], ["새싹요원", "어제", "12장", "5회"], ["분리왕", "오늘", "10장", "2회"], ["봄바람", "3일 전", "8장", "1회"],
  ], []);
  return (
    <main className="teacher-app">
      <aside className="teacher-sidebar">
        <div className="teacher-brand"><span>↻</span><div><b>다시봄 스쿨</b><small>교사 관리</small></div></div>
        <nav>
          <button className={tab === "overview" ? "active" : ""} onClick={() => setTab("overview")}>▦ 학급 현황</button>
          <button className={tab === "students" ? "active" : ""} onClick={() => setTab("students")}>♙ 참여 학생</button>
          <button className={tab === "content" ? "active" : ""} onClick={() => setTab("content")}>✦ 콘텐츠 관리</button>
          <button className={tab === "settings" ? "active" : ""} onClick={() => setTab("settings")}>⚙ 학급 설정</button>
        </nav>
        <button className="logout-button" onClick={onLogout}>← 로그아웃</button>
      </aside>
      <section className="teacher-main">
        <header><div><p>{classData?.school ?? "충북초등학교"}</p><h1>{classData?.grade ?? 4}학년 {classData?.className ?? 2}반</h1></div><span>{teacher?.name ?? "김다시봄"} 선생님</span></header>
        {notice && <div className="teacher-notice">✓ {notice}<button onClick={() => setNotice("")}>×</button></div>}
        {tab === "overview" && <TeacherOverview joinCode={joinCode} locked={locked} classData={classData} onRefreshCode={refreshCode} onLock={toggleLock} />}
        {tab === "students" && (
          <div className="teacher-panel">
            <div className="panel-heading"><div><p className="eyebrow">익명 참여</p><h2>참여 학생 23명</h2></div><span>개인 순위는 표시하지 않습니다</span></div>
            <div className="student-table">
              <div><b>닉네임</b><b>마지막 활동</b><b>도감 카드</b><b>교정 성공</b></div>
              {students.map((student) => (
                <div key={student[0]}>{student.map((value, index) => <span key={`${student[0]}-${index}`}>{value}</span>)}</div>
              ))}
            </div>
          </div>
        )}
        {tab === "content" && (
          <div className="teacher-panel">
            <div className="panel-heading"><div><p className="eyebrow">운영 콘텐츠</p><h2>미션·지역 카드 관리</h2></div><span>시제품 로컬 관리</span></div>
            <div className="content-admin-list">
              {contentItems.map((item) => (
                <article key={item.id}>
                  <span>{item.type.includes("카드") ? "💚" : "⚡"}</span>
                  <div><strong>{item.title}</strong><small>{item.type}</small></div>
                  <button
                    className={item.active ? "published" : "draft"}
                    onClick={() => setContentItems((current) => current.map((target) => target.id === item.id ? { ...target, active: !target.active } : target))}
                  >{item.active ? "게시 중" : "초안"}</button>
                </article>
              ))}
            </div>
            <button className="secondary-button content-add-button" onClick={() => setNotice("새 콘텐츠 작성 기능은 백엔드 CMS 연결 후 활성화됩니다.")}>+ 새 콘텐츠 만들기</button>
          </div>
        )}
        {tab === "settings" && (
          <div className="teacher-settings-grid">
            <section className="teacher-panel">
              <p className="eyebrow">참여 관리</p><h2>학급 참여 코드</h2>
              <div className="join-code-display"><b>{joinCode}</b><button onClick={() => { void navigator.clipboard?.writeText(joinCode); setNotice("참여 코드를 복사했어요."); }}>복사</button></div>
              <button className="secondary-button" onClick={() => void refreshCode()}>코드 새로고침</button>
            </section>
            <section className="teacher-panel">
              <p className="eyebrow">학급 생성 API</p><h2>새 학급 만들기</h2>
              <form className="class-create-form" onSubmit={createClass}>
                <label>학교<input required value={classForm.school} onChange={(event) => setClassForm((value) => ({ ...value, school: event.target.value }))} /></label>
                <label>학년<input type="number" min="1" max="6" value={classForm.grade} onChange={(event) => setClassForm((value) => ({ ...value, grade: Number(event.target.value) }))} /></label>
                <label>반<input type="number" min="1" max="30" value={classForm.className} onChange={(event) => setClassForm((value) => ({ ...value, className: Number(event.target.value) }))} /></label>
                <label>목표 카드<input type="number" min="1" value={classForm.goalTarget} onChange={(event) => setClassForm((value) => ({ ...value, goalTarget: Number(event.target.value) }))} /></label>
                <button className="primary-button" disabled={creatingClass}>{creatingClass ? "만드는 중…" : "학급 만들기"}</button>
              </form>
            </section>
            <section className="teacher-panel">
              <p className="eyebrow">보안</p><h2>학급 잠금</h2><p>잠그면 새로운 학생의 참여만 중단돼요. 기존 학생은 계속 이용할 수 있어요.</p>
              <button className={`lock-button ${locked ? "locked" : ""}`} onClick={() => void toggleLock()}>{locked ? "🔒 잠금 해제" : "🔓 학급 잠그기"}</button>
            </section>
            <section className="teacher-panel comparison-setting">
              <p className="eyebrow">선택 기능</p><h2>다른 학급과 비교</h2><p>학급 전체 누적치만 비교하며 학생 개인 정보나 순위는 표시하지 않아요.</p>
              <div className="comparison-switch"><span><strong>학급 비교 허용</strong><small>기본값은 꺼짐이에요</small></span><input aria-label="학급 비교 허용" type="checkbox" checked={comparisonEnabled} onChange={(event) => setComparisonEnabled(event.target.checked)} /></div>
              {comparisonEnabled && <div className="comparison-preview"><span>우리 반 312장</span><span>같은 학년 평균 284장</span></div>}
            </section>
          </div>
        )}
      </section>
    </main>
  );
}

function TeacherOverview({ joinCode, locked, classData, onRefreshCode, onLock }: { joinCode: string; locked: boolean; classData?: TeacherClassResponse | null; onRefreshCode: () => void; onLock: () => void }) {
  const current = classData?.goalCurrent ?? 312;
  const target = classData?.goalTarget ?? 500;
  const percent = target > 0 ? Math.min(100, current / target * 100) : 0;
  return <><div className="teacher-summary"><article><span>👫</span><p>참여 학생</p><h2>{classData?.studentCount ?? 23}명</h2><small>익명 학생 기준</small></article><article><span>📚</span><p>누적 카드</p><h2>{current}장</h2><small>목표의 {Math.round(percent)}%</small></article><article><span>↻</span><p>교정 완료율</p><h2>78%</h2><small>지난주보다 +8%</small></article><article><span>⚡</span><p>미션 완료</p><h2>17명</h2><small>학급의 74%</small></article></div><div className="teacher-dashboard-grid"><section className="teacher-panel class-progress-panel"><div className="panel-heading"><div><p className="eyebrow">공동 목표</p><h2>카드 {target}장 모으기</h2></div><strong>{current} / {target}</strong></div><div className="class-progress"><span style={{ width: `${percent}%` }} /></div><p>{Math.max(0, target - current)}장 더 모으면 공동 목표를 달성해요.</p><button className="secondary-button" onClick={() => window.print()}>인증서 미리보기</button></section><section className="teacher-panel code-panel"><div className="panel-heading"><div><p className="eyebrow">학생 참여</p><h2>학급 코드</h2></div><span className={locked ? "status-locked" : "status-open"}>{locked ? "잠김" : "참여 가능"}</span></div><div className="join-code-display"><b>{joinCode}</b><button onClick={() => void navigator.clipboard?.writeText(joinCode)}>복사</button></div><div className="code-actions"><button onClick={onRefreshCode}>코드 새로고침</button><button onClick={() => void onLock()}>{locked ? "잠금 해제" : "학급 잠금"}</button></div></section><section className="teacher-panel confusion-panel"><div className="panel-heading"><div><p className="eyebrow">수업 활용</p><h2>많이 헷갈린 품목</h2></div><span>이번 주</span></div>{[["투명 페트병", 82, "라벨"], ["우유팩", 64, "내용물"], ["배달 용기", 46, "오염"]].map(([name, value, issue]) => <div className="confusion-row" key={name}><div><b>{name}</b><small>{issue} 상태를 자주 놓쳤어요</small></div><span><i style={{ width: `${value}%` }} /></span><strong>{value}%</strong></div>)}</section><section className="teacher-panel weekly-panel"><div className="panel-heading"><div><p className="eyebrow">활동 추이</p><h2>이번 주 판정</h2></div><strong>총 86회</strong></div><div className="bar-chart">{[35, 62, 48, 82, 68].map((value, index) => <div key={index}><span style={{ height: `${value}%` }} /><small>{["월", "화", "수", "목", "금"][index]}</small></div>)}</div></section></div></>;
}
