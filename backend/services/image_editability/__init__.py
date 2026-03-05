"""
圖片可編輯化服務模組

核心設計：
- 無狀態服務 - 執行緒安全，可並行呼叫
- 依賴注入 - 透過配置物件注入所有依賴
- 單一職責 - 只負責單張圖片的可編輯化，批次處理由呼叫者控制

元件：
- 資料模型（BBox, EditableElement, EditableImage）
- 元素提取器（ElementExtractor及其實現）
- Inpaint提供者（InpaintProvider及其實現）
- 工廠和配置（ServiceConfig）
- 主服務類（ImageEditabilityService）

Example:
    >>> from services.image_editability import ServiceConfig, ImageEditabilityService
    >>> 
    >>> # 建立配置
    >>> config = ServiceConfig.from_defaults(mineru_token="your_token")
    >>> 
    >>> # 建立服務
    >>> service = ImageEditabilityService(config)
    >>> 
    >>> # 序列處理
    >>> result = service.make_image_editable("image.png")
    >>> 
    >>> # 並行處理（推薦）
    >>> from concurrent.futures import ThreadPoolExecutor, as_completed
    >>> 
    >>> images = ["img1.png", "img2.png", "img3.png"]
    >>> with ThreadPoolExecutor(max_workers=4) as executor:
    ...     futures = {executor.submit(service.make_image_editable, img): img 
    ...                for img in images}
    ...     results = {images[i]: future.result() 
    ...                for i, future in enumerate(as_completed(futures))}
"""

# 資料模型
from .data_models import BBox, EditableElement, EditableImage

# 座標對映
from .coordinate_mapper import CoordinateMapper

# 元素提取器
from .extractors import (
    ElementExtractor,
    MinerUElementExtractor,
    BaiduOCRElementExtractor,
    BaiduAccurateOCRElementExtractor,
    ExtractorRegistry
)

# 混合提取器
from .hybrid_extractor import (
    HybridElementExtractor,
    BBoxUtils,
    create_hybrid_extractor
)

# Inpaint提供者
from .inpaint_providers import (
    InpaintProvider,
    DefaultInpaintProvider,
    GenerativeEditInpaintProvider,
    BaiduInpaintProvider,
    HybridInpaintProvider,
    InpaintProviderRegistry
)

# 文字屬性提取器
from .text_attribute_extractors import (
    TextStyleResult,
    TextAttributeExtractor,
    CaptionModelTextAttributeExtractor,
    TextAttributeExtractorRegistry
)

# 工廠和配置
from .factories import (
    ExtractorFactory,
    InpaintProviderFactory,
    TextAttributeExtractorFactory,
    ServiceConfig
)

# 主服務
from .service import ImageEditabilityService

__all__ = [
    # 資料模型
    'BBox',
    'EditableElement',
    'EditableImage',
    # 座標對映
    'CoordinateMapper',
    # 元素提取器
    'ElementExtractor',
    'MinerUElementExtractor',
    'BaiduOCRElementExtractor',
    'BaiduAccurateOCRElementExtractor',
    'ExtractorRegistry',
    # 混合提取器
    'HybridElementExtractor',
    'BBoxUtils',
    'create_hybrid_extractor',
    # Inpaint提供者
    'InpaintProvider',
    'DefaultInpaintProvider',
    'GenerativeEditInpaintProvider',
    'BaiduInpaintProvider',
    'HybridInpaintProvider',
    'InpaintProviderRegistry',
    # 文字屬性提取器
    'TextStyleResult',
    'TextAttributeExtractor',
    'CaptionModelTextAttributeExtractor',
    'TextAttributeExtractorRegistry',
    # 工廠和配置
    'ExtractorFactory',
    'InpaintProviderFactory',
    'TextAttributeExtractorFactory',
    'ServiceConfig',
    # 主服務
    'ImageEditabilityService',
]

