/**
 * 头像堆叠组件
 *
 * 显示最多 3 个小头像圆圈，模拟多人协作头像。
 */

export function AvatarStack({ count }: { count: number }) {
  const displayCount = Math.min(count, 3);
  return (
    <div className="flex -space-x-1.5">
      {Array.from({ length: displayCount }).map((_, i) => (
        <div
          key={i}
          className={`h-5 w-5 rounded-full border-2 border-white flex items-center justify-center text-[8px] font-medium text-foreground ${
            ["bg-amber-200", "bg-blue-300", "bg-green-300"][i]
          }`}
        />
      ))}
    </div>
  );
}
