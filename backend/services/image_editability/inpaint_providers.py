"""
Inpaint提供者 - 抽象不同的inpaint實現

提供多種重繪方法：
1. DefaultInpaintProvider - 基於mask的精確區域重繪（使用Volcengine Inpainting服務）
2. GenerativeEditInpaintProvider - 基於生成式大模型的整圖編輯重繪（如Gemini圖片編輯）
3. BaiduInpaintProvider - 基於百度影象修復API的區域重繪
4. HybridInpaintProvider - 混合方法：先百度修復去除文字，再生成式提升畫質

以及登錄檔：
- InpaintProviderRegistry - 元素型別到重繪方法的對映登錄檔
"""
import logging
import tempfile
from abc import ABC, abstractmethod
from typing import List, Optional, Dict
from PIL import Image

from utils.mask_utils import create_mask_from_bboxes

logger = logging.getLogger(__name__)


class InpaintProvider(ABC):
    """
    Inpaint提供者抽象介面
    
    用於抽象不同的inpaint方法，支援接入多種實現：
    - 基於InpaintingService的實現（當前預設）
    - Gemini API實現
    - SD/SDXL等其他模型實現
    - 第三方API實現
    """
    
    @abstractmethod
    def inpaint_regions(
        self,
        image: Image.Image,
        bboxes: List[tuple],
        types: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Image.Image]:
        """
        對影象中指定區域進行inpaint處理
        
        Args:
            image: 原始PIL影象物件
            bboxes: 邊界框列表，每個bbox格式為 (x0, y0, x1, y1)
            types: 可選的元素型別列表，與bboxes一一對應（如 'text', 'image', 'table'等）
            **kwargs: 其他由具體實現自定義的引數
        
        Returns:
            處理後的PIL影象物件，失敗返回None
        """
        pass


class DefaultInpaintProvider(InpaintProvider):
    """
    基於InpaintingService的預設Inpaint提供者
    
    這是當前系統使用的實現，呼叫已有的InpaintingService
    """
    
    def __init__(self, inpainting_service):
        """
        初始化預設Inpaint提供者
        
        Args:
            inpainting_service: InpaintingService例項
        """
        self.inpainting_service = inpainting_service
    
    def inpaint_regions(
        self,
        image: Image.Image,
        bboxes: List[tuple],
        types: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Image.Image]:
        """
        使用InpaintingService處理inpaint
        
        支援的kwargs引數：
        - expand_pixels: int, 擴充套件畫素數，預設10
        - merge_bboxes: bool, 是否合併bbox，預設False
        - merge_threshold: int, 合併閾值，預設20
        - save_mask_path: str, mask儲存路徑，可選
        - full_page_image: Image.Image, 完整頁面影象（用於Gemini），可選
        - crop_box: tuple, 裁剪框 (x0, y0, x1, y1)，可選
        """
        expand_pixels = kwargs.get('expand_pixels', 10)
        merge_bboxes = kwargs.get('merge_bboxes', False)
        merge_threshold = kwargs.get('merge_threshold', 20)
        save_mask_path = kwargs.get('save_mask_path')
        full_page_image = kwargs.get('full_page_image')
        crop_box = kwargs.get('crop_box')
        
        try:
            result_img = self.inpainting_service.remove_regions_by_bboxes(
                image=image,
                bboxes=bboxes,
                expand_pixels=expand_pixels,
                merge_bboxes=merge_bboxes,
                merge_threshold=merge_threshold,
                save_mask_path=save_mask_path,
                full_page_image=full_page_image,
                crop_box=crop_box
            )
            return result_img
        except Exception as e:
            logger.error(f"DefaultInpaintProvider處理失敗: {e}", exc_info=True)
            return None


class GenerativeEditInpaintProvider(InpaintProvider):
    """
    基於生成式大模型圖片編輯的Inpaint提供者
    
    使用生成式大模型（如Gemini的圖片編輯功能）透過自然語言指令移除圖片中的文字、圖示等元素。
    
    與DefaultInpaintProvider的區別：
    - DefaultInpaintProvider: 基於mask的精確區域重繪（需要準確的bbox）
    - GenerativeEditInpaintProvider: 整圖生成式編輯（透過prompt描述要移除的內容）
    
    優點：不需要精確的bbox，大模型自動理解並移除相關元素
    缺點：可能改變背景細節，生成速度較慢，消耗更多token
    
    適用場景：
    - bbox不夠精確時
    - 需要移除複雜或分散的元素時
    - 作為mask-based方法的備選方案
    """
    
    def __init__(self, ai_service, aspect_ratio: str = "16:9", resolution: str = "2K"):
        """
        初始化生成式編輯Inpaint提供者
        
        Args:
            ai_service: AIService例項（需要支援edit_image方法）
            aspect_ratio: 目標寬高比
            resolution: 目標解析度
        """
        self.ai_service = ai_service
        self.aspect_ratio = aspect_ratio
        self.resolution = resolution
    
    def inpaint_regions(
        self,
        image: Image.Image,
        bboxes: List[tuple],
        types: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Image.Image]:
        """
        使用生成式大模型編輯生成乾淨背景
        
        注意：此方法忽略bboxes引數，透過大模型自動識別並移除所有文字和圖示
        
        支援的kwargs引數：
        - aspect_ratio: str, 寬高比，預設使用初始化時的值
        - resolution: str, 解析度，預設使用初始化時的值
        """
        aspect_ratio = kwargs.get('aspect_ratio', self.aspect_ratio)
        resolution = kwargs.get('resolution', self.resolution)
        
        try:
            from services.prompts import get_clean_background_prompt
            
            # 獲取清理背景的prompt
            edit_instruction = get_clean_background_prompt()
            
            # 儲存臨時圖片檔案（AI服務需要檔案路徑）
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                image.save(tmp_path)
            
            logger.info("GenerativeEditInpaintProvider: 開始生成式編輯重繪...")
            
            # 呼叫AI服務編輯圖片
            clean_bg_image = self.ai_service.edit_image(
                prompt=edit_instruction,
                current_image_path=tmp_path,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                original_description=None,
                additional_ref_images=None
            )
            
            if not clean_bg_image:
                logger.error("GenerativeEditInpaintProvider: 生成式編輯返回空結果")
                return None
            
            # 轉換為PIL Image
            if not isinstance(clean_bg_image, Image.Image):
                # Google GenAI返回自己的Image型別，需要提取_pil_image
                if hasattr(clean_bg_image, '_pil_image'):
                    clean_bg_image = clean_bg_image._pil_image
                else:
                    logger.error(f"GenerativeEditInpaintProvider: 未知的圖片型別: {type(clean_bg_image)}")
                    return None
            
            logger.info("GenerativeEditInpaintProvider: 重繪完成")
            return clean_bg_image
        
        except Exception as e:
            logger.error(f"GenerativeEditInpaintProvider處理失敗: {e}", exc_info=True)
            return None


class BaiduInpaintProvider(InpaintProvider):
    """
    基於百度影象修復API的Inpaint提供者
    
    使用百度AI在指定矩形區域去除遮擋物並用背景內容填充。
    
    特點：
    - 基於bbox的精確區域修復
    - 快速響應，使用背景內容智慧填充
    - 適合去除文字、水印等規則區域
    
    注意：修復質量可能不如生成式模型，但速度快且穩定
    """
    
    def __init__(self, baidu_inpainting_provider):
        """
        初始化百度影象修復提供者
        
        Args:
            baidu_inpainting_provider: BaiduInpaintingProvider例項（來自ai_providers.image）
        """
        self._provider = baidu_inpainting_provider
    
    def inpaint_regions(
        self,
        image: Image.Image,
        bboxes: List[tuple],
        types: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Image.Image]:
        """
        使用百度影象修復API處理指定區域
        
        支援的kwargs引數：
        - expand_pixels: int, 擴充套件畫素數，預設2
        """
        expand_pixels = kwargs.get('expand_pixels', 2)
        
        try:
            logger.info(f"BaiduInpaintProvider: 開始修復 {len(bboxes)} 個區域...")
            
            result_image = self._provider.inpaint_bboxes(
                image=image,
                bboxes=bboxes,
                expand_pixels=expand_pixels
            )
            
            if result_image:
                logger.info("BaiduInpaintProvider: 修復完成")
            else:
                logger.warning("BaiduInpaintProvider: 修復返回空結果")
                return None
            
            # 合併原圖和修復後的圖片，只取bboxes區域的修復結果（不擴充套件，避免影響bbox外的區域）
            mask = create_mask_from_bboxes(image.size, bboxes, expand_pixels=0)
            return Image.composite(result_image, image, mask.convert('L'))
        
        except Exception as e:
            logger.error(f"BaiduInpaintProvider處理失敗: {e}", exc_info=True)
            return None


class HybridInpaintProvider(InpaintProvider):
    """
    混合Inpaint提供者 - 百度修復 + 生成式畫質提升
    
    工作流程：
    1. 先使用百度影象修復API去除指定區域的內容（如文字、水印）
    2. 再使用生成式大模型（如Gemini）提升整體畫質，保持內容不變
    
    優點：
    - 百度修復快速精確地去除文字，不會遺漏
    - 生成式模型提升畫質，使修復痕跡更自然
    
    適用場景：
    - 需要精確去除文字且保證高畫質的場景
    - 單獨使用生成式模型容易遺漏文字的情況
    """
    
    def __init__(
        self,
        baidu_provider: BaiduInpaintProvider,
        generative_provider: 'GenerativeEditInpaintProvider',
        enhance_quality: bool = True
    ):
        """
        初始化混合Inpaint提供者
        
        Args:
            baidu_provider: 百度影象修復提供者
            generative_provider: 生成式編輯提供者（用於畫質提升）
            enhance_quality: 是否在百度修復後使用生成式模型提升畫質，預設True
        """
        self._baidu_provider = baidu_provider
        self._generative_provider = generative_provider
        self._enhance_quality = enhance_quality
    
    def inpaint_regions(
        self,
        image: Image.Image,
        bboxes: List[tuple],
        types: Optional[List[str]] = None,
        **kwargs
    ) -> Optional[Image.Image]:
        """
        混合處理：先百度修復，再生成式畫質提升
        
        支援的kwargs引數：
        - expand_pixels: int, 百度修復的擴充套件畫素數，預設2
        - enhance_quality: bool, 是否提升畫質，預設使用初始化時的值
        - aspect_ratio: str, 畫質提升的寬高比
        - resolution: str, 畫質提升的解析度
        """
        expand_pixels = kwargs.get('expand_pixels', 2)
        enhance_quality = kwargs.get('enhance_quality', self._enhance_quality)
        
        try:
            # Step 1: 百度影象修復 - 精確去除文字
            logger.info(f"HybridInpaintProvider Step 1: 百度修復 {len(bboxes)} 個區域...")
            
            repaired_image = self._baidu_provider.inpaint_regions(
                image=image,
                bboxes=bboxes,
                types=types,
                expand_pixels=expand_pixels
            )
            
            if repaired_image is None:
                logger.error("HybridInpaintProvider: 百度修復失敗")
                return None
            
            logger.info("HybridInpaintProvider: 百度修復完成")
            
            # Step 2: 生成式畫質提升（可選）
            if enhance_quality and self._generative_provider:
                logger.info("HybridInpaintProvider Step 2: 生成式畫質提升...")
                
                # 使用專門的畫質提升prompt，傳入被修復的區域資訊
                enhanced_image = self._enhance_image_quality(
                    repaired_image,
                    inpainted_bboxes=bboxes,  # 傳入被修復的區域
                    aspect_ratio=kwargs.get('aspect_ratio'),
                    resolution=kwargs.get('resolution')
                )
                
                if enhanced_image:
                    logger.info("HybridInpaintProvider: 畫質提升完成")
                    return enhanced_image
                else:
                    logger.warning("HybridInpaintProvider: 畫質提升失敗，返回百度修復結果")
                    return repaired_image
            else:
                logger.info("HybridInpaintProvider: 跳過畫質提升")
                return repaired_image
        
        except Exception as e:
            logger.error(f"HybridInpaintProvider處理失敗: {e}", exc_info=True)
            return None
    
    def _enhance_image_quality(
        self,
        image: Image.Image,
        inpainted_bboxes: Optional[List[tuple]] = None,
        aspect_ratio: Optional[str] = None,
        resolution: Optional[str] = None
    ) -> Optional[Image.Image]:
        """
        使用生成式模型提升影象畫質
        
        Args:
            image: 需要提升畫質的影象
            inpainted_bboxes: 被修復區域的bbox列表，格式為 [(x0, y0, x1, y1), ...]
            aspect_ratio: 寬高比（可選）
            resolution: 解析度（可選）
        
        Returns:
            提升畫質後的影象
        """
        try:
            # 儲存臨時圖片
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_path = tmp_file.name
                image.save(tmp_path)
            
            # 將bboxes轉換為百分比形式（相對於圖片寬高）
            regions = None
            if inpainted_bboxes:
                # 先合併上下間距很小的bbox（減少傳遞給生成式模型的區域數量）
                from utils.mask_utils import merge_vertical_nearby_bboxes
                original_count = len(inpainted_bboxes)
                merged_bboxes = merge_vertical_nearby_bboxes(inpainted_bboxes)
                if len(merged_bboxes) < original_count:
                    logger.info(f"合併相鄰文字行後：{original_count} -> {len(merged_bboxes)} 個區域")
                
                img_width, img_height = image.size
                regions = []
                for bbox in merged_bboxes:
                    x0, y0, x1, y1 = bbox
                    # 轉換為百分比（0-100）
                    regions.append({
                        'left': round(x0 / img_width * 100, 1),
                        'top': round(y0 / img_height * 100, 1),
                        'right': round(x1 / img_width * 100, 1),
                        'bottom': round(y1 / img_height * 100, 1),
                        'width_percent': round((x1 - x0) / img_width * 100, 1),
                        'height_percent': round((y1 - y0) / img_height * 100, 1)
                    })
                logger.info(f"傳遞 {len(regions)} 個被修復區域給生成式模型（百分比座標）")
            
            # 獲取畫質提升的prompt（包含被修復區域資訊）
            from services.prompts import get_quality_enhancement_prompt
            enhance_prompt = get_quality_enhancement_prompt(inpainted_regions=regions)
            
            # 使用AI服務的aspect_ratio和resolution（如果提供）
            ar = aspect_ratio or self._generative_provider.aspect_ratio
            res = resolution or self._generative_provider.resolution
            
            # 呼叫AI服務
            enhanced_image = self._generative_provider.ai_service.edit_image(
                prompt=enhance_prompt,
                current_image_path=tmp_path,
                aspect_ratio=ar,
                resolution=res,
                original_description=None,
                additional_ref_images=None
            )
            
            if not enhanced_image:
                return None
            
            # 轉換為PIL Image
            if not isinstance(enhanced_image, Image.Image):
                if hasattr(enhanced_image, '_pil_image'):
                    enhanced_image = enhanced_image._pil_image
                else:
                    logger.error(f"未知的圖片型別: {type(enhanced_image)}")
                    return None
            
            return enhanced_image
        
        except Exception as e:
            logger.error(f"畫質提升失敗: {e}", exc_info=True)
            return None


class InpaintProviderRegistry:
    """
    元素型別到重繪方法的對映登錄檔
    
    根據元素型別選擇合適的重繪方法：
    - 文字元素 → DefaultInpaintProvider（mask-based精確移除）
    - 表格元素 → DefaultInpaintProvider（保持表格框架）
    - 圖片/圖表元素 → GenerativeEditInpaintProvider（整圖重繪）
    - 其他型別 → 預設提供者
    
    使用方式：
        >>> registry = InpaintProviderRegistry()
        >>> registry.register('text', mask_provider)
        >>> registry.register('image', generative_provider)
        >>> registry.register_default(mask_provider)
        >>> 
        >>> provider = registry.get_provider('text')  # 返回 mask_provider
        >>> provider = registry.get_provider('chart')  # 返回 generative_provider
    """
    
    # 預定義的元素型別分組
    TEXT_TYPES = {'text', 'title', 'paragraph', 'header', 'footer', 'list'}
    TABLE_TYPES = {'table', 'table_cell'}
    IMAGE_TYPES = {'image', 'figure', 'chart', 'diagram'}
    
    def __init__(self):
        """初始化登錄檔"""
        self._type_mapping: Dict[str, InpaintProvider] = {}
        self._default_provider: Optional[InpaintProvider] = None
    
    def register(self, element_type: str, provider: InpaintProvider) -> 'InpaintProviderRegistry':
        """
        註冊元素型別到重繪方法的對映
        
        Args:
            element_type: 元素型別（如 'text', 'image' 等）
            provider: 對應的重繪提供者例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._type_mapping[element_type] = provider
        logger.debug(f"註冊重繪提供者: {element_type} -> {provider.__class__.__name__}")
        return self
    
    def register_types(self, element_types: List[str], provider: InpaintProvider) -> 'InpaintProviderRegistry':
        """
        批次註冊多個元素型別到同一個重繪方法
        
        Args:
            element_types: 元素型別列表
            provider: 對應的重繪提供者例項
        
        Returns:
            self，支援鏈式呼叫
        """
        for t in element_types:
            self.register(t, provider)
        return self
    
    def register_default(self, provider: InpaintProvider) -> 'InpaintProviderRegistry':
        """
        註冊預設重繪方法（當沒有特定型別對映時使用）
        
        Args:
            provider: 預設重繪提供者例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._default_provider = provider
        logger.debug(f"註冊預設重繪提供者: {provider.__class__.__name__}")
        return self
    
    def get_provider(self, element_type: Optional[str]) -> Optional[InpaintProvider]:
        """
        根據元素型別獲取對應的重繪方法
        
        Args:
            element_type: 元素型別，None表示使用預設提供者
        
        Returns:
            對應的重繪提供者，如果沒有註冊則返回預設提供者
        """
        if element_type is None:
            return self._default_provider
        
        # 先查詢精確匹配
        if element_type in self._type_mapping:
            return self._type_mapping[element_type]
        
        # 返回預設提供者
        return self._default_provider
    
    def get_all_providers(self) -> List[InpaintProvider]:
        """
        獲取所有已註冊的重繪提供者（去重）
        
        Returns:
            重繪提供者列表
        """
        providers = list(set(self._type_mapping.values()))
        if self._default_provider and self._default_provider not in providers:
            providers.append(self._default_provider)
        return providers
    
    @classmethod
    def create_default(
        cls,
        mask_provider: Optional[InpaintProvider] = None,
        generative_provider: Optional[InpaintProvider] = None
    ) -> 'InpaintProviderRegistry':
        """
        建立預設配置的登錄檔
        
        預設配置：
        - 文字型別 → mask-based（精確移除文字區域）
        - 表格型別 → mask-based（保持表格框架，只移除單元格內容）
        - 圖片/圖表型別 → generative（整圖重繪，處理複雜圖形）
        - 其他型別 → mask-based（預設）
        
        Args:
            mask_provider: 基於mask的重繪提供者（DefaultInpaintProvider）
            generative_provider: 生成式重繪提供者（GenerativeEditInpaintProvider）
        
        Returns:
            配置好的登錄檔例項
        """
        registry = cls()
        
        # 如果沒有提供任何provider，返回空登錄檔
        if not mask_provider and not generative_provider:
            logger.warning("建立InpaintProviderRegistry時未提供任何provider")
            return registry
        
        # 設定預設提供者（優先使用mask_provider）
        default_provider = mask_provider or generative_provider
        registry.register_default(default_provider)
        
        # 文字型別使用mask-based
        if mask_provider:
            registry.register_types(list(cls.TEXT_TYPES), mask_provider)
            registry.register_types(list(cls.TABLE_TYPES), mask_provider)
        
        # 圖片型別使用generative（如果可用），否則使用mask-based
        image_provider = generative_provider or mask_provider
        if image_provider:
            registry.register_types(list(cls.IMAGE_TYPES), image_provider)
        
        logger.info(f"建立預設InpaintProviderRegistry: "
                   f"文字/表格->{mask_provider.__class__.__name__ if mask_provider else 'None'}, "
                   f"圖片->{image_provider.__class__.__name__ if image_provider else 'None'}")
        
        return registry

