import React, { useState, useEffect, useRef, useCallback } from 'react';
import { FileText, Upload, X, Loader2, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import { Button, useToast, Modal } from '@/components/shared';
import {
  listProjectReferenceFiles,
  uploadReferenceFile,
  deleteReferenceFile,
  getReferenceFile,
  triggerFileParse,
  type ReferenceFile,
} from '@/api/endpoints';

interface ReferenceFileSelectorProps {
  projectId?: string | null; // 可選，如果不提供則使用全域性檔案
  isOpen: boolean;
  onClose: () => void;
  onSelect: (files: ReferenceFile[]) => void;
  multiple?: boolean; // 是否支援多選
  maxSelection?: number; // 最大選擇數量
  initialSelectedIds?: string[]; // 初始已選擇的檔案ID列表
}

/**
 * 參考檔案選擇器元件
 * - 瀏覽專案下的所有參考檔案
 * - 支援單選/多選
 * - 支援上傳本地檔案
 * - 支援從檔案庫選擇（已解析的直接用，未解析的選中後當場解析）
 * - 支援刪除檔案
 */
export const ReferenceFileSelector: React.FC<ReferenceFileSelectorProps> = React.memo(({
  projectId,
  isOpen,
  onClose,
  onSelect,
  multiple = true,
  maxSelection,
  initialSelectedIds = [],
}) => {
  const { show } = useToast();
  const [files, setFiles] = useState<ReferenceFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [parsingIds, setParsingIds] = useState<Set<string>>(new Set());
  const [filterProjectId, setFilterProjectId] = useState<string>('all'); // 始終預設顯示所有附件
  const fileInputRef = useRef<HTMLInputElement>(null);
  const initialSelectedIdsRef = useRef(initialSelectedIds);
  const showRef = useRef(show);

  // 更新 ref 以保持最新的值，避免將其加入依賴陣列導致無限迴圈
  useEffect(() => {
    initialSelectedIdsRef.current = initialSelectedIds;
    showRef.current = show;
  }, [initialSelectedIds, show]);

  const loadFiles = useCallback(async () => {
    setIsLoading(true);
    try {
      // 根據 filterProjectId 決定查詢哪些檔案
      // 'all' - 所有檔案（全域性 + 專案）
      // 'none' - 只查詢未歸類檔案（全域性檔案，project_id=None）
      // 專案ID - 只查詢該專案的檔案
      const targetProjectId = filterProjectId === 'all' ? 'all' : filterProjectId === 'none' ? 'none' : filterProjectId;
      const response = await listProjectReferenceFiles(targetProjectId);
      
      if (response.data?.files) {
        // 合併新舊檔案列表，避免丟失正在解析的檔案
        setFiles(prev => {
          const fileMap = new Map<string, ReferenceFile>();
          const serverFiles = response.data!.files; // 已經檢查過 response.data?.files
          
          // 先新增伺服器返回的檔案（這些是權威資料）
          serverFiles.forEach((f: ReferenceFile) => {
            fileMap.set(f.id, f);
          });
          
          // 然後新增正在解析的檔案（可能伺服器還沒更新狀態）
          prev.forEach(f => {
            if (parsingIds.has(f.id) && !fileMap.has(f.id)) {
              fileMap.set(f.id, f);
            }
          });
          
          return Array.from(fileMap.values());
        });
      }
    } catch (error: any) {
      console.error('載入參考檔案列表失敗:', error);
      showRef.current({
        message: error?.response?.data?.error?.message || error.message || '載入參考檔案列表失敗',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [filterProjectId, parsingIds]);

  useEffect(() => {
    if (isOpen) {
      loadFiles();
      // 恢復初始選擇
      setSelectedFiles(new Set(initialSelectedIdsRef.current));
    }
  }, [isOpen, filterProjectId, loadFiles]);

  // 輪詢解析狀態
  useEffect(() => {
    if (!isOpen || parsingIds.size === 0) return;

    const intervalId = setInterval(async () => {
      const idsToCheck = Array.from(parsingIds);
      const updatedFiles: ReferenceFile[] = [];
      const completedIds: string[] = [];

      for (const fileId of idsToCheck) {
        try {
          const response = await getReferenceFile(fileId);
          if (response.data?.file) {
            const updatedFile = response.data.file;
            updatedFiles.push(updatedFile);
            
            // 如果解析完成或失敗，標記為完成
            if (updatedFile.parse_status === 'completed' || updatedFile.parse_status === 'failed') {
              completedIds.push(fileId);
            }
          }
        } catch (error) {
          console.error(`Failed to poll file ${fileId}:`, error);
        }
      }

      // 批次更新檔案列表
      if (updatedFiles.length > 0) {
        setFiles(prev => {
          const fileMap = new Map(prev.map(f => [f.id, f]));
          updatedFiles.forEach(uf => fileMap.set(uf.id, uf));
          return Array.from(fileMap.values());
        });
      }

      // 從輪詢列表中移除已完成的檔案
      if (completedIds.length > 0) {
        setParsingIds(prev => {
          const newSet = new Set(prev);
          completedIds.forEach(id => newSet.delete(id));
          return newSet;
        });
      }
    }, 2000); // 每2秒輪詢一次

    return () => clearInterval(intervalId);
  }, [isOpen, parsingIds]);

  const handleSelectFile = (file: ReferenceFile) => {
    // 允許選擇所有狀態的檔案（包括 pending 和 parsing）
    // pending 的檔案會在確定時觸發解析
    // parsing 的檔案會等待解析完成

    if (multiple) {
      const newSelected = new Set(selectedFiles);
      if (newSelected.has(file.id)) {
        newSelected.delete(file.id);
      } else {
        if (maxSelection && newSelected.size >= maxSelection) {
          show({
            message: `最多隻能選擇 ${maxSelection} 個檔案`,
            type: 'info',
          });
          return;
        }
        newSelected.add(file.id);
      }
      setSelectedFiles(newSelected);
    } else {
      setSelectedFiles(new Set([file.id]));
    }
  };

  const handleConfirm = async () => {
    const selected = files.filter((f) => selectedFiles.has(f.id));
    
    if (selected.length === 0) {
      show({ message: '請至少選擇一個檔案', type: 'info' });
      return;
    }
    
    // 檢查是否有未解析的檔案需要觸發解析
    const unparsedFiles = selected.filter(f => f.parse_status === 'pending');
    
    if (unparsedFiles.length > 0) {
      // 觸發解析未解析的檔案，但立即返回（不等待）
      try {
        show({
          message: `已觸發 ${unparsedFiles.length} 個檔案的解析，將在後臺進行`,
          type: 'success',
        });

        // 觸發所有未解析檔案的解析（不等待完成）
        unparsedFiles.forEach(file => {
          triggerFileParse(file.id).catch(error => {
            console.error(`觸發檔案 ${file.filename} 解析失敗:`, error);
          });
        });
        
        // 立即返回所有選中的檔案（包括 pending 狀態的）
        onSelect(selected);
        onClose();
      } catch (error: any) {
        console.error('觸發檔案解析失敗:', error);
        show({
          message: error?.response?.data?.error?.message || error.message || '觸發檔案解析失敗',
          type: 'error',
        });
      }
    } else {
      // 所有檔案都已解析或正在解析，直接確認
      // 允許選擇所有狀態的檔案（completed, parsing）
      const validFiles = selected.filter(f => 
        f.parse_status === 'completed' || f.parse_status === 'parsing'
      );
      
      if (validFiles.length === 0) {
        show({ message: '請選擇有效的檔案', type: 'info' });
        return;
      }
      
      onSelect(validFiles);
      onClose();
    }
  };

  const handleClear = () => {
    setSelectedFiles(new Set());
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    // 檢查是否有PPT檔案，提示建議使用PDF
    const hasPptFiles = Array.from(files).some(file => {
      const fileExt = file.name.split('.').pop()?.toLowerCase();
      return fileExt === 'ppt' || fileExt === 'pptx';
    });
    
    if (hasPptFiles) show({  message: '💡 提示：建議將PPT轉換為PDF格式上傳，可獲得更好的解析效果', type: 'info' });
    

    setIsUploading(true);
    try {
      // 根據當前篩選條件決定上傳檔案的歸屬
      // 如果篩選為 'all' 或 'none'，上傳為全域性檔案（不關聯專案）
      // 如果篩選為專案ID，上傳到該專案
      const targetProjectId = (filterProjectId === 'all' || filterProjectId === 'none')
        ? null
        : filterProjectId;
      
      // 上傳所有選中的檔案
      const uploadPromises = Array.from(files).map(file =>
        uploadReferenceFile(file, targetProjectId)
      );

      const results = await Promise.all(uploadPromises);
      const uploadedFiles = results
        .map(r => r.data?.file)
        .filter((f): f is ReferenceFile => f !== undefined);

      if (uploadedFiles.length > 0) {
        show({ message: `成功上傳 ${uploadedFiles.length} 個檔案`, type: 'success' });
        
        // 只有正在解析的檔案才新增到輪詢列表（pending 狀態的檔案不輪詢）
        const needsParsing = uploadedFiles.filter(f => 
          f.parse_status === 'parsing'
        );
        if (needsParsing.length > 0) {
          setParsingIds(prev => {
            const newSet = new Set(prev);
            needsParsing.forEach(f => newSet.add(f.id));
            return newSet;
          });
        }
        
        // 合併新上傳的檔案到現有列表，而不是完全替換
        setFiles(prev => {
          const fileMap = new Map(prev.map(f => [f.id, f]));
          uploadedFiles.forEach(uf => fileMap.set(uf.id, uf));
          return Array.from(fileMap.values());
        });
        
        // 延遲重新載入檔案列表，確保伺服器端資料已更新
        setTimeout(() => {
          loadFiles();
        }, 500);
      }
    } catch (error: any) {
      console.error('上傳檔案失敗:', error);
      show({
        message: error?.response?.data?.error?.message || error.message || '上傳檔案失敗',
        type: 'error',
      });
    } finally {
      setIsUploading(false);
      // 清空 input 值，以便可以重複選擇同一檔案
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteFile = async (
    e: React.MouseEvent<HTMLButtonElement, MouseEvent>,
    file: ReferenceFile
  ) => {
    e.stopPropagation();
    const fileId = file.id;

    if (!fileId) {
      show({ message: '無法刪除：缺少檔案ID', type: 'error' });
      return;
    }

    setDeletingIds((prev) => {
      const newSet = new Set(prev);
      newSet.add(fileId);
      return newSet;
    });

    try {
      await deleteReferenceFile(fileId);
      show({ message: '檔案刪除成功', type: 'success' });
      
      // 從選擇中移除
      setSelectedFiles((prev) => {
        const newSet = new Set(prev);
        newSet.delete(fileId);
        return newSet;
      });
      
      // 從輪詢列表中移除
      setParsingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(fileId);
        return newSet;
      });
      
      loadFiles(); // 重新載入檔案列表
    } catch (error: any) {
      console.error('刪除檔案失敗:', error);
      show({
        message: error?.response?.data?.error?.message || error.message || '刪除檔案失敗',
        type: 'error',
      });
    } finally {
      setDeletingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(fileId);
        return newSet;
      });
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusIcon = (file: ReferenceFile) => {
    if (parsingIds.has(file.id) || file.parse_status === 'parsing') {
      return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
    }
    switch (file.parse_status) {
      case 'completed':
        return <CheckCircle2 className="w-4 h-4 text-green-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getStatusText = (file: ReferenceFile) => {
    if (parsingIds.has(file.id) || file.parse_status === 'parsing') {
      return '解析中...';
    }
    switch (file.parse_status) {
      case 'pending':
        return '等待解析';
      case 'completed':
        return '解析完成';
      case 'failed':
        return '解析失敗';
      default:
        return '';
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="選擇參考檔案" size="lg">
      <div className="space-y-4">
        {/* 工具欄 */}
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>{files.length > 0 ? `共 ${files.length} 個檔案` : '暫無檔案'}</span>
            {selectedFiles.size > 0 && (
              <span className="ml-2 text-banana-600">
                已選擇 {selectedFiles.size} 個
              </span>
            )}
            {isLoading && files.length > 0 && (
              <RefreshCw size={14} className="animate-spin text-gray-400" />
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* 專案篩選下拉選單 */}
            <select
              value={filterProjectId}
              onChange={(e) => setFilterProjectId(e.target.value)}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-banana-500"
            >
              <option value="all">所有附件</option>
              <option value="none">未歸類附件</option>
              {projectId && projectId !== 'global' && projectId !== 'none' && (
                <option value={projectId}>當前專案附件</option>
              )}
            </select>
            
            <Button
              variant="ghost"
              size="sm"
              icon={<RefreshCw size={16} />}
              onClick={loadFiles}
              disabled={isLoading}
            >
              重新整理
            </Button>
            
            <Button
              variant="ghost"
              size="sm"
              icon={<Upload size={16} />}
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
            >
              {isUploading ? '上傳中...' : '上傳檔案'}
            </Button>
            
            {selectedFiles.size > 0 && (
              <Button variant="ghost" size="sm" onClick={handleClear}>
                清空選擇
              </Button>
            )}
          </div>
        </div>

        {/* 隱藏的檔案輸入 */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.csv,.txt,.md"
          onChange={handleUpload}
          className="hidden"
        />

        {/* 檔案列表 */}
        <div className="border border-gray-200 rounded-lg max-h-96 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
              <span className="ml-2 text-gray-500">載入中...</span>
            </div>
          ) : files.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-gray-400">
              <FileText className="w-12 h-12 mb-2" />
              <p>暫無參考檔案</p>
              <p className="text-sm mt-1">點選"上傳檔案"按鈕新增檔案</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {files.map((file) => {
                const isSelected = selectedFiles.has(file.id);
                const isDeleting = deletingIds.has(file.id);
                const isPending = file.parse_status === 'pending';

                return (
                  <div
                    key={file.id}
                    onClick={() => handleSelectFile(file)}
                    className={`
                      p-4 cursor-pointer transition-colors
                      ${isSelected ? 'bg-banana-50 border-l-4 border-l-banana-500' : 'hover:bg-gray-50'}
                      ${file.parse_status === 'failed' ? 'opacity-60' : ''}
                    `}
                  >
                    <div className="flex items-start gap-3">
                      {/* 選擇框 */}
                      <div className="flex-shrink-0 mt-1">
                        <div
                          className={`
                            w-5 h-5 rounded border-2 flex items-center justify-center
                            ${isSelected
                              ? 'bg-banana-500 border-banana-500'
                              : 'border-gray-300'
                            }
                            ${file.parse_status === 'failed' ? 'opacity-50' : ''}
                          `}
                        >
                          {isSelected && (
                            <CheckCircle2 className="w-4 h-4 text-white" />
                          )}
                        </div>
                      </div>

                      {/* 檔案圖示 */}
                      <div className="flex-shrink-0">
                        <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center">
                          <FileText className="w-5 h-5 text-blue-600" />
                        </div>
                      </div>

                      {/* 檔案資訊 */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-gray-900 truncate">
                            {file.filename}
                          </p>
                          <span className="text-xs text-gray-500 flex-shrink-0">
                            {formatFileSize(file.file_size)}
                          </span>
                        </div>

                        {/* 狀態 */}
                        <div className="flex items-center gap-1.5 mt-1">
                          {getStatusIcon(file)}
                          <p className="text-xs text-gray-600">
                            {getStatusText(file)}
                            {isPending && (
                              <span className="ml-1 text-orange-500">(確定後解析)</span>
                            )}
                          </p>
                        </div>

                        {/* 失敗資訊 */}
                        {file.parse_status === 'failed' && file.error_message && (
                          <p className="text-xs text-red-500 mt-1 line-clamp-1">
                            {file.error_message}
                          </p>
                        )}

                        {/* 圖片識別失敗警告 */}
                        {file.parse_status === 'completed' && 
                         typeof file.image_caption_failed_count === 'number' && 
                         file.image_caption_failed_count > 0 && (
                          <p className="text-xs text-orange-500 mt-1">
                            ⚠️ {file.image_caption_failed_count} 張圖片未能生成描述
                          </p>
                        )}
                      </div>

                      {/* 刪除按鈕 */}
                      <button
                        onClick={(e) => handleDeleteFile(e, file)}
                        disabled={isDeleting}
                        className="flex-shrink-0 p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors disabled:opacity-50"
                        title="刪除檔案"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <X className="w-4 h-4" />
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 底部操作欄 */}
        <div className="flex items-center justify-between pt-4 border-t border-gray-200">
          <p className="text-xs text-gray-500">
            💡 提示：選擇未解析的檔案將自動開始解析
          </p>
          <div className="flex items-center gap-2">
            <Button variant="ghost" onClick={onClose}>
              取消
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={selectedFiles.size === 0}
            >
              確定 ({selectedFiles.size})
            </Button>
          </div>
        </div>
      </div>
    </Modal>
  );
});

