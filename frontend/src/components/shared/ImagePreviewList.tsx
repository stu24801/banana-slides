import React, { useMemo } from 'react';
import { X } from 'lucide-react';

interface ImagePreviewListProps {
  content: string;
  onRemoveImage?: (imageUrl: string) => void;
  className?: string;
}

/**
 * 解析markdown文字中的圖片連結
 * 支援格式: ![alt](url) 或 ![](url)
 */
const parseMarkdownImages = (text: string): Array<{ url: string; alt: string; fullMatch: string }> => {
  const imageRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
  const images: Array<{ url: string; alt: string; fullMatch: string }> = [];
  let match;

  while ((match = imageRegex.exec(text)) !== null) {
    images.push({
      alt: match[1] || 'image',
      url: match[2],
      fullMatch: match[0]
    });
  }

  return images;
};

/**
 * 圖片預覽列表元件 - 橫向滾動
 * 解析並顯示編輯框中的所有markdown圖片
 */
export const ImagePreviewList: React.FC<ImagePreviewListProps> = ({
  content,
  onRemoveImage,
  className = ''
}) => {
  // 解析圖片列表
  const images = useMemo(() => parseMarkdownImages(content), [content]);

  // 如果沒有圖片，不顯示元件
  if (images.length === 0) {
    return null;
  }

  return (
    <div className={`${className}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-sm font-medium text-gray-700">
          圖片預覽 ({images.length})
        </span>
      </div>
      
      {/* 橫向滾動容器 */}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {images.map((image, index) => (
          <div
            key={`${image.url}-${index}`}
            className="relative flex-shrink-0 group"
          >
            {/* 圖片容器 */}
            <div className="relative w-32 h-32 bg-gray-100 rounded-lg overflow-hidden border-2 border-gray-200 hover:border-banana-400 transition-colors">
              <img
                src={image.url}
                alt={image.alt}
                className="w-full h-full object-cover"
                onError={(e) => {
                  // 圖片載入失敗時顯示佔位符
                  const target = e.target as HTMLImageElement;
                  target.style.display = 'none';
                  const parent = target.parentElement;
                  if (parent && !parent.querySelector('.error-placeholder')) {
                    const placeholder = document.createElement('div');
                    placeholder.className = 'error-placeholder w-full h-full flex items-center justify-center text-gray-400 text-xs text-center p-2';
                    placeholder.textContent = '圖片載入失敗';
                    parent.appendChild(placeholder);
                  }
                }}
              />
              
              {/* 刪除按鈕 */}
              {onRemoveImage && (
                <button
                  onClick={() => onRemoveImage(image.url)}
                  className="absolute top-1 right-1 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 active:scale-95"
                  title="移除此圖片"
                >
                  <X size={14} />
                </button>
              )}
              
              {/* 懸浮時顯示完整URL */}
              <div className="absolute inset-x-0 bottom-0 bg-black/70 text-white text-xs p-1 opacity-0 group-hover:opacity-100 transition-opacity truncate">
                {image.url}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ImagePreviewList;

