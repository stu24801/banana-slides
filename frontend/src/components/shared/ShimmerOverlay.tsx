import React from 'react';

interface ShimmerOverlayProps {
  /** 是否顯示漸變效果 */
  show: boolean;
  /** 透明度，預設 0.4 */
  opacity?: number;
  /** 圓角型別，預設 'card' */
  rounded?: 'card' | 'lg' | 'md' | 'sm' | 'none';
}

/**
 * 通用的漸變滾動覆蓋層元件
 * 用於在卡片上顯示"生成中"或"處理中"的視覺反饋
 * 複用了 Skeleton 元件的漸變效果樣式
 */
export const ShimmerOverlay: React.FC<ShimmerOverlayProps> = ({
  show,
  opacity = 0.4,
  rounded = 'card',
}) => {
  if (!show) return null;

  const roundedClass = {
    card: 'rounded-card',
    lg: 'rounded-lg',
    md: 'rounded-md',
    sm: 'rounded-sm',
    none: '',
  }[rounded];

  return (
    <div className={`absolute inset-0 ${roundedClass} overflow-hidden pointer-events-none z-10`}>
      <div 
        className="absolute inset-0 bg-gradient-to-r from-gray-200 via-banana-50 to-gray-200 animate-shimmer" 
        style={{ 
          backgroundSize: '200% 100%',
          opacity 
        }}
      />
    </div>
  );
};

