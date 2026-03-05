import { create } from 'zustand';
import type { Project, Task } from '@/types';
import * as api from '@/api/endpoints';
import { debounce, normalizeProject, normalizeErrorMessage } from '@/utils';

interface ProjectState {
  // 狀態
  currentProject: Project | null;
  isGlobalLoading: boolean;
  activeTaskId: string | null;
  taskProgress: { total: number; completed: number } | null;
  error: string | null;
  // 每個頁面的生成任務ID對映 (pageId -> taskId)
  pageGeneratingTasks: Record<string, string>;
  // 每個頁面的描述生成狀態 (pageId -> boolean)
  pageDescriptionGeneratingTasks: Record<string, boolean>;

  // Actions
  setCurrentProject: (project: Project | null) => void;
  setGlobalLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  
  // 專案操作
  initializeProject: (type: 'idea' | 'outline' | 'description', content: string, templateImage?: File, templateStyle?: string) => Promise<void>;
  syncProject: (projectId?: string) => Promise<void>;
  
  // 頁面操作
  updatePageLocal: (pageId: string, data: any) => void;
  saveAllPages: () => Promise<void>;
  reorderPages: (newOrder: string[]) => Promise<void>;
  addNewPage: () => Promise<void>;
  deletePageById: (pageId: string) => Promise<void>;
  
  // 非同步任務
  startAsyncTask: (apiCall: () => Promise<any>) => Promise<void>;
  pollTask: (taskId: string) => Promise<void>;
  pollImageTask: (taskId: string, pageIds: string[]) => void;
  
  // 生成操作
  generateOutline: () => Promise<void>;
  generateFromDescription: () => Promise<void>;
  generateDescriptions: () => Promise<void>;
  generatePageDescription: (pageId: string) => Promise<void>;
  generateImages: (pageIds?: string[]) => Promise<void>;
  editPageImage: (
    pageId: string,
    editPrompt: string,
    contextImages?: {
      useTemplate?: boolean;
      descImageUrls?: string[];
      uploadedFiles?: File[];
    }
  ) => Promise<void>;
  
  // 匯出
  exportPPTX: (pageIds?: string[]) => Promise<void>;
  exportPDF: (pageIds?: string[]) => Promise<void>;
  exportEditablePPTX: (filename?: string, pageIds?: string[]) => Promise<void>;
}

export const useProjectStore = create<ProjectState>((set, get) => {
  // 防抖的API更新函式（在store內部定義，以便訪問syncProject）
const debouncedUpdatePage = debounce(
  async (projectId: string, pageId: string, data: any) => {
      try {
    const promises: Promise<any>[] = [];
    
    // 如果更新的是 description_content，使用專門的端點
    if (data.description_content) {
      promises.push(api.updatePageDescription(projectId, pageId, data.description_content));
    }
    
    // 如果更新的是 outline_content，使用專門的端點
    if (data.outline_content) {
      promises.push(api.updatePageOutline(projectId, pageId, data.outline_content));
    }
    
    // 如果沒有特定的內容更新，使用通用端點
    if (promises.length === 0) {
      await api.updatePage(projectId, pageId, data);
    } else {
      // 並行執行所有更新請求
      await Promise.all(promises);
    }
        
        // API呼叫成功後，同步專案狀態以更新updated_at
        // 這樣可以確保歷史記錄頁面顯示最新的更新時間
        const { syncProject } = get();
        await syncProject(projectId);
      } catch (error: any) {
        console.error('儲存頁面失敗:', error);
        // 可以在這裡新增錯誤提示，但為了避免頻繁提示，暫時只記錄日誌
        // 如果需要，可以透過事件系統或toast通知使用者
    }
  },
  1000
);

  return {
  // 初始狀態
  currentProject: null,
  isGlobalLoading: false,
  activeTaskId: null,
  taskProgress: null,
  error: null,
  pageGeneratingTasks: {},
  pageDescriptionGeneratingTasks: {},

  // Setters
  setCurrentProject: (project) => set({ currentProject: project }),
  setGlobalLoading: (loading) => set({ isGlobalLoading: loading }),
  setError: (error) => set({ error }),

  // 初始化專案
  initializeProject: async (type, content, templateImage, templateStyle) => {
    set({ isGlobalLoading: true, error: null });
    try {
      const request: any = {};
      
      if (type === 'idea') {
        request.idea_prompt = content;
      } else if (type === 'outline') {
        request.outline_text = content;
      } else if (type === 'description') {
        request.description_text = content;
      }
      
      // 新增風格描述（如果有）
      if (templateStyle && templateStyle.trim()) {
        request.template_style = templateStyle.trim();
      }
      
      // 1. 建立專案
      const response = await api.createProject(request);
      const projectId = response.data?.project_id;
      
      if (!projectId) {
        throw new Error('專案建立失敗：未返回專案ID');
      }
      
      // 2. 如果有模板圖片，上傳模板
      if (templateImage) {
        try {
          await api.uploadTemplate(projectId, templateImage);
        } catch (error) {
          console.warn('模板上傳失敗:', error);
          // 模板上傳失敗不影響專案建立，繼續執行
        }
      }
      
      // 3. 如果是 description 型別，自動生成大綱和頁面描述
      if (type === 'description') {
        try {
          await api.generateFromDescription(projectId, content);
          console.log('[初始化專案] 從描述生成大綱和頁面描述完成');
        } catch (error) {
          console.error('[初始化專案] 從描述生成失敗:', error);
          // 繼續執行，讓使用者可以手動操作
        }
      }
      
      // 4. 獲取完整專案資訊
      const projectResponse = await api.getProject(projectId);
      const project = normalizeProject(projectResponse.data);
      
      if (project) {
        set({ currentProject: project });
        // 儲存到 localStorage
        localStorage.setItem('currentProjectId', project.id!);
      }
    } catch (error: any) {
      set({ error: normalizeErrorMessage(error.message || '建立專案失敗') });
      throw error;
    } finally {
      set({ isGlobalLoading: false });
    }
  },

  // 同步專案資料
  syncProject: async (projectId?: string) => {
    const { currentProject } = get();
    
    // 如果沒有提供 projectId，嘗試從 currentProject 或 localStorage 獲取
    let targetProjectId = projectId;
    if (!targetProjectId) {
      if (currentProject?.id) {
        targetProjectId = currentProject.id;
      } else {
        targetProjectId = localStorage.getItem('currentProjectId') || undefined;
      }
    }
    
    if (!targetProjectId) {
      console.warn('syncProject: 沒有可用的專案ID');
      return;
    }

    try {
      const response = await api.getProject(targetProjectId);
      if (response.data) {
        const project = normalizeProject(response.data);
        console.log('[syncProject] 同步專案資料:', {
          projectId: project.id,
          pagesCount: project.pages?.length || 0,
          status: project.status
        });
        set({ currentProject: project });
        // 確保 localStorage 中儲存了專案ID
        localStorage.setItem('currentProjectId', project.id!);
      }
    } catch (error: any) {
      // 提取更詳細的錯誤資訊
      let errorMessage = '同步專案失敗';
      let shouldClearStorage = false;
      
      if (error.response) {
        // 伺服器返回了錯誤響應
        const errorData = error.response.data;
        if (error.response.status === 404) {
          // 404錯誤：專案不存在，清除localStorage
          errorMessage = errorData?.error?.message || '專案不存在，可能已被刪除';
          shouldClearStorage = true;
        } else if (errorData?.error?.message) {
          // 從後端錯誤格式中提取訊息
          errorMessage = errorData.error.message;
        } else if (errorData?.message) {
          errorMessage = errorData.message;
        } else if (errorData?.error) {
          errorMessage = typeof errorData.error === 'string' ? errorData.error : errorData.error.message || '請求失敗';
        } else {
          errorMessage = `請求失敗: ${error.response.status}`;
        }
      } else if (error.request) {
        // 請求已傳送但沒有收到響應
        errorMessage = '網路錯誤，請檢查後端服務是否啟動';
      } else if (error.message) {
        // 其他錯誤
        errorMessage = error.message;
      }
      
      // 如果專案不存在，清除localStorage並重置當前專案
      if (shouldClearStorage) {
        console.warn('[syncProject] 專案不存在，清除localStorage');
        localStorage.removeItem('currentProjectId');
        set({ currentProject: null, error: normalizeErrorMessage(errorMessage) });
      } else {
        set({ error: normalizeErrorMessage(errorMessage) });
      }
    }
  },

  // 本地更新頁面（樂觀更新）
  updatePageLocal: (pageId, data) => {
    const { currentProject } = get();
    if (!currentProject) return;

    const updatedPages = currentProject.pages.map((page) =>
      page.id === pageId ? { ...page, ...data } : page
    );

    set({
      currentProject: {
        ...currentProject,
        pages: updatedPages,
      },
    });

    // 防抖後呼叫API
    debouncedUpdatePage(currentProject.id, pageId, data);
  },

  // 立即儲存所有頁面的更改（用於儲存按鈕）
  // 等待防抖完成，然後同步專案狀態以確保updated_at更新
  saveAllPages: async () => {
    const { currentProject } = get();
    if (!currentProject) return;

    // 等待防抖延遲時間（1秒）+ 額外時間確保API呼叫完成
    await new Promise(resolve => setTimeout(resolve, 1500));
    
    // 同步專案狀態，這會從後端獲取最新的updated_at
    await get().syncProject(currentProject.id);
  },

  // 重新排序頁面
  reorderPages: async (newOrder) => {
    const { currentProject } = get();
    if (!currentProject) return;

    // 樂觀更新
    const reorderedPages = newOrder
      .map((id) => currentProject.pages.find((p) => p.id === id))
      .filter(Boolean) as any[];

    set({
      currentProject: {
        ...currentProject,
        pages: reorderedPages,
      },
    });

    try {
      await api.updatePagesOrder(currentProject.id, newOrder);
    } catch (error: any) {
      set({ error: error.message || '更新順序失敗' });
      // 失敗後重新同步
      await get().syncProject();
    }
  },

  // 新增新頁面
  addNewPage: async () => {
    const { currentProject } = get();
    if (!currentProject) return;

    try {
      const newPage = {
        outline_content: { title: '新頁面', points: [] },
        order_index: currentProject.pages.length,
      };
      
      const response = await api.addPage(currentProject.id, newPage);
      if (response.data) {
        await get().syncProject();
      }
    } catch (error: any) {
      set({ error: error.message || '新增頁面失敗' });
    }
  },

  // 刪除頁面
  deletePageById: async (pageId) => {
    const { currentProject } = get();
    if (!currentProject) return;

    try {
      await api.deletePage(currentProject.id, pageId);
      await get().syncProject();
    } catch (error: any) {
      set({ error: error.message || '刪除頁面失敗' });
    }
  },

  // 啟動非同步任務
  startAsyncTask: async (apiCall) => {
    console.log('[非同步任務] 啟動非同步任務...');
    set({ isGlobalLoading: true, error: null });
    try {
      const response = await apiCall();
      console.log('[非同步任務] API響應:', response);
      
      // task_id 在 response.data 中
      const taskId = response.data?.task_id;
      if (taskId) {
        console.log('[非同步任務] 收到task_id:', taskId, '開始輪詢...');
        set({ activeTaskId: taskId });
        await get().pollTask(taskId);
      } else {
        console.warn('[非同步任務] 響應中沒有task_id，可能是同步操作:', response);
        // 同步操作完成後，重新整理專案資料
        await get().syncProject();
        set({ isGlobalLoading: false });
      }
    } catch (error: any) {
      console.error('[非同步任務] 啟動失敗:', error);
      set({ error: error.message || '任務啟動失敗', isGlobalLoading: false });
      throw error;
    }
  },

  // 輪詢任務狀態
  pollTask: async (taskId) => {
    console.log(`[輪詢] 開始輪詢任務: ${taskId}`);
    const { currentProject } = get();
    if (!currentProject) {
      console.warn('[輪詢] 沒有當前專案，停止輪詢');
      return;
    }

    const poll = async () => {
      try {
        console.log(`[輪詢] 查詢任務狀態: ${taskId}`);
        const response = await api.getTaskStatus(currentProject.id!, taskId);
        const task = response.data;
        
        if (!task) {
          console.warn('[輪詢] 響應中沒有任務資料');
          return;
        }

        // 更新進度
        if (task.progress) {
          set({ taskProgress: task.progress });
        }

        console.log(`[輪詢] Task ${taskId} 狀態: ${task.status}`, task);

        // 檢查任務狀態
        if (task.status === 'COMPLETED') {
          console.log(`[輪詢] Task ${taskId} 已完成，重新整理專案資料`);
          
          // 如果是匯出可編輯PPTX任務，檢查是否有下載連結
          if (task.task_type === 'EXPORT_EDITABLE_PPTX' && task.progress) {
            const progress = typeof task.progress === 'string' 
              ? JSON.parse(task.progress) 
              : task.progress;
            
            const downloadUrl = progress?.download_url;
            if (downloadUrl) {
              console.log('[匯出可編輯PPTX] 從任務響應中獲取下載連結:', downloadUrl);
              // 延遲一下，確保狀態更新完成後再開啟下載連結
              setTimeout(() => {
                window.open(downloadUrl, '_blank');
              }, 500);
            } else {
              console.warn('[匯出可編輯PPTX] 任務完成但沒有下載連結');
            }
          }
          
          set({ 
            activeTaskId: null, 
            taskProgress: null, 
            isGlobalLoading: false 
          });
          // 重新整理專案資料
          await get().syncProject();
        } else if (task.status === 'FAILED') {
          console.error(`[輪詢] Task ${taskId} 失敗:`, task.error_message || task.error);
          set({ 
            error: normalizeErrorMessage(task.error_message || task.error || '任務失敗'),
            activeTaskId: null,
            taskProgress: null,
            isGlobalLoading: false
          });
        } else if (task.status === 'PENDING' || task.status === 'PROCESSING') {
          // 繼續輪詢（PENDING 或 PROCESSING）
          console.log(`[輪詢] Task ${taskId} 處理中，2秒後繼續輪詢...`);
          setTimeout(poll, 2000);
        } else {
          // 未知狀態，停止輪詢
          console.warn(`[輪詢] Task ${taskId} 未知狀態: ${task.status}，停止輪詢`);
          set({ 
            error: `未知任務狀態: ${task.status}`,
            activeTaskId: null,
            taskProgress: null,
            isGlobalLoading: false
          });
        }
      } catch (error: any) {
        console.error('任務輪詢錯誤:', error);
        set({ 
          error: normalizeErrorMessage(error.message || '任務查詢失敗'),
          activeTaskId: null,
          isGlobalLoading: false
        });
      }
    };

    await poll();
  },

  // 生成大綱（同步操作，不需要輪詢）
  generateOutline: async () => {
    const { currentProject } = get();
    if (!currentProject) return;

    set({ isGlobalLoading: true, error: null });
    try {
      const response = await api.generateOutline(currentProject.id!);
      console.log('[生成大綱] API響應:', response);
      
      // 重新整理專案資料，確保獲取最新的大綱頁面
      await get().syncProject();
      
      // 再次確認資料已更新
      const { currentProject: updatedProject } = get();
      console.log('[生成大綱] 重新整理後的專案:', updatedProject?.pages.length, '個頁面');
    } catch (error: any) {
      console.error('[生成大綱] 錯誤:', error);
      set({ error: error.message || '生成大綱失敗' });
      throw error;
    } finally {
      set({ isGlobalLoading: false });
    }
  },

  // 從描述生成大綱和頁面描述（同步操作）
  generateFromDescription: async () => {
    const { currentProject } = get();
    if (!currentProject) return;

    set({ isGlobalLoading: true, error: null });
    try {
      const response = await api.generateFromDescription(currentProject.id!);
      console.log('[從描述生成] API響應:', response);
      
      // 重新整理專案資料，確保獲取最新的大綱和描述
      await get().syncProject();
      
      // 再次確認資料已更新
      const { currentProject: updatedProject } = get();
      console.log('[從描述生成] 重新整理後的專案:', updatedProject?.pages.length, '個頁面');
    } catch (error: any) {
      console.error('[從描述生成] 錯誤:', error);
      set({ error: error.message || '從描述生成失敗' });
      throw error;
    } finally {
      set({ isGlobalLoading: false });
    }
  },

  // 生成描述（使用非同步任務，實時顯示進度）
  generateDescriptions: async () => {
    const { currentProject } = get();
    if (!currentProject || !currentProject.id) return;

    const pages = currentProject.pages.filter((p) => p.id);
    if (pages.length === 0) return;

    set({ error: null });
    
    // 標記所有頁面為生成中
    const initialTasks: Record<string, boolean> = {};
    pages.forEach((page) => {
      if (page.id) {
        initialTasks[page.id] = true;
      }
    });
    set({ pageDescriptionGeneratingTasks: initialTasks });
    
    try {
      // 呼叫批次生成介面，返回 task_id
      const projectId = currentProject.id;
      if (!projectId) {
        throw new Error('專案ID不存在');
      }
      
      const response = await api.generateDescriptions(projectId);
      const taskId = response.data?.task_id;
      
      if (!taskId) {
        throw new Error('未收到任務ID');
      }
      
      // 啟動輪詢任務狀態和定期同步專案資料
      const pollAndSync = async () => {
        try {
          // 輪詢任務狀態
          const taskResponse = await api.getTaskStatus(projectId, taskId);
          const task = taskResponse.data;
          
          if (task) {
            // 更新進度
            if (task.progress) {
              set({ taskProgress: task.progress });
            }
            
            // 同步專案資料以獲取最新的頁面狀態
            await get().syncProject();
            
            // 根據專案資料更新每個頁面的生成狀態
            const { currentProject: updatedProject } = get();
            if (updatedProject) {
              const updatedTasks: Record<string, boolean> = {};
              updatedProject.pages.forEach((page) => {
                if (page.id) {
                  // 如果頁面已有描述，說明已完成
                  const hasDescription = !!page.description_content;
                  // 如果狀態是 GENERATING 或還沒有描述，說明還在生成中
                  const isGenerating = page.status === 'GENERATING' || 
                                      (!hasDescription && initialTasks[page.id]);
                  if (isGenerating) {
                    updatedTasks[page.id] = true;
                  }
                }
              });
              set({ pageDescriptionGeneratingTasks: updatedTasks });
            }
            
            // 檢查任務是否完成
            if (task.status === 'COMPLETED') {
              // 清除所有生成狀態
              set({ 
                pageDescriptionGeneratingTasks: {},
                taskProgress: null,
                activeTaskId: null
              });
              // 最後同步一次確保資料最新
              await get().syncProject();
            } else if (task.status === 'FAILED') {
              // 任務失敗
              set({ 
                pageDescriptionGeneratingTasks: {},
                taskProgress: null,
                activeTaskId: null,
                error: normalizeErrorMessage(task.error_message || task.error || '生成描述失敗')
              });
            } else if (task.status === 'PENDING' || task.status === 'PROCESSING') {
              // 繼續輪詢
              setTimeout(pollAndSync, 2000);
            }
          }
        } catch (error: any) {
          console.error('[生成描述] 輪詢錯誤:', error);
          // 即使輪詢出錯，也繼續嘗試同步專案資料
          await get().syncProject();
          setTimeout(pollAndSync, 2000);
        }
      };
      
      // 開始輪詢
      setTimeout(pollAndSync, 2000);
      
    } catch (error: any) {
      console.error('[生成描述] 啟動任務失敗:', error);
      set({ 
        pageDescriptionGeneratingTasks: {},
        error: normalizeErrorMessage(error.message || '啟動生成任務失敗')
      });
      throw error;
    }
  },

  // 生成單頁描述
  generatePageDescription: async (pageId: string) => {
    const { currentProject, pageDescriptionGeneratingTasks } = get();
    if (!currentProject) return;

    // 如果該頁面正在生成，不重複提交
    if (pageDescriptionGeneratingTasks[pageId]) {
      console.log(`[生成描述] 頁面 ${pageId} 正在生成中，跳過重複請求`);
      return;
    }

    set({ error: null });
    
    // 標記為生成中
    set({
      pageDescriptionGeneratingTasks: {
        ...pageDescriptionGeneratingTasks,
        [pageId]: true,
      },
    });

    try {
      // 立即同步一次專案資料，以更新頁面狀態
      await get().syncProject();
      
      // 傳遞 force_regenerate=true 以允許重新生成已有描述
      await api.generatePageDescription(currentProject.id, pageId, true);
      
      // 重新整理專案資料
      await get().syncProject();
    } catch (error: any) {
      set({ error: normalizeErrorMessage(error.message || '生成描述失敗') });
      throw error;
    } finally {
      // 清除生成狀態
      const { pageDescriptionGeneratingTasks: currentTasks } = get();
      const newTasks = { ...currentTasks };
      delete newTasks[pageId];
      set({ pageDescriptionGeneratingTasks: newTasks });
    }
  },

  // 生成圖片（非阻塞，每個頁面顯示生成狀態）
  generateImages: async (pageIds?: string[]) => {
    const { currentProject, pageGeneratingTasks } = get();
    if (!currentProject) return;

    // 確定要生成的頁面ID列表
    const targetPageIds = pageIds || currentProject.pages.map(p => p.id).filter((id): id is string => !!id);
    
    // 檢查是否有頁面正在生成
    const alreadyGenerating = targetPageIds.filter(id => pageGeneratingTasks[id]);
    if (alreadyGenerating.length > 0) {
      console.log(`[批次生成] ${alreadyGenerating.length} 個頁面正在生成中，跳過`);
      // 過濾掉已經在生成的頁面
      const newPageIds = targetPageIds.filter(id => !pageGeneratingTasks[id]);
      if (newPageIds.length === 0) {
        console.log('[批次生成] 所有頁面都在生成中，跳過請求');
        return;
      }
    }

    set({ error: null });
    
    try {
      // 呼叫批次生成 API
      const response = await api.generateImages(currentProject.id, undefined, pageIds);
      const taskId = response.data?.task_id;
      
      if (taskId) {
        console.log(`[批次生成] 收到 task_id: ${taskId}，標記 ${targetPageIds.length} 個頁面為生成中`);
        
        // 為所有目標頁面設定任務ID
        const newPageGeneratingTasks = { ...pageGeneratingTasks };
        targetPageIds.forEach(id => {
          newPageGeneratingTasks[id] = taskId;
        });
        set({ pageGeneratingTasks: newPageGeneratingTasks });
        
        // 立即同步一次專案資料，以獲取後端設定的 'GENERATING' 狀態
        await get().syncProject();
        
        // 開始輪詢批次任務狀態（非阻塞）
        get().pollImageTask(taskId, targetPageIds);
      } else {
        // 如果沒有返回 task_id，可能是同步介面，直接重新整理
        await get().syncProject();
      }
    } catch (error: any) {
      console.error('[批次生成] 啟動失敗:', error);
      throw error;
    }
  },

  // 輪詢圖片生成任務（非阻塞，支援單頁和批次）
  pollImageTask: async (taskId: string, pageIds: string[]) => {
    const { currentProject } = get();
    if (!currentProject) {
      console.warn('[批次輪詢] 沒有當前專案，停止輪詢');
      return;
    }

    const poll = async () => {
      try {
        const response = await api.getTaskStatus(currentProject.id!, taskId);
        const task = response.data;
        
        if (!task) {
          console.warn('[批次輪詢] 響應中沒有任務資料');
          return;
        }

        console.log(`[批次輪詢] Task ${taskId} 狀態: ${task.status}`, task.progress);

        // 檢查任務狀態
        if (task.status === 'COMPLETED') {
          console.log(`[批次輪詢] Task ${taskId} 已完成，清除任務記錄`);
          // 清除所有相關頁面的任務記錄
          const { pageGeneratingTasks } = get();
          const newTasks = { ...pageGeneratingTasks };
          pageIds.forEach(id => {
            if (newTasks[id] === taskId) {
              delete newTasks[id];
            }
          });
          set({ pageGeneratingTasks: newTasks });
          // 重新整理專案資料
          await get().syncProject();
        } else if (task.status === 'FAILED') {
          console.error(`[批次輪詢] Task ${taskId} 失敗:`, task.error_message || task.error);
          // 清除所有相關頁面的任務記錄
          const { pageGeneratingTasks } = get();
          const newTasks = { ...pageGeneratingTasks };
          pageIds.forEach(id => {
            if (newTasks[id] === taskId) {
              delete newTasks[id];
            }
          });
          set({ 
            pageGeneratingTasks: newTasks,
            error: normalizeErrorMessage(task.error_message || task.error || '批次生成失敗')
          });
          // 重新整理專案資料以更新頁面狀態
          await get().syncProject();
        } else if (task.status === 'PENDING' || task.status === 'PROCESSING') {
          // 繼續輪詢，同時同步專案資料以更新頁面狀態
          console.log(`[批次輪詢] Task ${taskId} 處理中，同步專案資料...`);
          await get().syncProject();
          console.log(`[批次輪詢] Task ${taskId} 處理中，2秒後繼續輪詢...`);
          setTimeout(poll, 2000);
        } else {
          // 未知狀態，停止輪詢
          console.warn(`[批次輪詢] Task ${taskId} 未知狀態: ${task.status}，停止輪詢`);
          const { pageGeneratingTasks } = get();
          const newTasks = { ...pageGeneratingTasks };
          pageIds.forEach(id => {
            if (newTasks[id] === taskId) {
              delete newTasks[id];
            }
          });
          set({ pageGeneratingTasks: newTasks });
        }
      } catch (error: any) {
        console.error('[批次輪詢] 輪詢錯誤:', error);
        // 清除所有相關頁面的任務記錄
        const { pageGeneratingTasks } = get();
        const newTasks = { ...pageGeneratingTasks };
        pageIds.forEach(id => {
          if (newTasks[id] === taskId) {
            delete newTasks[id];
          }
        });
        set({ pageGeneratingTasks: newTasks });
      }
    };

    // 開始輪詢（不 await，立即返回讓 UI 繼續響應）
    poll();
  },

  // 編輯頁面圖片（非同步）
  editPageImage: async (pageId, editPrompt, contextImages) => {
    const { currentProject, pageGeneratingTasks } = get();
    if (!currentProject) return;

    // 如果該頁面正在生成，不重複提交
    if (pageGeneratingTasks[pageId]) {
      console.log(`[編輯] 頁面 ${pageId} 正在生成中，跳過重複請求`);
      return;
    }

    set({ error: null });
    try {
      const response = await api.editPageImage(currentProject.id, pageId, editPrompt, contextImages);
      const taskId = response.data?.task_id;
      
      if (taskId) {
        // 記錄該頁面的任務ID
        set({ 
          pageGeneratingTasks: { ...pageGeneratingTasks, [pageId]: taskId }
        });
        
        // 立即同步一次專案資料，以獲取後端設定的'GENERATING'狀態
        await get().syncProject();
        
        // 開始輪詢（使用統一的輪詢函式）
        get().pollImageTask(taskId, [pageId]);
      } else {
        // 如果沒有返回task_id，可能是同步介面，直接重新整理
        await get().syncProject();
      }
    } catch (error: any) {
      // 清除該頁面的任務記錄
      const { pageGeneratingTasks } = get();
      const newTasks = { ...pageGeneratingTasks };
      delete newTasks[pageId];
      set({ pageGeneratingTasks: newTasks, error: normalizeErrorMessage(error.message || '編輯圖片失敗') });
      throw error;
    }
  },

  // 匯出PPTX
  exportPPTX: async (pageIds?: string[]) => {
    const { currentProject } = get();
    if (!currentProject) return;

    set({ isGlobalLoading: true, error: null });
    try {
      const response = await api.exportPPTX(currentProject.id, pageIds);
      // 優先使用相對路徑，避免 Docker 環境下的埠問題
      const downloadUrl =
        response.data?.download_url || response.data?.download_url_absolute;

      if (!downloadUrl) {
        throw new Error('匯出連結獲取失敗');
      }

      // 使用瀏覽器直接下載連結，避免 axios 受頻寬和超時影響
      window.open(downloadUrl, '_blank');
    } catch (error: any) {
      set({ error: error.message || '匯出失敗' });
    } finally {
      set({ isGlobalLoading: false });
    }
  },

  // 匯出PDF
  exportPDF: async (pageIds?: string[]) => {
    const { currentProject } = get();
    if (!currentProject) return;

    set({ isGlobalLoading: true, error: null });
    try {
      const response = await api.exportPDF(currentProject.id, pageIds);
      // 優先使用相對路徑，避免 Docker 環境下的埠問題
      const downloadUrl =
        response.data?.download_url || response.data?.download_url_absolute;

      if (!downloadUrl) {
        throw new Error('匯出連結獲取失敗');
      }

      // 使用瀏覽器直接下載連結，避免 axios 受頻寬和超時影響
      window.open(downloadUrl, '_blank');
    } catch (error: any) {
      set({ error: error.message || '匯出失敗' });
    } finally {
      set({ isGlobalLoading: false });
    }
  },

  // 匯出可編輯PPTX（非同步任務）
  exportEditablePPTX: async (filename?: string, pageIds?: string[]) => {
    const { currentProject, startAsyncTask } = get();
    if (!currentProject) return;

    try {
      console.log('[匯出可編輯PPTX] 啟動非同步匯出任務...');
      // startAsyncTask 中的 pollTask 會在任務完成時自動處理下載
      await startAsyncTask(() => api.exportEditablePPTX(currentProject.id, filename, pageIds));
      console.log('[匯出可編輯PPTX] 非同步任務完成');
    } catch (error: any) {
      console.error('[匯出可編輯PPTX] 匯出失敗:', error);
      set({ error: error.message || '匯出可編輯PPTX失敗' });
    }
  },
};});