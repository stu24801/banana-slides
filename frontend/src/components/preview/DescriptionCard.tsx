import React, { useState } from 'react';
import { Edit2, FileText, RefreshCw } from 'lucide-react';
import { Card, ContextualStatusBadge, Button, Modal, Textarea, Skeleton, Markdown } from '@/components/shared';
import { useDescriptionGeneratingState } from '@/hooks/useGeneratingState';
import type { Page, DescriptionContent } from '@/types';

export interface DescriptionCardProps {
  page: Page;
  index: number;
  onUpdate: (data: Partial<Page>) => void;
  onRegenerate: () => void;
  isGenerating?: boolean;
  isAiRefining?: boolean;
}

export const DescriptionCard: React.FC<DescriptionCardProps> = ({
  page,
  index,
  onUpdate,
  onRegenerate,
  isGenerating = false,
  isAiRefining = false,
}) => {
  // 從 description_content 提取文字內容
  const getDescriptionText = (descContent: DescriptionContent | undefined): string => {
    if (!descContent) return '';
    if ('text' in descContent) {
      return descContent.text;
    } else if ('text_content' in descContent && Array.isArray(descContent.text_content)) {
      return descContent.text_content.join('\n');
    }
    return '';
  };

  const text = getDescriptionText(page.description_content);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  
  // 使用專門的描述生成狀態 hook，不受圖片生成狀態影響
  const generating = useDescriptionGeneratingState(isGenerating, isAiRefining);

  const handleEdit = () => {
    // 在開啟編輯對話方塊時，從當前的 page 獲取最新值
    const currentText = getDescriptionText(page.description_content);
    setEditContent(currentText);
    setIsEditing(true);
  };

  const handleSave = () => {
    // 儲存時使用 text 格式（後端期望的格式）
    onUpdate({
      description_content: {
        text: editContent,
      } as DescriptionContent,
    });
    setIsEditing(false);
  };

  return (
    <>
      <Card className="p-0 overflow-hidden flex flex-col">
        {/* 標題欄 */}
        <div className="bg-banana-50 px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-gray-900">第 {index + 1} 頁</span>
              {page.part && (
                <span className="text-xs px-2 py-0.5 bg-blue-100 text-blue-700 rounded">
                  {page.part}
                </span>
              )}
            </div>
            <ContextualStatusBadge page={page} context="description" />
          </div>
        </div>

        {/* 內容 */}
        <div className="p-4 flex-1">
          {generating ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <div className="text-center py-4 text-gray-500 text-sm">
                正在生成描述...
              </div>
            </div>
          ) : text ? (
            <div className="text-sm text-gray-700">
              <Markdown>{text}</Markdown>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">
              <div className="flex text-3xl mb-2 justify-center"><FileText className="text-gray-400" size={48} /></div>
              <p className="text-sm">尚未生成描述</p>
            </div>
          )}
        </div>

        {/* 操作欄 */}
        <div className="border-t border-gray-100 px-4 py-3 flex justify-end gap-2 mt-auto">
          <Button
            variant="ghost"
            size="sm"
            icon={<Edit2 size={16} />}
            onClick={handleEdit}
            disabled={generating}
          >
            編輯
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon={<RefreshCw size={16} className={generating ? 'animate-spin' : ''} />}
            onClick={onRegenerate}
            disabled={generating}
          >
            {generating ? '生成中...' : '重新生成'}
          </Button>
        </div>
      </Card>

      {/* 編輯對話方塊 */}
      <Modal
        isOpen={isEditing}
        onClose={() => setIsEditing(false)}
        title="編輯頁面描述"
        size="lg"
      >
        <div className="space-y-4">
          <Textarea
            label="描述內容"
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            rows={12}
          />
          <div className="flex justify-end gap-3 pt-4">
            <Button variant="ghost" onClick={() => setIsEditing(false)}>
              取消
            </Button>
            <Button variant="primary" onClick={handleSave}>
              儲存
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
};

