import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import * as api from '@/api/endpoints';

// Note: Backend uses 'RUNNING' but we also accept 'PROCESSING' for compatibility
export type ExportTaskStatus = 'PENDING' | 'PROCESSING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
export type ExportTaskType = 'pptx' | 'pdf' | 'editable-pptx';

export interface ExportTask {
  id: string;
  taskId: string;
  projectId: string;
  type: ExportTaskType;
  status: ExportTaskStatus;
  pageIds?: string[]; // 選中的頁面ID列表，undefined表示全部
  progress?: {
    total: number;
    completed: number;
    percent?: number;
    current_step?: string;
    messages?: string[];
    warnings?: string[];  // 匯出警告資訊
    warning_details?: {   // 警告詳細資訊
      style_extraction_failed?: Array<{ element_id: string; reason: string }>;
      text_render_failed?: Array<{ text: string; reason: string }>;
      image_add_failed?: Array<{ path: string; reason: string }>;
      json_parse_failed?: Array<{ context: string; reason: string }>;
      other_warnings?: string[];
      total_warnings?: number;
    };
  };
  downloadUrl?: string;
  filename?: string;
  errorMessage?: string;
  createdAt: string;
  completedAt?: string;
}

interface ExportTasksState {
  tasks: ExportTask[];
  
  // Actions
  addTask: (task: Omit<ExportTask, 'createdAt'>) => void;
  updateTask: (id: string, updates: Partial<ExportTask>) => void;
  removeTask: (id: string) => void;
  clearCompleted: () => void;
  pollTask: (id: string, projectId: string, taskId: string) => Promise<void>;
  restoreActiveTasks: () => void; // 恢復正在進行的任務並重新開始輪詢
}

export const useExportTasksStore = create<ExportTasksState>()(
  persist(
    (set, get) => ({
      tasks: [],

      addTask: (task) => {
        set((state) => {
          // Check if task with this id already exists
          const existingIndex = state.tasks.findIndex(t => t.id === task.id);
          
          if (existingIndex >= 0) {
            // Update existing task
            const updatedTasks = [...state.tasks];
            updatedTasks[existingIndex] = {
              ...updatedTasks[existingIndex],
              ...task,
              // Update completedAt if status changed to completed/failed
              completedAt: (task.status === 'COMPLETED' || task.status === 'FAILED')
                ? new Date().toISOString()
                : updatedTasks[existingIndex].completedAt,
            };
            return { tasks: updatedTasks };
          } else {
            // Add new task
            const newTask: ExportTask = {
              ...task,
              createdAt: new Date().toISOString(),
            };
            return {
              tasks: [newTask, ...state.tasks].slice(0, 20), // Keep max 20 tasks
            };
          }
        });
      },

      updateTask: (id, updates) => {
        set((state) => ({
          tasks: state.tasks.map((task) =>
            task.id === id ? { ...task, ...updates } : task
          ),
        }));
      },

      removeTask: (id) => {
        set((state) => ({
          tasks: state.tasks.filter((task) => task.id !== id),
        }));
      },

      clearCompleted: () => {
        set((state) => ({
          tasks: state.tasks.filter(
            (task) => task.status !== 'COMPLETED' && task.status !== 'FAILED'
          ),
        }));
      },

      pollTask: async (id, projectId, taskId) => {
        const poll = async () => {
          try {
            const response = await api.getTaskStatus(projectId, taskId);
            const task = response.data;

            if (!task) {
              console.warn('[ExportTasksStore] No task data in response');
              return;
            }

            const updates: Partial<ExportTask> = {
              status: task.status as ExportTaskStatus,
            };

            if (task.progress) {
              // Parse progress if it's a string (from database JSON field)
              let progressData = task.progress;
              if (typeof progressData === 'string') {
                try {
                  progressData = JSON.parse(progressData);
                } catch (e) {
                  console.warn('[ExportTasksStore] Failed to parse progress:', e);
                }
              }
              
              updates.progress = progressData;
              
              // Extract download URL if available
              if (progressData.download_url) {
                updates.downloadUrl = progressData.download_url;
              }
              if (progressData.filename) {
                updates.filename = progressData.filename;
              }
            }

            if (task.status === 'COMPLETED') {
              updates.completedAt = new Date().toISOString();
              get().updateTask(id, updates);
            } else if (task.status === 'FAILED') {
              updates.errorMessage = task.error_message || task.error || '匯出失敗';
              updates.completedAt = new Date().toISOString();
              get().updateTask(id, updates);
            } else if (task.status === 'PENDING' || task.status === 'RUNNING' || task.status === 'PROCESSING') {
              get().updateTask(id, updates);
              // Continue polling
              setTimeout(poll, 2000);
            }
          } catch (error: any) {
            console.error('[ExportTasksStore] Poll error:', error);
            get().updateTask(id, {
              status: 'FAILED',
              errorMessage: error.message || '輪詢失敗',
              completedAt: new Date().toISOString(),
            });
          }
        };

        await poll();
      },

      restoreActiveTasks: () => {
        // 恢復所有正在進行的任務並重新開始輪詢
        const state = get();
        const activeTasks = state.tasks.filter(
          task => task.status === 'PENDING' || task.status === 'PROCESSING' || task.status === 'RUNNING'
        );
        
        if (activeTasks.length > 0) {
          console.log(`[ExportTasksStore] 恢復 ${activeTasks.length} 個正在進行的任務`);
          activeTasks.forEach(task => {
            // 重新開始輪詢
            state.pollTask(task.id, task.projectId, task.taskId).catch(err => {
              console.error(`[ExportTasksStore] 恢復任務 ${task.id} 失敗:`, err);
            });
          });
        }
      },
    }),
    {
      name: 'export-tasks-storage',
      partialize: (state) => ({
        // Persist all tasks (including active ones) so they can be restored after page refresh
        tasks: state.tasks.slice(0, 20), // Keep max 20 tasks
      }),
    }
  )
);

