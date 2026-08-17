import type { CollectionCard, ScanAnalysis } from "./types";

export const beforeAnalysis: ScanAnalysis = {
  analysisId: "analysis-before-demo",
  scanSessionId: "scan-demo-001",
  phase: "BEFORE",
  status: "ACTION_REQUIRED",
  detection: {
    classCode: "pet_transparent",
    classNameKo: "투명 페트병",
    confidence: 0.94,
  },
  requiredActions: [
    {
      code: "REMOVE_LABEL",
      labelKo: "라벨 떼기",
      description: "비닐 라벨은 병에서 완전히 분리해줘.",
      icon: "🏷️",
    },
    {
      code: "REMOVE_CAP",
      labelKo: "뚜껑 분리하기",
      description: "뚜껑과 고리를 병에서 떼어내자.",
      icon: "🧢",
    },
    {
      code: "CRUSH",
      labelKo: "납작하게 누르기",
      description: "공기를 빼고 납작하게 눌러줘.",
      icon: "🤏",
    },
  ],
  feedback: {
    title: "페트병을 찾았어!",
    message: "거의 다 왔어. 세 가지만 고치면 멋지게 재활용할 수 있어!",
    ttsText:
      "페트병을 찾았어! 라벨과 뚜껑을 떼고 납작하게 눌러보자.",
  },
};

export const afterAnalysis: ScanAnalysis = {
  ...beforeAnalysis,
  analysisId: "analysis-after-demo",
  phase: "AFTER",
  status: "COMPLETED",
  requiredActions: [],
  feedback: {
    title: "완벽해!",
    message: "라벨도 떼고, 뚜껑도 분리하고, 납작하게 잘 눌렀어.",
    ttsText: "완벽해! 이제 투명 페트병 전용함으로 보내주자.",
  },
};

export const collectionCards: CollectionCard[] = [
  {
    id: "pet",
    name: "투명 페트병",
    icon: "🧴",
    rarity: "일반",
    acquired: true,
    hint: "라벨과 뚜껑을 분리해요",
  },
  {
    id: "paper",
    name: "종이 상자",
    icon: "📦",
    rarity: "일반",
    acquired: true,
    hint: "테이프를 떼고 접어요",
  },
  {
    id: "can",
    name: "음료 캔",
    icon: "🥫",
    rarity: "일반",
    acquired: true,
    hint: "내용물을 비워요",
  },
  {
    id: "milk",
    name: "우유팩",
    icon: "🥛",
    rarity: "희귀",
    acquired: false,
    hint: "씻고, 펼치고, 말려요",
  },
  {
    id: "vinyl",
    name: "포장 비닐",
    icon: "🛍️",
    rarity: "희귀",
    acquired: false,
    hint: "내용물을 깨끗이 털어요",
  },
  {
    id: "icepack",
    name: "아이스팩",
    icon: "❄️",
    rarity: "전설",
    acquired: false,
    hint: "종류별 배출법이 달라요",
  },
  {
    id: "yeongdong-grape",
    name: "영동 포도 상자",
    icon: "🍇",
    rarity: "희귀",
    acquired: true,
    hint: "테이프와 송장을 떼고 접어요",
  },
  {
    id: "goesan-paste",
    name: "괴산 장류 용기",
    icon: "🌶️",
    rarity: "전설",
    acquired: false,
    hint: "내용물을 비우고 깨끗이 씻어요",
  },
  {
    id: "cheongju-delivery",
    name: "청주 배달 용기",
    icon: "🍱",
    rarity: "희귀",
    acquired: false,
    hint: "재질을 나누고 깨끗이 씻어요",
  },
];
