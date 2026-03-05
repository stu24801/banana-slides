"""
掩碼影象生成工具
用於從邊界框（bbox）生成黑白掩碼影象
"""
import logging
from typing import List, Tuple, Union, Callable
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


# ============== Bbox 工具函式 ==============

def normalize_bbox(bbox: Union[Tuple, List, dict]) -> Tuple[int, int, int, int]:
    """
    將各種格式的bbox標準化為 (x1, y1, x2, y2) 元組格式
    
    支援的輸入格式：
    - 元組/列表: (x1, y1, x2, y2)
    - 字典: {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
    - 字典: {"x": x, "y": y, "width": w, "height": h}
    """
    if isinstance(bbox, dict):
        if 'x1' in bbox:
            return (bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2'])
        elif 'x' in bbox:
            return (bbox['x'], bbox['y'], 
                   bbox['x'] + bbox['width'], 
                   bbox['y'] + bbox['height'])
        else:
            raise ValueError(f"無法識別的bbox字典格式: {bbox}")
    elif isinstance(bbox, (tuple, list)) and len(bbox) == 4:
        return tuple(bbox)
    else:
        raise ValueError(f"無法識別的bbox格式: {bbox}")


def normalize_bboxes(bboxes: List[Union[Tuple, List, dict]]) -> List[Tuple[int, int, int, int]]:
    """批次標準化bbox列表"""
    result = []
    for bbox in bboxes:
        try:
            result.append(normalize_bbox(bbox))
        except ValueError as e:
            logger.warning(str(e))
    return result


def merge_two_boxes(box1: Tuple, box2: Tuple) -> Tuple[int, int, int, int]:
    """合併兩個bbox為一個包含它們的最小bbox"""
    return (
        min(box1[0], box2[0]),
        min(box1[1], box2[1]),
        max(box1[2], box2[2]),
        max(box1[3], box2[3])
    )


def _iterative_merge(
    bboxes: List[Tuple[int, int, int, int]],
    should_merge_fn: Callable[[Tuple, Tuple], bool]
) -> List[Tuple[int, int, int, int]]:
    """
    通用的迭代合併演算法
    
    Args:
        bboxes: 標準化後的bbox列表
        should_merge_fn: 判斷兩個bbox是否應該合併的函式
    
    Returns:
        合併後的bbox列表
    """
    if not bboxes:
        return []
    if len(bboxes) == 1:
        return list(bboxes)
    
    normalized = list(bboxes)
    merged = True
    
    while merged:
        merged = False
        new_boxes = []
        used = set()
        
        for i, box1 in enumerate(normalized):
            if i in used:
                continue
            
            current_box = box1
            
            for j, box2 in enumerate(normalized):
                if j <= i or j in used:
                    continue
                
                if should_merge_fn(current_box, box2):
                    current_box = merge_two_boxes(current_box, box2)
                    used.add(j)
                    merged = True
            
            new_boxes.append(current_box)
            used.add(i)
        
        normalized = new_boxes
    
    return normalized


def create_mask_from_bboxes(
    image_size: Tuple[int, int],
    bboxes: List[Union[Tuple[int, int, int, int], dict]],
    mask_color: Tuple[int, int, int] = (255, 255, 255),
    background_color: Tuple[int, int, int] = (0, 0, 0),
    expand_pixels: int = 0
) -> Image.Image:
    """
    從邊界框列表建立掩碼影象
    
    Args:
        image_size: 影象尺寸 (width, height)
        bboxes: 邊界框列表，每個元素可以是：
                - 元組格式: (x1, y1, x2, y2) 其中 (x1,y1) 是左上角，(x2,y2) 是右下角
                - 字典格式: {"x": x, "y": y, "width": w, "height": h}
                - 字典格式: {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        mask_color: 掩碼區域的顏色（預設白色），表示需要消除的區域
        background_color: 背景區域的顏色（預設黑色），表示保留的區域
        expand_pixels: 擴充套件畫素數，可以讓掩碼區域略微擴大（用於更好的消除效果）
        
    Returns:
        PIL Image 物件，RGB 模式的掩碼影象
    """
    try:
        # 建立黑色背景影象
        mask = Image.new('RGB', image_size, background_color)
        draw = ImageDraw.Draw(mask)
        
        logger.info(f"建立掩碼影象，尺寸: {image_size}, bbox數量: {len(bboxes)}")
        
        # 繪製每個 bbox 為白色區域
        bbox_list = []  # 用於記錄所有bbox座標
        for i, bbox in enumerate(bboxes):
            # 解析不同格式的 bbox
            if isinstance(bbox, dict):
                if 'x1' in bbox and 'y1' in bbox and 'x2' in bbox and 'y2' in bbox:
                    # 格式: {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
                    x1 = bbox['x1']
                    y1 = bbox['y1']
                    x2 = bbox['x2']
                    y2 = bbox['y2']
                elif 'x' in bbox and 'y' in bbox and 'width' in bbox and 'height' in bbox:
                    # 格式: {"x": x, "y": y, "width": w, "height": h}
                    x1 = bbox['x']
                    y1 = bbox['y']
                    x2 = x1 + bbox['width']
                    y2 = y1 + bbox['height']
                else:
                    logger.warning(f"無法識別的 bbox 字典格式: {bbox}")
                    continue
            elif isinstance(bbox, (tuple, list)) and len(bbox) == 4:
                # 格式: (x1, y1, x2, y2)
                x1, y1, x2, y2 = bbox
            else:
                logger.warning(f"無法識別的 bbox 格式: {bbox}")
                continue
            
            # 記錄原始座標
            x1_orig, y1_orig, x2_orig, y2_orig = x1, y1, x2, y2
            
            # 應用擴充套件或收縮
            if expand_pixels > 0:
                # 擴充套件
                x1 = max(0, x1 - expand_pixels)
                y1 = max(0, y1 - expand_pixels)
                x2 = min(image_size[0], x2 + expand_pixels)
                y2 = min(image_size[1], y2 + expand_pixels)
            elif expand_pixels < 0:
                # 收縮（向內收縮）
                shrink = abs(expand_pixels)
                x1 = x1 + shrink
                y1 = y1 + shrink
                x2 = x2 - shrink
                y2 = y2 - shrink
                # 確保收縮後仍然有效（寬度和高度必須大於0）
                if x2 <= x1 or y2 <= y1:
                    logger.warning(f"bbox {i+1} 收縮後無效: ({x1}, {y1}, {x2}, {y2})，跳過")
                    continue
            
            # 確保座標在影象範圍內
            x1 = max(0, min(x1, image_size[0]))
            y1 = max(0, min(y1, image_size[1]))
            x2 = max(0, min(x2, image_size[0]))
            y2 = max(0, min(y2, image_size[1]))
            
            # 再次檢查有效性
            if x2 <= x1 or y2 <= y1:
                logger.warning(f"bbox {i+1} 最終座標無效: ({x1}, {y1}, {x2}, {y2})，跳過")
                continue
            
            # 繪製矩形
            draw.rectangle([x1, y1, x2, y2], fill=mask_color)
            width = x2 - x1
            height = y2 - y1
            if expand_pixels > 0:
                bbox_list.append(f"  [{i+1}] 原始: ({x1_orig}, {y1_orig}, {x2_orig}, {y2_orig}) -> 擴充套件後: ({x1}, {y1}, {x2}, {y2}) 尺寸: {width}x{height}")
            elif expand_pixels < 0:
                bbox_list.append(f"  [{i+1}] 原始: ({x1_orig}, {y1_orig}, {x2_orig}, {y2_orig}) -> 收縮後: ({x1}, {y1}, {x2}, {y2}) 尺寸: {width}x{height}")
            else:
                bbox_list.append(f"  [{i+1}] ({x1}, {y1}, {x2}, {y2}) 尺寸: {width}x{height}")
            logger.debug(f"bbox {i+1}: ({x1}, {y1}, {x2}, {y2}) 尺寸: {width}x{height}")
        
        # 輸出所有bbox的詳細資訊
        if bbox_list:
            logger.info(f"新增了 {len(bbox_list)} 個bbox的mask:")
            for bbox_info in bbox_list:
                logger.info(bbox_info)
        
        logger.info(f"掩碼影象建立完成")
        return mask
        
    except Exception as e:
        logger.error(f"建立掩碼影象失敗: {str(e)}", exc_info=True)
        raise


def create_inverse_mask_from_bboxes(
    image_size: Tuple[int, int],
    bboxes: List[Union[Tuple[int, int, int, int], dict]],
    expand_pixels: int = 0
) -> Image.Image:
    """
    建立反向掩碼（保留 bbox 區域，消除其他區域）
    
    Args:
        image_size: 影象尺寸 (width, height)
        bboxes: 邊界框列表
        expand_pixels: 擴充套件畫素數
        
    Returns:
        PIL Image 物件，反向掩碼影象
    """
    # 交換顏色即可
    return create_mask_from_bboxes(
        image_size,
        bboxes,
        mask_color=(0, 0, 0),  # bbox 區域為黑色（保留）
        background_color=(255, 255, 255),  # 背景為白色（消除）
        expand_pixels=expand_pixels
    )


def create_mask_from_image_and_bboxes(
    image: Image.Image,
    bboxes: List[Union[Tuple[int, int, int, int], dict]],
    expand_pixels: int = 0
) -> Image.Image:
    """
    從影象和邊界框建立掩碼（便捷函式）
    
    Args:
        image: 原始影象
        bboxes: 邊界框列表
        expand_pixels: 擴充套件畫素數
        
    Returns:
        掩碼影象
    """
    return create_mask_from_bboxes(
        image.size,
        bboxes,
        expand_pixels=expand_pixels
    )


def visualize_mask_overlay(
    original_image: Image.Image,
    mask_image: Image.Image,
    alpha: float = 0.5
) -> Image.Image:
    """
    將掩碼疊加到原始影象上以便視覺化
    
    Args:
        original_image: 原始影象
        mask_image: 掩碼影象
        alpha: 掩碼透明度 (0.0-1.0)
        
    Returns:
        疊加後的影象
    """
    try:
        # 確保兩個影象尺寸相同
        if original_image.size != mask_image.size:
            logger.warning(f"影象尺寸不匹配，調整掩碼尺寸: {mask_image.size} -> {original_image.size}")
            mask_image = mask_image.resize(original_image.size, Image.LANCZOS)
        
        # 轉換為 RGBA
        if original_image.mode != 'RGBA':
            original_rgba = original_image.convert('RGBA')
        else:
            original_rgba = original_image.copy()
        
        # 建立黑色半透明掩碼用於視覺化
        mask_rgba = Image.new('RGBA', original_image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(mask_rgba)
        
        # 遍歷掩碼影象，將白色區域繪製為黑色半透明
        mask_array = mask_image.load()
        mask_rgba_array = mask_rgba.load()
        
        for y in range(mask_image.size[1]):
            for x in range(mask_image.size[0]):
                pixel = mask_array[x, y]
                # 如果是白色（或接近白色），設定為黑色半透明
                if isinstance(pixel, tuple):
                    brightness = sum(pixel) / len(pixel)
                else:
                    brightness = pixel
                
                if brightness > 200:  # 接近白色
                    mask_rgba_array[x, y] = (0, 0, 0, int(128 * alpha))
        
        # 疊加
        result = Image.alpha_composite(original_rgba, mask_rgba)
        return result.convert('RGB')
        
    except Exception as e:
        logger.error(f"視覺化掩碼疊加失敗: {str(e)}", exc_info=True)
        return original_image


def merge_vertical_nearby_bboxes(
    bboxes: List[Tuple[int, int, int, int]],
    vertical_gap_ratio: float = 0.8,
    horizontal_overlap_ratio: float = 0.3
) -> List[Tuple[int, int, int, int]]:
    """
    合併上下間距很小的邊界框（適用於文字行合併）
    
    合併策略（基於原始bbox判斷，避免雪球效應）：
    - 按y座標排序後，先判斷每對相鄰原始bbox是否應該合併
    - 如果垂直間距小於平均行高的 vertical_gap_ratio 倍
    - 並且在水平方向上有至少 horizontal_overlap_ratio 的重疊
    - 則標記為可合併，最後統一執行合併
    
    Args:
        bboxes: 邊界框列表 [(x1, y1, x2, y2), ...]
        vertical_gap_ratio: 垂直間距閾值，相對於平均行高的比例，預設0.8
        horizontal_overlap_ratio: 水平重疊比例閾值，預設0.3
        
    Returns:
        合併後的邊界框列表
    """
    if not bboxes or len(bboxes) <= 1:
        return list(bboxes) if bboxes else []
    
    normalized = normalize_bboxes(bboxes)
    if not normalized:
        return []
    
    # 按y座標排序（從上到下）
    normalized.sort(key=lambda b: b[1])
    
    # 計算原始bbox的平均行高
    avg_height = sum(b[3] - b[1] for b in normalized) / len(normalized)
    max_vertical_gap = avg_height * vertical_gap_ratio
    
    def get_horizontal_overlap(box1, box2):
        """計算兩個bbox在水平方向的重疊比例（相對於較小的寬度）"""
        overlap_start = max(box1[0], box2[0])
        overlap_end = min(box1[2], box2[2])
        overlap = max(0, overlap_end - overlap_start)
        min_width = min(box1[2] - box1[0], box2[2] - box2[0])
        return overlap / min_width if min_width > 0 else 0
    
    def should_merge_adjacent(box1, box2):
        """判斷兩個相鄰（按y排序）的原始bbox是否應該合併"""
        # 垂直間距 = box2的頂部 - box1的底部
        v_gap = box2[1] - box1[3]
        
        # 如果垂直間距太大，不合並
        if v_gap > max_vertical_gap:
            return False
        
        # 檢查水平重疊
        h_overlap = get_horizontal_overlap(box1, box2)
        if h_overlap >= horizontal_overlap_ratio:
            return True
        
        # 沒有重疊但水平距離很近也合併
        if h_overlap <= 0:
            h_gap = max(0, max(box2[0] - box1[2], box1[0] - box2[2]))
            if h_gap < avg_height:
                return True
        
        return False
    
    # 第一步：基於原始bbox判斷哪些相鄰對應該合併
    merge_with_next = []
    for i in range(len(normalized) - 1):
        merge_with_next.append(should_merge_adjacent(normalized[i], normalized[i + 1]))
    
    # 第二步：根據標記執行合併
    result = []
    current_box = normalized[0]
    
    for i in range(len(merge_with_next)):
        if merge_with_next[i]:
            # 和下一個合併
            current_box = merge_two_boxes(current_box, normalized[i + 1])
        else:
            # 不合並，儲存當前，開始新組
            result.append(current_box)
            current_box = normalized[i + 1]
    
    # 新增最後一個
    result.append(current_box)
    
    logger.info(f"合併相鄰文字行bbox：{len(bboxes)} -> {len(result)}")
    return result


def merge_overlapping_bboxes(
    bboxes: List[Tuple[int, int, int, int]],
    merge_threshold: int = 10
) -> List[Tuple[int, int, int, int]]:
    """
    合併重疊或相鄰的邊界框
    
    Args:
        bboxes: 邊界框列表 [(x1, y1, x2, y2), ...]
        merge_threshold: 合併閾值（畫素），邊界框距離小於此值時會合並
        
    Returns:
        合併後的邊界框列表
    """
    if not bboxes:
        return []
    
    normalized = normalize_bboxes(bboxes)
    if not normalized:
        return []
    
    def should_merge(box1, box2):
        x1, y1, x2, y2 = box1
        bx1, by1, bx2, by2 = box2
        return (x1 - merge_threshold <= bx2 and bx1 <= x2 + merge_threshold and
                y1 - merge_threshold <= by2 and by1 <= y2 + merge_threshold)
    
    result = _iterative_merge(normalized, should_merge)
    logger.info(f"合併邊界框：{len(bboxes)} -> {len(result)}")
    return result

