import React, { useState } from 'react';
import { X, FileText, Settings as SettingsIcon, Download, Sparkles, AlertTriangle } from 'lucide-react';
import { Button, Textarea } from '@/components/shared';
import { Settings } from '@/pages/Settings';
import type { ExportExtractorMethod, ExportInpaintMethod } from '@/types';

interface ProjectSettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  // 專案設定
  extraRequirements: string;
  templateStyle: string;
  onExtraRequirementsChange: (value: string) => void;
  onTemplateStyleChange: (value: string) => void;
  onSaveExtraRequirements: () => void;
  onSaveTemplateStyle: () => void;
  isSavingRequirements: boolean;
  isSavingTemplateStyle: boolean;
  // 匯出設定
  exportExtractorMethod?: ExportExtractorMethod;
  exportInpaintMethod?: ExportInpaintMethod;
  onExportExtractorMethodChange?: (value: ExportExtractorMethod) => void;
  onExportInpaintMethodChange?: (value: ExportInpaintMethod) => void;
  onSaveExportSettings?: () => void;
  isSavingExportSettings?: boolean;
}

type SettingsTab = 'project' | 'global' | 'export';

// 元件提取方法選項
const EXTRACTOR_METHOD_OPTIONS: { value: ExportExtractorMethod; label: string; description: string }[] = [
  { 
    value: 'hybrid', 
    label: '混合提取（推薦）', 
    description: 'MinerU版面分析 + 百度高精度OCR，文字識別更精確' 
  },
  { 
    value: 'mineru', 
    label: 'MinerU提取', 
    description: '僅使用MinerU進行版面分析和文字識別' 
  },
];

// 背景圖獲取方法選項
const INPAINT_METHOD_OPTIONS: { value: ExportInpaintMethod; label: string; description: string; usesAI: boolean }[] = [
  { 
    value: 'hybrid', 
    label: '混合方式獲取（推薦）', 
    description: '百度精確去除文字 + 生成式模型提升畫質',
    usesAI: true 
  },
  { 
    value: 'generative', 
    label: '生成式獲取', 
    description: '使用生成式大模型（如Gemini）直接生成背景，背景質量高但有遺留元素的可能',
    usesAI: true 
  },
  { 
    value: 'baidu', 
    label: '百度抹除服務獲取', 
    description: '使用百度影象修復API，速度快但畫質一般',
    usesAI: false 
  },
];

export const ProjectSettingsModal: React.FC<ProjectSettingsModalProps> = ({
  isOpen,
  onClose,
  extraRequirements,
  templateStyle,
  onExtraRequirementsChange,
  onTemplateStyleChange,
  onSaveExtraRequirements,
  onSaveTemplateStyle,
  isSavingRequirements,
  isSavingTemplateStyle,
  // 匯出設定
  exportExtractorMethod = 'hybrid',
  exportInpaintMethod = 'hybrid',
  onExportExtractorMethodChange,
  onExportInpaintMethodChange,
  onSaveExportSettings,
  isSavingExportSettings = false,
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>('project');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden">
        {/* 頂部標題欄 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 flex-shrink-0">
          <h2 className="text-xl font-bold text-gray-900">設定</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            aria-label="關閉"
          >
            <X size={20} />
          </button>
        </div>

        {/* 主內容區 */}
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* 左側導航欄 */}
          <aside className="w-64 bg-gray-50 border-r border-gray-200 flex-shrink-0">
            <nav className="p-4 space-y-2">
              <button
                onClick={() => setActiveTab('project')}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  activeTab === 'project'
                    ? 'bg-banana-500 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                }`}
              >
                <FileText size={20} />
                <span className="font-medium">專案設定</span>
              </button>
              <button
                onClick={() => setActiveTab('export')}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  activeTab === 'export'
                    ? 'bg-banana-500 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                }`}
              >
                <Download size={20} />
                <span className="font-medium">匯出設定</span>
              </button>
              <button
                onClick={() => setActiveTab('global')}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                  activeTab === 'global'
                    ? 'bg-banana-500 text-white shadow-md'
                    : 'bg-white text-gray-700 hover:bg-gray-100'
                }`}
              >
                <SettingsIcon size={20} />
                <span className="font-medium">全域性設定</span>
              </button>
            </nav>
          </aside>

          {/* 右側內容區 */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'project' ? (
              <div className="max-w-3xl space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">專案級配置</h3>
                  <p className="text-sm text-gray-600 mb-6">
                    這些設定僅應用於當前專案，不影響其他專案
                  </p>
                </div>

                {/* 額外要求 */}
                <div className="bg-gray-50 rounded-lg p-6 space-y-4">
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-2">額外要求</h4>
                    <p className="text-sm text-gray-600">
                      在生成每個頁面時，AI 會參考這些額外要求
                    </p>
                  </div>
                  <Textarea
                    value={extraRequirements}
                    onChange={(e) => onExtraRequirementsChange(e.target.value)}
                    placeholder="例如：使用緊湊的佈局，頂部展示一級大綱標題，加入更豐富的PPT插圖..."
                    rows={4}
                    className="text-sm"
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={onSaveExtraRequirements}
                    disabled={isSavingRequirements}
                    className="w-full sm:w-auto"
                  >
                    {isSavingRequirements ? '儲存中...' : '儲存額外要求'}
                  </Button>
                </div>

                {/* 風格描述 */}
                <div className="bg-blue-50 rounded-lg p-6 space-y-4">
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-2">風格描述</h4>
                    <p className="text-sm text-gray-600">
                      描述您期望的 PPT 整體風格，AI 將根據描述生成相應風格的頁面
                    </p>
                  </div>
                  <Textarea
                    value={templateStyle}
                    onChange={(e) => onTemplateStyleChange(e.target.value)}
                    placeholder="例如：簡約商務風格，使用深藍色和白色配色，字型清晰大方，佈局整潔..."
                    rows={5}
                    className="text-sm"
                  />
                  <div className="flex flex-col sm:flex-row gap-3">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={onSaveTemplateStyle}
                      disabled={isSavingTemplateStyle}
                      className="w-full sm:w-auto"
                    >
                      {isSavingTemplateStyle ? '儲存中...' : '儲存風格描述'}
                    </Button>
                  </div>
                  <div className="bg-blue-100 rounded-md p-3">
                    <p className="text-xs text-blue-900">
                      💡 <strong>提示：</strong>風格描述會在生成圖片時自動新增到提示詞中。
                      如果同時上傳了模板圖片，風格描述會作為補充說明。
                    </p>
                  </div>
                </div>
              </div>
            ) : activeTab === 'export' ? (
              <div className="max-w-3xl space-y-6">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">可編輯 PPTX 匯出設定</h3>
                  <p className="text-sm text-gray-600 mb-6">
                    配置「匯出可編輯 PPTX」功能的處理方式。這些設定影響匯出質量和API呼叫成本。
                  </p>
                </div>

                {/* 元件提取方法 */}
                <div className="bg-gray-50 rounded-lg p-6 space-y-4">
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-2">元件提取方法</h4>
                    <p className="text-sm text-gray-600">
                      選擇如何從PPT圖片中提取文字、表格等可編輯元件
                    </p>
                  </div>
                  <div className="space-y-3">
                    {EXTRACTOR_METHOD_OPTIONS.map((option) => (
                      <label
                        key={option.value}
                        className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                          exportExtractorMethod === option.value
                            ? 'border-banana-500 bg-banana-50'
                            : 'border-gray-200 hover:border-gray-300 bg-white'
                        }`}
                      >
                        <input
                          type="radio"
                          name="extractorMethod"
                          value={option.value}
                          checked={exportExtractorMethod === option.value}
                          onChange={(e) => onExportExtractorMethodChange?.(e.target.value as ExportExtractorMethod)}
                          className="mt-1 w-4 h-4 text-banana-500 focus:ring-banana-500"
                        />
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{option.label}</div>
                          <div className="text-sm text-gray-600 mt-1">{option.description}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>

                {/* 背景圖獲取方法 */}
                <div className="bg-orange-50 rounded-lg p-6 space-y-4">
                  <div>
                    <h4 className="text-base font-semibold text-gray-900 mb-2">背景圖獲取方法</h4>
                    <p className="text-sm text-gray-600">
                      選擇如何生成乾淨的背景圖（移除原圖中的文字後用於PPT背景）
                    </p>
                  </div>
                  <div className="space-y-3">
                    {INPAINT_METHOD_OPTIONS.map((option) => (
                      <label
                        key={option.value}
                        className={`flex items-start gap-3 p-4 rounded-lg border-2 cursor-pointer transition-all ${
                          exportInpaintMethod === option.value
                            ? 'border-banana-500 bg-banana-50'
                            : 'border-gray-200 hover:border-gray-300 bg-white'
                        }`}
                      >
                        <input
                          type="radio"
                          name="inpaintMethod"
                          value={option.value}
                          checked={exportInpaintMethod === option.value}
                          onChange={(e) => onExportInpaintMethodChange?.(e.target.value as ExportInpaintMethod)}
                          className="mt-1 w-4 h-4 text-banana-500 focus:ring-banana-500"
                        />
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900">{option.label}</span>
                            {option.usesAI && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
                                <Sparkles size={12} />
                                使用文生圖模型
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-gray-600 mt-1">{option.description}</div>
                        </div>
                      </label>
                    ))}
                  </div>
                  <div className="bg-amber-100 rounded-md p-3 flex items-start gap-2">
                    <AlertTriangle size={16} className="text-amber-700 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-900">
                      <strong>成本提示：</strong>標有「使用文生圖模型」的選項會呼叫AI圖片生成API（如Gemini），
                      每頁會產生額外的API呼叫費用。如果需要控制成本，可選擇「百度修復」方式。
                    </p>
                  </div>
                </div>

                {/* 儲存按鈕 */}
                {onSaveExportSettings && (
                  <div className="flex justify-end pt-4">
                    <Button
                      variant="primary"
                      onClick={onSaveExportSettings}
                      disabled={isSavingExportSettings}
                    >
                      {isSavingExportSettings ? '儲存中...' : '儲存匯出設定'}
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              <div className="max-w-4xl">
                <div className="mb-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">全域性設定</h3>
                  <p className="text-sm text-gray-600">
                    這些設定應用於所有專案
                  </p>
                </div>
                {/* 複用 Settings 元件的內容 */}
                <Settings />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

