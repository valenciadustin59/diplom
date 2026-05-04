import type { ScoreBreakdown } from "../types";

export const earlyStopMismatchTitle = "Страница не соответствует запросу";

export const earlyStopMismatchMessage =
  "Сравнение с конкурентами не запускалось, потому что страница не отвечает теме запроса. Выберите другую страницу или измените запрос.";

export type EarlyStopMismatchView = {
  title: string;
  message: string;
  score: number | null;
};

function getEarlyStopDecision(breakdown: ScoreBreakdown | null | undefined) {
  return breakdown?.relevance_guardrail?.early_stop_decision ?? breakdown?.early_stop_decision ?? null;
}

export function getEarlyStopMismatchView(
  breakdown: ScoreBreakdown | null | undefined,
): EarlyStopMismatchView | null {
  const relevanceGuardrail = breakdown?.relevance_guardrail;
  const earlyStop = relevanceGuardrail?.early_stop ?? breakdown?.early_stop ?? false;
  const decision = getEarlyStopDecision(breakdown);

  if (earlyStop !== true || decision?.reason !== "confident_full_query_mismatch") {
    return null;
  }

  const decisionScore = typeof decision.score === "number" && Number.isFinite(decision.score) ? decision.score : null;
  const breakdownScore =
    typeof breakdown?.final_score === "number" && Number.isFinite(breakdown.final_score) ? breakdown.final_score : null;

  return {
    title: earlyStopMismatchTitle,
    message: earlyStopMismatchMessage,
    score: decisionScore ?? breakdownScore,
  };
}
