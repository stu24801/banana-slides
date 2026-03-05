"""
輔助函式和工具方法

純函式，不依賴任何具體實現
"""
import logging
import tempfile
from typing import List
from PIL import Image

from .data_models import EditableElement, BBox

logger = logging.getLogger(__name__)


def collect_bboxes_from_elements(elements: List[EditableElement]) -> List[tuple]:
    """
    收集當前層級元素的bbox列表（不遞迴到子元素）
    
    Args:
        elements: 元素列表
        
    Returns:
        bbox元組列表 [(x0, y0, x1, y1), ...]
    """
    bboxes = []
    for elem in elements:
        bbox_tuple = elem.bbox.to_tuple()
        bboxes.append(bbox_tuple)
        logger.debug(f"元素 {elem.element_id} ({elem.element_type}): bbox={bbox_tuple}")
    return bboxes


def crop_element_from_image(
    source_image_path: str,
    bbox: BBox
) -> str:
    """
    從源圖片中裁剪出元素區域
    
    Args:
        source_image_path: 源圖片路徑
        bbox: 裁剪區域
        
    Returns:
        裁剪後圖片的臨時檔案路徑
    """
    img = Image.open(source_image_path)
    
    # 裁剪
    crop_box = (int(bbox.x0), int(bbox.y0), int(bbox.x1), int(bbox.y1))
    cropped = img.crop(crop_box)
    
    # 儲存到臨時檔案
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        cropped.save(tmp.name)
        return tmp.name


def should_recurse_into_element(
    element: EditableElement,
    parent_image_size: tuple,
    min_image_size: int,
    min_image_area: int,
    max_child_coverage_ratio: float
) -> bool:
    """
    判斷是否應該對元素進行遞迴分析
    
    Args:
        element: 待判斷的元素
        parent_image_size: 父圖尺寸 (width, height)
        min_image_size: 最小圖片尺寸
        min_image_area: 最小圖片面積
        max_child_coverage_ratio: 最大子圖覆蓋比例
    """
    # 如果已經有子元素（例如表格單元格），不再遞迴
    if element.children:
        logger.debug(f"  元素 {element.element_id} 已有 {len(element.children)} 個子元素，不遞迴")
        return False
    
    # 只對圖片和圖表型別遞迴
    if element.element_type not in ['image', 'figure', 'chart', 'table']:
        return False
    
    # 檢查尺寸是否足夠大
    bbox = element.bbox
    if bbox.width < min_image_size or bbox.height < min_image_size:
        logger.debug(f"  元素 {element.element_id} 尺寸過小 ({bbox.width}x{bbox.height})，不遞迴")
        return False
    
    if bbox.area < min_image_area:
        logger.debug(f"  元素 {element.element_id} 面積過小 ({bbox.area})，不遞迴")
        return False
    
    # 檢查子圖是否佔據父圖絕大部分面積
    parent_width, parent_height = parent_image_size
    parent_area = parent_width * parent_height
    coverage_ratio = bbox.area / parent_area if parent_area > 0 else 0
    
    if coverage_ratio > max_child_coverage_ratio:
        logger.info(f"  元素 {element.element_id} 佔父圖面積 {coverage_ratio*100:.1f}% (>{max_child_coverage_ratio*100:.0f}%)，不遞迴")
        return False
    
    return True
