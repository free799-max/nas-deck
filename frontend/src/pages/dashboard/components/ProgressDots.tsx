/**
 * 进度点阵组件
 *
 * 用 10 个小圆点可视化百分比进度。
 */

export function ProgressDots({
  percentage,
  color,
}: {
  percentage: number;
  color: string;
}) {
  const total = 10;
  const filled = Math.round(percentage / 10);
  return (
    <div className="flex items-center gap-2">
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <div
            key={i}
            className={`h-1.5 w-1.5 rounded-full ${
              i < filled ? color : "bg-gray-300/60"
            }`}
          />
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground">{percentage}%</span>
    </div>
  );
}
