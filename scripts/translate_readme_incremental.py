#!/usr/bin/env python3
"""
基於 diff 的增量翻譯 README.md 到 README_EN.md

"""

import os
import sys
import logging
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict

# 新增backend目錄到Python路徑
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def split_by_headers(content: str) -> List[Tuple[str, str, str]]:
    """
    按 Markdown 標題將內容分塊

    Returns:
        List of (header, title, content) tuples
        header: 標題行 (如 "## 功能特性")
        title: 標題文字 (如 "功能特性")
        content: 該標題下的內容（不含標題本身）
    """
    # 匹配 Markdown 標題（# 到 #### 級別）
    header_pattern = re.compile(r'^(#{1,4})\s+(.+)$', re.MULTILINE)

    blocks = []
    last_pos = 0
    last_header = ""
    last_title = ""

    for match in header_pattern.finditer(content):
        # 儲存上一個塊的內容
        if last_pos > 0 or match.start() > 0:
            block_content = content[last_pos:match.start()].strip()
            if last_header or block_content:  # 儲存非空塊
                blocks.append((last_header, last_title, block_content))

        # 更新當前標題資訊
        last_header = match.group(0)  # 完整的標題行
        last_title = match.group(2).strip()  # 標題文字
        last_pos = match.end() + 1  # 跳過換行符

    # 儲存最後一個塊
    if last_pos < len(content):
        block_content = content[last_pos:].strip()
        blocks.append((last_header, last_title, block_content))
    elif last_header:
        # 如果最後一個標題後面沒有內容
        blocks.append((last_header, last_title, ""))

    return blocks


def get_git_diff_lines(file_path: str) -> set:
    """
    獲取檔案在 git 中修改的行號

    Returns:
        修改的行號集合
    """
    try:
        # 獲取 git diff，顯示修改的行
        result = subprocess.run(
            ['git', 'diff', '-U0', 'HEAD', file_path],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            logger.warning(f"Git diff 失敗，將翻譯全部內容")
            return set()

        # 解析 diff 輸出，提取修改的行號
        changed_lines = set()
        for line in result.stdout.split('\n'):
            # 匹配 @@ -x,y +a,b @@ 格式
            if line.startswith('@@'):
                # 提取新檔案的行號範圍 (+a,b)
                match = re.search(r'\+(\d+)(?:,(\d+))?', line)
                if match:
                    start = int(match.group(1))
                    count = int(match.group(2)) if match.group(2) else 1
                    changed_lines.update(range(start, start + count))

        logger.info(f"檢測到 {len(changed_lines)} 行修改")
        return changed_lines

    except Exception as e:
        logger.warning(f"獲取 git diff 失敗: {e}，將翻譯全部內容")
        return set()


def find_changed_blocks(content: str, changed_lines: set) -> set:
    """
    根據修改的行號，找出哪些塊被修改了

    Returns:
        修改的塊的標題集合
    """
    if not changed_lines:
        logger.info("沒有檢測到具體的修改行，將翻譯所有塊")
        return set()

    blocks = split_by_headers(content)
    changed_blocks = set()

    current_line = 1
    for header, title, block_content in blocks:
        # 計算這個塊的行範圍
        block_lines = len(header.split('\n')) + len(block_content.split('\n'))
        block_range = set(range(current_line, current_line + block_lines))

        # 檢查是否有交集
        if block_range & changed_lines:
            changed_blocks.add(title)
            logger.info(f"檢測到修改的塊: {title}")

        current_line += block_lines

    return changed_blocks


def translate_block(content: str, text_provider) -> str:
    """翻譯單個內容塊"""
    translation_prompt = f"""Please translate the following Chinese Markdown content to English.

Requirements:
1. Keep Markdown format unchanged (headings, links, images, code blocks, etc.)
2. Keep all HTML tags and attributes unchanged
3. Keep all URLs unchanged
4. Keep all badges links and format unchanged
5. Use common English expressions for technical terms
6. Professional, clear, and readable style
7. Keep original paragraph structure and layout
8. Output ONLY the translated content without any extra explanations

Original content:

{content}

Translated English version:"""

    translated = text_provider.generate_text(translation_prompt)
    return translated.strip()


def incremental_translate(source_file: str, target_file: str, force_full: bool = False):
    """
    增量翻譯 README

    Args:
        source_file: 原始檔路徑 (中文README.md)
        target_file: 目標檔案路徑 (英文README_EN.md)
        force_full: 是否強制全文翻譯
    """
    try:
        from services.ai_providers import get_text_provider

        # 讀取原始檔
        logger.info(f"讀取原始檔: {source_file}")
        with open(source_file, 'r', encoding='utf-8') as f:
            source_content = f.read()

        if not source_content.strip():
            logger.error("原始檔為空")
            sys.exit(1)

        # 讀取現有的英文檔案（如果存在）
        target_content = ""
        target_blocks = {}
        if os.path.exists(target_file) and not force_full:
            logger.info(f"讀取現有英文檔案: {target_file}")
            with open(target_file, 'r', encoding='utf-8') as f:
                target_content = f.read()

            # 解析英文檔案的塊
            for header, title, content in split_by_headers(target_content):
                target_blocks[title] = (header, content)

        # 獲取 AI 提供者
        logger.info("初始化AI文字提供者...")
        text_model = os.getenv('TEXT_MODEL', 'gemini-3-flash-preview')
        text_provider = get_text_provider(model=text_model)
        logger.info(f"使用模型: {text_model}")

        # 檢測修改的行
        changed_lines = get_git_diff_lines(source_file) if not force_full else set()

        # 分塊處理
        source_blocks = split_by_headers(source_content)
        changed_block_titles = find_changed_blocks(source_content, changed_lines) if changed_lines else set()

        # 如果沒有檢測到具體的變化，或者是新檔案，則翻譯全部
        if not target_content or force_full or not changed_lines:
            logger.info("執行全文翻譯")
            changed_block_titles = {title for _, title, _ in source_blocks}

        # 翻譯修改的塊
        translated_blocks = []
        total_blocks = len(source_blocks)
        translated_count = 0

        for idx, (header, title, content) in enumerate(source_blocks, 1):
            # 如果這個塊被修改了，或者目標檔案中不存在，則需要翻譯
            needs_translation = (
                not changed_lines or  # 沒有 diff 資訊，翻譯全部
                title in changed_block_titles or  # 塊被修改
                title not in target_blocks  # 新增的塊
            )

            if needs_translation:
                logger.info(f"[{idx}/{total_blocks}] 翻譯塊: {title}")

                # 翻譯標題和內容
                if header:
                    translated_header = translate_block(header, text_provider)
                else:
                    translated_header = ""

                if content:
                    translated_content = translate_block(content, text_provider)
                else:
                    translated_content = ""

                translated_blocks.append((translated_header, translated_content))
                translated_count += 1
            else:
                # 使用現有的翻譯
                logger.info(f"[{idx}/{total_blocks}] 複用現有翻譯: {title}")
                if title in target_blocks:
                    existing_header, existing_content = target_blocks[title]
                    translated_blocks.append((existing_header, existing_content))
                else:
                    # 不應該到這裡，但以防萬一
                    logger.warning(f"未找到現有翻譯，將翻譯: {title}")
                    translated_header = translate_block(header, text_provider) if header else ""
                    translated_content = translate_block(content, text_provider) if content else ""
                    translated_blocks.append((translated_header, translated_content))
                    translated_count += 1

        # 組裝最終內容
        final_content = ""
        for header, content in translated_blocks:
            if header:
                final_content += header + "\n\n"
            if content:
                final_content += content + "\n\n"

        # 後處理：確保中英文連結互換
        final_content = final_content.replace(
            '**中文 | [English](README_EN.md)**',
            '**[中文](README.md) | English**'
        ).replace(
            '**Chinese | [English](README_EN.md)**',
            '**[中文](README.md) | English**'
        )

        # 寫入目標檔案
        logger.info(f"寫入目標檔案: {target_file}")
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(final_content.strip() + "\n")

        logger.info(f"✅ 翻譯完成！共處理 {total_blocks} 個塊，翻譯了 {translated_count} 個塊")

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

    # 檢查是否強制全文翻譯
    force_full = "--full" in sys.argv

    logger.info("README 增量翻譯工具")
    logger.info(f"專案根目錄: {project_root}")
    logger.info(f"原始檔: {source_file}")
    logger.info(f"目標檔案: {target_file}")
    if force_full:
        logger.info("模式: 強制全文翻譯")
    else:
        logger.info("模式: 增量翻譯（僅翻譯修改的部分）")

    # 檢查原始檔是否存在
    if not source_file.exists():
        logger.error(f"原始檔不存在: {source_file}")
        sys.exit(1)

    # 執行翻譯
    incremental_translate(str(source_file), str(target_file), force_full=force_full)


if __name__ == "__main__":
    main()
