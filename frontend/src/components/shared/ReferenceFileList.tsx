import React, { useState, useEffect, useRef } from 'react';
import { ReferenceFileCard, useToast } from '@/components/shared';
import { listProjectReferenceFiles, type ReferenceFile } from '@/api/endpoints';

interface ReferenceFileListProps {
  // 兩種模式：1. 從 API 載入（傳入 projectId） 2. 直接顯示（傳入 files）
  projectId?: string | null;
  files?: ReferenceFile[]; // 如果傳入 files，則直接顯示，不從 API 載入
  onFileClick?: (fileId: string) => void;
  onFileStatusChange?: (file: ReferenceFile) => void;
  onFileDelete?: (fileId: string) => void; // 如果傳入，使用外部刪除邏輯
  deleteMode?: 'delete' | 'remove';
  title?: string; // 自定義標題
  className?: string; // 自定義樣式
}

export const ReferenceFileList: React.FC<ReferenceFileListProps> = ({
  projectId,
  files: externalFiles,
  onFileClick,
  onFileStatusChange,
  onFileDelete,
  deleteMode = 'remove',
  title = '已上傳的檔案',
  className = 'mb-6',
}) => {
  const [internalFiles, setInternalFiles] = useState<ReferenceFile[]>([]);
  const { show } = useToast();
  const showRef = useRef(show);

  // 如果傳入了 files，使用外部檔案列表；否則從 API 載入
  const isExternalMode = externalFiles !== undefined;
  const files = isExternalMode ? externalFiles : internalFiles;

  useEffect(() => {
    showRef.current = show;
  }, [show]);

  // 只在非外部模式下從 API 載入
  useEffect(() => {
    if (isExternalMode || !projectId) {
      if (!isExternalMode) {
        setInternalFiles([]);
      }
      return;
    }

    const loadFiles = async () => {
      try {
        const response = await listProjectReferenceFiles(projectId);
        if (response.data?.files) {
          setInternalFiles(response.data.files);
        }
      } catch (error: any) {
        console.error('載入檔案列表失敗:', error);
        showRef.current({
          message: error?.response?.data?.error?.message || error.message || '載入檔案列表失敗',
          type: 'error',
        });
      }
    };

    loadFiles();
  }, [projectId, isExternalMode]);

  const handleFileStatusChange = (updatedFile: ReferenceFile) => {
    if (!isExternalMode) {
      setInternalFiles(prev => prev.map(f => f.id === updatedFile.id ? updatedFile : f));
    }
    onFileStatusChange?.(updatedFile);
  };

  const handleFileDelete = (fileId: string) => {
    if (onFileDelete) {
      // 使用外部刪除邏輯
      onFileDelete(fileId);
    } else if (!isExternalMode) {
      // 內部刪除邏輯
      setInternalFiles(prev => prev.filter(f => f.id !== fileId));
    }
  };

  if (files.length === 0) {
    return null;
  }

  return (
    <div className={className}>
      <h3 className="text-sm font-semibold text-gray-700 mb-3">{title}</h3>
      <div className="space-y-2">
        {files.map(file => (
          <ReferenceFileCard
            key={file.id}
            file={file}
            onDelete={handleFileDelete}
            onStatusChange={handleFileStatusChange}
            deleteMode={deleteMode}
            onClick={() => onFileClick?.(file.id)}
          />
        ))}
      </div>
    </div>
  );
};

