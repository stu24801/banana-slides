"""
Inpainting 服務
提供基於多種 provider 的影象區域消除和背景重新生成功能
支援的 provider:
- volcengine: 火山引擎 Inpainting
- gemini: Google Gemini 2.5 Flash Image Preview
"""
import logging
from typing import List, Tuple, Union, Optional
from PIL import Image

from services.ai_providers.image.volcengine_inpainting_provider import VolcengineInpaintingProvider
from services.ai_providers.image.gemini_inpainting_provider import GeminiInpaintingProvider
from utils.mask_utils import (
    create_mask_from_bboxes,
    create_inverse_mask_from_bboxes,
    create_mask_from_image_and_bboxes,
    merge_overlapping_bboxes,
    visualize_mask_overlay
)
from config import get_config

logger = logging.getLogger(__name__)


class InpaintingService:
    """
    Inpainting 服務類
    
    主要功能：
    1. 從 bbox 生成掩碼影象
    2. 呼叫 inpainting provider 消除指定區域
    3. 提供便捷的背景重生成介面
    
    支援的 provider:
    - volcengine: 火山引擎 Inpainting
    - gemini: Google Gemini 2.5 Flash Image Preview
    """
    
    def __init__(self, provider=None, provider_type: str = "volcengine"):
        """
        初始化 Inpainting 服務
        
        Args:
            provider: Inpainting 提供者例項，如果為 None 則從配置建立
            provider_type: Provider 型別 ('volcengine' 或 'gemini')
        """
        if provider is None:
            config = get_config()
            
            if provider_type == "gemini":
                # 使用 Gemini Inpainting Provider
                api_key = config.GOOGLE_API_KEY
                api_base = config.GOOGLE_API_BASE
                timeout = config.GENAI_TIMEOUT
                
                if not api_key:
                    raise ValueError("Google API Key 未配置")
                
                self.provider = GeminiInpaintingProvider(
                    api_key=api_key,
                    api_base=api_base,
                    timeout=timeout
                )
                self.provider_type = "gemini"
            else:
                # 使用火山引擎 Inpainting Provider（預設）
                access_key = config.VOLCENGINE_ACCESS_KEY
                secret_key = config.VOLCENGINE_SECRET_KEY
                timeout = config.VOLCENGINE_INPAINTING_TIMEOUT
                
                if not access_key or not secret_key:
                    raise ValueError("火山引擎 Access Key 和 Secret Key 未配置")
                
                self.provider = VolcengineInpaintingProvider(
                    access_key=access_key,
                    secret_key=secret_key,
                    timeout=timeout
                )
                self.provider_type = "volcengine"
        else:
            self.provider = provider
            self.provider_type = provider_type
        
        self.config = get_config()
    
    def remove_regions_by_bboxes(
        self,
        image: Image.Image,
        bboxes: List[Union[Tuple[int, int, int, int], dict]],
        expand_pixels: int = 5,
        merge_bboxes: bool = False,
        merge_threshold: int = 10,
        save_mask_path: Optional[str] = None,
        full_page_image: Optional[Image.Image] = None,
        crop_box: Optional[tuple] = None
    ) -> Optional[Image.Image]:
        """
        根據邊界框列表消除影象中的指定區域
        
        Args:
            image: 原始影象（PIL Image）
            bboxes: 邊界框列表，支援以下格式：
                    - (x1, y1, x2, y2) 元組
                    - {"x1": x1, "y1": y1, "x2": x2, "y2": y2} 字典
                    - {"x": x, "y": y, "width": w, "height": h} 字典
            expand_pixels: 擴充套件畫素數，讓掩碼區域略微擴大（預設5畫素）
            merge_bboxes: 是否合併重疊或相鄰的邊界框（預設False）
            merge_threshold: 合併閾值，邊界框距離小於此值時會合並（預設10畫素）
            save_mask_path: Mask 儲存路徑（可選）
            full_page_image: 完整的 PPT 頁面影象（僅用於 Gemini provider）
            crop_box: 裁剪框 (x0, y0, x1, y1)，從完整頁面結果中裁剪的區域（僅用於 Gemini provider）
            
        Returns:
            處理後的影象，失敗返回 None
        """
        try:
            logger.info(f"開始處理影象消除，原始 bbox 數量: {len(bboxes)}")
            
            # 合併重疊的邊界框（如果啟用）
            if merge_bboxes and len(bboxes) > 1:
                # 先標準化所有 bbox 格式
                normalized_bboxes = []
                for bbox in bboxes:
                    if isinstance(bbox, dict):
                        if 'x1' in bbox:
                            normalized_bboxes.append((bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']))
                        elif 'x' in bbox:
                            normalized_bboxes.append((bbox['x'], bbox['y'], 
                                                    bbox['x'] + bbox['width'], 
                                                    bbox['y'] + bbox['height']))
                    else:
                        normalized_bboxes.append(tuple(bbox))
                
                bboxes = merge_overlapping_bboxes(normalized_bboxes, merge_threshold)
                logger.info(f"合併後 bbox 數量: {len(bboxes)}")
            
            # 生成掩碼影象
            mask = create_mask_from_image_and_bboxes(
                image,
                bboxes,
                expand_pixels=expand_pixels
            )
            
            logger.info(f"掩碼影象已生成，尺寸: {mask.size}")
            
            # 儲存mask影象（如果指定了路徑）
            if save_mask_path:
                try:
                    mask.save(save_mask_path)
                    logger.info(f"📷 Mask影象已儲存: {save_mask_path}")
                except Exception as e:
                    logger.warning(f"⚠️ 儲存mask影象失敗: {e}")
            
            # 呼叫 inpainting 服務（已內建重試邏輯）
            result = self.provider.inpaint_image(
                original_image=image,
                mask_image=mask,
                full_page_image=full_page_image,
                crop_box=crop_box
            )
            
            if result is not None:
                logger.info(f"影象消除成功，結果尺寸: {result.size}")
            else:
                logger.error("影象消除失敗")
            
            return result
            
        except Exception as e:
            logger.error(f"消除區域失敗: {str(e)}", exc_info=True)
            return None
    
    def regenerate_background(
        self,
        image: Image.Image,
        foreground_bboxes: List[Union[Tuple[int, int, int, int], dict]],
        expand_pixels: int = 5
    ) -> Optional[Image.Image]:
        """
        重新生成背景（保留前景物件，消除其他區域）
        
        這個方法使用反向掩碼：保留 bbox 區域，消除其他所有區域
        
        Args:
            image: 原始影象
            foreground_bboxes: 前景物件的邊界框列表（這些區域會被保留）
            expand_pixels: 收縮畫素數（負數表示擴充套件），讓前景邊緣更自然
            
        Returns:
            處理後的影象，失敗返回 None
        """
        try:
            logger.info(f"開始重新生成背景，前景物件數量: {len(foreground_bboxes)}")
            
            # 生成反向掩碼（保留前景，消除背景）
            mask = create_inverse_mask_from_bboxes(
                image.size,
                foreground_bboxes,
                expand_pixels=expand_pixels
            )
            
            logger.info(f"反向掩碼已生成，尺寸: {mask.size}")
            
            # 呼叫 inpainting 服務（已內建重試邏輯）
            result = self.provider.inpaint_image(
                original_image=image,
                mask_image=mask
            )
            
            if result is not None:
                logger.info(f"背景重生成成功，結果尺寸: {result.size}")
            else:
                logger.error("背景重生成失敗")
            
            return result
            
        except Exception as e:
            logger.error(f"重新生成背景失敗: {str(e)}", exc_info=True)
            return None
    
    def create_mask_preview(
        self,
        image: Image.Image,
        bboxes: List[Union[Tuple[int, int, int, int], dict]],
        expand_pixels: int = 0,
        alpha: float = 0.5
    ) -> Image.Image:
        """
        建立掩碼預覽圖（用於除錯和視覺化）
        
        Args:
            image: 原始影象
            bboxes: 邊界框列表
            expand_pixels: 擴充套件畫素數
            alpha: 掩碼透明度
            
        Returns:
            疊加了黑色半透明掩碼的預覽圖
        """
        mask = create_mask_from_image_and_bboxes(image, bboxes, expand_pixels)
        return visualize_mask_overlay(image, mask, alpha)
    
    @staticmethod
    def create_mask_image(
        image_size: Tuple[int, int],
        bboxes: List[Union[Tuple[int, int, int, int], dict]],
        expand_pixels: int = 0
    ) -> Image.Image:
        """
        靜態方法：建立掩碼影象（不需要例項化服務）
        
        Args:
            image_size: 影象尺寸 (width, height)
            bboxes: 邊界框列表
            expand_pixels: 擴充套件畫素數
            
        Returns:
            掩碼影象
        """
        return create_mask_from_bboxes(image_size, bboxes, expand_pixels)


# 便捷函式

_inpainting_service_instances = {}


def get_inpainting_service(provider_type: str = None) -> InpaintingService:
    """
    獲取 InpaintingService 例項（單例模式，每種 provider 一個例項）
    
    Args:
        provider_type: Provider 型別 ('volcengine', 'gemini')，
                      如果為 None 則從配置讀取
    
    Returns:
        InpaintingService 例項
    """
    global _inpainting_service_instances
    
    # 從配置讀取預設 provider
    if provider_type is None:
        config = get_config()
        provider_type = getattr(config, 'INPAINTING_PROVIDER', 'gemini')  # 預設使用 gemini
    
    # 獲取或建立對應的例項
    if provider_type not in _inpainting_service_instances:
        _inpainting_service_instances[provider_type] = InpaintingService(
            provider_type=provider_type
        )
    
    return _inpainting_service_instances[provider_type]


def remove_regions(
    image: Image.Image,
    bboxes: List[Union[Tuple[int, int, int, int], dict]],
    **kwargs
) -> Optional[Image.Image]:
    """
    便捷函式：消除影象中的指定區域
    
    Args:
        image: 原始影象
        bboxes: 邊界框列表
        **kwargs: 其他引數傳遞給 InpaintingService.remove_regions_by_bboxes
        
    Returns:
        處理後的影象
    """
    service = get_inpainting_service()
    return service.remove_regions_by_bboxes(image, bboxes, **kwargs)


def regenerate_background(
    image: Image.Image,
    foreground_bboxes: List[Union[Tuple[int, int, int, int], dict]],
    **kwargs
) -> Optional[Image.Image]:
    """
    便捷函式：重新生成背景
    
    Args:
        image: 原始影象
        foreground_bboxes: 前景物件的邊界框列表
        **kwargs: 其他引數傳遞給 InpaintingService.regenerate_background
        
    Returns:
        處理後的影象
    """
    service = get_inpainting_service()
    return service.regenerate_background(image, foreground_bboxes, **kwargs)

