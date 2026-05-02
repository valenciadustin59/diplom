import type { ScoreConfidenceView } from "../lib/auditConfidence";
import { Card } from "./Card";

export function ScoreConfidenceCard({ confidence }: { confidence: ScoreConfidenceView }) {
  return (
    <Card
      title="Доверие к score"
      subtitle="UX-слой D42: объясняет надёжность оценки по сохранённым данным аудита, не меняя саму формулу score."
    >
      <div className="score-confidence">
        <div className="score-confidence__header">
          <span className={`score-confidence__badge score-confidence__badge--${confidence.tone}`}>{confidence.label}</span>
          <span className="score-confidence__counts">
            {confidence.passedCount} ok · {confidence.warningCount} warning · {confidence.errorCount} error
          </span>
        </div>
        <p className="score-confidence__summary">{confidence.summary}</p>
        <p className="score-confidence__detail">{confidence.detail}</p>
        <ul className="score-confidence__reasons" aria-label="Причины уверенности score">
          {confidence.reasons.map((reason) => (
            <li key={reason.code} className={`score-confidence__reason score-confidence__reason--${reason.tone}`}>
              <strong>{reason.label}</strong>
              <span>{reason.detail}</span>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
