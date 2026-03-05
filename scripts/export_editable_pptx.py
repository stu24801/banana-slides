#!/usr/bin/env python3
"""
可編輯 PPTX 匯出指令碼

此指令碼用於從指定的圖片生成可編輯的 PPTX 檔案。
支援單張圖片或多張圖片批次處理。

使用方法:
    # 處理單張圖片
    python scripts/export_editable_pptx.py path/to/image.png
    
    # 處理多張圖片
    python scripts/export_editable_pptx.py img1.png img2.png img3.png
    
    # 處理目錄中的所有圖片
    python scripts/export_editable_pptx.py path/to/images/
    
    # 指定輸出檔案
    python scripts/export_editable_pptx.py image.png -o output.pptx
    
    # 使用不同的提取方法
    python scripts/export_editable_pptx.py image.png --extractor mineru
    python scripts/export_editable_pptx.py image.png --extractor hybrid
    
    # 使用不同的背景修復方法
    python scripts/export_editable_pptx.py image.png --inpaint baidu
    python scripts/export_editable_pptx.py image.png --inpaint generative
    python scripts/export_editable_pptx.py image.png --inpaint hybrid

環境要求:
    需要配置 .env 檔案，包含以下變數：
    - MINERU_TOKEN: MinerU API token
    - BAIDU_API_KEY, BAIDU_SECRET_KEY: 百度 API 金鑰（用於 baidu/hybrid 方法）
    - GEMINI_API_KEY 或 OPENAI_API_KEY: 用於 generative/hybrid 方法

成本提示:
    - 'generative' 和 'hybrid' 背景修復方法會呼叫文生圖模型 API，產生額外費用
    - 'baidu' 方法使用百度影象修復 API，費用較低
    - 'mineru' 和 'hybrid' 提取方法都使用 MinerU API
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# 新增專案根目錄到 Python 路徑
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
BACKEND_DIR = PROJECT_ROOT / 'backend'
sys.path.insert(0, str(BACKEND_DIR))

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_flask_app():
    """初始化 Flask 應用上下文（用於載入配置）"""
    from dotenv import load_dotenv
    
    # 載入 .env 檔案
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"已載入環境變數: {env_path}")
    
    # 建立 Flask 應用
    from app import create_app
    app = create_app()
    return app


def collect_image_paths(paths: List[str]) -> List[str]:
    """收集所有要處理的圖片路徑"""
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    result = []
    
    for path_str in paths:
        path = Path(path_str)
        
        if path.is_file():
            if path.suffix.lower() in image_extensions:
                result.append(str(path.resolve()))
            else:
                logger.warning(f"跳過非圖片檔案: {path}")
        elif path.is_dir():
            for file in sorted(path.iterdir()):
                if file.suffix.lower() in image_extensions:
                    result.append(str(file.resolve()))
        else:
            logger.warning(f"路徑不存在: {path}")
    
    return result


def create_service_config(
    extractor_method: str = 'hybrid',
    inpaint_method: str = 'hybrid'
):
    """
    建立服務配置
    
    Args:
        extractor_method: 提取方法 ('mineru' 或 'hybrid')
        inpaint_method: 背景修復方法 ('generative', 'baidu', 'hybrid')
    """
    from services.image_editability import ServiceConfig
    
    # 根據方法選擇配置
    use_hybrid_extractor = (extractor_method == 'hybrid')
    use_hybrid_inpaint = (inpaint_method == 'hybrid')
    
    logger.info(f"配置: 提取方法={extractor_method}, 背景修復={inpaint_method}")
    
    config = ServiceConfig.from_defaults(
        use_hybrid_extractor=use_hybrid_extractor,
        use_hybrid_inpaint=use_hybrid_inpaint,
        max_depth=1  # 遞迴深度
    )
    
    # 如果指定了非 hybrid 的 inpaint 方法，需要手動配置
    if inpaint_method != 'hybrid':
        from services.image_editability import (
            InpaintProviderFactory,
            InpaintProviderRegistry
        )
        
        inpaint_registry = InpaintProviderRegistry()
        
        if inpaint_method == 'generative':
            provider = InpaintProviderFactory.create_generative_edit_provider()
            inpaint_registry.register_default(provider)
            logger.info("使用生成式修復方法（會呼叫文生圖模型 API）")
        elif inpaint_method == 'baidu':
            provider = InpaintProviderFactory.create_baidu_inpaint_provider()
            if provider:
                inpaint_registry.register_default(provider)
                logger.info("使用百度影象修復方法")
            else:
                logger.warning("百度修復不可用，回退到生成式方法")
                provider = InpaintProviderFactory.create_generative_edit_provider()
                inpaint_registry.register_default(provider)
        
        config.inpaint_registry = inpaint_registry
    
    return config


def export_editable_pptx(
    image_paths: List[str],
    output_file: str,
    extractor_method: str = 'hybrid',
    inpaint_method: str = 'hybrid',
    extract_text_styles: bool = True
):
    """
    匯出可編輯 PPTX
    
    Args:
        image_paths: 圖片路徑列表
        output_file: 輸出檔案路徑
        extractor_method: 提取方法
        inpaint_method: 背景修復方法
        extract_text_styles: 是否提取文字樣式（顏色、粗體等）
    """
    from services.image_editability import ImageEditabilityService
    from services.export_service import ExportService
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    logger.info(f"開始處理 {len(image_paths)} 張圖片...")
    
    # 建立配置和服務
    config = create_service_config(extractor_method, inpaint_method)
    service = ImageEditabilityService(config)
    
    # 並行分析所有圖片
    logger.info("步驟 1/3: 分析圖片結構...")
    editable_images = []
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(service.make_image_editable, path): idx
            for idx, path in enumerate(image_paths)
        }
        
        results = [None] * len(image_paths)
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
                logger.info(f"  完成: {image_paths[idx]}")
            except Exception as e:
                logger.error(f"  失敗: {image_paths[idx]} - {e}")
                raise
        
        editable_images = results
    
    # 建立文字屬性提取器（可選）
    text_attribute_extractor = None
    if extract_text_styles:
        logger.info("步驟 2/3: 提取文字樣式...")
        try:
            from services.image_editability import TextAttributeExtractorFactory
            text_attribute_extractor = TextAttributeExtractorFactory.create_caption_model_extractor()
            logger.info("  文字樣式提取器已建立（會呼叫視覺語言模型 API）")
        except Exception as e:
            logger.warning(f"  無法建立文字樣式提取器: {e}")
    else:
        logger.info("步驟 2/3: 跳過文字樣式提取")
    
    # 生成 PPTX
    logger.info("步驟 3/3: 生成可編輯 PPTX...")
    
    def progress_callback(step, message, percent):
        logger.info(f"  [{percent}%] {step}: {message}")
    
    # 如果output_file已經存在，給一個字尾防止衝突
    if os.path.exists(output_file):
        output_file = output_file.rsplit('.', 1)[0] + '_1.pptx'
        logger.warning(f"輸出檔案已存在，給一個字尾防止衝突: {output_file}")
    
    # 根據實際圖片尺寸動態設定幻燈片尺寸
    # 統一到最小尺寸，並檢查所有圖片是否為16:9比例
    if editable_images:
        # 16:9 比例的標準值
        ASPECT_RATIO_16_9 = 16 / 9  # ≈ 1.7778
        ASPECT_RATIO_TOLERANCE = 0.02  # 允許2%的誤差
        
        # 檢查所有圖片是否為16:9比例，並找到最小尺寸
        min_width = float('inf')
        min_height = float('inf')
        
        for idx, img in enumerate(editable_images):
            aspect_ratio = img.width / img.height
            ratio_diff = abs(aspect_ratio - ASPECT_RATIO_16_9) / ASPECT_RATIO_16_9
            
            if ratio_diff > ASPECT_RATIO_TOLERANCE:
                logger.error(f"圖片 {idx + 1} ({image_paths[idx]}) 不是16:9比例: "
                           f"{img.width}x{img.height} (比例 {aspect_ratio:.4f}, 期望 {ASPECT_RATIO_16_9:.4f})")
                raise ValueError(f"所有圖片必須是16:9比例，但第 {idx + 1} 張圖片 ({img.width}x{img.height}) 不符合要求")
            
            min_width = min(min_width, img.width)
            min_height = min(min_height, img.height)
            logger.info(f"圖片 {idx + 1}: {img.width}x{img.height} (比例 {aspect_ratio:.4f})")
        
        slide_width_pixels = int(min_width)
        slide_height_pixels = int(min_height)
        logger.info(f"統一使用最小尺寸作為幻燈片尺寸: {slide_width_pixels}x{slide_height_pixels}")
        
        # 如果圖片尺寸不一致，給出警告
        if any(img.width != slide_width_pixels or img.height != slide_height_pixels for img in editable_images):
            logger.warning(f"圖片尺寸不一致，已統一到最小尺寸 {slide_width_pixels}x{slide_height_pixels}")
    else:
        # 如果沒有圖片，使用預設尺寸
        slide_width_pixels = 1920
        slide_height_pixels = 1080
        logger.warning("沒有圖片，使用預設尺寸: 1920x1080")
    
    ExportService.create_editable_pptx_with_recursive_analysis(
        editable_images=editable_images,
        output_file=output_file,
        slide_width_pixels=slide_width_pixels,
        slide_height_pixels=slide_height_pixels,
        text_attribute_extractor=text_attribute_extractor,
        progress_callback=progress_callback
    )
    
    logger.info(f"✓ 匯出完成: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='從圖片生成可編輯的 PPTX 檔案',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s slide1.png slide2.png -o presentation.pptx
  %(prog)s ./slides/ --extractor hybrid --inpaint baidu
  %(prog)s image.png --no-text-styles

成本提示:
  - 'generative' 和 'hybrid' 背景修復方法會呼叫文生圖模型 API
  - '--no-text-styles' 可跳過文字樣式提取，減少 API 呼叫
        """
    )
    
    parser.add_argument(
        'images',
        nargs='+',
        help='圖片檔案或目錄路徑'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='output_editable.pptx',
        help='輸出 PPTX 檔案路徑（預設: output_editable.pptx）'
    )
    
    parser.add_argument(
        '--extractor',
        choices=['mineru', 'hybrid'],
        default='hybrid',
        help='元件提取方法（預設: hybrid）'
    )
    
    parser.add_argument(
        '--inpaint',
        choices=['generative', 'baidu', 'hybrid'],
        default='hybrid',
        help='背景修復方法（預設: hybrid）。generative/hybrid 會呼叫文生圖模型'
    )
    
    parser.add_argument(
        '--no-text-styles',
        action='store_true',
        help='跳過文字樣式提取（減少 API 呼叫）'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='顯示詳細日誌'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 收集圖片路徑
    image_paths = collect_image_paths(args.images)
    
    if not image_paths:
        logger.error("未找到任何圖片檔案")
        sys.exit(1)
    
    logger.info(f"找到 {len(image_paths)} 張圖片:")
    for path in image_paths:
        logger.info(f"  - {path}")
    
    # 初始化 Flask 應用
    app = setup_flask_app()
    
    with app.app_context():
        try:
            export_editable_pptx(
                image_paths=image_paths,
                output_file=args.output,
                extractor_method=args.extractor,
                inpaint_method=args.inpaint,
                extract_text_styles=not args.no_text_styles
            )
        except Exception as e:
            logger.error(f"匯出失敗: {e}", exc_info=True)
            sys.exit(1)


if __name__ == '__main__':
    main()

