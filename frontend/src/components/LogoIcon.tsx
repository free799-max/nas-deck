/**
 * NasDeck Logo 图标组件
 *
 * 设计灵感：层叠的甲板/面板（Deck）+ NAS 服务器状态灯
 * 紫色圆角底 + 白色层叠卡片 + 紫色指示灯
 */

export function LogoIcon({ className = "", size = 32 }: { className?: string; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* 紫色圆角方形背景 */}
      <rect x="2" y="2" width="28" height="28" rx="8" fill="#7c3aed" />

      {/* 下层卡片（半透明，制造层叠感） */}
      <rect x="10" y="16" width="12" height="8" rx="3" fill="white" opacity="0.35" />

      {/* 上层主卡片 */}
      <rect x="7" y="7" width="18" height="10" rx="4" fill="white" />

      {/* 状态指示灯 */}
      <circle cx="20" cy="11" r="2" fill="#7c3aed" />
    </svg>
  );
}

/**
 * NasDeck 简洁版 Logo（仅图标，用于小尺寸场景）
 */
export function LogoIconSmall({ className = "", size = 20 }: { className?: string; size?: number }) {
  return <LogoIcon className={className} size={size} />;
}
