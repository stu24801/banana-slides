#!/usr/bin/env python3
"""
自動翻譯README.md到README_EN.md

使用專案的AI服務將中文README翻譯成英文。
適用於CI/CD自動化流程。
"""

import os
import sys
import logging
from pathlib import Path

# 新增backend目錄到Python路徑
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def translate_readme(source_file: str, target_file: str):
    """
    翻譯README檔案
    
    Args:
        source_file: 原始檔路徑 (中文README.md)
        target_file: 目標檔案路徑 (英文README_EN.md)
    """
    try:
        # 匯入AI服務
        from services.ai_providers import get_text_provider
        
        # 讀取原始檔
        logger.info(f"讀取原始檔: {source_file}")
        with open(source_file, 'r', encoding='utf-8') as f:
            source_content = f.read()
        
        if not source_content.strip():
            logger.error("原始檔為空")
            sys.exit(1)
        
        logger.info(f"原始檔長度: {len(source_content)} 字元")
        
        # 獲取文字提供者（使用環境變數中的配置）
        logger.info("初始化AI文字提供者...")
        text_model = os.getenv('TEXT_MODEL', 'gemini-3-flash-preview')
        text_provider = get_text_provider(model=text_model)
        logger.info(f"使用模型: {text_model}")
        
        # 構建翻譯提示詞
        translation_prompt = f"""請將以下中文Markdown文件翻譯成英文。

要求：
1. 保持Markdown格式不變（包括標題、連結、圖片、程式碼塊等）
2. 保持所有HTML標籤和屬性不變
3. 保持所有URL連結不變
4. 保持徽章（badges）的連結和格式不變
5. 技術術語使用常見的英文表達
6. 語言風格要專業、清晰、易讀
7. 保持原文的段落結構和排版
8. 不要新增任何額外的解釋或註釋，只輸出翻譯後的內容

原文：

{source_content}

翻譯後的英文版本："""

        # 呼叫AI進行翻譯
        logger.info("開始翻譯...")
        translated_content = text_provider.generate_text(translation_prompt)
        
        if not translated_content or not translated_content.strip():
            logger.error("翻譯結果為空")
            sys.exit(1)
        
        logger.info(f"翻譯完成，長度: {len(translated_content)} 字元")
        
        # 後處理：確保中英文連結互換
        # 將 **中文 | [English](README_EN.md)** 替換為 **[中文](README.md) | English**
        translated_content = translated_content.replace(
            '**中文 | [English](README_EN.md)**',
            '**[中文](README.md) | English**'
        ).replace(
            '**Chinese | [English](README_EN.md)**',
            '**[中文](README.md) | English**'
        )
        
        # 寫入目標檔案
        logger.info(f"寫入目標檔案: {target_file}")
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        logger.info("✅ 翻譯成功完成！")
        return True
        
    except ImportError as e:
        logger.error(f"匯入錯誤: {e}")
        logger.error("請確保已安裝所有依賴: uv sync")
        sys.exit(1)
    except FileNotFoundError as e:
        logger.error(f"檔案不存在: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"翻譯失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """主函式"""
    # 獲取專案根目錄
    project_root = Path(__file__).parent.parent
    source_file = project_root / "README.md"
    target_file = project_root / "README_EN.md"
    
    logger.info("README 自動翻譯工具:")
    logger.info(f"專案根目錄: {project_root}")
    logger.info(f"原始檔: {source_file}")
    logger.info(f"目標檔案: {target_file}")
    
    # 檢查原始檔是否存在
    if not source_file.exists():
        logger.error(f"原始檔不存在: {source_file}")
        sys.exit(1)
    
    # 執行翻譯
    translate_readme(str(source_file), str(target_file))


if __name__ == "__main__":
    main()

