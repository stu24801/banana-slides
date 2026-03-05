import React, { useState, useEffect } from 'react';
import { Button, useToast, MaterialSelector } from '@/components/shared';
import { getImageUrl } from '@/api/client';
import { listUserTemplates, uploadUserTemplate, deleteUserTemplate, type UserTemplate } from '@/api/endpoints';
import { materialUrlToFile } from '@/components/shared/MaterialSelector';
import type { Material } from '@/api/endpoints';
import { ImagePlus, X } from 'lucide-react';

const presetTemplates = [
  { id: '1', name: '復古卷軸', preview: '/templates/template_y.png', thumb: '/templates/template_y-thumb.webp' },
  { id: '2', name: '向量插畫', preview: '/templates/template_vector_illustration.png', thumb: '/templates/template_vector_illustration-thumb.webp' },
  { id: '3', name: '擬物玻璃', preview: '/templates/template_glass.png', thumb: '/templates/template_glass-thumb.webp' },
  { id: '4', name: '科技藍', preview: '/templates/template_b.png', thumb: '/templates/template_b-thumb.webp' },
  { id: '5', name: '簡約商務', preview: '/templates/template_s.png', thumb: '/templates/template_s-thumb.webp' },
  { id: '6', name: '學術報告', preview: '/templates/template_academic.jpg', thumb: '/templates/template_academic-thumb.webp' },
];

interface TemplateSelectorProps {
  onSelect: (templateFile: File | null, templateId?: string) => void;
  selectedTemplateId?: string | null;
  selectedPresetTemplateId?: string | null;
  showUpload?: boolean; // 是否顯示上傳到使用者模板庫的選項
  projectId?: string | null; // 專案ID，用於素材選擇器
}

export const TemplateSelector: React.FC<TemplateSelectorProps> = ({
  onSelect,
  selectedTemplateId,
  selectedPresetTemplateId,
  showUpload = true,
  projectId,
}) => {
  const [userTemplates, setUserTemplates] = useState<UserTemplate[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [isMaterialSelectorOpen, setIsMaterialSelectorOpen] = useState(false);
  const [deletingTemplateId, setDeletingTemplateId] = useState<string | null>(null);
  const [saveToLibrary, setSaveToLibrary] = useState(true); // 上傳模板時是否儲存到模板庫（預設勾選）
  const { show, ToastContainer } = useToast();

  // 載入使用者模板列表
  useEffect(() => {
    loadUserTemplates();
  }, []);

  const loadUserTemplates = async () => {
    setIsLoadingTemplates(true);
    try {
      const response = await listUserTemplates();
      if (response.data?.templates) {
        setUserTemplates(response.data.templates);
      }
    } catch (error: any) {
      console.error('載入使用者模板失敗:', error);
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleTemplateUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      try {
        if (showUpload) {
          // 主頁模式：直接上傳到使用者模板庫
          const response = await uploadUserTemplate(file);
          if (response.data) {
            const template = response.data;
            setUserTemplates(prev => [template, ...prev]);
            onSelect(null, template.template_id);
            show({ message: '模板上傳成功', type: 'success' });
          }
        } else {
          // 預覽頁模式：根據 saveToLibrary 狀態決定是否儲存到模板庫
          if (saveToLibrary) {
            // 儲存到模板庫並應用
            const response = await uploadUserTemplate(file);
            if (response.data) {
              const template = response.data;
              setUserTemplates(prev => [template, ...prev]);
              onSelect(file, template.template_id);
              show({ message: '模板已儲存到模板庫', type: 'success' });
            }
          } else {
            // 僅應用到專案
            onSelect(file);
          }
        }
      } catch (error: any) {
        console.error('上傳模板失敗:', error);
        show({ message: '模板上傳失敗: ' + (error.message || '未知錯誤'), type: 'error' });
      }
    }
    // 清空 input，允許重複選擇同一檔案
    e.target.value = '';
  };

  const handleSelectUserTemplate = (template: UserTemplate) => {
    // 立即更新選擇狀態（不載入File，提升響應速度）
    onSelect(null, template.template_id);
  };

  const handleSelectPresetTemplate = (templateId: string, preview: string) => {
    if (!preview) return;
    // 立即更新選擇狀態（不載入File，提升響應速度）
    onSelect(null, templateId);
  };

  const handleSelectMaterials = async (materials: Material[], saveAsTemplate?: boolean) => {
    if (materials.length === 0) return;
    
    try {
      // 將第一個素材轉換為File物件
      const file = await materialUrlToFile(materials[0]);
      
      // 根據 saveAsTemplate 引數決定是否儲存到模板庫
      if (saveAsTemplate) {
        // 儲存到使用者模板庫
        const response = await uploadUserTemplate(file);
        if (response.data) {
          const template = response.data;
          setUserTemplates(prev => [template, ...prev]);
          // 傳遞檔案和模板ID，適配不同的使用場景
          onSelect(file, template.template_id);
          show({ message: '素材已儲存到模板庫', type: 'success' });
        }
      } else {
        // 僅作為模板使用
        onSelect(file);
        show({ message: '已從素材庫選擇作為模板', type: 'success' });
      }
    } catch (error: any) {
      console.error('載入素材失敗:', error);
      show({ message: '載入素材失敗: ' + (error.message || '未知錯誤'), type: 'error' });
    }
  };

  const handleDeleteUserTemplate = async (template: UserTemplate, e: React.MouseEvent) => {
    e.stopPropagation();
    if (selectedTemplateId === template.template_id) {
      show({ message: '當前使用中的模板不能刪除，請先取消選擇或切換', type: 'info' });
      return;
    }
    setDeletingTemplateId(template.template_id);
    try {
      await deleteUserTemplate(template.template_id);
      setUserTemplates((prev) => prev.filter((t) => t.template_id !== template.template_id));
      show({ message: '模板已刪除', type: 'success' });
    } catch (error: any) {
      console.error('刪除模板失敗:', error);
      show({ message: '刪除模板失敗: ' + (error.message || '未知錯誤'), type: 'error' });
    } finally {
      setDeletingTemplateId(null);
    }
  };

  return (
    <>
      <div className="space-y-4">
        {/* 使用者已儲存的模板 */}
        {userTemplates.length > 0 && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">我的模板</h4>
            <div className="grid grid-cols-4 gap-4 mb-4">
              {userTemplates.map((template) => (
                <div
                  key={template.template_id}
                  onClick={() => handleSelectUserTemplate(template)}
                  className={`aspect-[4/3] rounded-lg border-2 cursor-pointer transition-all relative group ${
                    selectedTemplateId === template.template_id
                      ? 'border-banana-500 ring-2 ring-banana-200'
                      : 'border-gray-200 hover:border-banana-300'
                  }`}
                >
                  <img
                    src={getImageUrl(template.thumb_url || template.template_image_url)}
                    alt={template.name || 'Template'}
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  {/* 刪除按鈕：僅使用者模板，且未被選中時顯示（常顯） */}
                  {selectedTemplateId !== template.template_id && (
                    <button
                      type="button"
                      onClick={(e) => handleDeleteUserTemplate(template, e)}
                      disabled={deletingTemplateId === template.template_id}
                      className={`absolute -top-2 -right-2 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center shadow z-20 opacity-0 group-hover:opacity-100 transition-opacity ${
                        deletingTemplateId === template.template_id ? 'opacity-60 cursor-not-allowed' : ''
                      }`}
                      aria-label="刪除模板"
                    >
                      <X size={12} />
                    </button>
                  )}
                  {selectedTemplateId === template.template_id && (
                    <div className="absolute inset-0 bg-banana-500 bg-opacity-20 flex items-center justify-center pointer-events-none">
                      <span className="text-white font-semibold text-sm">已選擇</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">預設模板</h4>
          <div className="grid grid-cols-4 gap-4">
            {/* 預設模板 */}
            {presetTemplates.map((template) => (
              <div
                key={template.id}
                onClick={() => template.preview && handleSelectPresetTemplate(template.id, template.preview)}
                className={`aspect-[4/3] rounded-lg border-2 cursor-pointer transition-all bg-gray-100 flex items-center justify-center relative ${
                  selectedPresetTemplateId === template.id
                    ? 'border-banana-500 ring-2 ring-banana-200'
                    : 'border-gray-200 hover:border-banana-500'
                }`}
              >
                {template.preview ? (
                  <>
                    <img
                      src={template.thumb || template.preview}
                      alt={template.name}
                      className="absolute inset-0 w-full h-full object-cover"
                    />
                    {selectedPresetTemplateId === template.id && (
                      <div className="absolute inset-0 bg-banana-500 bg-opacity-20 flex items-center justify-center pointer-events-none">
                        <span className="text-white font-semibold text-sm">已選擇</span>
                      </div>
                    )}
                  </>
                ) : (
                  <span className="text-sm text-gray-500">{template.name}</span>
                )}
              </div>
            ))}

            {/* 上傳新模板 */}
            <label className="aspect-[4/3] rounded-lg border-2 border-dashed border-gray-300 hover:border-banana-500 cursor-pointer transition-all flex flex-col items-center justify-center gap-2 relative overflow-hidden">
              <span className="text-2xl">+</span>
              <span className="text-sm text-gray-500">上傳模板</span>
              <input
                type="file"
                accept="image/*"
                onChange={handleTemplateUpload}
                className="hidden"
                disabled={isLoadingTemplates}
              />
            </label>
          </div>
          
          {/* 在預覽頁顯示：上傳模板時是否儲存到模板庫的選項 */}
          {!showUpload && (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg border border-blue-200">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={saveToLibrary}
                  onChange={(e) => setSaveToLibrary(e.target.checked)}
                  className="w-4 h-4 text-banana-500 border-gray-300 rounded focus:ring-banana-500"
                />
                <span className="text-sm text-gray-700">
                  上傳模板時同時儲存到我的模板庫
                </span>
              </label>
            </div>
          )}
        </div>

        {/* 從素材庫選擇作為模板 */}
        {projectId && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">從素材庫選擇</h4>
            <Button
              variant="secondary"
              size="sm"
              icon={<ImagePlus size={16} />}
              onClick={() => setIsMaterialSelectorOpen(true)}
              className="w-full"
            >
              從素材庫選擇作為模板
            </Button>
          </div>
        )}
      </div>
      <ToastContainer />
      {/* 素材選擇器 */}
      {projectId && (
        <MaterialSelector
          projectId={projectId}
          isOpen={isMaterialSelectorOpen}
          onClose={() => setIsMaterialSelectorOpen(false)}
          onSelect={handleSelectMaterials}
          multiple={false}
          showSaveAsTemplateOption={true}
        />
      )}
    </>
  );
};

/**
 * 根據模板ID獲取模板File物件（按需載入）
 * @param templateId 模板ID
 * @param userTemplates 使用者模板列表
 * @returns Promise<File | null>
 */
export const getTemplateFile = async (
  templateId: string,
  userTemplates: UserTemplate[]
): Promise<File | null> => {
  // 檢查是否是預設模板
  const presetTemplate = presetTemplates.find(t => t.id === templateId);
  if (presetTemplate && presetTemplate.preview) {
    try {
      const response = await fetch(presetTemplate.preview);
      const blob = await response.blob();
      return new File([blob], presetTemplate.preview.split('/').pop() || 'template.png', { type: blob.type });
    } catch (error) {
      console.error('載入預設模板失敗:', error);
      return null;
    }
  }

  // 檢查是否是使用者模板
  const userTemplate = userTemplates.find(t => t.template_id === templateId);
  if (userTemplate) {
    try {
      const imageUrl = getImageUrl(userTemplate.template_image_url);
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      return new File([blob], 'template.png', { type: blob.type });
    } catch (error) {
      console.error('載入使用者模板失敗:', error);
      return null;
    }
  }

  return null;
};

