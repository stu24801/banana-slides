"""
圖片可編輯化服務 - 核心服務類

設計原則：
1. 無狀態設計 - 執行緒安全，可並行呼叫
2. 單一職責 - 只負責單張圖片的可編輯化
3. 依賴注入 - 透過配置物件注入所有依賴
4. 零具體實現依賴 - 完全依賴抽象介面
"""
import logging
import uuid
from typing import List, Optional, Tuple
from PIL import Image

from .data_models import BBox, EditableElement, EditableImage
from .coordinate_mapper import CoordinateMapper
from .extractors import ElementExtractor, ExtractionResult
from .inpaint_providers import InpaintProvider
from .factories import ServiceConfig
from .helpers import collect_bboxes_from_elements, should_recurse_into_element, crop_element_from_image

logger = logging.getLogger(__name__)


class ImageEditabilityService:
    """
    圖片可編輯化服務
    
    執行緒安全的無狀態服務，可並行呼叫 make_image_editable()
    完全依賴抽象介面，不知道任何具體實現細節
    
    Example:
        >>> config = ServiceConfig.from_defaults(mineru_token="xxx")
        >>> service = ImageEditabilityService(config)
        >>> 
        >>> # 序列處理
        >>> result = service.make_image_editable("image.png")
        >>> 
        >>> # 並行處理（由呼叫者控制）
        >>> from concurrent.futures import ThreadPoolExecutor
        >>> with ThreadPoolExecutor() as executor:
        ...     futures = [executor.submit(service.make_image_editable, img) 
        ...                for img in image_paths]
        ...     results = [f.result() for f in futures]
    """
    
    def __init__(self, config: ServiceConfig):
        """
        初始化服務
        
        Args:
            config: ServiceConfig配置物件，包含所有依賴
        """
        # 只讀配置，執行緒安全
        self._upload_folder = config.upload_folder
        self._extractor_registry = config.extractor_registry
        self._inpaint_registry = config.inpaint_registry
        self._max_depth = config.max_depth
        self._min_image_size = config.min_image_size
        self._min_image_area = config.min_image_area
        self._max_child_coverage_ratio = 0.85
        
        extractors = self._extractor_registry.get_all_extractors()
        inpaint_providers = self._inpaint_registry.get_all_providers()
        logger.info(
            f"ImageEditabilityService: {len(extractors)} extractors, "
            f"{len(inpaint_providers)} inpaint providers, "
            f"max_depth={self._max_depth}"
        )
    
    def make_image_editable(
        self,
        image_path: str,
        depth: int = 0,
        parent_id: Optional[str] = None,
        parent_bbox: Optional[BBox] = None,
        root_image_size: Optional[Tuple[int, int]] = None,
        element_type: Optional[str] = None,
        root_image_path: Optional[str] = None
    ) -> EditableImage:
        """
        將圖片轉換為可編輯結構（遞迴）
        
        執行緒安全：此方法可以被多個執行緒並行呼叫
        
        Args:
            image_path: 圖片路徑
            depth: 當前遞迴深度（內部使用）
            parent_id: 父圖片ID（內部使用）
            parent_bbox: 當前圖片在父圖中的bbox位置（內部使用）
            root_image_size: 根圖片尺寸（內部使用）
            element_type: 元素型別，用於選擇提取器（內部使用）
            root_image_path: 根圖片路徑（內部使用）
        
        Returns:
            EditableImage物件
        
        Raises:
            FileNotFoundError: 圖片檔案不存在
            ValueError: 圖片格式不支援
        """
        image_id = str(uuid.uuid4())[:8]
        logger.info(f"{'  ' * depth}[{image_id}] 開始處理")
        
        # 1. 載入圖片
        try:
            img = Image.open(image_path)
            width, height = img.size
        except Exception as e:
            logger.error(f"無法載入圖片 {image_path}: {e}")
            raise
        
        # 記錄根圖片資訊
        if root_image_size is None:
            root_image_size = (width, height)
        if root_image_path is None:
            root_image_path = image_path
        
        # 2. 提取元素
        extraction_result = self._extract_elements(
            image_path=image_path,
            element_type=element_type,
            depth=depth
        )
        
        # 從context獲取image_size（提取器自己獲取）
        extracted_image_size = extraction_result.context.metadata.get('image_size', (width, height))
        
        elements = self._convert_to_editable_elements(
            element_dicts=extraction_result.elements,
            image_id=image_id,
            parent_bbox=parent_bbox,
            image_size=extracted_image_size,
            root_image_size=root_image_size,
            source_image_path=image_path  # 傳入源圖片路徑用於裁剪
        )
        
        logger.info(f"{'  ' * depth}提取到 {len(elements)} 個元素")
        
        # 3. 生成clean background（根據元素型別選擇重繪方法）
        clean_background = None
        if self._inpaint_registry and elements:
            clean_background = self._generate_clean_background(
                image_path=image_path,
                elements=elements,
                image_id=image_id,
                depth=depth,
                parent_bbox=parent_bbox,
                root_image_path=root_image_path,
                image_size=(width, height),
                element_type=element_type  # 傳遞元素型別以選擇對應的重繪方法
            )
        
        # 4. 遞迴處理子元素
        # max_depth 語義：max_depth=1 表示只處理1層不遞迴，max_depth=2 遞迴一次
        if depth + 1 < self._max_depth:
            self._process_children(
                elements=elements,
                current_image_path=image_path,
                depth=depth,
                image_id=image_id,
                root_image_size=root_image_size,
                current_image_size=(width, height),
                root_image_path=root_image_path
            )
        
        # 5. 構建結果
        editable_image = EditableImage(
            image_id=image_id,
            image_path=image_path,
            width=width,
            height=height,
            elements=elements,
            clean_background=clean_background,
            depth=depth,
            parent_id=parent_id
        )
        
        logger.info(f"{'  ' * depth}[{image_id}] 處理完成")
        return editable_image
    
    def _extract_elements(
        self,
        image_path: str,
        element_type: Optional[str],
        depth: int
    ) -> ExtractionResult:
        """提取元素（完全依賴提取器介面）"""
        logger.info(f"{'  ' * depth}提取元素...")
        
        # 選擇提取器
        extractor = self._select_extractor(element_type)
        
        # 呼叫提取器（提取器自己處理所有細節，包括獲取image_size）
        return extractor.extract(
            image_path=image_path,
            element_type=element_type,
            depth=depth
        )
    
    def _select_extractor(self, element_type: Optional[str]) -> ElementExtractor:
        """根據元素型別從登錄檔選擇對應的提取器"""
        extractor = self._extractor_registry.get_extractor(element_type)
        if extractor is None:
            raise ValueError(f"未找到元素型別 '{element_type}' 對應的提取器")
        return extractor
    
    def _convert_to_editable_elements(
        self,
        element_dicts: List[dict],
        image_id: str,
        parent_bbox: Optional[BBox],
        image_size: Tuple[int, int],
        root_image_size: Tuple[int, int],
        source_image_path: Optional[str] = None
    ) -> List[EditableElement]:
        """
        將提取器返回的字典轉換為EditableElement物件
        
        對每個元素根據 bbox 從原圖裁剪並儲存圖片，不依賴 MinerU 提取的圖片。
        這樣所有元素（包括文字）都有 image_path，可用於樣式提取。
        """
        elements = []
        
        # 準備輸出目錄
        output_dir = None
        source_img = None
        if source_image_path:
            output_dir = self._upload_folder / 'editable_images' / image_id / 'elements'
            output_dir.mkdir(parents=True, exist_ok=True)
            try:
                source_img = Image.open(source_image_path)
            except Exception as e:
                logger.warning(f"無法載入源圖片進行裁剪: {e}")
        
        for idx, elem_dict in enumerate(element_dicts):
            bbox_list = elem_dict['bbox']
            local_bbox = BBox(
                x0=bbox_list[0],
                y0=bbox_list[1],
                x1=bbox_list[2],
                y1=bbox_list[3]
            )
            
            # 計算全域性座標
            if parent_bbox is None:
                global_bbox = local_bbox
            else:
                global_bbox = CoordinateMapper.local_to_global(
                    local_bbox=local_bbox,
                    parent_bbox=parent_bbox,
                    local_image_size=image_size,
                    parent_image_size=root_image_size
                )
            
            # 為每個元素裁剪並儲存圖片（統一使用自己裁剪的圖片）
            element_image_path = None
            if source_img and output_dir:
                try:
                    # 裁剪元素區域
                    crop_box = (
                        max(0, int(local_bbox.x0)),
                        max(0, int(local_bbox.y0)),
                        min(source_img.width, int(local_bbox.x1)),
                        min(source_img.height, int(local_bbox.y1))
                    )
                    
                    # 檢查裁剪區域有效性
                    if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                        cropped = source_img.crop(crop_box)
                        element_image_path = str(output_dir / f"{idx}_{elem_dict['type']}.png")
                        cropped.save(element_image_path)
                except Exception as e:
                    logger.warning(f"裁剪元素 {idx} 失敗: {e}")
            
            element = EditableElement(
                element_id=f"{image_id}_{idx}",
                element_type=elem_dict['type'],
                bbox=local_bbox,
                bbox_global=global_bbox,
                content=elem_dict.get('content'),
                image_path=element_image_path,  # 使用自己裁剪的圖片路徑
                metadata=elem_dict.get('metadata', {})
            )
            
            elements.append(element)
        
        # 關閉源圖片
        if source_img:
            source_img.close()
        
        return elements
    
    def _generate_clean_background(
        self,
        image_path: str,
        elements: List[EditableElement],
        image_id: str,
        depth: int,
        parent_bbox: Optional[BBox],
        root_image_path: str,
        image_size: Tuple[int, int],
        element_type: Optional[str] = None
    ) -> Optional[str]:
        """
        生成clean background
        
        根據元素型別從登錄檔選擇對應的重繪方法：
        - 如果指定了element_type，使用該型別對應的重繪方法
        - 否則使用預設的重繪方法
        """
        logger.info(f"{'  ' * depth}生成clean background (element_type={element_type})...")
        
        # 從登錄檔獲取重繪方法
        inpaint_provider = self._inpaint_registry.get_provider(element_type)
        if inpaint_provider is None:
            logger.warning(f"{'  ' * depth}未找到重繪方法，跳過")
            return None
        
        try:
            bboxes = collect_bboxes_from_elements(elements)
            img = Image.open(image_path)
            img_width, img_height = img.size
            element_types = [elem.element_type for elem in elements]
            
            # 計算crop_box
            if depth == 0:
                crop_box = (0, 0, img_width, img_height)
            elif parent_bbox:
                crop_box = (
                    int(parent_bbox.x0),
                    int(parent_bbox.y0),
                    int(parent_bbox.x1),
                    int(parent_bbox.y1)
                )
            else:
                crop_box = None
            
            # 載入完整頁面影象
            full_page_img = None
            if root_image_path != image_path:
                full_page_img = Image.open(root_image_path)
            
            # 過濾覆蓋過大的bbox
            filtered_bboxes = []
            filtered_types = []
            for bbox, elem_type in zip(bboxes, element_types):
                if isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                    x0, y0, x1, y1 = bbox
                    coverage = ((x1 - x0) * (y1 - y0)) / (img_width * img_height)
                    if coverage > 0.95:
                        continue
                filtered_bboxes.append(bbox)
                filtered_types.append(elem_type)
            
            if not filtered_bboxes:
                return None
            
            # 準備輸出
            output_dir = self._upload_folder / 'editable_images' / image_id
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # 呼叫登錄檔中選擇的重繪方法
            logger.info(f"{'  ' * depth}使用 {inpaint_provider.__class__.__name__} 進行重繪")
            result_img = inpaint_provider.inpaint_regions(
                image=img,
                bboxes=filtered_bboxes,
                types=filtered_types,
                expand_pixels=10,
                save_mask_path=str(output_dir / 'mask.png'),
                full_page_image=full_page_img,
                crop_box=crop_box
            )
            
            if result_img is None:
                return None
            
            # 儲存結果
            output_path = output_dir / 'clean_background.png'
            result_img.save(str(output_path))
            return str(output_path)
        
        except Exception as e:
            logger.error(f"生成clean background失敗: {e}", exc_info=True)
            return None
    
    def _process_children(
        self,
        elements: List[EditableElement],
        current_image_path: str,
        depth: int,
        image_id: str,
        root_image_size: Tuple[int, int],
        current_image_size: Tuple[int, int],
        root_image_path: str
    ):
        """遞迴處理子元素（透過裁剪原圖獲取子圖，並行處理多個子元素）"""
        logger.info(f"{'  ' * depth}遞迴處理子元素...")
        
        # 篩選需要遞迴的元素
        elements_to_process = []
        for element in elements:
            if should_recurse_into_element(
                element=element,
                parent_image_size=current_image_size,
                min_image_size=self._min_image_size,
                min_image_area=self._min_image_area,
                max_child_coverage_ratio=self._max_child_coverage_ratio
            ):
                elements_to_process.append(element)
        
        if not elements_to_process:
            return
        
        # 並行處理多個子元素
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        def process_single_element(element):
            """處理單個子元素"""
            try:
                # 從當前圖片裁剪出子區域
                child_image_path = crop_element_from_image(
                    source_image_path=current_image_path,
                    bbox=element.bbox
                )
                
                child_editable = self.make_image_editable(
                    image_path=child_image_path,
                    depth=depth + 1,
                    parent_id=image_id,
                    parent_bbox=element.bbox_global,
                    root_image_size=root_image_size,
                    element_type=element.element_type,
                    root_image_path=root_image_path
                )
                
                return element, child_editable, None
            
            except Exception as e:
                return element, None, e
        
        logger.info(f"{'  ' * depth}  並行處理 {len(elements_to_process)} 個子元素...")
        
        # 使用執行緒池並行處理
        max_workers = min(8, len(elements_to_process))  # 限制併發數
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single_element, elem): elem for elem in elements_to_process}
            
            for future in as_completed(futures):
                element, child_editable, error = future.result()
                
                if error:
                    logger.error(f"{'  ' * depth}  ✗ {element.element_id} 失敗: {error}")
                else:
                    element.children = child_editable.elements
                    element.inpainted_background_path = child_editable.clean_background
                    logger.info(f"{'  ' * depth}  ✓ {element.element_id} 完成: {len(child_editable.elements)} 個子元素")
