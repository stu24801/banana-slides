"""
工廠類 - 負責建立和配置具體的提取器和Inpaint提供者
"""
import logging
from typing import List, Optional, Any
from pathlib import Path

from .extractors import ElementExtractor, MinerUElementExtractor, BaiduOCRElementExtractor, BaiduAccurateOCRElementExtractor, ExtractorRegistry
from .hybrid_extractor import HybridElementExtractor, create_hybrid_extractor
from .inpaint_providers import (
    InpaintProvider, 
    DefaultInpaintProvider, 
    GenerativeEditInpaintProvider, 
    BaiduInpaintProvider,
    HybridInpaintProvider,
    InpaintProviderRegistry
)
from .text_attribute_extractors import (
    TextAttributeExtractor,
    CaptionModelTextAttributeExtractor,
    TextAttributeExtractorRegistry,
    TextStyleResult
)

logger = logging.getLogger(__name__)


class ExtractorFactory:
    """元素提取器工廠"""
    
    @staticmethod
    def create_default_extractors(
        parser_service: Any,
        upload_folder: Path,
        baidu_table_ocr_provider: Optional[Any] = None
    ) -> List[ElementExtractor]:
        """
        建立預設的元素提取器列表
        
        Args:
            parser_service: MinerU解析服務例項
            upload_folder: 上傳資料夾路徑
            baidu_table_ocr_provider: 百度表格OCR Provider例項（可選）
        
        Returns:
            提取器列表（按優先順序排序）
        
        Note:
            推薦使用 create_extractor_registry() 方法，它提供更清晰的型別到提取器對映
        """
        extractors: List[ElementExtractor] = []
        
        # 1. 百度OCR提取器（用於表格）
        if baidu_table_ocr_provider is None:
            try:
                from services.ai_providers.ocr import create_baidu_table_ocr_provider
                baidu_provider = create_baidu_table_ocr_provider()
                if baidu_provider:
                    extractors.append(BaiduOCRElementExtractor(baidu_provider))
                    logger.info("✅ 百度表格OCR提取器已啟用")
            except Exception as e:
                logger.warning(f"無法初始化百度表格OCR: {e}")
        else:
            extractors.append(BaiduOCRElementExtractor(baidu_table_ocr_provider))
            logger.info("✅ 百度表格OCR提取器已啟用")
        
        # 2. MinerU提取器（預設通用提取器）
        mineru_extractor = MinerUElementExtractor(parser_service, upload_folder)
        extractors.append(mineru_extractor)
        logger.info("✅ MinerU提取器已啟用")
        
        return extractors
    
    @staticmethod
    def create_extractor_registry(
        parser_service: Any,
        upload_folder: Path,
        baidu_table_ocr_provider: Optional[Any] = None
    ) -> ExtractorRegistry:
        """
        建立元素型別到提取器的登錄檔
        
        預設配置：
        - 表格型別（table, table_cell）→ 百度OCR（如果可用），否則MinerU
        - 圖片型別（image, figure, chart）→ MinerU
        - 其他型別 → MinerU（預設）
        
        Args:
            parser_service: MinerU解析服務例項
            upload_folder: 上傳資料夾路徑
            baidu_table_ocr_provider: 百度表格OCR Provider例項（可選）
        
        Returns:
            配置好的ExtractorRegistry例項
        """
        # 建立MinerU提取器
        mineru_extractor = MinerUElementExtractor(parser_service, upload_folder)
        logger.info("✅ MinerU提取器已建立")
        
        # 嘗試建立百度OCR提取器
        baidu_ocr_extractor = None
        if baidu_table_ocr_provider is None:
            try:
                from services.ai_providers.ocr import create_baidu_table_ocr_provider
                baidu_provider = create_baidu_table_ocr_provider()
                if baidu_provider:
                    baidu_ocr_extractor = BaiduOCRElementExtractor(baidu_provider)
                    logger.info("✅ 百度表格OCR提取器已建立")
            except Exception as e:
                logger.warning(f"無法初始化百度表格OCR: {e}")
        else:
            baidu_ocr_extractor = BaiduOCRElementExtractor(baidu_table_ocr_provider)
            logger.info("✅ 百度表格OCR提取器已建立")
        
        # 嘗試建立百度高精度OCR提取器
        baidu_accurate_ocr_extractor = None
        try:
            from services.ai_providers.ocr import create_baidu_accurate_ocr_provider
            baidu_accurate_provider = create_baidu_accurate_ocr_provider()
            if baidu_accurate_provider:
                baidu_accurate_ocr_extractor = BaiduAccurateOCRElementExtractor(baidu_accurate_provider)
                logger.info("✅ 百度高精度OCR提取器已建立")
        except Exception as e:
            logger.warning(f"無法初始化百度高精度OCR: {e}")
        
        # 使用登錄檔的工廠方法建立預設配置
        return ExtractorRegistry.create_default(
            mineru_extractor=mineru_extractor,
            baidu_ocr_extractor=baidu_ocr_extractor,
            baidu_accurate_ocr_extractor=baidu_accurate_ocr_extractor
        )
    
    @staticmethod
    def create_baidu_accurate_ocr_extractor(
        baidu_accurate_ocr_provider: Optional[Any] = None
    ) -> Optional[BaiduAccurateOCRElementExtractor]:
        """
        建立百度高精度OCR提取器
        
        Args:
            baidu_accurate_ocr_provider: 百度高精度OCR Provider例項（可選，自動建立）
        
        Returns:
            BaiduAccurateOCRElementExtractor例項，如果不可用則返回None
        """
        if baidu_accurate_ocr_provider is None:
            try:
                from services.ai_providers.ocr import create_baidu_accurate_ocr_provider
                baidu_accurate_ocr_provider = create_baidu_accurate_ocr_provider()
            except Exception as e:
                logger.warning(f"無法初始化百度高精度OCR Provider: {e}")
                return None
        
        if baidu_accurate_ocr_provider is None:
            return None
        
        return BaiduAccurateOCRElementExtractor(baidu_accurate_ocr_provider)
    
    @staticmethod
    def create_hybrid_extractor(
        parser_service: Any,
        upload_folder: Path,
        baidu_accurate_ocr_provider: Optional[Any] = None,
        contain_threshold: float = 0.8,
        intersection_threshold: float = 0.3
    ) -> Optional[HybridElementExtractor]:
        """
        建立混合元素提取器
        
        混合提取器結合MinerU版面分析和百度高精度OCR：
        - MinerU負責識別元素型別和整體佈局
        - 百度OCR負責精確的文字識別和定位
        
        合併策略：
        1. 圖片型別bbox裡包含的百度OCR bbox → 刪除（圖片內的文字不需要單獨提取）
        2. 表格型別bbox裡包含的百度OCR bbox → 保留百度OCR結果，刪除MinerU表格bbox
        3. 其他型別（文字等）與百度OCR bbox有交集 → 使用百度OCR結果，刪除MinerU bbox
        
        Args:
            parser_service: MinerU解析服務例項
            upload_folder: 上傳資料夾路徑
            baidu_accurate_ocr_provider: 百度高精度OCR Provider例項（可選，自動建立）
            contain_threshold: 包含判斷閾值，預設0.8（80%面積在內部算包含）
            intersection_threshold: 交集判斷閾值，預設0.3（30%重疊算有交集）
        
        Returns:
            HybridElementExtractor例項，如果無法建立則返回None
        """
        # 建立MinerU提取器
        mineru_extractor = MinerUElementExtractor(parser_service, upload_folder)
        logger.info("✅ MinerU提取器已建立（用於混合提取）")
        
        # 建立百度高精度OCR提取器
        baidu_ocr_extractor = ExtractorFactory.create_baidu_accurate_ocr_extractor(
            baidu_accurate_ocr_provider
        )
        
        if baidu_ocr_extractor is None:
            logger.warning("無法建立百度高精度OCR提取器，混合提取器建立失敗")
            return None
        
        logger.info("✅ 百度高精度OCR提取器已建立（用於混合提取）")
        
        return HybridElementExtractor(
            mineru_extractor=mineru_extractor,
            baidu_ocr_extractor=baidu_ocr_extractor,
            contain_threshold=contain_threshold,
            intersection_threshold=intersection_threshold
        )
    
    @staticmethod
    def create_hybrid_extractor_registry(
        parser_service: Any,
        upload_folder: Path,
        baidu_table_ocr_provider: Optional[Any] = None,
        baidu_accurate_ocr_provider: Optional[Any] = None,
        contain_threshold: float = 0.8,
        intersection_threshold: float = 0.3
    ) -> ExtractorRegistry:
        """
        建立使用混合提取器的登錄檔
        
        預設配置：
        - 所有型別 → 混合提取器（如果可用）
        - 回退到MinerU（如果混合提取器不可用）
        
        Args:
            parser_service: MinerU解析服務例項
            upload_folder: 上傳資料夾路徑
            baidu_table_ocr_provider: 百度表格OCR Provider例項（可選）
            baidu_accurate_ocr_provider: 百度高精度OCR Provider例項（可選）
            contain_threshold: 包含判斷閾值
            intersection_threshold: 交集判斷閾值
        
        Returns:
            配置好的ExtractorRegistry例項
        """
        # 建立MinerU提取器作為回退
        mineru_extractor = MinerUElementExtractor(parser_service, upload_folder)
        logger.info("✅ MinerU提取器已建立")
        
        # 嘗試建立混合提取器
        hybrid_extractor = ExtractorFactory.create_hybrid_extractor(
            parser_service=parser_service,
            upload_folder=upload_folder,
            baidu_accurate_ocr_provider=baidu_accurate_ocr_provider,
            contain_threshold=contain_threshold,
            intersection_threshold=intersection_threshold
        )
        
        # 嘗試建立百度表格OCR提取器
        baidu_table_ocr_extractor = None
        if baidu_table_ocr_provider is None:
            try:
                from services.ai_providers.ocr import create_baidu_table_ocr_provider
                baidu_provider = create_baidu_table_ocr_provider()
                if baidu_provider:
                    from .extractors import BaiduOCRElementExtractor
                    baidu_table_ocr_extractor = BaiduOCRElementExtractor(baidu_provider)
                    logger.info("✅ 百度表格OCR提取器已建立")
            except Exception as e:
                logger.warning(f"無法初始化百度表格OCR: {e}")
        else:
            from .extractors import BaiduOCRElementExtractor
            baidu_table_ocr_extractor = BaiduOCRElementExtractor(baidu_table_ocr_provider)
            logger.info("✅ 百度表格OCR提取器已建立")
        
        # 建立登錄檔
        registry = ExtractorRegistry()
        
        # 設定預設提取器
        if hybrid_extractor:
            registry.register_default(hybrid_extractor)
            logger.info("✅ 使用混合提取器作為預設提取器")
        else:
            registry.register_default(mineru_extractor)
            logger.info("⚠️ 混合提取器不可用，回退到MinerU提取器")
        
        # 表格型別使用百度表格OCR（如果可用）
        if baidu_table_ocr_extractor:
            registry.register_types(list(ExtractorRegistry.TABLE_TYPES), baidu_table_ocr_extractor)
        
        return registry


class InpaintProviderFactory:
    """Inpaint提供者工廠"""
    
    @staticmethod
    def create_default_provider(inpainting_service: Optional[Any] = None) -> Optional[InpaintProvider]:
        """
        建立預設的Inpaint提供者（使用Volcengine Inpainting服務）
        
        Args:
            inpainting_service: InpaintingService例項（可選）
        
        Returns:
            InpaintProvider例項，失敗返回None
        """
        if inpainting_service is None:
            from services.inpainting_service import get_inpainting_service
            inpainting_service = get_inpainting_service()
        
        logger.info("建立DefaultInpaintProvider")
        return DefaultInpaintProvider(inpainting_service)
    
    @staticmethod
    def create_generative_edit_provider(
        ai_service: Optional[Any] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K"
    ) -> InpaintProvider:
        """
        建立基於生成式大模型的Inpaint提供者
        
        使用生成式大模型（如Gemini圖片編輯）透過自然語言指令移除圖片中的文字和圖示。
        適用於不需要精確bbox的場景，大模型自動理解並移除相關元素。
        
        Args:
            ai_service: AIService例項（可選，如果不提供則自動獲取）
            aspect_ratio: 目標寬高比
            resolution: 目標解析度
        
        Returns:
            GenerativeEditInpaintProvider例項
        
        Raises:
            如果AI服務初始化失敗，會丟擲異常
        """
        if ai_service is None:
            from services.ai_service_manager import get_ai_service
            ai_service = get_ai_service()
        
        logger.info("建立GenerativeEditInpaintProvider")
        return GenerativeEditInpaintProvider(ai_service, aspect_ratio, resolution)
    
    @staticmethod
    def create_inpaint_registry(
        mask_provider: Optional[InpaintProvider] = None,
        generative_provider: Optional[InpaintProvider] = None,
        default_provider_type: str = "generative"
    ) -> InpaintProviderRegistry:
        """
        建立重繪方法登錄檔
        
        支援動態註冊新元素型別，不限於預定義型別。
        
        Args:
            mask_provider: 基於mask的重繪提供者（可選，自動建立）
            generative_provider: 生成式重繪提供者（可選，自動建立）
            default_provider_type: 預設使用的提供者型別 ("mask" 或 "generative")
        
        Returns:
            配置好的InpaintProviderRegistry例項
        """
        # 自動建立提供者
        if mask_provider is None:
            mask_provider = InpaintProviderFactory.create_default_provider()
        
        if generative_provider is None:
            generative_provider = InpaintProviderFactory.create_generative_edit_provider()
        
        # 建立登錄檔
        registry = InpaintProviderRegistry()
        
        # 設定預設提供者
        if default_provider_type == "generative" and generative_provider:
            registry.register_default(generative_provider)
        elif mask_provider:
            registry.register_default(mask_provider)
        elif generative_provider:
            registry.register_default(generative_provider)
        
        # 註冊型別對映（可透過registry.register()動態擴充套件）
        if mask_provider:
            # 文字和表格使用mask-based精確移除
            registry.register_types(['text', 'title', 'paragraph'], mask_provider)
            registry.register_types(['table', 'table_cell'], mask_provider)
        
        if generative_provider:
            # 圖片和圖表使用生成式重繪
            registry.register_types(['image', 'figure', 'chart', 'diagram'], generative_provider)
        
        logger.info(f"建立InpaintProviderRegistry: 預設={default_provider_type}, "
                   f"mask={mask_provider is not None}, generative={generative_provider is not None}")
        
        return registry
    
    @staticmethod
    def create_baidu_inpaint_provider() -> Optional[BaiduInpaintProvider]:
        """
        建立百度影象修復提供者
        
        使用百度AI在指定矩形區域去除遮擋物並用背景內容填充。
        
        Returns:
            BaiduInpaintProvider例項，如果不可用則返回None
        """
        try:
            from services.ai_providers.image.baidu_inpainting_provider import create_baidu_inpainting_provider
            baidu_provider = create_baidu_inpainting_provider()
            if baidu_provider:
                logger.info("✅ 建立BaiduInpaintProvider")
                return BaiduInpaintProvider(baidu_provider)
            else:
                logger.warning("⚠️ 無法建立百度影象修復Provider（API Key未配置）")
                return None
        except Exception as e:
            logger.warning(f"⚠️ 建立BaiduInpaintProvider失敗: {e}")
            return None
    
    @staticmethod
    def create_hybrid_inpaint_provider(
        baidu_provider: Optional[BaiduInpaintProvider] = None,
        generative_provider: Optional[GenerativeEditInpaintProvider] = None,
        ai_service: Optional[Any] = None,
        enhance_quality: bool = True
    ) -> Optional[HybridInpaintProvider]:
        """
        建立混合Inpaint提供者（百度修復 + 生成式畫質提升）
        
        工作流程：
        1. 先使用百度影象修復API精確去除文字
        2. 再使用生成式大模型提升整體畫質
        
        Args:
            baidu_provider: 百度影象修復提供者（可選，自動建立）
            generative_provider: 生成式編輯提供者（可選，自動建立）
            ai_service: AI服務例項（用於建立生成式提供者）
            enhance_quality: 是否啟用畫質提升，預設True
        
        Returns:
            HybridInpaintProvider例項，如果無法建立則返回None
        """
        # 建立百度修復提供者
        if baidu_provider is None:
            baidu_provider = InpaintProviderFactory.create_baidu_inpaint_provider()
        
        if baidu_provider is None:
            logger.warning("⚠️ 無法建立百度影象修復Provider，混合Provider建立失敗")
            return None
        
        # 建立生成式提供者（用於畫質提升）
        if generative_provider is None:
            generative_provider = InpaintProviderFactory.create_generative_edit_provider(
                ai_service=ai_service
            )
        
        logger.info("✅ 建立HybridInpaintProvider（百度修復 + 生成式畫質提升）")
        return HybridInpaintProvider(
            baidu_provider=baidu_provider,
            generative_provider=generative_provider,
            enhance_quality=enhance_quality
        )


class ServiceConfig:
    """服務配置類 - 純配置，不持有具體服務引用"""
    
    def __init__(
        self,
        upload_folder: Path,
        extractor_registry: ExtractorRegistry,
        inpaint_registry: InpaintProviderRegistry,
        max_depth: int = 1,
        min_image_size: int = 200,
        min_image_area: int = 40000
    ):
        """
        初始化服務配置
        
        Args:
            upload_folder: 上傳資料夾路徑
            extractor_registry: 元素型別到提取器的登錄檔
            inpaint_registry: 元素型別到重繪方法的登錄檔
            max_depth: 最大遞迴深度（預設1）
            min_image_size: 最小圖片尺寸
            min_image_area: 最小圖片面積
        """
        self.upload_folder = upload_folder
        self.extractor_registry = extractor_registry
        self.inpaint_registry = inpaint_registry
        self.max_depth = max_depth
        self.min_image_size = min_image_size
        self.min_image_area = min_image_area
    
    @classmethod
    def from_defaults(
        cls,
        mineru_token: Optional[str] = None,
        mineru_api_base: Optional[str] = None,
        upload_folder: Optional[str] = None,
        ai_service: Optional[Any] = None,
        use_hybrid_extractor: bool = True,
        use_hybrid_inpaint: bool = True,
        extractor_method: Optional[str] = None,  # 'mineru' 或 'hybrid'，優先於 use_hybrid_extractor
        inpaint_method: Optional[str] = None,    # 'generative', 'baidu', 'hybrid'，優先於 use_hybrid_inpaint
        **kwargs
    ) -> 'ServiceConfig':
        """
        從預設引數建立配置
        
        預設配置（推薦用於匯出PPTX）：
        - 元素提取：混合提取器（MinerU版面分析 + 百度高精度OCR）
        - 背景生成：混合Inpaint（百度影象修復 + 生成式畫質提升）
        - 遞迴深度：1
        
        混合提取器合併策略：
        1. 圖片型別bbox裡包含的百度OCR bbox → 刪除
        2. 表格型別bbox裡包含的百度OCR bbox → 保留百度OCR結果，刪除MinerU表格bbox
        3. 其他型別與百度OCR bbox有交集 → 使用百度OCR結果
        
        混合Inpaint策略：
        1. 先用百度影象修復精確去除指定區域的文字
        2. 再用生成式模型提升整體畫質
        
        支援動態註冊新的元素型別到不同的提取器/重繪方法。
        
        如果不提供引數，會自動從 Flask app.config 獲取配置。
        
        Args:
            mineru_token: MinerU API token（可選，預設從 Flask config 獲取）
            mineru_api_base: MinerU API base URL（可選，預設從 Flask config 獲取）
            upload_folder: 上傳資料夾路徑（可選，預設從 Flask config 獲取）
            ai_service: AI服務例項（可選，用於生成式重繪）
            use_hybrid_extractor: 是否使用混合提取器（預設True，會被 extractor_method 覆蓋）
            use_hybrid_inpaint: 是否使用混合Inpaint（預設True，會被 inpaint_method 覆蓋）
            extractor_method: 元件提取方法，'mineru' 或 'hybrid'（優先於 use_hybrid_extractor）
            inpaint_method: 背景修復方法，'generative', 'baidu', 'hybrid'（優先於 use_hybrid_inpaint）
            **kwargs: 其他配置引數
                - max_depth: 最大遞迴深度（預設1）
                - min_image_size: 最小圖片尺寸（預設200）
                - min_image_area: 最小圖片面積（預設40000）
                - contain_threshold: 混合提取器包含判斷閾值（預設0.8）
                - intersection_threshold: 混合提取器交集判斷閾值（預設0.3）
                - enhance_quality: 混合Inpaint是否啟用畫質提升（預設True）
        
        Returns:
            ServiceConfig例項
        
        Raises:
            ValueError: 如果 mineru_token 未配置
        """
        # 處理新引數：extractor_method 優先於 use_hybrid_extractor
        if extractor_method is not None:
            use_hybrid_extractor = (extractor_method == 'hybrid')
            logger.info(f"extractor_method={extractor_method} -> use_hybrid_extractor={use_hybrid_extractor}")
        # 自動從 Flask config 獲取配置
        from flask import current_app, has_app_context
        
        if has_app_context() and current_app:
            if mineru_token is None:
                mineru_token = current_app.config.get('MINERU_TOKEN')
            if mineru_api_base is None:
                mineru_api_base = current_app.config.get('MINERU_API_BASE', 'https://mineru.net')
            if upload_folder is None:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', './uploads')
        else:
            # 回退到預設值
            if mineru_api_base is None:
                mineru_api_base = 'https://mineru.net'
            if upload_folder is None:
                upload_folder = './uploads'
        
        # 驗證必需配置
        if not mineru_token:
            raise ValueError("MinerU token is required. Please configure MINERU_TOKEN.")
        
        from services.file_parser_service import FileParserService
        
        # 解析upload_folder路徑
        upload_path = Path(upload_folder)
        if not upload_path.is_absolute():
            current_file = Path(__file__).resolve()
            backend_dir = current_file.parent.parent
            project_root = backend_dir.parent
            upload_path = project_root / upload_folder.lstrip('./')
        
        logger.info(f"Upload folder resolved to: {upload_path}")
        
        # 建立MinerU解析服務
        parser_service = FileParserService(
            mineru_token=mineru_token,
            mineru_api_base=mineru_api_base
        )
        
        # 建立提取器登錄檔
        extractor_registry = ExtractorRegistry()
        
        if use_hybrid_extractor:
            # 嘗試建立混合提取器（MinerU + 百度高精度OCR）
            hybrid_extractor = ExtractorFactory.create_hybrid_extractor(
                parser_service=parser_service,
                upload_folder=upload_path,
                contain_threshold=kwargs.get('contain_threshold', 0.8),
                intersection_threshold=kwargs.get('intersection_threshold', 0.3)
            )
            
            if hybrid_extractor:
                extractor_registry.register_default(hybrid_extractor)
                logger.info("✅ 混合提取器已建立（MinerU + 百度高精度OCR）")
            else:
                # 回退到MinerU
                mineru_extractor = MinerUElementExtractor(parser_service, upload_path)
                extractor_registry.register_default(mineru_extractor)
                logger.warning("⚠️ 混合提取器建立失敗，回退到MinerU提取器")
        else:
            # 使用純MinerU提取器
            mineru_extractor = MinerUElementExtractor(parser_service, upload_path)
            extractor_registry.register_default(mineru_extractor)
            logger.info("✅ MinerU提取器已建立（通用分割）")
        
        # 建立Inpaint提供者
        inpaint_registry = InpaintProviderRegistry()
        
        # 處理 inpaint_method 引數（優先於 use_hybrid_inpaint）
        effective_inpaint_method = inpaint_method
        if effective_inpaint_method is None:
            # 向後相容：根據 use_hybrid_inpaint 轉換
            effective_inpaint_method = 'hybrid' if use_hybrid_inpaint else 'generative'
        
        logger.info(f"inpaint_method={effective_inpaint_method}")
        
        if effective_inpaint_method == 'hybrid':
            # 混合Inpaint提供者（百度修復 + 生成式畫質提升）
            hybrid_inpaint = InpaintProviderFactory.create_hybrid_inpaint_provider(
                ai_service=ai_service,
                enhance_quality=kwargs.get('enhance_quality', True)
            )
            
            if hybrid_inpaint:
                inpaint_registry.register_default(hybrid_inpaint)
                logger.info("✅ 混合Inpaint提供者已建立（百度修復 + 生成式畫質提升）")
            else:
                # 回退到純生成式重繪
                generative_provider = InpaintProviderFactory.create_generative_edit_provider(
                    ai_service=ai_service
                )
                inpaint_registry.register_default(generative_provider)
                logger.warning("⚠️ 混合Inpaint建立失敗，回退到GenerativeEdit")
        
        elif effective_inpaint_method == 'baidu':
            # 只用百度影象修復（不使用生成式模型，低成本）
            baidu_inpaint = InpaintProviderFactory.create_baidu_inpaint_provider()
            
            if baidu_inpaint:
                inpaint_registry.register_default(baidu_inpaint)
                logger.info("✅ 百度Inpaint提供者已建立（純百度修復）")
            else:
                # 回退到生成式
                generative_provider = InpaintProviderFactory.create_generative_edit_provider(
                    ai_service=ai_service
                )
                inpaint_registry.register_default(generative_provider)
                logger.warning("⚠️ 百度Inpaint建立失敗，回退到GenerativeEdit")
        
        else:  # 'generative' 或其他
            # 使用純生成式重繪
            generative_provider = InpaintProviderFactory.create_generative_edit_provider(
                ai_service=ai_service
            )
            inpaint_registry.register_default(generative_provider)
            logger.info("✅ 重繪登錄檔已建立（GenerativeEdit通用）")
        
        return cls(
            upload_folder=upload_path,
            extractor_registry=extractor_registry,
            inpaint_registry=inpaint_registry,
            max_depth=kwargs.get('max_depth', 1),
            min_image_size=kwargs.get('min_image_size', 200),
            min_image_area=kwargs.get('min_image_area', 40000)
        )


class TextAttributeExtractorFactory:
    """文字屬性提取器工廠"""
    
    @staticmethod
    def create_caption_model_extractor(
        ai_service: Optional[Any] = None,
        prompt_template: Optional[str] = None
    ) -> TextAttributeExtractor:
        """
        建立基於Caption Model的文字屬性提取器
        
        使用視覺語言模型（如Gemini）分析文字區域影象，
        透過生成JSON的方式獲取字型顏色、是否粗體、是否斜體等屬性。
        
        Args:
            ai_service: AIService例項（可選，如果不提供則自動獲取）
            prompt_template: 自定義的prompt模板（可選），必須使用 {content_hint} 作為佔位符
        
        Returns:
            CaptionModelTextAttributeExtractor例項
        
        Raises:
            如果AI服務初始化失敗，會丟擲異常
        """
        if ai_service is None:
            from services.ai_service_manager import get_ai_service
            ai_service = get_ai_service()
        
        logger.info("建立CaptionModelTextAttributeExtractor")
        return CaptionModelTextAttributeExtractor(ai_service, prompt_template)
    
    @staticmethod
    def create_text_attribute_registry(
        caption_extractor: Optional[TextAttributeExtractor] = None,
        ai_service: Optional[Any] = None
    ) -> TextAttributeExtractorRegistry:
        """
        建立文字屬性提取器登錄檔
        
        支援動態註冊新元素型別，不限於預定義型別。
        
        Args:
            caption_extractor: Caption Model提取器（可選，自動建立）
            ai_service: AIService例項（可選，用於自動建立提取器）
        
        Returns:
            配置好的TextAttributeExtractorRegistry例項
        
        Raises:
            如果提取器建立失敗，會丟擲異常
        """
        # 自動建立提取器
        if caption_extractor is None:
            caption_extractor = TextAttributeExtractorFactory.create_caption_model_extractor(
                ai_service=ai_service
            )
        
        # 建立登錄檔
        registry = TextAttributeExtractorRegistry()
        
        # 設定預設提取器
        registry.register_default(caption_extractor)
        
        # 註冊文字型別
        registry.register_types(
            ['text', 'title', 'paragraph', 'heading', 'table_cell'],
            caption_extractor
        )
        
        logger.info("建立TextAttributeExtractorRegistry")
        
        return registry

