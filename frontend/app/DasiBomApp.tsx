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
import { apiConfig } from "../lib/api/config";
import { apiErrorMessage, disposalNames, toScanAnalysis, withRo } from "../lib/api/adapters";
import { collectionApi, missionApi, scanApi, studentApi, teacherApi } from "../lib/api/services";
import { studentSessionStore, teacherSessionStore, type StudentSession, type TeacherSession } from "../lib/api/session";
import { imageUrlToBlob, pollAfterAnalysis, pollAnalysis } from "../lib/api/workflows";
import type { CollectionItemResponse, CollectionResponse, HomeResponse, Mission, RewardResponse, TeacherClassResponse } from "../lib/api/contracts";

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

function Join({ onBack, onSuccess }: { onBack: () => void; onSuccess: (code: string) => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState("");

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (apiConfig.enableMock) {
      if (code.toUpperCase() !== DEMO_CODE) {
        setError(`체험 코드는 ${DEMO_CODE}예요.`);
        return;
      }
    } else if (!/^\d{6}$/.test(code)) {
      // 실제 학급 코드는 숫자 6자리다. 여기서 막지 않으면 별명 단계까지 가서야 422가 난다.
      setError("참여 코드는 숫자 6자리야.");
      return;
    }
    onSuccess(code.toUpperCase());
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
        <p>{apiConfig.enableMock ? "영문 또는 숫자로 된 6자리 코드야." : "숫자 6자리 코드야."}</p>
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
            placeholder={apiConfig.enableMock ? DEMO_CODE : "000000"}
            autoCapitalize="characters"
            autoComplete="off"
            aria-describedby={error ? "code-error" : undefined}
          />
          {error && <p id="code-error" className="form-error">{error}</p>}
          <button className="primary-button" disabled={code.length !== 6}>다음으로</button>
        </form>
        {apiConfig.enableMock && (
          <button className="text-button" onClick={() => { setCode(DEMO_CODE); setError(""); }}>
            체험 코드 자동 입력
          </button>
        )}
      </section>
    </main>
  );
}

function Nickname({ onComplete }: { onComplete: (nickname: string) => Promise<void> }) {
  const [nickname, setNickname] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (nickname.trim().length < 2 || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await onComplete(nickname.trim());
    } catch (reason) {
      setError(apiErrorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  };
  return (
    <main className="auth-screen">
      <header className="simple-header"><span /><Brand compact /><span /></header>
      <section className="auth-card">
        <StepDots current={2} />
        <div className="auth-icon">👋</div>
        <p className="eyebrow">마지막 준비</p>
        <h1>어떻게 불러주면 될까?</h1>
        <p>진짜 이름 대신 나만의 별명을 만들어보자.</p>
        <form onSubmit={submit}>
          <label htmlFor="nickname">나의 별명</label>
          <input
            id="nickname"
            value={nickname}
            onChange={(event) => setNickname(event.target.value.slice(0, 10))}
            placeholder="예: 초록탐험가"
            autoComplete="off"
          />
          <div className="input-meta"><span>2~10글자로 입력해줘</span><span>{nickname.length}/10</span></div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={nickname.trim().length < 2 || submitting}>{submitting ? "우리 반에 들어가는 중…" : "탐험 시작하기"}</button>
        </form>
      </section>
    </main>
  );
}

function AppHeader({ nickname, onHome, onSettings, homeData }: { nickname: string; onHome: () => void; onSettings?: () => void; homeData?: HomeResponse | null }) {
  return (
    <header className="app-header">
      <button className="brand-button" onClick={onHome}><Brand compact /></button>
      <div className="header-stats">
        <span>🌱 Lv. {homeData?.student.level ?? 3}</span><span>⭐ {homeData?.student.xp ?? 180} XP</span><button className="profile-button" onClick={onSettings} aria-label="설정 열기">{nickname.slice(0, 1)}</button>
      </div>
    </header>
  );
}

function Home({ nickname, homeData, mission, onScan, onCollection, onMissions, onCharacter, onBadges, onChecklist, onGoal, onSettings }: { nickname: string; homeData?: HomeResponse | null; mission?: Mission | null; onScan: () => void; onCollection: () => void; onMissions: () => void; onCharacter: () => void; onBadges: () => void; onChecklist: () => void; onGoal: () => void; onSettings: () => void }) {
  const goalCurrent = homeData?.classGoal.current ?? 312;
  const goalTarget = homeData?.classGoal.target ?? 500;
  const goalPercent = goalTarget > 0 ? Math.min(100, goalCurrent / goalTarget * 100) : 0;
  return (
    <main className="app-shell">
      <AppHeader nickname={nickname} homeData={homeData} onHome={() => undefined} onSettings={onSettings} />
      <section className="home-grid">
        <div className="home-main">
          <div className="greeting"><div><p>안녕, {nickname}! 👋</p><h1>오늘은 어떤 쓰레기를<br />새롭게 만나볼까?</h1></div><div className="mini-mascot">•ᴗ•<span>🌱</span></div></div>
          <button className="scan-cta" onClick={onScan}>
            <span className="scan-cta-icon">⌾</span>
            <span><small>자유 촬영</small><strong>아무 쓰레기나 찍어보기</strong><em>언제나 열려 있어요</em></span>
            <b>→</b>
          </button>
          <button className="section-block clickable-block" onClick={onMissions}>
            <div className="section-heading"><div><span className="section-icon">⚡</span><div><small>오늘의 보너스</small><h2>{mission?.title ?? "라벨 구출 작전"}</h2></div></div><b className="bonus-chip">{mission ? `+${mission.rewardXp} XP` : "XP 2배"}</b></div>
            <p>{mission?.description ?? "라벨을 떼고 다시 찍어서 성공해보자!"}</p>
            <div className="mission-progress"><span style={{ width: "50%" }} /></div>
            <div className="progress-caption"><span>1 / 2번 성공</span><strong>한 번만 더!</strong></div>
          </button>
          <button className="section-block class-goal clickable-block" onClick={onGoal}>
            <div className="section-heading"><div><span className="section-icon blue">🤝</span><div><small>우리 반 공동 목표</small><h2>우리 반 카드 {goalTarget}장 모으기</h2></div></div><strong>{goalCurrent}장</strong></div>
            <div className="class-progress"><span style={{ width: `${goalPercent}%` }} /></div>
            <p>{Math.max(0, goalTarget - goalCurrent)}장 더 모으면 목표를 달성해요!</p>
          </button>
        </div>
        <aside className="home-side">
          <button className="character-card" onClick={onCharacter}>
            <div className="level-pill">LEVEL 3</div>
            <div className="side-mascot"><span>🌱</span><b>•ᴗ•</b></div>
            <h2>새싹 봄이</h2><p>다음 성장까지 {Math.max(0, (homeData?.student.nextLevelXp ?? 250) - (homeData?.student.xp ?? 180))} XP</p>
            <div className="xp-progress"><span style={{ width: `${Math.min(100, (homeData?.student.xp ?? 180) / (homeData?.student.nextLevelXp ?? 250) * 100)}%` }} /></div>
            <div className="xp-label"><span>{homeData?.student.xp ?? 180}</span><span>{homeData?.student.nextLevelXp ?? 250} XP</span></div>
          </button>
          <button className="menu-card" onClick={onCollection}><span>📚</span><div><strong>헷갈림 도감</strong><small>{homeData?.collection.collected ?? 3} / {homeData?.collection.total ?? 30}종 발견</small></div><b>→</b></button>
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

function Analysis({ phase, mode, run, onDone, onRetry, onHome }: { phase: "before" | "after"; mode: AnalysisMode; run?: () => Promise<ScanAnalysis>; onDone: (result: ScanAnalysis) => void; onRetry: () => void; onHome: () => void }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const first = window.setTimeout(() => setStage(1), 900);
    if (run) {
      void run().then(onDone).catch(() => setStage(2));
      return () => window.clearTimeout(first);
    }
    const second = window.setTimeout(() => {
      if (mode === "timeout") setStage(2);
      else onDone(phase === "before" ? beforeAnalysis : afterAnalysis);
    }, mode === "cached" ? 1100 : 2200);
    return () => { window.clearTimeout(first); window.clearTimeout(second); };
  }, [mode, onDone, phase, run]);
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

// 고칠 개수는 판정마다 다르다. "세 가지"로 못박으면 두 개만 뜰 때 아이가 하나를 찾아 헤맨다.
const COUNT_KO = ["", "한", "두", "세", "네", "다섯", "여섯"];
function actionHeading(count: number) {
  if (count === 0) return "고칠 게 없어!";
  const word = COUNT_KO[count] ?? String(count);
  return `이 ${word} 가지만 고쳐보자`;
}

function ActionResult({ result, onRetry, onSpeak }: { result: ScanAnalysis; onRetry: () => void; onSpeak: (text: string) => void }) {
  return (
    <main className="result-screen">
      <header className="result-header"><Brand compact /><span className="result-chip">🧴 {result.detection.classNameKo}</span></header>
      <section className="result-hero warning">
        <div className="result-character">🌱<b>•ᴗ•</b></div>
        <div><p className="eyebrow">거의 다 왔어!</p><h1>{result.feedback.title}</h1><p>{result.feedback.message}</p><button className="speak-button" onClick={() => onSpeak(result.feedback.ttsText)}>🔊 다시 듣기</button></div>
      </section>
      <section className="action-list-wrap"><div className="section-heading"><div><span className="section-icon">✨</span><div><small>직접 해볼 차례</small><h2>{actionHeading(result.requiredActions.length)}</h2></div></div><b className="count-chip">{result.requiredActions.length}가지</b></div><div className="action-list">{result.requiredActions.map((action, index) => <article className="action-item" key={`${action.code}-${index}`}><b>{index + 1}</b><span>{action.icon}</span><div><h3>{action.labelKo}</h3><p>{action.description}</p></div></article>)}</div></section>
      <footer className="sticky-action"><div><span>💡</span><p><strong>다 고쳤다면?</strong><small>같은 물건을 다시 찍어 보여줘!</small></p></div><button className="primary-button" onClick={onRetry}>고치고 다시 찍기 <span>→</span></button></footer>
    </main>
  );
}

// 도감 카드 class 별 그림. 카드 자체 아이콘이 백엔드에 없어서 여기서 고른다.
const CARD_ART: Record<string, string> = {
  pet: "🧴", plastic: "🥡", can: "🥫", glass: "🍾",
  pack: "🥛", paper: "📦", vinyl: "🛍️", etc: "♻️",
};

function rarityOf(level?: number) {
  if (!level) return "일반";
  return level >= 3 ? "전설" : level === 2 ? "희귀" : "일반";
}

function Reward({ nickname, reward, result, card, onHome, onCollection }: { nickname: string; reward?: RewardResponse | null; result: ScanAnalysis; card?: CollectionItemResponse | null; onHome: () => void; onCollection: () => void }) {
  const [revealed, setRevealed] = useState(false);
  useEffect(() => { const timer = window.setTimeout(() => setRevealed(true), 450); return () => window.clearTimeout(timer); }, []);

  // 도감 카드 이름이 가장 정확하다. 없으면 판정 품목명으로 떨어진다.
  const itemName = card?.name ?? result.detection.classNameKo;
  const binName = result.disposalCategory ? disposalNames[result.disposalCategory] : undefined;
  const doneActions = result.requiredActions.map((action) => action.labelKo);
  const registered = reward?.collection?.registered ?? false;
  const gainedXp = reward?.reward.xp;

  return (
    <main className="reward-screen">
      <div className="confetti" aria-hidden="true">✦ ● ★ ✦ ● ★</div>
      <section className="reward-card">
        <div className="success-mark">✓</div><p className="eyebrow">행동 완성!</p><h1>완벽해, {nickname}!</h1>
        <p>{doneActions.length > 0 ? `${doneActions.join(", ")} 잘 해냈어.` : `${itemName}, 그대로 배출해도 좋아.`}{binName && <><br />{`이제 ${withRo(binName)} 보내주자!`}</>}</p>
        {registered && (
          <div className={`unlocked-card ${revealed ? "revealed" : ""}`}>
            <span className="rarity">{rarityOf(card?.level)} 카드</span>
            <div className="card-art">{CARD_ART[card?.class ?? "etc"] ?? "♻️"}<small>✦</small></div>
            <h2>{itemName}</h2>
            <p>{reward?.collection?.isNew ? "새로 발견한 카드!" : `${reward?.collection?.count ?? card?.count ?? 1}번째 발견`}</p>
          </div>
        )}
        <div className="reward-row">
          <span><b>+10</b><small>판정 완료</small></span>
          {reward?.reward.missionCompleted && <span><b>+30</b><small>미션 완료</small></span>}
          {typeof reward?.student.level === "number" && <span><b>Lv.{reward.student.level}</b><small>지금 레벨</small></span>}
          <strong><b>{typeof gainedXp === "number" ? `+${gainedXp} XP` : "XP 계산 중"}</b><small>{typeof reward?.student.xp === "number" ? `누적 ${reward.student.xp} XP` : "총 획득"}</small></strong>
        </div>
        <div className="reward-actions"><button className="secondary-button" onClick={onCollection}>도감에서 보기</button><button className="primary-button" onClick={onHome}>홈으로 돌아가기</button></div>
      </section>
    </main>
  );
}

function Collection({ nickname, remoteCollection, onBack }: { nickname: string; remoteCollection?: CollectionResponse | null; onBack: () => void }) {
  const [filter, setFilter] = useState<"all" | "chungbuk">("all");
  const apiCards = remoteCollection?.collections.map((card) => ({
    id: card.cardId,
    name: card.name,
    icon: "♻️",
    rarity: (card.level >= 3 ? "전설" : card.level === 2 ? "희귀" : "일반") as "일반" | "희귀" | "전설",
    acquired: card.collected,
    hint: card.needsActions?.join(" · ") ?? (card.collected ? `${card.count}회 발견` : "아직 발견하지 않은 카드예요"),
  }));
  const sourceCards = apiCards?.length ? apiCards : collectionCards;
  const visibleCards = filter === "chungbuk"
    ? collectionCards.filter((card) => ["yeongdong-grape", "goesan-paste", "cheongju-delivery"].includes(card.id))
    : sourceCards;
  return (
    <main className="app-shell"><AppHeader nickname={nickname} onHome={onBack} /><section className="collection-page"><button className="back-link" onClick={onBack}>← 홈으로</button><p className="eyebrow">헷갈림 도감</p><h1>쓰레기를 만날수록<br />도감이 채워져요</h1><p>{remoteCollection?.collectedCount ?? 4} / {remoteCollection?.totalCount ?? 30}종 발견 · 새 품목을 촬영하면 카드가 열려요.</p><div className="collection-filters"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>전체 카드</button><button className={filter === "chungbuk" ? "active" : ""} onClick={() => setFilter("chungbuk")}>💚 충북 특화</button></div><div className="collection-grid">{visibleCards.map((card) => <article key={card.id} className={`collection-item ${card.acquired ? "" : "locked"}`}><span className={`rarity rarity-${card.rarity}`}>{card.rarity}</span><div>{card.acquired ? card.icon : "?"}</div><h2>{card.acquired ? card.name : "아직 비밀"}</h2><p>{card.hint}</p></article>)}</div></section></main>
  );
}

export default function DasiBomApp() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [nickname, setNickname] = useState("초록탐험가");
  const [pendingClassCode, setPendingClassCode] = useState(DEMO_CODE);
  const [studentSession, setStudentSession] = useState<StudentSession | null>(null);
  const [teacherSession, setTeacherSession] = useState<TeacherSession | null>(null);
  const [homeData, setHomeData] = useState<HomeResponse | null>(null);
  const [todayMission, setTodayMission] = useState<Mission | null>(null);
  const [remoteCollection, setRemoteCollection] = useState<CollectionResponse | null>(null);
  const [teacherClass, setTeacherClass] = useState<TeacherClassResponse | null>(null);
  const [scanSessionId, setScanSessionId] = useState<string | null>(null);
  const [reward, setReward] = useState<RewardResponse | null>(null);
  const [rewardCard, setRewardCard] = useState<CollectionItemResponse | null>(null);
  const [apiNotice, setApiNotice] = useState("");
  const [analysisAttempt, setAnalysisAttempt] = useState(0);
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
    const timer = window.setTimeout(() => {
      setStudentSession(studentSessionStore.get());
      setTeacherSession(teacherSessionStore.get());
      if (saved) setNickname(saved);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (apiConfig.enableMock || !studentSession || screen !== "home") return;
    let active = true;
    void Promise.all([
      studentApi.home(studentSession.studentToken),
      missionApi.today(studentSession.studentToken),
    ]).then(([nextHome, nextMission]) => {
      if (!active) return;
      setHomeData(nextHome);
      setTodayMission(nextMission.mission);
      setApiNotice("");
    }).catch((error) => active && setApiNotice(apiErrorMessage(error)));
    return () => { active = false; };
  }, [screen, studentSession]);

  useEffect(() => {
    if (apiConfig.enableMock || !studentSession || screen !== "collection") return;
    let active = true;
    void collectionApi.list(studentSession.studentToken)
      .then((value) => { if (active) setRemoteCollection(value); })
      .catch((error) => active && setApiNotice(apiErrorMessage(error)));
    return () => { active = false; };
  }, [screen, studentSession]);

  useEffect(() => {
    if (apiConfig.enableMock || !teacherSession || screen !== "teacher-dashboard") return;
    let active = true;
    const classId = teacherSession.classId ?? apiConfig.teacherClassId;
    void Promise.all([
      teacherApi.classDashboard(teacherSession.teacherId, classId),
      teacherApi.classCode(teacherSession.teacherId, classId),
    ]).then(([value, code]) => { if (active) setTeacherClass({ ...value, ...code }); })
      .catch((error) => active && setApiNotice(apiErrorMessage(error)));
    return () => { active = false; };
  }, [screen, teacherSession]);

  const enterStudent = useCallback(async (name: string) => {
    let nextSession: StudentSession;
    if (apiConfig.enableMock) {
      nextSession = {
        studentId: "demo-student",
        studentToken: "demo-token",
        nickname: name,
        classId: "demo-class",
        classCode: pendingClassCode,
      };
    } else {
      const response = await studentApi.enter(pendingClassCode, name);
      nextSession = { ...response, classCode: pendingClassCode };
    }
    studentSessionStore.set(nextSession);
    setStudentSession(nextSession);
    setNickname(nextSession.nickname);
    window.sessionStorage.setItem("dasibom-nickname", nextSession.nickname);
    setScreen("home");
  }, [pendingClassCode]);

  // 보상 응답은 cardId 만 준다. 카드 이름·등급은 도감 상세에서 가져온다.
  const grantReward = useCallback(async (sessionId: string, studentToken: string) => {
    const nextReward = await scanApi.reward(sessionId, studentToken);
    setReward(nextReward);
    const cardId = nextReward.collection?.registered ? nextReward.collection.cardId : null;
    if (cardId) {
      // 카드 조회가 실패해도 보상 자체는 이미 지급됐다. 화면을 막지 않는다.
      void collectionApi.detail(cardId, studentToken)
        .then((detail) => setRewardCard(detail))
        .catch(() => setRewardCard(null));
    }
    if (todayMission) {
      void missionApi.complete(todayMission.missionId, sessionId, studentToken).catch(() => undefined);
    }
    return nextReward;
  }, [todayMission]);

  const runLiveAnalysis = useCallback(async (phase: "before" | "after") => {
    if (!studentSession) throw new Error("학생 인증이 필요해요. 다시 입장해주세요.");
    if (phase === "before") {
      const blob = await imageUrlToBlob(image);
      const session = await scanApi.create(studentSession.studentToken, "FREE");
      setScanSessionId(session.sessionId);
      await scanApi.uploadBefore(session.sessionId, studentSession.studentToken, blob);
      const analysis = toScanAnalysis(await pollAnalysis(session.sessionId, studentSession.studentToken));
      // 처음부터 깨끗해서 고칠 게 없으면 AFTER 없이 여기서 끝난다.
      // 그때도 보상은 받아야 하므로 직접 지급한다. (AFTER 경로에는 아래에 따로 있다)
      if (analysis.status === "COMPLETED") {
        await grantReward(session.sessionId, studentSession.studentToken);
      }
      return analysis;
    }
    if (!scanSessionId) throw new Error("진행 중인 촬영 세션을 찾지 못했어요.");
    const afterBlob = await imageUrlToBlob(image);
    await scanApi.uploadAfter(scanSessionId, studentSession.studentToken, afterBlob);
    const afterResult = await pollAfterAnalysis(scanSessionId, studentSession.studentToken);
    const after = afterResult.after ?? { improved: false, remainingActions: [] };
    if (!after.improved) {
      const message = after.remainingActions[0] ?? "아직 조금 더 손봐야 해.";
      return {
        ...beforeAnalysis,
        analysisId: `analysis-after-${scanSessionId}`,
        scanSessionId,
        phase: "AFTER",
        requiredActions: after.remainingActions.map((label, index) => ({
          ...beforeAnalysis.requiredActions[index % beforeAnalysis.requiredActions.length],
          labelKo: label,
          description: label,
        })),
        feedback: { title: "한 번만 더 고쳐보자", message, ttsText: message },
      } satisfies ScanAnalysis;
    }
    await grantReward(scanSessionId, studentSession.studentToken);
    return { ...afterAnalysis, scanSessionId, analysisId: `analysis-after-${scanSessionId}` };
  }, [grantReward, image, scanSessionId, studentSession]);

  const loginTeacher = useCallback(async (name: string, email: string) => {
    const response = apiConfig.enableMock
      ? { success: true as const, teacherId: "demo-teacher", name, email }
      : await teacherApi.login(name, email);
    const nextSession: TeacherSession = { ...response, classId: apiConfig.teacherClassId };
    teacherSessionStore.set(nextSession);
    setTeacherSession(nextSession);
    setScreen("teacher-dashboard");
  }, []);

  const toggleTeacherClassLock = useCallback(async (locked: boolean) => {
    if (!teacherSession || apiConfig.enableMock) {
      setTeacherClass((current) => current ? { ...current, locked } : current);
      return;
    }
    await teacherApi.setLocked(teacherSession.teacherId, teacherSession.classId ?? apiConfig.teacherClassId, locked);
    setTeacherClass((current) => current ? { ...current, locked } : current);
  }, [teacherSession]);

  const createTeacherClass = useCallback(async (input: { school: string; grade: number; className: number; goalTarget: number }) => {
    if (!teacherSession) throw new Error("교사 로그인이 필요합니다.");
    const created = apiConfig.enableMock
      ? { success: true as const, classId: "demo-class", classCode: "581942", ...input, goalCurrent: 0, locked: false, studentCount: 0 }
      : await teacherApi.createClass(teacherSession.teacherId, input);
    const nextSession = { ...teacherSession, classId: created.classId };
    teacherSessionStore.set(nextSession);
    setTeacherSession(nextSession);
    setTeacherClass(created);
  }, [teacherSession]);

  const refreshTeacherCode = useCallback(async () => {
    if (!teacherSession || apiConfig.enableMock) return "581942";
    const value = await teacherApi.classCode(teacherSession.teacherId, teacherSession.classId ?? apiConfig.teacherClassId);
    setTeacherClass((current) => current ? { ...current, ...value } : current);
    return value.classCode;
  }, [teacherSession]);

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
      case "join": return <Join onBack={() => setScreen("welcome")} onSuccess={(code) => { setPendingClassCode(code); setScreen("nickname"); }} />;
      case "nickname": return <Nickname onComplete={enterStudent} />;
      case "home": return <Home nickname={nickname} homeData={homeData} mission={todayMission} onScan={() => { setScanSessionId(null); setReward(null); setRewardCard(null); setScreen("camera"); }} onCollection={() => setScreen("collection")} onMissions={() => setScreen("missions")} onCharacter={() => setScreen("character")} onBadges={() => setScreen("badges")} onChecklist={() => setScreen("checklist")} onGoal={() => setScreen("class-goal")} onSettings={() => setScreen("settings")} />;
      case "camera": return <CameraView phase="before" onCancel={() => setScreen("home")} onCapture={(photo) => { setImage(photo); setScreen("preview"); }} />;
      case "preview": return <PhotoPreview image={image} phase="before" onRetake={() => setScreen("camera")} onUse={() => setScreen("analysis")} />;
      case "analysis": return <Analysis key={`before-${analysisAttempt}`} phase="before" mode={effectiveAnalysisMode} run={apiConfig.enableMock ? undefined : () => runLiveAnalysis("before")} onDone={(analysis) => { setResult(analysis); setScreen(analysis.status === "COMPLETED" ? "reward" : "action"); }} onRetry={() => { setAnalysisMode("normal"); setAnalysisAttempt((value) => value + 1); }} onHome={() => setScreen("home")} />;
      case "action": return <ActionResult result={result} onRetry={() => setScreen("after-camera")} onSpeak={speak} />;
      case "after-camera": return <CameraView phase="after" onCancel={() => setScreen("action")} onCapture={(photo) => { setImage(photo); setScreen("after-preview"); }} />;
      case "after-preview": return <PhotoPreview image={image} phase="after" onRetake={() => setScreen("after-camera")} onUse={() => setScreen("after-analysis")} />;
      case "after-analysis": return <Analysis key={`after-${analysisAttempt}`} phase="after" mode={effectiveAnalysisMode} run={apiConfig.enableMock ? undefined : () => runLiveAnalysis("after")} onDone={(analysis) => { setResult(analysis); setScreen(analysis.status === "COMPLETED" ? "reward" : "action"); }} onRetry={() => { setAnalysisMode("normal"); setAnalysisAttempt((value) => value + 1); }} onHome={() => setScreen("home")} />;
      case "reward": return <Reward nickname={nickname} reward={reward} result={result} card={rewardCard} onHome={() => setScreen("home")} onCollection={() => setScreen("collection")} />;
      case "collection": return <Collection nickname={nickname} remoteCollection={remoteCollection} onBack={() => setScreen("home")} />;
      case "missions": return <MissionsPage mission={todayMission} onBack={() => setScreen("home")} onScan={() => setScreen("camera")} />;
      case "character": return <CharacterPage onBack={() => setScreen("home")} onBadges={() => setScreen("badges")} />;
      case "badges": return <BadgesPage onBack={() => setScreen("home")} />;
      case "class-goal": return <ClassGoalPage onBack={() => setScreen("home")} />;
      case "checklist": return <ChecklistPage onBack={() => setScreen("home")} onComplete={() => setScreen("checklist-result")} />;
      case "checklist-result": return <ChecklistResult onBack={() => setScreen("home")} />;
      case "settings": return <SettingsPage muted={muted} onMutedChange={setMuted} demoMode={analysisMode} onDemoModeChange={setAnalysisMode} onBack={() => setScreen("home")} onTeacher={() => setScreen("teacher-login")} />;
      case "teacher-login": return <TeacherLogin onBack={() => setScreen("welcome")} onLogin={loginTeacher} />;
      case "teacher-dashboard": return <TeacherDashboard teacher={teacherSession} classData={teacherClass} onCreateClass={createTeacherClass} onRefreshCode={refreshTeacherCode} onToggleLock={toggleTeacherClassLock} onLogout={() => { teacherSessionStore.clear(); setTeacherSession(null); setScreen("welcome"); }} />;
    }
  }, [analysisAttempt, analysisMode, createTeacherClass, effectiveAnalysisMode, enterStudent, homeData, image, loginTeacher, muted, nickname, refreshTeacherCode, remoteCollection, result, reward, rewardCard, runLiveAnalysis, screen, speak, teacherClass, teacherSession, todayMission, toggleTeacherClassLock]);

  return (
    <>
      <NetworkBanner online={online} />
      {apiNotice && <div className="api-status-banner" role="alert">{apiNotice}<button onClick={() => setApiNotice("")} aria-label="알림 닫기">×</button></div>}
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
