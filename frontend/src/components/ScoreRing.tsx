type ScoreRingProps = {
  value: number;
  label?: string;
};

export function ScoreRing({ value, label = "Общий score" }: ScoreRingProps) {
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (value / 100) * circumference;

  return (
    <div className="score-ring">
      <svg viewBox="0 0 140 140" className="score-ring__svg">
        <circle cx="70" cy="70" r={radius} className="score-ring__track" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          className="score-ring__progress"
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: dashOffset,
          }}
        />
      </svg>
      <div className="score-ring__content">
        <span className="score-ring__value">{value}</span>
        <span className="score-ring__label">{label}</span>
      </div>
    </div>
  );
}
