"use client";

import type { Screen } from "./types";

export type AnalysisMode = "normal" | "cached" | "timeout";

export function NetworkBanner({ online }: { online: boolean }) {
  if (online) return null;
  return (
    <div className="network-banner" role="status">
      <span>●</span>
      인터넷 연결이 끊겼어요. 준비된 사례는 캐시 모드로 계속 체험할 수 있어요.
    </div>
  );
}

export function ResumeNotice({
  screen,
  onResume,
  onDiscard,
}: {
  screen: Screen;
  onResume: () => void;
  onDiscard: () => void;
}) {
  return (
    <aside className="resume-notice" role="status">
      <div className="resume-icon">↻</div>
      <div>
        <strong>진행 중이던 촬영이 있어요</strong>
        <p>30분 동안 안전하게 기억하고 있어요. 이어서 해볼까요?</p>
      </div>
      <button className="text-button" onClick={onDiscard}>새로 시작</button>
      <button className="primary-button" onClick={onResume}>이어서 하기</button>
      <span className="sr-only">저장된 화면: {screen}</span>
    </aside>
  );
}

export function AnalysisRecovery({
  onRetry,
  onUseCache,
  onHome,
}: {
  onRetry: () => void;
  onUseCache: () => void;
  onHome: () => void;
}) {
  return (
    <main className="recovery-page">
      <div className="recovery-mascot">🌱<b>•︵•</b></div>
      <p className="eyebrow">잠시 연결이 느려요</p>
      <h1>봄이가 조금 오래<br />생각하고 있어요</h1>
      <p>사진은 안전하게 처리했어요. 다시 시도하거나 준비된 판정으로 계속할 수 있어요.</p>
      <div className="recovery-actions">
        <button className="primary-button" onClick={onRetry}>다시 판정하기</button>
        <button className="secondary-button" onClick={onUseCache}>캐시 결과로 계속</button>
        <button className="text-button" onClick={onHome}>홈으로 돌아가기</button>
      </div>
    </main>
  );
}

export function DemoModeControl({
  value,
  onChange,
}: {
  value: AnalysisMode;
  onChange: (value: AnalysisMode) => void;
}) {
  return (
    <section className="demo-mode-control">
      <div><span>🛟</span><div><strong>발표 안정화 모드</strong><small>실제 서버 상태에 따른 화면을 미리 점검해요</small></div></div>
      <div className="segmented-control">
        <button className={value === "normal" ? "active" : ""} onClick={() => onChange("normal")}>정상</button>
        <button className={value === "cached" ? "active" : ""} onClick={() => onChange("cached")}>캐시</button>
        <button className={value === "timeout" ? "active" : ""} onClick={() => onChange("timeout")}>지연 테스트</button>
      </div>
    </section>
  );
}
