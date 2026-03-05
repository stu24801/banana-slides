// 頁面狀態
export type PageStatus = 'DRAFT' | 'DESCRIPTION_GENERATED' | 'GENERATING' | 'COMPLETED' | 'FAILED';

// 專案狀態
export type ProjectStatus = 'DRAFT' | 'OUTLINE_GENERATED' | 'DESCRIPTIONS_GENERATED' | 'COMPLETED';

// 大綱內容
export interface OutlineContent {
  title: string;
  points: string[];
}

// 描述內容 - 支援兩種格式：後端可能返回純文字或結構化內容
export type DescriptionContent = 
  | {
      // 格式1: 後端返回的純文字格式
      text: string;
    }
  | {
      // 格式2: 型別定義中的結構化格式
      title: string;
      text_content: string[];
      layout_suggestion?: string;
    };

// 圖片版本
export interface ImageVersion {
  version_id: string;
  page_id: string;
  image_path: string;
  image_url?: string;
  version_number: number;
  is_current: boolean;
  created_at?: string;
}

// 頁面
export interface Page {
  page_id: string;  // 後端返回 page_id
  id?: string;      // 前端使用的別名
  order_index: number;
  part?: string; // 章節名
  outline_content: OutlineContent;
  description_content?: DescriptionContent;
  generated_image_url?: string; // 後端返回 generated_image_url
  generated_image_path?: string; // 前端使用的別名
  status: PageStatus;
  created_at?: string;
  updated_at?: string;
  image_versions?: ImageVersion[]; // 歷史版本列表
}

// 匯出設定 - 元件提取方法
export type ExportExtractorMethod = 'mineru' | 'hybrid';

// 匯出設定 - 背景圖獲取方法
export type ExportInpaintMethod = 'generative' | 'baidu' | 'hybrid';

// 專案
export interface Project {
  project_id: string;  // 後端返回 project_id
  id?: string;         // 前端使用的別名
  idea_prompt: string;
  outline_text?: string;  // 使用者輸入的大綱文字（用於outline型別）
  description_text?: string;  // 使用者輸入的描述文字（用於description型別）
  extra_requirements?: string; // 額外要求，應用到每個頁面的AI提示詞
  creation_type?: string;
  template_image_url?: string; // 後端返回 template_image_url
  template_image_path?: string; // 前端使用的別名
  template_style?: string; // 風格描述文字（無模板圖模式）
  // 匯出設定
  export_extractor_method?: ExportExtractorMethod; // 元件提取方法
  export_inpaint_method?: ExportInpaintMethod; // 背景圖獲取方法
  status: ProjectStatus;
  pages: Page[];
  created_at: string;
  updated_at: string;
}

// 任務狀態
export type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';

// 任務資訊
export interface Task {
  task_id: string;
  id?: string; // 別名
  task_type?: string;
  status: TaskStatus;
  progress?: {
    total: number;
    completed: number;
    failed?: number;
    [key: string]: any; // 允許額外的欄位，如material_id, image_url等
  };
  error_message?: string;
  result?: any;
  error?: string; // 別名
  created_at?: string;
  completed_at?: string;
}

// 建立專案請求
export interface CreateProjectRequest {
  idea_prompt?: string;
  outline_text?: string;
  description_text?: string;
  template_image?: File;
  template_style?: string;
}

// API響應
export interface ApiResponse<T = any> {
  success?: boolean;
  data?: T;
  task_id?: string;
  message?: string;
  error?: string;
}

// 設定
export interface Settings {
  id: number;
  ai_provider_format: 'openai' | 'gemini';
  api_base_url?: string;
  api_key_length: number;
  image_resolution: string;
  image_aspect_ratio: string;
  max_description_workers: number;
  max_image_workers: number;
  text_model?: string;
  image_model?: string;
  mineru_api_base?: string;
  mineru_token_length: number;
  image_caption_model?: string;
  output_language: 'zh' | 'en' | 'ja' | 'auto';
  // 推理模式配置（分別控制文字和影象）
  enable_text_reasoning: boolean;
  text_thinking_budget: number;
  enable_image_reasoning: boolean;
  image_thinking_budget: number;
  baidu_ocr_api_key_length: number;
  created_at?: string;
  updated_at?: string;
}


