import React from 'react';
import { cn } from '@/utils';
import type { Page } from '@/types';
import { usePageStatus, type PageStatusContext } from '@/hooks/usePageStatus';

interface ContextualStatusBadgeProps {
  page: Page;
  /** 上下文：description（描述頁）、image（圖片頁）、full（完整狀態） */
  context?: PageStatusContext;
  /** 是否顯示詳細描述（懸停提示） */
  showDescription?: boolean;
}

/**
 * 根據上下文智慧顯示狀態的徽章
 * 
 * - 在描述編輯頁面：只顯示描述相關狀態
 * - 在圖片預覽頁面：顯示圖片生成狀態
 * - 其他場景：顯示完整頁面狀態
 */
export const ContextualStatusBadge: React.FC<ContextualStatusBadgeProps> = ({
  page,
  context = 'full',
  showDescription = true,
}) => {
  const { status, label, description } = usePageStatus(page, context);

  const statusConfig = {
    DRAFT: 'bg-gray-100 text-gray-600',
    DESCRIPTION_GENERATED: 'bg-blue-100 text-blue-600',
    GENERATING: 'bg-orange-100 text-orange-600 animate-pulse',
    COMPLETED: 'bg-green-100 text-green-600',
    FAILED: 'bg-red-100 text-red-600',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded text-xs font-medium',
        statusConfig[status]
      )}
      title={showDescription ? description : undefined}
    >
      {label}
    </span>
  );
};

