import React, { useEffect, useCallback, useState } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import { ArrowLeft, ArrowRight, FileText, Sparkles, Download } from 'lucide-react';
import { Button, Loading, useToast, useConfirm, AiRefineInput, FilePreviewModal, ProjectResourcesList } from '@/components/shared';
import { DescriptionCard } from '@/components/preview/DescriptionCard';
import { useProjectStore } from '@/store/useProjectStore';
import { refineDescriptions } from '@/api/endpoints';
import { exportDescriptionsToMarkdown } from '@/utils/projectUtils';

export const DetailEditor: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { projectId } = useParams<{ projectId: string }>();
  const fromHistory = (location.state as any)?.from === 'history';
  const {
    currentProject,
    syncProject,
    updatePageLocal,
    generateDescriptions,
    generatePageDescription,
    pageDescriptionGeneratingTasks,
  } = useProjectStore();
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();
  const [isAiRefining, setIsAiRefining] = React.useState(false);
  const [previewFileId, setPreviewFileId] = useState<string | null>(null);

  // 載入專案資料
  useEffect(() => {
    if (projectId && (!currentProject || currentProject.id !== projectId)) {
      // 直接使用 projectId 同步專案資料
      syncProject(projectId);
    } else if (projectId && currentProject && currentProject.id === projectId) {
      // 如果專案已存在，也同步一次以確保資料是最新的（特別是從描述生成後）
      // 但只在首次載入時同步，避免頻繁請求
      const shouldSync = !currentProject.pages.some(p => p.description_content);
      if (shouldSync) {
        syncProject(projectId);
      }
    }
  }, [projectId, currentProject?.id]); // 只在 projectId 或專案ID變化時更新


  const handleGenerateAll = async () => {
    const hasDescriptions = currentProject?.pages.some(
      (p) => p.description_content
    );
    
    const executeGenerate = async () => {
      await generateDescriptions();
    };
    
    if (hasDescriptions) {
      confirm(
        '部分頁面已有描述，重新生成將覆蓋，確定繼續嗎？',
        executeGenerate,
        { title: '確認重新生成', variant: 'warning' }
      );
    } else {
      await executeGenerate();
    }
  };

  const handleRegeneratePage = async (pageId: string) => {
    if (!currentProject) return;
    
    const page = currentProject.pages.find((p) => p.id === pageId);
    if (!page) return;
    
    // 如果已有描述，詢問是否覆蓋
    if (page.description_content) {
      confirm(
        '該頁面已有描述，重新生成將覆蓋現有內容，確定繼續嗎？',
        async () => {
          try {
            await generatePageDescription(pageId);
            show({ message: '生成成功', type: 'success' });
          } catch (error: any) {
            show({ 
              message: `生成失敗: ${error.message || '未知錯誤'}`, 
              type: 'error' 
            });
          }
        },
        { title: '確認重新生成', variant: 'warning' }
      );
      return;
    }
    
    try {
      await generatePageDescription(pageId);
      show({ message: '生成成功', type: 'success' });
    } catch (error: any) {
      show({ 
        message: `生成失敗: ${error.message || '未知錯誤'}`, 
        type: 'error' 
      });
    }
  };

  const handleAiRefineDescriptions = useCallback(async (requirement: string, previousRequirements: string[]) => {
    if (!currentProject || !projectId) return;
    
    try {
      const response = await refineDescriptions(projectId, requirement, previousRequirements);
      await syncProject(projectId);
      show({ 
        message: response.data?.message || '頁面描述修改成功', 
        type: 'success' 
      });
    } catch (error: any) {
      console.error('修改頁面描述失敗:', error);
      const errorMessage = error?.response?.data?.error?.message 
        || error?.message 
        || '修改失敗，請稍後重試';
      show({ message: errorMessage, type: 'error' });
      throw error; // 丟擲錯誤讓元件知道失敗了
    }
  }, [currentProject, projectId, syncProject, show]);

  // 匯出頁面描述為 Markdown 檔案
  const handleExportDescriptions = useCallback(() => {
    if (!currentProject) return;
    exportDescriptionsToMarkdown(currentProject);
    show({ message: '匯出成功', type: 'success' });
  }, [currentProject, show]);

  if (!currentProject) {
    return <Loading fullscreen message="載入專案中..." />;
  }

  const hasAllDescriptions = currentProject.pages.every(
    (p) => p.description_content
  );

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 頂欄 */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-3 md:px-6 py-2 md:py-3 flex-shrink-0">
        <div className="flex items-center justify-between gap-2 md:gap-4">
          {/* 左側：Logo 和標題 */}
          <div className="flex items-center gap-2 md:gap-4 flex-shrink-0">
            <Button
              variant="ghost"
              size="sm"
              icon={<ArrowLeft size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => {
                if (fromHistory) {
                  navigate('/history');
                } else {
                  navigate(`/project/${projectId}/outline`);
                }
              }}
              className="flex-shrink-0"
            >
              <span className="hidden sm:inline">返回</span>
            </Button>
            <div className="flex items-center gap-1.5 md:gap-2">
              <span className="text-xl md:text-2xl">🍌</span>
              <span className="text-base md:text-xl font-bold">蕉幻</span>
            </div>
            <span className="text-gray-400 hidden lg:inline">|</span>
            <span className="text-sm md:text-lg font-semibold hidden lg:inline">編輯頁面描述</span>
          </div>
          
          {/* 中間：AI 修改輸入框 */}
          <div className="flex-1 max-w-xl mx-auto hidden md:block md:-translate-x-3 pr-10">
            <AiRefineInput
              title=""
              placeholder="例如：讓描述更詳細、刪除第2頁的某個要點、強調XXX的重要性... · Ctrl+Enter提交"
              onSubmit={handleAiRefineDescriptions}
              disabled={false}
              className="!p-0 !bg-transparent !border-0"
              onStatusChange={setIsAiRefining}
            />
          </div>
          
          {/* 右側：操作按鈕 */}
          <div className="flex items-center gap-1.5 md:gap-2 flex-shrink-0">
            <Button
              variant="secondary"
              size="sm"
              icon={<ArrowLeft size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => navigate(`/project/${projectId}/outline`)}
              className="hidden md:inline-flex"
            >
              <span className="hidden lg:inline">上一步</span>
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={<ArrowRight size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => navigate(`/project/${projectId}/preview`)}
              disabled={!hasAllDescriptions}
              className="text-xs md:text-sm"
            >
              <span className="hidden sm:inline">生成圖片</span>
            </Button>
          </div>
        </div>
        
        {/* 移動端：AI 輸入框 */}
        <div className="mt-2 md:hidden">
          <AiRefineInput
            title=""
            placeholder="例如：讓描述更詳細... · Ctrl+Enter"
            onSubmit={handleAiRefineDescriptions}
            disabled={false}
            className="!p-0 !bg-transparent !border-0"
            onStatusChange={setIsAiRefining}
          />
        </div>
      </header>

      {/* 操作欄 */}
      <div className="bg-white border-b border-gray-200 px-3 md:px-6 py-3 md:py-4 flex-shrink-0">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2 sm:gap-3">
          <div className="flex items-center gap-2 sm:gap-3 flex-1">
            <Button
              variant="primary"
              icon={<Sparkles size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={handleGenerateAll}
              className="flex-1 sm:flex-initial text-sm md:text-base"
            >
              批次生成描述
            </Button>
            <Button
              variant="secondary"
              icon={<Download size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={handleExportDescriptions}
              disabled={!currentProject.pages.some(p => p.description_content)}
              className="flex-1 sm:flex-initial text-sm md:text-base"
            >
              匯出描述
            </Button>
            <span className="text-xs md:text-sm text-gray-500 whitespace-nowrap">
              {currentProject.pages.filter((p) => p.description_content).length} /{' '}
              {currentProject.pages.length} 頁已完成
            </span>
          </div>
        </div>
      </div>

      {/* 主內容區 */}
      <main className="flex-1 p-3 md:p-6 overflow-y-auto min-h-0">
        <div className="max-w-7xl mx-auto">
          {/* 專案資源列表（檔案和圖片） */}
          <ProjectResourcesList
            projectId={projectId || null}
            onFileClick={setPreviewFileId}
            showFiles={true}
            showImages={true}
          />
          
          {currentProject.pages.length === 0 ? (
            <div className="text-center py-12 md:py-20">
              <div className="flex justify-center mb-4"><FileText size={48} className="text-gray-300" /></div>
              <h3 className="text-lg md:text-xl font-semibold text-gray-700 mb-2">
                還沒有頁面
              </h3>
              <p className="text-sm md:text-base text-gray-500 mb-6">
                請先返回大綱編輯頁新增頁面
              </p>
              <Button
                variant="primary"
                onClick={() => navigate(`/project/${projectId}/outline`)}
                className="text-sm md:text-base"
              >
                返回大綱編輯
              </Button>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 md:gap-6">
              {currentProject.pages.map((page, index) => {
                const pageId = page.id || page.page_id;
                return (
                  <DescriptionCard
                    key={pageId}
                    page={page}
                    index={index}
                    onUpdate={(data) => updatePageLocal(pageId, data)}
                    onRegenerate={() => handleRegeneratePage(pageId)}
                    isGenerating={pageId ? !!pageDescriptionGeneratingTasks[pageId] : false}
                    isAiRefining={isAiRefining}
                  />
                );
              })}
            </div>
          )}
        </div>
      </main>
      <ToastContainer />
      {ConfirmDialog}
      <FilePreviewModal fileId={previewFileId} onClose={() => setPreviewFileId(null)} />
    </div>
  );
};

