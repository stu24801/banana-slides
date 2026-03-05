import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Home, Trash2 } from 'lucide-react';
import { Button, Loading, Card, useToast, useConfirm } from '@/components/shared';
import { ProjectCard } from '@/components/history/ProjectCard';
import { useProjectStore } from '@/store/useProjectStore';
import * as api from '@/api/endpoints';
import { normalizeProject } from '@/utils';
import { getProjectTitle, getProjectRoute } from '@/utils/projectUtils';
import type { Project } from '@/types';

export const History: React.FC = () => {
  const navigate = useNavigate();
  const { syncProject, setCurrentProject } = useProjectStore();
  
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProjects, setSelectedProjects] = useState<Set<string>>(new Set());
  const [isDeleting, setIsDeleting] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState<string>('');
  const { show, ToastContainer } = useToast();
  const { confirm, ConfirmDialog } = useConfirm();

  useEffect(() => {
    loadProjects();
  }, []);

  // ===== 資料載入 =====

  const loadProjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.listProjects(50, 0);
      if (response.data?.projects) {
        const normalizedProjects = response.data.projects.map(normalizeProject);
        setProjects(normalizedProjects);
      }
    } catch (err: any) {
      console.error('載入歷史專案失敗:', err);
      setError(err.message || '載入歷史專案失敗');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // ===== 專案選擇與導航 =====

  const handleSelectProject = useCallback(async (project: Project) => {
    const projectId = project.id || project.project_id;
    if (!projectId) return;

    // 如果正在批次選擇模式，不跳轉
    if (selectedProjects.size > 0) {
      return;
    }

    // 如果正在編輯該專案，不跳轉
    if (editingProjectId === projectId) {
      return;
    }

    try {
      // 設定當前專案
      setCurrentProject(project);
      localStorage.setItem('currentProjectId', projectId);
      
      // 同步專案資料
      await syncProject(projectId);
      
      // 根據專案狀態跳轉到不同頁面
      const route = getProjectRoute(project);
      navigate(route, { state: { from: 'history' } });
    } catch (err: any) {
      console.error('開啟專案失敗:', err);
      show({ 
        message: '開啟專案失敗: ' + (err.message || '未知錯誤'), 
        type: 'error' 
      });
    }
  }, [selectedProjects, editingProjectId, setCurrentProject, syncProject, navigate, getProjectRoute, show]);

  // ===== 批次選擇操作 =====

  const handleToggleSelect = useCallback((projectId: string) => {
    setSelectedProjects(prev => {
      const newSelected = new Set(prev);
      if (newSelected.has(projectId)) {
        newSelected.delete(projectId);
      } else {
        newSelected.add(projectId);
      }
      return newSelected;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    setSelectedProjects(prev => {
      if (prev.size === projects.length) {
        return new Set();
      } else {
        const allIds = projects.map(p => p.id || p.project_id).filter(Boolean) as string[];
        return new Set(allIds);
      }
    });
  }, [projects]);

  // ===== 刪除操作 =====

  const deleteProjects = useCallback(async (projectIds: string[]) => {
    setIsDeleting(true);
    const currentProjectId = localStorage.getItem('currentProjectId');
    let deletedCurrentProject = false;

    try {
      // 批次刪除
      const deletePromises = projectIds.map(projectId => api.deleteProject(projectId));
      await Promise.all(deletePromises);

      // 檢查是否刪除了當前專案
      if (currentProjectId && projectIds.includes(currentProjectId)) {
        localStorage.removeItem('currentProjectId');
        setCurrentProject(null);
        deletedCurrentProject = true;
      }

      // 從列表中移除已刪除的專案
      setProjects(prev => prev.filter(p => {
        const id = p.id || p.project_id;
        return id && !projectIds.includes(id);
      }));

      // 清空選擇
      setSelectedProjects(new Set());

      if (deletedCurrentProject) {
        show({ 
          message: '已刪除專案，包括當前開啟的專案', 
          type: 'info' 
        });
      } else {
        show({ 
          message: `成功刪除 ${projectIds.length} 個專案`, 
          type: 'success' 
        });
      }
    } catch (err: any) {
      console.error('刪除專案失敗:', err);
      show({ 
        message: '刪除專案失敗: ' + (err.message || '未知錯誤'), 
        type: 'error' 
      });
    } finally {
      setIsDeleting(false);
    }
  }, [setCurrentProject, show]);

  const handleDeleteProject = useCallback(async (e: React.MouseEvent, project: Project) => {
    e.stopPropagation(); // 阻止事件冒泡，避免觸發專案選擇
    
    const projectId = project.id || project.project_id;
    if (!projectId) return;

    const projectTitle = getProjectTitle(project);
    confirm(
      `確定要刪除專案"${projectTitle}"嗎？此操作不可恢復。`,
      async () => {
        await deleteProjects([projectId]);
      },
      { title: '確認刪除', variant: 'danger' }
    );
  }, [confirm, deleteProjects]);

  const handleBatchDelete = useCallback(async () => {
    if (selectedProjects.size === 0) return;

    const count = selectedProjects.size;
    confirm(
      `確定要刪除選中的 ${count} 個專案嗎？此操作不可恢復。`,
      async () => {
        const projectIds = Array.from(selectedProjects);
        await deleteProjects(projectIds);
      },
      { title: '確認批次刪除', variant: 'danger' }
    );
  }, [selectedProjects, confirm, deleteProjects]);

  // ===== 編輯操作 =====

  const handleStartEdit = useCallback((e: React.MouseEvent, project: Project) => {
    e.stopPropagation(); // 阻止事件冒泡，避免觸發專案選擇
    
    // 如果正在批次選擇模式，不允許編輯
    if (selectedProjects.size > 0) {
      return;
    }
    
    const projectId = project.id || project.project_id;
    if (!projectId) return;
    
    const currentTitle = getProjectTitle(project);
    setEditingProjectId(projectId);
    setEditingTitle(currentTitle);
  }, [selectedProjects]);

  const handleCancelEdit = useCallback(() => {
    setEditingProjectId(null);
    setEditingTitle('');
  }, []);

  const handleSaveEdit = useCallback(async (projectId: string) => {
    if (!editingTitle.trim()) {
      show({ message: '專案名稱不能為空', type: 'error' });
      return;
    }

    try {
      // 呼叫API更新專案名稱
      await api.updateProject(projectId, { idea_prompt: editingTitle.trim() });
      
      // 更新本地狀態
      setProjects(prev => prev.map(p => {
        const id = p.id || p.project_id;
        if (id === projectId) {
          return { ...p, idea_prompt: editingTitle.trim() };
        }
        return p;
      }));

      setEditingProjectId(null);
      setEditingTitle('');
      show({ message: '專案名稱已更新', type: 'success' });
    } catch (err: any) {
      console.error('更新專案名稱失敗:', err);
      show({ 
        message: '更新專案名稱失敗: ' + (err.message || '未知錯誤'), 
        type: 'error' 
      });
    }
  }, [editingTitle, show]);

  const handleTitleKeyDown = useCallback((e: React.KeyboardEvent, projectId: string) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveEdit(projectId);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      handleCancelEdit();
    }
  }, [handleSaveEdit, handleCancelEdit]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-banana-50 via-white to-gray-50">
      {/* 導航欄 */}
      <nav className="h-14 md:h-16 bg-white shadow-sm border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-3 md:px-4 h-full flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 md:w-10 md:h-10 bg-gradient-to-br from-banana-500 to-banana-600 rounded-lg flex items-center justify-center text-xl md:text-2xl">
              🍌
            </div>
            <span className="text-lg md:text-xl font-bold text-gray-900">蕉幻</span>
          </div>
          <div className="flex items-center gap-2 md:gap-4">
            <Button
              variant="ghost"
              size="sm"
              icon={<Home size={16} className="md:w-[18px] md:h-[18px]" />}
              onClick={() => navigate('/')}
              className="text-xs md:text-sm"
            >
              <span className="hidden sm:inline">主頁</span>
              <span className="sm:hidden">主頁</span>
            </Button>
          </div>
        </div>
      </nav>

      {/* 主內容 */}
      <main className="max-w-6xl mx-auto px-3 md:px-4 py-6 md:py-8">
        <div className="mb-6 md:mb-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-1 md:mb-2">歷史專案</h1>
            <p className="text-sm md:text-base text-gray-600">檢視和管理你的所有專案</p>
          </div>
          {projects.length > 0 && selectedProjects.size > 0 && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">
                已選擇 {selectedProjects.size} 項
              </span>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedProjects(new Set())}
                disabled={isDeleting}
              >
                取消選擇
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Trash2 size={16} />}
                onClick={handleBatchDelete}
                disabled={isDeleting}
                loading={isDeleting}
              >
                批次刪除
              </Button>
            </div>
          )}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loading message="載入中..." />
          </div>
        ) : error ? (
          <Card className="p-8 text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <p className="text-gray-600 mb-4">{error}</p>
            <Button variant="primary" onClick={loadProjects}>
              重試
            </Button>
          </Card>
        ) : projects.length === 0 ? (
          <Card className="p-12 text-center">
            <div className="text-6xl mb-4">📭</div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">
              暫無歷史專案
            </h3>
            <p className="text-gray-500 mb-6">
              建立你的第一個專案開始使用吧
            </p>
            <Button variant="primary" onClick={() => navigate('/')}>
              建立新專案
            </Button>
          </Card>
        ) : (
          <div className="space-y-4">
            {/* 全選工具欄 */}
            {projects.length > 0 && (
              <div className="flex items-center gap-3 pb-2 border-b border-gray-200">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selectedProjects.size === projects.length && projects.length > 0}
                    onChange={handleSelectAll}
                    className="w-4 h-4 text-banana-600 border-gray-300 rounded focus:ring-banana-500"
                  />
                  <span className="text-sm text-gray-700">
                    {selectedProjects.size === projects.length ? '取消全選' : '全選'}
                  </span>
                </label>
              </div>
            )}
            
            {projects.map((project) => {
              const projectId = project.id || project.project_id;
              if (!projectId) return null;
              
              return (
                <ProjectCard
                  key={projectId}
                  project={project}
                  isSelected={selectedProjects.has(projectId)}
                  isEditing={editingProjectId === projectId}
                  editingTitle={editingTitle}
                  onSelect={handleSelectProject}
                  onToggleSelect={handleToggleSelect}
                  onDelete={handleDeleteProject}
                  onStartEdit={handleStartEdit}
                  onTitleChange={setEditingTitle}
                  onTitleKeyDown={handleTitleKeyDown}
                  onSaveEdit={handleSaveEdit}
                  isBatchMode={selectedProjects.size > 0}
                />
              );
            })}
          </div>
        )}
      </main>
      <ToastContainer />
      {ConfirmDialog}
    </div>
  );
};

