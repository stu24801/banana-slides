import type { Page, PageStatus } from '@/types';

/**
 * 頁面狀態型別
 */
export type PageStatusContext = 'description' | 'image' | 'full';

/**
 * 派生的頁面狀態
 */
export interface DerivedPageStatus {
  status: PageStatus;
  label: string;
  description: string;
}

/**
 * 根據上下文獲取頁面的派生狀態
 * 
 * @param page - 頁面物件
 * @param context - 上下文：'description' | 'image' | 'full'
 * @returns 派生的狀態資訊
 */
export const usePageStatus = (
  page: Page,
  context: PageStatusContext = 'full'
): DerivedPageStatus => {
  const hasDescription = !!page.description_content;
  const hasImage = !!page.generated_image_path;
  const pageStatus = page.status;

  switch (context) {
    case 'description':
      // 描述頁面上下文：只關心描述是否生成
      if (!hasDescription) {
        return {
          status: 'DRAFT',
          label: '未生成描述',
          description: '還沒有生成描述'
        };
      }
      return {
        status: 'DESCRIPTION_GENERATED',
        label: '已生成描述',
        description: '描述已生成'
      };

    case 'image':
      // 圖片頁面上下文：關心圖片生成狀態
      if (!hasDescription) {
        return {
          status: 'DRAFT',
          label: '未生成描述',
          description: '需要先生成描述'
        };
      }
      if (!hasImage && pageStatus !== 'GENERATING') {
        return {
          status: 'DESCRIPTION_GENERATED',
          label: '未生成圖片',
          description: '描述已生成，等待生成圖片'
        };
      }
      if (pageStatus === 'GENERATING') {
        return {
          status: 'GENERATING',
          label: '生成中',
          description: '正在生成圖片'
        };
      }
      if (pageStatus === 'FAILED') {
        return {
          status: 'FAILED',
          label: '失敗',
          description: '圖片生成失敗'
        };
      }
      if (hasImage) {
        return {
          status: 'COMPLETED',
          label: '已完成',
          description: '圖片已生成'
        };
      }
      // 預設返回頁面狀態
      return {
        status: pageStatus,
        label: '未知',
        description: '狀態未知'
      };

    case 'full':
    default:
      // 完整上下文：顯示頁面的實際狀態
      return {
        status: pageStatus,
        label: getStatusLabel(pageStatus),
        description: getStatusDescription(pageStatus, hasDescription, hasImage)
      };
  }
};

/**
 * 獲取狀態標籤
 */
function getStatusLabel(status: PageStatus): string {
  const labels: Record<PageStatus, string> = {
    DRAFT: '草稿',
    DESCRIPTION_GENERATED: '已生成描述',
    GENERATING: '生成中',
    COMPLETED: '已完成',
    FAILED: '失敗',
  };
  return labels[status] || '未知';
}

/**
 * 獲取狀態描述
 */
function getStatusDescription(
  status: PageStatus,
  _hasDescription: boolean,
  _hasImage: boolean
): string {
  if (status === 'DRAFT') return '草稿階段';
  if (status === 'DESCRIPTION_GENERATED') return '描述已生成';
  if (status === 'GENERATING') return '正在生成中';
  if (status === 'FAILED') return '生成失敗';
  if (status === 'COMPLETED') return '全部完成';
  return '狀態未知';
}

