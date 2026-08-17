"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { afterAnalysis, beforeAnalysis, collectionCards } from "./mockData";
import type { ScanAnalysis, Screen } from "./types";
import { useCamera } from "./useCamera";
import {
  BadgesPage,
  CharacterPage,
  ChecklistPage,
  ChecklistResult,
  ClassGoalPage,
  MissionsPage,
  SettingsPage,
  TeacherDashboard,
  TeacherLogin,
} from "./P1Features";
import {
  AnalysisRecovery,
  NetworkBanner,
  ResumeNotice,
  type AnalysisMode,
} from "./P2Features";
import { useOnlineStatus, useScanRecovery, useServiceWorker } from "./useResilience";

const DEMO_CODE = "4B7K2M";

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`brand ${compact ? "brand-compact" : ""}`}>
      <span className="brand-mark" aria-hidden="true">↻</span>
      <span>다시봄 스쿨</span>
    </div>
  );
}

function StepDots({ current }: { current: number }) {
  return (
    <div className="step-dots" aria-label={`전체 3단계 중 ${current}단계`}>
      {[1, 2, 3].map((step) => (
        <span key={step} className={step <= current ? "active" : ""} />
      ))}
    </div>
  );
}

function Welcome({ onStart, onTeacher }: { onStart: () => void; onTeacher: () => void }) {
  return (
    <main className="welcome-screen">
      <div className="welcome-orb orb-one" />
      <div className="welcome-orb orb-two" />
      <section className="welcome-copy">
        <Brand />
        <p className="eyebrow">AI 카메라 분리배출 탐험</p>
        <h1>
          찍고, 고치고,
          <br />
          <em>다시 보면</em> 알게 돼!
        </h1>
        <p className="welcome-description">
          집과 교실의 진짜 쓰레기를 찍어봐. 봄이가 어떻게 바꾸면 좋을지
          바로 알려줄게.
        </p>
        <button className="primary-button welcome-button" onClick={onStart}>
          학생으로 시작하기 <span aria-hidden="true">→</span>
        </button>
        <button className="welcome-teacher-link" onClick={onTeacher}>교사로 시작하기</button>
        <p className="privacy-note">
          <span aria-hidden="true">●</span> 이름·나이·이메일은 받지 않아요
        </p>
      </section>
      <section className="hero-card" aria-label="서비스 체험 단계">
        <div className="character-stage">
          <div className="spark spark-one">✦</div>
          <div className="spark spark-two">✦</div>
          <div className="mascot" aria-label="다시봄 캐릭터 봄이">
            <span className="mascot-leaf">🌱</span>
            <span className="mascot-face">•ᴗ•</span>
          </div>
          <div className="speech-bubble">쓰레기 탐험을 떠나볼까?</div>
        </div>
        <div className="how-it-works">
          <div><b>1</b><span>찍고</span><small>진짜 쓰레기 촬영</small></div>
          <span className="flow-arrow">→</span>
          <div><b>2</b><span>판정받고</span><small>AI가 바로 확인</small></div>
          <span className="flow-arrow">→</span>
          <div><b>3</b><span>고쳐본다</span><small>직접 행동해보기</small></div>
        </div>
      </section>
    </main>
  );
}

function Join({ onBack, onSuccess }: { onBack: () => void; onSuccess: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (code.toUpperCase() !== DEMO_CODE) {
      setError(`체험 코드는 ${DEMO_CODE}예요.`);
      return;
    }
    onSuccess();
  };

  return (
    <main className="auth-screen">
      <header className="simple-header">
        <button className="icon-button" onClick={onBack} aria-label="뒤로 가기">←</button>
        <Brand compact />
        <span />
      </header>
      <section className="auth-card">
        <StepDots current={1} />
        <div className="auth-icon">🏫</div>
        <p className="eyebrow">우리 반에 들어가기</p>
        <h1>선생님이 알려준<br />참여 코드를 입력해줘</h1>
        <p>영문과 숫자로 된 6자리 코드야.</p>
        <form onSubmit={submit}>
          <label htmlFor="class-code">학급 참여 코드</label>
          <input
            id="class-code"
            className="code-input"
            value={code}
            onChange={(event) => {
              setCode(event.target.value.replace(/\s/g, "").toUpperCase().slice(0, 6));
              setError("");
            }}
            placeholder={DEMO_CODE}
            autoCapitalize="characters"
            autoComplete="off"
            aria-describedby={error ? "code-error" : undefined}
          />
          {error && <p id="code-error" className="form-error">{error}</p>}
          <button className="primary-button" disabled={code.length !== 6}>다음으로</button>
        </form>
        <button className="text-button" onClick={() => { setCode(DEMO_CODE); setError(""); }}>
          체험 코드 자동 입력
        </button>
      </section>
    </main>
  );
}

function Nickname({ onComplete }: { onComplete: (nickname: string) => void }) {
  const [nickname, setNickname] = useState("");
  return (
    <main className="auth-screen">
      <header className="simple-header"><span /><Brand compact /><span /></header>
      <section className="auth-card">
        <StepDots current={2} />
        <div className="auth-icon">👋</div>
        <p className="eyebrow">마지막 준비</p>
        <h1>어떻게 불러주면 될까?</h1>
        <p>진짜 이름 대신 나만의 별명을 만들어보자.</p>
        <form onSubmit={(event) => { event.preventDefault(); if (nickname.trim().length >= 2) onComplete(nickname.trim()); }}>
          <label htmlFor="nickname">나의 별명</label>
          <input
            id="nickname"
            value={nickname}
            onChange={(event) => setNickname(event.target.value.slice(0, 10))}
            placeholder="예: 초록탐험가"
            autoComplete="off"
          />
          <div className="input-meta"><span>2~10글자로 입력해줘</span><span>{nickname.length}/10</span></div>
          <button className="primary-button" disabled={nickname.trim().length < 2}>탐험 시작하기</button>
        </form>
      </section>
    </main>
  );
}

function AppHeader({ nickname, onHome, onSettings }: { nickname: string; onHome: () => void; onSettings?: () => void }) {
  return (
    <header className="app-header">
      <button className="brand-button" onClick={onHome}><Brand compact /></button>
      <div className="header-stats">
        <span>🌱 Lv. 3</span><span>⭐ 180 XP</span><button className="profile-button" onClick={onSettings} aria-label="설정 열기">{nickname.slice(0, 1)}</button>
      </div>
    </header>
  );
}

function Home({ nickname, onScan, onCollection, onMissions, onCharacter, onBadges, onChecklist, onGoal, onSettings }: { nickname: string; onScan: () => void; onCollection: () => void; onMissions: () => void; onCharacter: () => void; onBadges: () => void; onChecklist: () => void; onGoal: () => void; onSettings: () => void }) {
  return (
    <main className="app-shell">
      <AppHeader nickname={nickname} onHome={() => undefined} onSettings={onSettings} />
      <section className="home-grid">
        <div className="home-main">
          <div className="greeting"><div><p>안녕, {nickname}! 👋</p><h1>오늘은 어떤 쓰레기를<br />새롭게 만나볼까?</h1></div><div className="mini-mascot">•ᴗ•<span>🌱</span></div></div>
          <button className="scan-cta" onClick={onScan}>
            <span className="scan-cta-icon">⌾</span>
            <span><small>자유 촬영</small><strong>아무 쓰레기나 찍어보기</strong><em>언제나 열려 있어요</em></span>
            <b>→</b>
          </button>
          <button className="section-block clickable-block" onClick={onMissions}>
            <div className="section-heading"><div><span className="section-icon">⚡</span><div><small>오늘의 보너스</small><h2>라벨 구출 작전</h2></div></div><b className="bonus-chip">XP 2배</b></div>
            <p>라벨을 떼고 다시 찍어서 성공해보자!</p>
            <div className="mission-progress"><span style={{ width: "50%" }} /></div>
            <div className="progress-caption"><span>1 / 2번 성공</span><strong>한 번만 더!</strong></div>
          </button>
          <button className="section-block class-goal clickable-block" onClick={onGoal}>
            <div className="section-heading"><div><span className="section-icon blue">🤝</span><div><small>4학년 2반 공동 목표</small><h2>우리 반 카드 500장 모으기</h2></div></div><strong>312장</strong></div>
            <div className="class-progress"><span style={{ width: "62.4%" }} /></div>
            <p>188장 더 모으면 나무 심기 인증서를 받아요!</p>
          </button>
        </div>
        <aside className="home-side">
          <button className="character-card" onClick={onCharacter}>
            <div className="level-pill">LEVEL 3</div>
            <div className="side-mascot"><span>🌱</span><b>•ᴗ•</b></div>
            <h2>새싹 봄이</h2><p>다음 성장까지 70 XP</p>
            <div className="xp-progress"><span style={{ width: "64%" }} /></div>
            <div className="xp-label"><span>180</span><span>250 XP</span></div>
          </button>
          <button className="menu-card" onClick={onCollection}><span>📚</span><div><strong>헷갈림 도감</strong><small>3 / 30종 발견</small></div><b>→</b></button>
          <button className="menu-card" onClick={onBadges}><span>🏅</span><div><strong>나의 뱃지</strong><small>2개 획득</small></div><b>→</b></button>
          <button className="menu-card" onClick={onChecklist}><span>🏫</span><div><strong>우리 학교 살펴보기</strong><small>5문항 체크리스트</small></div><b>→</b></button>
        </aside>
      </section>
    </main>
  );
}

function CameraView({ phase, onCancel, onCapture }: { phase: "before" | "after"; onCancel: () => void; onCapture: (image: string) => void }) {
  const active = true;
  const { videoRef, status, capture } = useCamera(active);

  const takePhoto = async () => {
    const captured = await capture();
    onCapture(captured ?? "demo");
  };

  return (
    <main className="camera-screen">
      <header className="camera-header">
        <button onClick={onCancel} className="camera-icon-button" aria-label="촬영 닫기">×</button>
        <div><small>{phase === "before" ? "자유 촬영" : "다시 확인하기"}</small><strong>{phase === "before" ? "쓰레기를 하나만 보여줘" : "고친 쓰레기를 보여줘"}</strong></div>
        <button className="camera-icon-button" aria-label="음성 안내 끄기">♬</button>
      </header>
      <div className="camera-viewport">
        <video ref={videoRef} playsInline muted className={status === "ready" ? "visible" : ""} />
        {status !== "ready" && (
          <div className="camera-placeholder">
            <div className="placeholder-object">🧴</div>
            <p>{status === "requesting" ? "카메라를 준비하고 있어요" : "발표용 데모 카메라"}</p>
            <small>권한이 없어도 아래 버튼으로 흐름을 체험할 수 있어요.</small>
          </div>
        )}
        <div className="camera-frame"><span /><span /><span /><span /></div>
        <div className="camera-guide">물건이 네모 안에 꽉 차게 맞춰줘!</div>
      </div>
      <footer className="camera-footer">
        <button className="gallery-button" onClick={() => onCapture("demo")}><span>▧</span><small>데모 사진</small></button>
        <button className="shutter-button" onClick={takePhoto} aria-label="사진 촬영"><span /></button>
        <div className="camera-tip"><span>💡</span><small>밝은 곳에서<br />한 개만 찍어요</small></div>
      </footer>
    </main>
  );
}

function PhotoPreview({ image, phase, onRetake, onUse }: { image: string; phase: "before" | "after"; onRetake: () => void; onUse: () => void }) {
  return (
    <main className="preview-screen">
      <header className="simple-header"><button className="icon-button" onClick={onRetake}>←</button><h1>사진 확인</h1><span /></header>
      <section className="preview-content">
        <p className="eyebrow">{phase === "before" ? "처음 사진" : "고친 뒤 사진"}</p>
        <h2>물건이 잘 보이나요?</h2>
        <div className={`photo-preview ${image === "demo" ? "demo-photo" : ""}`} style={image !== "demo" ? { backgroundImage: `url(${image})` } : undefined}>
          {image === "demo" && <><span>🧴</span><b>{phase === "before" ? "라벨이 붙은 페트병" : "깨끗하게 고친 페트병"}</b></>}
        </div>
        <div className="preview-actions"><button className="secondary-button" onClick={onRetake}>다시 찍기</button><button className="primary-button" onClick={onUse}>이 사진 사용하기</button></div>
      </section>
    </main>
  );
}

function Analysis({ phase, mode, onDone, onRetry, onHome }: { phase: "before" | "after"; mode: AnalysisMode; onDone: (result: ScanAnalysis) => void; onRetry: () => void; onHome: () => void }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const first = window.setTimeout(() => setStage(1), 900);
    const second = window.setTimeout(() => {
      if (mode === "timeout") setStage(2);
      else onDone(phase === "before" ? beforeAnalysis : afterAnalysis);
    }, mode === "cached" ? 1100 : 2200);
    return () => { window.clearTimeout(first); window.clearTimeout(second); };
  }, [mode, onDone, phase]);
  if (stage === 2) {
    return <AnalysisRecovery onRetry={onRetry} onUseCache={() => onDone(phase === "before" ? beforeAnalysis : afterAnalysis)} onHome={onHome} />;
  }
  return (
    <main className="analysis-screen">
      <div className="analysis-visual"><div className="analysis-ring ring-one" /><div className="analysis-ring ring-two" /><div className="analysis-mascot"><span>🌱</span><b>{stage === 0 ? "•‿•" : "•◡•"}</b></div><div className="scan-line" /></div>
      <p className="eyebrow">{phase === "before" ? "AI 판정 중" : "다시 확인하는 중"}</p>
      <h1>{stage === 0 ? "어떤 물건인지 찾았어!" : "어떻게 바뀌었는지 살펴볼게"}</h1>
      <p>{mode === "cached" ? "저장된 안전 판정을 사용하고 있어요." : stage === 0 ? "투명 페트병을 발견했어." : "조금만 기다려줘. 금방 알려줄게!"}</p>
      <div className="analysis-steps"><span className="done">✓ 품목 찾기</span><span className={stage === 1 ? "active" : ""}>상태 살펴보기</span><span>배출법 알려주기</span></div>
    </main>
  );
}

function ActionResult({ result, onRetry, onSpeak }: { result: ScanAnalysis; onRetry: () => void; onSpeak: (text: string) => void }) {
  return (
    <main className="result-screen">
      <header className="result-header"><Brand compact /><span className="result-chip">🧴 {result.detection.classNameKo}</span></header>
      <section className="result-hero warning">
        <div className="result-character">🌱<b>•ᴗ•</b></div>
        <div><p className="eyebrow">거의 다 왔어!</p><h1>{result.feedback.title}</h1><p>{result.feedback.message}</p><button className="speak-button" onClick={() => onSpeak(result.feedback.ttsText)}>🔊 다시 듣기</button></div>
      </section>
      <section className="action-list-wrap"><div className="section-heading"><div><span className="section-icon">✨</span><div><small>직접 해볼 차례</small><h2>이 세 가지만 고쳐보자</h2></div></div><b className="count-chip">3가지</b></div><div className="action-list">{result.requiredActions.map((action, index) => <article className="action-item" key={action.code}><b>{index + 1}</b><span>{action.icon}</span><div><h3>{action.labelKo}</h3><p>{action.description}</p></div></article>)}</div></section>
      <footer className="sticky-action"><div><span>💡</span><p><strong>다 고쳤다면?</strong><small>같은 물건을 다시 찍어 보여줘!</small></p></div><button className="primary-button" onClick={onRetry}>고치고 다시 찍기 <span>→</span></button></footer>
    </main>
  );
}

function Reward({ nickname, onHome, onCollection }: { nickname: string; onHome: () => void; onCollection: () => void }) {
  const [revealed, setRevealed] = useState(false);
  useEffect(() => { const timer = window.setTimeout(() => setRevealed(true), 450); return () => window.clearTimeout(timer); }, []);
  return (
    <main className="reward-screen">
      <div className="confetti" aria-hidden="true">✦ ● ★ ✦ ● ★</div>
      <section className="reward-card">
        <div className="success-mark">✓</div><p className="eyebrow">행동 완성!</p><h1>완벽해, {nickname}!</h1><p>라벨과 뚜껑을 떼고 납작하게 잘 눌렀어.<br />이제 투명 페트병 전용함으로 보내주자!</p>
        <div className={`unlocked-card ${revealed ? "revealed" : ""}`}><span className="rarity">일반 카드</span><div className="card-art">🧴<small>✦</small></div><h2>투명 페트병</h2><p>라벨·뚜껑 분리 완료</p></div>
        <div className="reward-row"><span><b>+10</b><small>판정 완료</small></span><span><b>+20</b><small>다시 찍기 성공</small></span><span><b>+30</b><small>새 카드 발견</small></span><strong><b>+60 XP</b><small>총 획득</small></strong></div>
        <div className="reward-actions"><button className="secondary-button" onClick={onCollection}>도감에서 보기</button><button className="primary-button" onClick={onHome}>홈으로 돌아가기</button></div>
      </section>
    </main>
  );
}

function Collection({ nickname, onBack }: { nickname: string; onBack: () => void }) {
  const [filter, setFilter] = useState<"all" | "chungbuk">("all");
  const visibleCards = filter === "chungbuk"
    ? collectionCards.filter((card) => ["yeongdong-grape", "goesan-paste", "cheongju-delivery"].includes(card.id))
    : collectionCards;
  return (
    <main className="app-shell"><AppHeader nickname={nickname} onHome={onBack} /><section className="collection-page"><button className="back-link" onClick={onBack}>← 홈으로</button><p className="eyebrow">헷갈림 도감</p><h1>쓰레기를 만날수록<br />도감이 채워져요</h1><p>4 / 30종 발견 · 새 품목을 촬영하면 카드가 열려요.</p><div className="collection-filters"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>전체 카드</button><button className={filter === "chungbuk" ? "active" : ""} onClick={() => setFilter("chungbuk")}>💚 충북 특화</button></div><div className="collection-grid">{visibleCards.map((card) => <article key={card.id} className={`collection-item ${card.acquired ? "" : "locked"}`}><span className={`rarity rarity-${card.rarity}`}>{card.rarity}</span><div>{card.acquired ? card.icon : "?"}</div><h2>{card.acquired ? card.name : "아직 비밀"}</h2><p>{card.hint}</p></article>)}</div></section></main>
  );
}

export default function DasiBomApp() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [nickname, setNickname] = useState("초록탐험가");
  const [image, setImage] = useState("demo");
  const [result, setResult] = useState<ScanAnalysis>(beforeAnalysis);
  const [muted, setMuted] = useState(false);
  const [analysisMode, setAnalysisMode] = useState<AnalysisMode>("normal");
  const online = useOnlineStatus();
  const { resumeScreen, clear: clearResume } = useScanRecovery(screen, nickname);
  useServiceWorker();
  const effectiveAnalysisMode: AnalysisMode = online ? analysisMode : "cached";

  useEffect(() => {
    const saved = window.sessionStorage.getItem("dasibom-nickname");
    if (!saved) return;
    const timer = window.setTimeout(() => setNickname(saved), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const speak = useCallback((text: string) => {
    if (muted || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "ko-KR";
    utterance.rate = 0.95;
    window.speechSynthesis.speak(utterance);
  }, [muted]);

  const page = useMemo(() => {
    switch (screen) {
      case "welcome": return <Welcome onStart={() => setScreen("join")} onTeacher={() => setScreen("teacher-login")} />;
      case "join": return <Join onBack={() => setScreen("welcome")} onSuccess={() => setScreen("nickname")} />;
      case "nickname": return <Nickname onComplete={(name) => { setNickname(name); window.sessionStorage.setItem("dasibom-nickname", name); setScreen("home"); }} />;
      case "home": return <Home nickname={nickname} onScan={() => setScreen("camera")} onCollection={() => setScreen("collection")} onMissions={() => setScreen("missions")} onCharacter={() => setScreen("character")} onBadges={() => setScreen("badges")} onChecklist={() => setScreen("checklist")} onGoal={() => setScreen("class-goal")} onSettings={() => setScreen("settings")} />;
      case "camera": return <CameraView phase="before" onCancel={() => setScreen("home")} onCapture={(photo) => { setImage(photo); setScreen("preview"); }} />;
      case "preview": return <PhotoPreview image={image} phase="before" onRetake={() => setScreen("camera")} onUse={() => setScreen("analysis")} />;
      case "analysis": return <Analysis phase="before" mode={effectiveAnalysisMode} onDone={(analysis) => { setResult(analysis); setScreen("action"); }} onRetry={() => setAnalysisMode("normal")} onHome={() => setScreen("home")} />;
      case "action": return <ActionResult result={result} onRetry={() => setScreen("after-camera")} onSpeak={speak} />;
      case "after-camera": return <CameraView phase="after" onCancel={() => setScreen("action")} onCapture={(photo) => { setImage(photo); setScreen("after-preview"); }} />;
      case "after-preview": return <PhotoPreview image={image} phase="after" onRetake={() => setScreen("after-camera")} onUse={() => setScreen("after-analysis")} />;
      case "after-analysis": return <Analysis phase="after" mode={effectiveAnalysisMode} onDone={() => setScreen("reward")} onRetry={() => setAnalysisMode("normal")} onHome={() => setScreen("home")} />;
      case "reward": return <Reward nickname={nickname} onHome={() => setScreen("home")} onCollection={() => setScreen("collection")} />;
      case "collection": return <Collection nickname={nickname} onBack={() => setScreen("home")} />;
      case "missions": return <MissionsPage onBack={() => setScreen("home")} onScan={() => setScreen("camera")} />;
      case "character": return <CharacterPage onBack={() => setScreen("home")} onBadges={() => setScreen("badges")} />;
      case "badges": return <BadgesPage onBack={() => setScreen("home")} />;
      case "class-goal": return <ClassGoalPage onBack={() => setScreen("home")} />;
      case "checklist": return <ChecklistPage onBack={() => setScreen("home")} onComplete={() => setScreen("checklist-result")} />;
      case "checklist-result": return <ChecklistResult onBack={() => setScreen("home")} />;
      case "settings": return <SettingsPage muted={muted} onMutedChange={setMuted} demoMode={analysisMode} onDemoModeChange={setAnalysisMode} onBack={() => setScreen("home")} onTeacher={() => setScreen("teacher-login")} />;
      case "teacher-login": return <TeacherLogin onBack={() => setScreen("welcome")} onLogin={() => setScreen("teacher-dashboard")} />;
      case "teacher-dashboard": return <TeacherDashboard onLogout={() => setScreen("welcome")} />;
    }
  }, [analysisMode, effectiveAnalysisMode, image, muted, nickname, result, screen, speak]);

  return (
    <>
      <NetworkBanner online={online} />
      {(screen === "home" || screen === "welcome") && resumeScreen && (
        <ResumeNotice
          screen={resumeScreen}
          onResume={() => { const target = resumeScreen; clearResume(); setScreen(target); }}
          onDiscard={clearResume}
        />
      )}
      {page}
    </>
  );
}
