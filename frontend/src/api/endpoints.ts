import { apiClient } from './client';
import type { Project, Task, ApiResponse, CreateProjectRequest, Page } from '@/types';
import type { Settings } from '../types/index';

// ===== 專案相關 API =====

/**
 * 建立專案
 */
export const createProject = async (data: CreateProjectRequest): Promise<ApiResponse<Project>> => {
  // 根據輸入型別確定 creation_type
  let creation_type = 'idea';
  if (data.description_text) {
    creation_type = 'descriptions';
  } else if (data.outline_text) {
    creation_type = 'outline';
  }

  const response = await apiClient.post<ApiResponse<Project>>('/api/projects', {
    creation_type,
    idea_prompt: data.idea_prompt,
    outline_text: data.outline_text,
    description_text: data.description_text,
    template_style: data.template_style,
  });
  return response.data;
};

/**
 * 上傳模板圖片
 */
export const uploadTemplate = async (
  projectId: string,
  templateImage: File
): Promise<ApiResponse<{ template_image_url: string }>> => {
  const formData = new FormData();
  formData.append('template_image', templateImage);

  const response = await apiClient.post<ApiResponse<{ template_image_url: string }>>(
    `/api/projects/${projectId}/template`,
    formData
  );
  return response.data;
};

/**
 * 獲取專案列表（歷史專案）
 */
export const listProjects = async (limit?: number, offset?: number): Promise<ApiResponse<{ projects: Project[]; total: number }>> => {
  const params = new URLSearchParams();
  if (limit !== undefined) params.append('limit', limit.toString());
  if (offset !== undefined) params.append('offset', offset.toString());

  const queryString = params.toString();
  const url = `/api/projects${queryString ? `?${queryString}` : ''}`;
  const response = await apiClient.get<ApiResponse<{ projects: Project[]; total: number }>>(url);
  return response.data;
};

/**
 * 獲取專案詳情
 */
export const getProject = async (projectId: string): Promise<ApiResponse<Project>> => {
  const response = await apiClient.get<ApiResponse<Project>>(`/api/projects/${projectId}`);
  return response.data;
};

/**
 * 刪除專案
 */
export const deleteProject = async (projectId: string): Promise<ApiResponse> => {
  const response = await apiClient.delete<ApiResponse>(`/api/projects/${projectId}`);
  return response.data;
};

/**
 * 更新專案
 */
export const updateProject = async (
  projectId: string,
  data: Partial<Project>
): Promise<ApiResponse<Project>> => {
  const response = await apiClient.put<ApiResponse<Project>>(`/api/projects/${projectId}`, data);
  return response.data;
};

/**
 * 更新頁面順序
 */
export const updatePagesOrder = async (
  projectId: string,
  pageIds: string[]
): Promise<ApiResponse<Project>> => {
  const response = await apiClient.put<ApiResponse<Project>>(
    `/api/projects/${projectId}`,
    { pages_order: pageIds }
  );
  return response.data;
};

// ===== 大綱生成 =====

/**
 * 生成大綱
 * @param projectId 專案ID
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 */
export const generateOutline = async (projectId: string, language?: OutputLanguage): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/generate/outline`,
    { language: lang }
  );
  return response.data;
};

// ===== 描述生成 =====

/**
 * 從描述文字生成大綱和頁面描述（一次性完成）
 * @param projectId 專案ID
 * @param descriptionText 描述文字（可選）
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 */
export const generateFromDescription = async (projectId: string, descriptionText?: string, language?: OutputLanguage): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/generate/from-description`,
    { 
      ...(descriptionText ? { description_text: descriptionText } : {}),
      language: lang 
    }
  );
  return response.data;
};

/**
 * 批次生成描述
 * @param projectId 專案ID
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 */
export const generateDescriptions = async (projectId: string, language?: OutputLanguage): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/generate/descriptions`,
    { language: lang }
  );
  return response.data;
};

/**
 * 生成單頁描述
 */
export const generatePageDescription = async (
  projectId: string,
  pageId: string,
  forceRegenerate: boolean = false,
  language?: OutputLanguage
): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/pages/${pageId}/generate/description`,
    { force_regenerate: forceRegenerate , language: lang}
  );
  return response.data;
};

/**
 * 根據使用者要求修改大綱
 * @param projectId 專案ID
 * @param userRequirement 使用者要求
 * @param previousRequirements 歷史要求（可選）
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 */
export const refineOutline = async (
  projectId: string,
  userRequirement: string,
  previousRequirements?: string[],
  language?: OutputLanguage
): Promise<ApiResponse<{ pages: Page[]; message: string }>> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse<{ pages: Page[]; message: string }>>(
    `/api/projects/${projectId}/refine/outline`,
    {
      user_requirement: userRequirement,
      previous_requirements: previousRequirements || [],
      language: lang
    }
  );
  return response.data;
};

/**
 * 根據使用者要求修改頁面描述
 * @param projectId 專案ID
 * @param userRequirement 使用者要求
 * @param previousRequirements 歷史要求（可選）
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 */
export const refineDescriptions = async (
  projectId: string,
  userRequirement: string,
  previousRequirements?: string[],
  language?: OutputLanguage
): Promise<ApiResponse<{ pages: Page[]; message: string }>> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse<{ pages: Page[]; message: string }>>(
    `/api/projects/${projectId}/refine/descriptions`,
    {
      user_requirement: userRequirement,
      previous_requirements: previousRequirements || [],
      language: lang
    }
  );
  return response.data;
};

// ===== 圖片生成 =====

/**
 * 批次生成圖片
 * @param projectId 專案ID
 * @param language 輸出語言（可選，預設從 sessionStorage 獲取）
 * @param pageIds 可選的頁面ID列表，如果不提供則生成所有頁面
 */
export const generateImages = async (projectId: string, language?: OutputLanguage, pageIds?: string[]): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/generate/images`,
    { language: lang, page_ids: pageIds }
  );
  return response.data;
};

/**
 * 生成單頁圖片
 */
export const generatePageImage = async (
  projectId: string,
  pageId: string,
  forceRegenerate: boolean = false,
  language?: OutputLanguage
): Promise<ApiResponse> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/pages/${pageId}/generate/image`,
    { force_regenerate: forceRegenerate, language: lang }
  );
  return response.data;
};

/**
 * 編輯圖片（自然語言修改）
 */
export const editPageImage = async (
  projectId: string,
  pageId: string,
  editPrompt: string,
  contextImages?: {
    useTemplate?: boolean;
    descImageUrls?: string[];
    uploadedFiles?: File[];
  }
): Promise<ApiResponse> => {
  // 如果有上傳的檔案，使用 multipart/form-data
  if (contextImages?.uploadedFiles && contextImages.uploadedFiles.length > 0) {
    const formData = new FormData();
    formData.append('edit_instruction', editPrompt);
    formData.append('use_template', String(contextImages.useTemplate || false));
    if (contextImages.descImageUrls && contextImages.descImageUrls.length > 0) {
      formData.append('desc_image_urls', JSON.stringify(contextImages.descImageUrls));
    }
    // 新增上傳的檔案
    contextImages.uploadedFiles.forEach((file) => {
      formData.append('context_images', file);
    });

    const response = await apiClient.post<ApiResponse>(
      `/api/projects/${projectId}/pages/${pageId}/edit/image`,
      formData
    );
    return response.data;
  } else {
    // 使用 JSON
    const response = await apiClient.post<ApiResponse>(
      `/api/projects/${projectId}/pages/${pageId}/edit/image`,
      {
        edit_instruction: editPrompt,
        context_images: {
          use_template: contextImages?.useTemplate || false,
          desc_image_urls: contextImages?.descImageUrls || [],
        },
      }
    );
    return response.data;
  }
};

/**
 * 獲取頁面圖片歷史版本
 */
export const getPageImageVersions = async (
  projectId: string,
  pageId: string
): Promise<ApiResponse<{ versions: any[] }>> => {
  const response = await apiClient.get<ApiResponse<{ versions: any[] }>>(
    `/api/projects/${projectId}/pages/${pageId}/image-versions`
  );
  return response.data;
};

/**
 * 設定當前使用的圖片版本
 */
export const setCurrentImageVersion = async (
  projectId: string,
  pageId: string,
  versionId: string
): Promise<ApiResponse> => {
  const response = await apiClient.post<ApiResponse>(
    `/api/projects/${projectId}/pages/${pageId}/image-versions/${versionId}/set-current`
  );
  return response.data;
};

// ===== 頁面操作 =====

/**
 * 更新頁面
 */
export const updatePage = async (
  projectId: string,
  pageId: string,
  data: Partial<Page>
): Promise<ApiResponse<Page>> => {
  const response = await apiClient.put<ApiResponse<Page>>(
    `/api/projects/${projectId}/pages/${pageId}`,
    data
  );
  return response.data;
};

/**
 * 更新頁面描述
 */
export const updatePageDescription = async (
  projectId: string,
  pageId: string,
  descriptionContent: any,
  language?: OutputLanguage
): Promise<ApiResponse<Page>> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.put<ApiResponse<Page>>(
    `/api/projects/${projectId}/pages/${pageId}/description`,
    { description_content: descriptionContent, language: lang }
  );
  return response.data;
};

/**
 * 更新頁面大綱
 */
export const updatePageOutline = async (
  projectId: string,
  pageId: string,
  outlineContent: any,
  language?: OutputLanguage
): Promise<ApiResponse<Page>> => {
  const lang = language || await getStoredOutputLanguage();
  const response = await apiClient.put<ApiResponse<Page>>(
    `/api/projects/${projectId}/pages/${pageId}/outline`,
    { outline_content: outlineContent, language: lang }
  );
  return response.data;
};

/**
 * 刪除頁面
 */
export const deletePage = async (projectId: string, pageId: string): Promise<ApiResponse> => {
  const response = await apiClient.delete<ApiResponse>(
    `/api/projects/${projectId}/pages/${pageId}`
  );
  return response.data;
};

/**
 * 新增頁面
 */
export const addPage = async (projectId: string, data: Partial<Page>): Promise<ApiResponse<Page>> => {
  const response = await apiClient.post<ApiResponse<Page>>(
    `/api/projects/${projectId}/pages`,
    data
  );
  return response.data;
};

// ===== 任務查詢 =====

/**
 * 查詢任務狀態
 */
export const getTaskStatus = async (projectId: string, taskId: string): Promise<ApiResponse<Task>> => {
  const response = await apiClient.get<ApiResponse<Task>>(`/api/projects/${projectId}/tasks/${taskId}`);
  return response.data;
};

// ===== 匯出 =====

/**
 * Helper function to build query string with page_ids
 */
const buildPageIdsQuery = (pageIds?: string[]): string => {
  if (!pageIds || pageIds.length === 0) return '';
  const params = new URLSearchParams();
  params.set('page_ids', pageIds.join(','));
  return `?${params.toString()}`;
};

/**
 * 匯出為PPTX
 * @param projectId 專案ID
 * @param pageIds 可選的頁面ID列表，如果不提供則匯出所有頁面
 */
export const exportPPTX = async (
  projectId: string,
  pageIds?: string[]
): Promise<ApiResponse<{ download_url: string; download_url_absolute?: string }>> => {
  const url = `/api/projects/${projectId}/export/pptx${buildPageIdsQuery(pageIds)}`;
  const response = await apiClient.get<
    ApiResponse<{ download_url: string; download_url_absolute?: string }>
  >(url);
  return response.data;
};

/**
 * 匯出為PDF
 * @param projectId 專案ID
 * @param pageIds 可選的頁面ID列表，如果不提供則匯出所有頁面
 */
export const exportPDF = async (
  projectId: string,
  pageIds?: string[]
): Promise<ApiResponse<{ download_url: string; download_url_absolute?: string }>> => {
  const url = `/api/projects/${projectId}/export/pdf${buildPageIdsQuery(pageIds)}`;
  const response = await apiClient.get<
    ApiResponse<{ download_url: string; download_url_absolute?: string }>
  >(url);
  return response.data;
};

/**
 * 匯出為可編輯PPTX（非同步任務）
 * @param projectId 專案ID
 * @param filename 可選的檔名
 * @param pageIds 可選的頁面ID列表，如果不提供則匯出所有頁面
 */
export const exportEditablePPTX = async (
  projectId: string,
  filename?: string,
  pageIds?: string[]
): Promise<ApiResponse<{ task_id: string }>> => {
  const response = await apiClient.post<
    ApiResponse<{ task_id: string }>
  >(`/api/projects/${projectId}/export/editable-pptx`, {
    filename,
    page_ids: pageIds
  });
  return response.data;
};

// ===== 素材生成 =====

/**
 * 生成單張素材圖片（不繫結具體頁面）
 * 現在返回非同步任務ID，需要透過getTaskStatus輪詢獲取結果
 */
export const generateMaterialImage = async (
  projectId: string,
  prompt: string,
  refImage?: File | null,
  extraImages?: File[]
): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const formData = new FormData();
  formData.append('prompt', prompt);
  if (refImage) {
    formData.append('ref_image', refImage);
  }

  if (extraImages && extraImages.length > 0) {
    extraImages.forEach((file) => {
      formData.append('extra_images', file);
    });
  }

  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>(
    `/api/projects/${projectId}/materials/generate`,
    formData
  );
  return response.data;
};

/**
 * 素材資訊介面
 */
export interface Material {
  id: string;
  project_id?: string | null;
  filename: string;
  url: string;
  relative_path: string;
  created_at: string;
  // 可選的附加資訊：用於展示友好名稱
  prompt?: string;
  original_filename?: string;
  source_filename?: string;
  name?: string;
}

/**
 * 獲取素材列表
 * @param projectId 專案ID，可選
 *   - If provided and not 'all' or 'none': Get materials for specific project via /api/projects/{projectId}/materials
 *   - If 'all': Get all materials via /api/materials?project_id=all
 *   - If 'none': Get global materials (not bound to any project) via /api/materials?project_id=none
 *   - If not provided: Get all materials via /api/materials
 */
export const listMaterials = async (
  projectId?: string
): Promise<ApiResponse<{ materials: Material[]; count: number }>> => {
  let url: string;

  if (!projectId || projectId === 'all') {
    // Get all materials using global endpoint
    url = '/api/materials?project_id=all';
  } else if (projectId === 'none') {
    // Get global materials (not bound to any project)
    url = '/api/materials?project_id=none';
  } else {
    // Get materials for specific project
    url = `/api/projects/${projectId}/materials`;
  }

  const response = await apiClient.get<ApiResponse<{ materials: Material[]; count: number }>>(url);
  return response.data;
};

/**
 * 上傳素材圖片
 * @param file 圖片檔案
 * @param projectId 可選的專案ID
 *   - If provided: Upload material bound to the project
 *   - If not provided or 'none': Upload as global material (not bound to any project)
 */
export const uploadMaterial = async (
  file: File,
  projectId?: string | null
): Promise<ApiResponse<Material>> => {
  const formData = new FormData();
  formData.append('file', file);

  let url: string;
  if (!projectId || projectId === 'none') {
    // Use global upload endpoint for materials not bound to any project
    url = '/api/materials/upload';
  } else {
    // Use project-specific upload endpoint
    url = `/api/projects/${projectId}/materials/upload`;
  }

  const response = await apiClient.post<ApiResponse<Material>>(url, formData);
  return response.data;
};

/**
 * 刪除素材
 */
export const deleteMaterial = async (materialId: string): Promise<ApiResponse<{ id: string }>> => {
  const response = await apiClient.delete<ApiResponse<{ id: string }>>(`/api/materials/${materialId}`);
  return response.data;
};

/**
 * 批次下載素材（打包為zip）
 * @param materialIds 素材ID列表
 */
export const downloadMaterialsZip = async (
  materialIds: string[]
): Promise<ApiResponse<{ download_url: string }>> => {
  const response = await apiClient.post<Blob>(
    '/api/materials/download',
    { material_ids: materialIds },
    { responseType: 'blob' }
  );

  // 直接觸發下載
  const blob = response.data;
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'materials.zip';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);

  return { success: true, data: { download_url: '' } };
};

/**
 * 關聯素材到專案（透過URL）
 * @param projectId 專案ID
 * @param materialUrls 素材URL列表
 */
export const associateMaterialsToProject = async (
  projectId: string,
  materialUrls: string[]
): Promise<ApiResponse<{ updated_ids: string[]; count: number }>> => {
  const response = await apiClient.post<ApiResponse<{ updated_ids: string[]; count: number }>>(
    '/api/materials/associate',
    { project_id: projectId, material_urls: materialUrls }
  );
  return response.data;
};

// ===== 使用者模板 =====

export interface UserTemplate {
  template_id: string;
  name?: string;
  template_image_url: string;
  thumb_url?: string;  // Thumbnail URL for faster loading
  created_at?: string;
  updated_at?: string;
}

/**
 * 上傳使用者模板
 */
export const uploadUserTemplate = async (
  templateImage: File,
  name?: string
): Promise<ApiResponse<UserTemplate>> => {
  const formData = new FormData();
  formData.append('template_image', templateImage);
  if (name) {
    formData.append('name', name);
  }

  const response = await apiClient.post<ApiResponse<UserTemplate>>(
    '/api/user-templates',
    formData
  );
  return response.data;
};

/**
 * 獲取使用者模板列表
 */
export const listUserTemplates = async (): Promise<ApiResponse<{ templates: UserTemplate[] }>> => {
  const response = await apiClient.get<ApiResponse<{ templates: UserTemplate[] }>>(
    '/api/user-templates'
  );
  return response.data;
};

/**
 * 刪除使用者模板
 */
export const deleteUserTemplate = async (templateId: string): Promise<ApiResponse> => {
  const response = await apiClient.delete<ApiResponse>(`/api/user-templates/${templateId}`);
  return response.data;
};

// ===== 參考檔案相關 API =====

export interface ReferenceFile {
  id: string;
  project_id: string | null;
  filename: string;
  file_size: number;
  file_type: string;
  parse_status: 'pending' | 'parsing' | 'completed' | 'failed';
  markdown_content: string | null;
  error_message: string | null;
  image_caption_failed_count?: number;  // Optional, calculated dynamically
  created_at: string;
  updated_at: string;
}

/**
 * 上傳參考檔案
 * @param file 檔案
 * @param projectId 可選的專案ID（如果不提供或為'none'，則為全域性檔案）
 */
export const uploadReferenceFile = async (
  file: File,
  projectId?: string | null
): Promise<ApiResponse<{ file: ReferenceFile }>> => {
  const formData = new FormData();
  formData.append('file', file);
  if (projectId && projectId !== 'none') {
    formData.append('project_id', projectId);
  }

  const response = await apiClient.post<ApiResponse<{ file: ReferenceFile }>>(
    '/api/reference-files/upload',
    formData
  );
  return response.data;
};

/**
 * 獲取參考檔案資訊
 * @param fileId 檔案ID
 */
export const getReferenceFile = async (fileId: string): Promise<ApiResponse<{ file: ReferenceFile }>> => {
  const response = await apiClient.get<ApiResponse<{ file: ReferenceFile }>>(
    `/api/reference-files/${fileId}`
  );
  return response.data;
};

/**
 * 列出專案的參考檔案
 * @param projectId 專案ID（'global' 或 'none' 表示列出全域性檔案）
 */
export const listProjectReferenceFiles = async (
  projectId: string
): Promise<ApiResponse<{ files: ReferenceFile[] }>> => {
  const response = await apiClient.get<ApiResponse<{ files: ReferenceFile[] }>>(
    `/api/reference-files/project/${projectId}`
  );
  return response.data;
};

/**
 * 刪除參考檔案
 * @param fileId 檔案ID
 */
export const deleteReferenceFile = async (fileId: string): Promise<ApiResponse<{ message: string }>> => {
  const response = await apiClient.delete<ApiResponse<{ message: string }>>(
    `/api/reference-files/${fileId}`
  );
  return response.data;
};

/**
 * 觸發檔案解析
 * @param fileId 檔案ID
 */
export const triggerFileParse = async (fileId: string): Promise<ApiResponse<{ file: ReferenceFile; message: string }>> => {
  const response = await apiClient.post<ApiResponse<{ file: ReferenceFile; message: string }>>(
    `/api/reference-files/${fileId}/parse`
  );
  return response.data;
};

/**
 * 將參考檔案關聯到專案
 * @param fileId 檔案ID
 * @param projectId 專案ID
 */
export const associateFileToProject = async (
  fileId: string,
  projectId: string
): Promise<ApiResponse<{ file: ReferenceFile }>> => {
  const response = await apiClient.post<ApiResponse<{ file: ReferenceFile }>>(
    `/api/reference-files/${fileId}/associate`,
    { project_id: projectId }
  );
  return response.data;
};

/**
 * 從專案中移除參考檔案（不刪除檔案本身）
 * @param fileId 檔案ID
 */
export const dissociateFileFromProject = async (
  fileId: string
): Promise<ApiResponse<{ file: ReferenceFile; message: string }>> => {
  const response = await apiClient.post<ApiResponse<{ file: ReferenceFile; message: string }>>(
    `/api/reference-files/${fileId}/dissociate`
  );
  return response.data;
};

// ===== 輸出語言設定 =====

export type OutputLanguage = 'zh' | 'ja' | 'en' | 'auto';

export interface OutputLanguageOption {
  value: OutputLanguage;
  label: string;
}

export const OUTPUT_LANGUAGE_OPTIONS: OutputLanguageOption[] = [
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日本語' },
  { value: 'en', label: 'English' },
  { value: 'auto', label: '自動' },
];

/**
 * 獲取預設輸出語言設定（從伺服器環境變數讀取）
 *
 * 注意：這隻返回伺服器配置的預設語言。
 * 實際的語言選擇應由前端在 sessionStorage 中管理，
 * 並在每次生成請求時透過 language 引數傳遞。
 */
export const getDefaultOutputLanguage = async (): Promise<ApiResponse<{ language: OutputLanguage }>> => {
  const response = await apiClient.get<ApiResponse<{ language: OutputLanguage }>>(
    '/api/output-language'
  );
  return response.data;
};

/**
 * 從後端 Settings 獲取使用者的輸出語言偏好
 * 如果獲取失敗，返回預設值 'zh'
 */
export const getStoredOutputLanguage = async (): Promise<OutputLanguage> => {
  try {
    const response = await apiClient.get<ApiResponse<{ language: OutputLanguage }>>('/api/output-language');
    return response.data.data?.language || 'zh';
  } catch (error) {
    console.warn('Failed to load output language from settings, using default', error);
    return 'zh';
  }
};

/**
 * 獲取系統設定
 */
export const getSettings = async (): Promise<ApiResponse<Settings>> => {
  const response = await apiClient.get<ApiResponse<Settings>>('/api/settings');
  return response.data;
};

/**
 * 更新系統設定
 */
export const updateSettings = async (
  data: Partial<Omit<Settings, 'id' | 'api_key_length' | 'mineru_token_length' | 'baidu_ocr_api_key_length' | 'created_at' | 'updated_at'>> & { 
    api_key?: string;
    mineru_token?: string;
    baidu_ocr_api_key?: string;
  }
): Promise<ApiResponse<Settings>> => {
  const response = await apiClient.put<ApiResponse<Settings>>('/api/settings', data);
  return response.data;
};

/**
 * 重置系統設定
 */
export const resetSettings = async (): Promise<ApiResponse<Settings>> => {
  const response = await apiClient.post<ApiResponse<Settings>>('/api/settings/reset');
  return response.data;
};

/**
 * 驗證 API key 是否可用
 */
export const verifyApiKey = async (): Promise<ApiResponse<{ available: boolean; message: string }>> => {
  const response = await apiClient.post<ApiResponse<{ available: boolean; message: string }>>('/api/settings/verify');
  return response.data;
};

/**
 * 可選的測試設定型別
 */
export interface TestSettingsOverride {
  api_key?: string;
  api_base_url?: string;
  text_model?: string;
  image_model?: string;
  image_caption_model?: string;
  mineru_api_base?: string;
  mineru_token?: string;
  baidu_ocr_api_key?: string;
  ai_provider_format?: 'openai' | 'gemini';
  image_resolution?: string;
  enable_text_reasoning?: boolean;
  text_thinking_budget?: number;
  enable_image_reasoning?: boolean;
  image_thinking_budget?: number;
}

/**
 * 測試百度 OCR 服務（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testBaiduOcr = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/baidu-ocr', settings || {});
  return response.data;
};

/**
 * 測試文字生成模型（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testTextModel = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/text-model', settings || {});
  return response.data;
};

/**
 * 測試圖片識別模型（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testCaptionModel = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/caption-model', settings || {});
  return response.data;
};

/**
 * 測試百度影象修復（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testBaiduInpaint = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/baidu-inpaint', settings || {});
  return response.data;
};

/**
 * 測試影象生成模型（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testImageModel = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/image-model', settings || {});
  return response.data;
};

/**
 * 測試 MinerU PDF 解析（非同步）
 * @param settings 可選的設定覆蓋（未儲存的設定）
 * @returns 返回任務ID，需要透過 getTestStatus 輪詢結果
 */
export const testMineruPdf = async (settings?: TestSettingsOverride): Promise<ApiResponse<{ task_id: string; status: string }>> => {
  const response = await apiClient.post<ApiResponse<{ task_id: string; status: string }>>('/api/settings/tests/mineru-pdf', settings || {});
  return response.data;
};

/**
 * 查詢測試任務狀態
 * @param taskId 任務ID
 * @returns 任務狀態資訊
 */
export const getTestStatus = async (taskId: string): Promise<ApiResponse<{
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  result?: any;
  error?: string;
  message?: string;
}>> => {
  const response = await apiClient.get<ApiResponse<any>>(`/api/settings/tests/${taskId}/status`);
  return response.data;
};
