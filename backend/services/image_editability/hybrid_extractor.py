"""
混合元素提取器 - 結合MinerU版面分析和百度高精度OCR的提取策略

工作流程：
1. MinerU和百度OCR並行識別（提升速度）
2. 結果合併：
   - 圖片型別bbox裡包含的百度OCR bbox → 刪除百度OCR bbox
   - 表格型別bbox裡包含的百度OCR bbox → 保留百度OCR bbox，刪除MinerU表格bbox
   - 其他型別bbox與百度OCR bbox有交集 → 使用百度OCR結果，刪除MinerU bbox
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

from .extractors import (
    ElementExtractor, 
    ExtractionResult, 
    ExtractionContext,
    MinerUElementExtractor,
    BaiduAccurateOCRElementExtractor
)

logger = logging.getLogger(__name__)


class BBoxUtils:
    """邊界框工具類"""
    
    @staticmethod
    def is_contained(inner_bbox: List[float], outer_bbox: List[float], threshold: float = 0.8) -> bool:
        """
        判斷inner_bbox是否被outer_bbox包含
        
        Args:
            inner_bbox: 內部bbox [x0, y0, x1, y1]
            outer_bbox: 外部bbox [x0, y0, x1, y1]
            threshold: 包含閾值，inner_bbox有多少比例在outer_bbox內算作包含，預設0.8
        
        Returns:
            是否被包含
        """
        if not inner_bbox or not outer_bbox:
            return False
        
        ix0, iy0, ix1, iy1 = inner_bbox
        ox0, oy0, ox1, oy1 = outer_bbox
        
        # 計算交集
        inter_x0 = max(ix0, ox0)
        inter_y0 = max(iy0, oy0)
        inter_x1 = min(ix1, ox1)
        inter_y1 = min(iy1, oy1)
        
        if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
            return False
        
        # 計算交集面積
        inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
        
        # 計算inner_bbox面積
        inner_area = (ix1 - ix0) * (iy1 - iy0)
        
        if inner_area <= 0:
            return False
        
        # 判斷包含比例
        return (inter_area / inner_area) >= threshold
    
    @staticmethod
    def has_intersection(bbox1: List[float], bbox2: List[float], min_overlap_ratio: float = 0.1) -> bool:
        """
        判斷兩個bbox是否有交集
        
        Args:
            bbox1: 第一個bbox [x0, y0, x1, y1]
            bbox2: 第二個bbox [x0, y0, x1, y1]
            min_overlap_ratio: 最小重疊比例（相對於較小bbox的面積），預設0.1
        
        Returns:
            是否有交集
        """
        if not bbox1 or not bbox2:
            return False
        
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2
        
        # 計算交集
        inter_x0 = max(x0_1, x0_2)
        inter_y0 = max(y0_1, y0_2)
        inter_x1 = min(x1_1, x1_2)
        inter_y1 = min(y1_1, y1_2)
        
        if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
            return False
        
        # 計算交集面積
        inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
        
        # 計算兩個bbox的面積
        area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
        area2 = (x1_2 - x0_2) * (y1_2 - y0_2)
        
        # 取較小面積作為基準
        min_area = min(area1, area2)
        
        if min_area <= 0:
            return False
        
        # 判斷重疊比例
        return (inter_area / min_area) >= min_overlap_ratio
    
    @staticmethod
    def get_intersection_ratio(bbox1: List[float], bbox2: List[float]) -> Tuple[float, float]:
        """
        計算兩個bbox的交集比例
        
        Args:
            bbox1: 第一個bbox
            bbox2: 第二個bbox
        
        Returns:
            (交集佔bbox1的比例, 交集佔bbox2的比例)
        """
        if not bbox1 or not bbox2:
            return (0.0, 0.0)
        
        x0_1, y0_1, x1_1, y1_1 = bbox1
        x0_2, y0_2, x1_2, y1_2 = bbox2
        
        # 計算交集
        inter_x0 = max(x0_1, x0_2)
        inter_y0 = max(y0_1, y0_2)
        inter_x1 = min(x1_1, x1_2)
        inter_y1 = min(y1_1, y1_2)
        
        if inter_x1 <= inter_x0 or inter_y1 <= inter_y0:
            return (0.0, 0.0)
        
        inter_area = (inter_x1 - inter_x0) * (inter_y1 - inter_y0)
        area1 = (x1_1 - x0_1) * (y1_1 - y0_1)
        area2 = (x1_2 - x0_2) * (y1_2 - y0_2)
        
        ratio1 = inter_area / area1 if area1 > 0 else 0.0
        ratio2 = inter_area / area2 if area2 > 0 else 0.0
        
        return (ratio1, ratio2)


class HybridElementExtractor(ElementExtractor):
    """
    混合元素提取器
    
    結合MinerU版面分析和百度高精度OCR，實現更精確的元素識別：
    - MinerU負責識別元素型別和整體佈局
    - 百度OCR負責精確的文字識別和定位
    
    合併策略：
    1. 圖片型別bbox裡包含的百度OCR bbox → 刪除（圖片內的文字不需要單獨提取）
    2. 表格型別bbox裡包含的百度OCR bbox → 保留百度OCR結果，刪除MinerU表格bbox
    3. 其他型別（文字等）與百度OCR bbox有交集 → 使用百度OCR結果，刪除MinerU bbox
    """
    
    # 元素型別分類
    IMAGE_TYPES = {'image', 'figure', 'chart', 'diagram'}
    TABLE_TYPES = {'table', 'table_cell'}
    TEXT_TYPES = {'text', 'title', 'paragraph', 'header', 'footer', 'list'}
    
    def __init__(
        self,
        mineru_extractor: MinerUElementExtractor,
        baidu_ocr_extractor: BaiduAccurateOCRElementExtractor,
        contain_threshold: float = 0.8,
        intersection_threshold: float = 0.3
    ):
        """
        初始化混合提取器
        
        Args:
            mineru_extractor: MinerU元素提取器
            baidu_ocr_extractor: 百度高精度OCR提取器
            contain_threshold: 包含判斷閾值，預設0.8（80%面積在內部算包含）
            intersection_threshold: 交集判斷閾值，預設0.3（30%重疊算有交集）
        """
        self._mineru_extractor = mineru_extractor
        self._baidu_ocr_extractor = baidu_ocr_extractor
        self._contain_threshold = contain_threshold
        self._intersection_threshold = intersection_threshold
    
    def supports_type(self, element_type: Optional[str]) -> bool:
        """混合提取器支援所有型別"""
        return True
    
    def extract(
        self,
        image_path: str,
        element_type: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        從影象中提取元素（混合策略）
        
        工作流程：
        1. 呼叫MinerU提取器獲取版面分析結果
        2. 呼叫百度OCR提取器獲取文字識別結果
        3. 合併結果
        
        Args:
            image_path: 影象檔案路徑
            element_type: 元素型別提示（可選）
            **kwargs: 其他引數
                - depth: 遞迴深度
                - language_type: 百度OCR語言型別
        
        Returns:
            合併後的ExtractionResult
        """
        depth = kwargs.get('depth', 0)
        indent = '  ' * depth
        
        logger.info(f"{indent}🔀 開始混合提取: {image_path}")
        
        # 1. MinerU版面分析 和 百度高精度OCR 並行執行
        logger.info(f"{indent}📄🔤 Step 1: MinerU + 百度OCR 並行識別...")
        
        mineru_result = None
        baidu_result = None
        
        def run_mineru():
            return self._mineru_extractor.extract(image_path, element_type, **kwargs)
        
        def run_baidu_ocr():
            return self._baidu_ocr_extractor.extract(image_path, element_type, **kwargs)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_mineru = executor.submit(run_mineru)
            future_baidu = executor.submit(run_baidu_ocr)
            
            # 等待兩個任務完成
            for future in as_completed([future_mineru, future_baidu]):
                try:
                    if future == future_mineru:
                        mineru_result = future.result()
                        logger.info(f"{indent}  ✅ MinerU識別到 {len(mineru_result.elements)} 個元素")
                    else:
                        baidu_result = future.result()
                        logger.info(f"{indent}  ✅ 百度OCR識別到 {len(baidu_result.elements)} 個元素")
                except Exception as e:
                    logger.error(f"{indent}  ❌ 提取失敗: {e}")
        
        # 確保兩個結果都存在
        if mineru_result is None:
            mineru_result = ExtractionResult(elements=[])
        if baidu_result is None:
            baidu_result = ExtractionResult(elements=[])
        
        mineru_elements = mineru_result.elements
        baidu_elements = baidu_result.elements
        
        # 2. 合併結果
        logger.info(f"{indent}🔧 Step 2: 合併結果...")
        merged_elements = self._merge_results(mineru_elements, baidu_elements, depth)
        logger.info(f"{indent}  合併後共 {len(merged_elements)} 個元素")
        
        # 合併上下文
        context = ExtractionContext(
            result_dir=mineru_result.context.result_dir,
            metadata={
                'source': 'hybrid',
                'mineru_count': len(mineru_elements),
                'baidu_count': len(baidu_elements),
                'merged_count': len(merged_elements),
                **mineru_result.context.metadata
            }
        )
        
        return ExtractionResult(elements=merged_elements, context=context)
    
    def _merge_results(
        self,
        mineru_elements: List[Dict[str, Any]],
        baidu_elements: List[Dict[str, Any]],
        depth: int = 0
    ) -> List[Dict[str, Any]]:
        """
        合併MinerU和百度OCR的結果
        
        合併規則：
        1. 圖片型別bbox裡包含的百度OCR bbox → 刪除百度OCR bbox
        2. 表格型別bbox裡包含的百度OCR bbox → 保留百度OCR bbox，刪除MinerU表格bbox
        3. 其他型別與百度OCR bbox有交集 → 使用百度OCR結果，刪除MinerU bbox
        
        Args:
            mineru_elements: MinerU識別的元素列表
            baidu_elements: 百度OCR識別的元素列表
            depth: 遞迴深度（用於日誌）
        
        Returns:
            合併後的元素列表
        """
        indent = '  ' * depth
        
        # 分類MinerU元素
        image_elements = []
        table_elements = []
        other_elements = []
        
        for elem in mineru_elements:
            elem_type = elem.get('type', '')
            if elem_type in self.IMAGE_TYPES:
                image_elements.append(elem)
            elif elem_type in self.TABLE_TYPES:
                table_elements.append(elem)
            else:
                other_elements.append(elem)
        
        logger.info(f"{indent}  MinerU分類: 圖片={len(image_elements)}, 表格={len(table_elements)}, 其他={len(other_elements)}")
        
        # 標記需要保留/刪除的百度OCR元素
        baidu_to_keep = set(range(len(baidu_elements)))  # 初始全部保留
        baidu_in_table = set()  # 在表格內的百度OCR元素
        
        # 規則1: 圖片型別bbox裡包含的百度OCR bbox → 刪除
        for img_elem in image_elements:
            img_bbox = img_elem.get('bbox', [])
            for idx, baidu_elem in enumerate(baidu_elements):
                baidu_bbox = baidu_elem.get('bbox', [])
                if BBoxUtils.is_contained(baidu_bbox, img_bbox, self._contain_threshold):
                    baidu_to_keep.discard(idx)
                    logger.debug(f"{indent}    百度OCR[{idx}]被圖片包含，刪除")
        
        # 規則2: 表格型別bbox裡包含的百度OCR bbox → 保留，並標記
        tables_to_remove = set()
        for table_idx, table_elem in enumerate(table_elements):
            table_bbox = table_elem.get('bbox', [])
            has_contained_text = False
            for idx, baidu_elem in enumerate(baidu_elements):
                baidu_bbox = baidu_elem.get('bbox', [])
                if BBoxUtils.is_contained(baidu_bbox, table_bbox, self._contain_threshold):
                    baidu_in_table.add(idx)
                    has_contained_text = True
                    logger.debug(f"{indent}    百度OCR[{idx}]在表格內，保留")
            
            if has_contained_text:
                tables_to_remove.add(table_idx)
                logger.debug(f"{indent}    表格[{table_idx}]有文字，刪除表格bbox")
        
        # 規則3: 其他型別與百度OCR bbox有交集 → 使用百度OCR結果
        other_to_remove = set()
        for other_idx, other_elem in enumerate(other_elements):
            other_bbox = other_elem.get('bbox', [])
            for idx, baidu_elem in enumerate(baidu_elements):
                if idx not in baidu_to_keep:
                    continue
                baidu_bbox = baidu_elem.get('bbox', [])
                if BBoxUtils.has_intersection(other_bbox, baidu_bbox, self._intersection_threshold):
                    other_to_remove.add(other_idx)
                    logger.debug(f"{indent}    MinerU其他[{other_idx}]與百度OCR[{idx}]有交集，使用百度OCR")
                    break
        
        # 構建最終結果
        merged = []
        
        # 新增圖片元素（全部保留）
        for elem in image_elements:
            elem_copy = elem.copy()
            elem_copy['metadata'] = elem_copy.get('metadata', {}).copy()
            elem_copy['metadata']['source'] = 'mineru'
            merged.append(elem_copy)
        
        # 新增表格元素（刪除有文字的表格bbox）
        for idx, elem in enumerate(table_elements):
            if idx not in tables_to_remove:
                elem_copy = elem.copy()
                elem_copy['metadata'] = elem_copy.get('metadata', {}).copy()
                elem_copy['metadata']['source'] = 'mineru'
                merged.append(elem_copy)
        
        # 新增其他MinerU元素（刪除與百度OCR有交集的）
        for idx, elem in enumerate(other_elements):
            if idx not in other_to_remove:
                elem_copy = elem.copy()
                elem_copy['metadata'] = elem_copy.get('metadata', {}).copy()
                elem_copy['metadata']['source'] = 'mineru'
                merged.append(elem_copy)
        
        # 新增保留的百度OCR元素
        for idx in baidu_to_keep:
            elem = baidu_elements[idx]
            elem_copy = elem.copy()
            elem_copy['metadata'] = elem_copy.get('metadata', {}).copy()
            elem_copy['metadata']['source'] = 'baidu_ocr'
            if idx in baidu_in_table:
                elem_copy['metadata']['in_table'] = True
            merged.append(elem_copy)
        
        logger.info(f"{indent}  合併結果: 保留圖片={len(image_elements)}, "
                   f"保留表格={len(table_elements) - len(tables_to_remove)}, "
                   f"保留MinerU其他={len(other_elements) - len(other_to_remove)}, "
                   f"保留百度OCR={len(baidu_to_keep)}")
        
        return merged


def create_hybrid_extractor(
    mineru_extractor: Optional[MinerUElementExtractor] = None,
    baidu_ocr_extractor: Optional[BaiduAccurateOCRElementExtractor] = None,
    parser_service: Optional[Any] = None,
    upload_folder: Optional[Any] = None,
    contain_threshold: float = 0.8,
    intersection_threshold: float = 0.3
) -> Optional[HybridElementExtractor]:
    """
    建立混合元素提取器
    
    Args:
        mineru_extractor: MinerU提取器（可選，自動建立）
        baidu_ocr_extractor: 百度OCR提取器（可選，自動建立）
        parser_service: FileParserService例項（用於建立MinerU提取器）
        upload_folder: 上傳資料夾路徑（用於建立MinerU提取器）
        contain_threshold: 包含判斷閾值
        intersection_threshold: 交集判斷閾值
    
    Returns:
        HybridElementExtractor例項，如果無法建立則返回None
    """
    from pathlib import Path
    
    # 建立MinerU提取器
    if mineru_extractor is None:
        if parser_service is None or upload_folder is None:
            logger.error("建立混合提取器需要提供 parser_service 和 upload_folder，或者直接提供 mineru_extractor")
            return None
        
        if isinstance(upload_folder, str):
            upload_folder = Path(upload_folder)
        
        mineru_extractor = MinerUElementExtractor(parser_service, upload_folder)
        logger.info("✅ MinerU提取器已建立")
    
    # 建立百度OCR提取器
    if baidu_ocr_extractor is None:
        try:
            from services.ai_providers.ocr import create_baidu_accurate_ocr_provider
            baidu_provider = create_baidu_accurate_ocr_provider()
            if baidu_provider is None:
                logger.warning("無法建立百度高精度OCR Provider")
                return None
            baidu_ocr_extractor = BaiduAccurateOCRElementExtractor(baidu_provider)
            logger.info("✅ 百度高精度OCR提取器已建立")
        except Exception as e:
            logger.error(f"建立百度高精度OCR提取器失敗: {e}")
            return None
    
    return HybridElementExtractor(
        mineru_extractor=mineru_extractor,
        baidu_ocr_extractor=baidu_ocr_extractor,
        contain_threshold=contain_threshold,
        intersection_threshold=intersection_threshold
    )

