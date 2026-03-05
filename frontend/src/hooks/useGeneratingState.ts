import type { Page } from '@/types';

/**
 * 判斷頁面描述是否處於生成狀態
 * 只檢查與描述生成相關的狀態：
 * 1. 描述生成任務（isGenerating）
 * 2. AI 修改時的全域性狀態（isAiRefining）
 * 
 * 注意：不檢查 page.status === 'GENERATING'，因為該狀態在圖片生成時也會被設定
 */
export const useDescriptionGeneratingState = (
  isGenerating: boolean,
  isAiRefining: boolean
): boolean => {
  return isGenerating || isAiRefining;
};

/**
 * 判斷頁面圖片是否處於生成狀態
 * 檢查與圖片生成相關的狀態：
 * 1. 圖片生成任務（isGenerating）
 * 2. 頁面的 GENERATING 狀態（在圖片生成過程中設定）
 */
export const useImageGeneratingState = (
  page: Page,
  isGenerating: boolean
): boolean => {
  return isGenerating || page.status === 'GENERATING';
};

/**
 * @deprecated 使用 useDescriptionGeneratingState 或 useImageGeneratingState 替代
 * 原來的通用版本：合併所有生成狀態
 * 問題：無法區分描述生成和圖片生成，導致在描述頁面看到圖片生成狀態
 */
export const useGeneratingState = (
  page: Page,
  isGenerating: boolean,
  isAiRefining: boolean
): boolean => {
  return isGenerating || page.status === 'GENERATING' || isAiRefining;
};

/**
 * 簡單版本：只判斷頁面自身的生成狀態
 */
export const usePageGeneratingState = (
  page: Page,
  isGenerating: boolean
): boolean => {
  return isGenerating || page.status === 'GENERATING';
};


