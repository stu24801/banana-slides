"""
座標對映工具 - 處理父子圖片間的座標轉換
"""
from typing import Tuple
from .data_models import BBox


class CoordinateMapper:
    """座標對映工具 - 處理父子圖片間的座標轉換"""
    
    @staticmethod
    def local_to_global(
        local_bbox: BBox,
        parent_bbox: BBox,
        local_image_size: Tuple[int, int],
        parent_image_size: Tuple[int, int]
    ) -> BBox:
        """
        將子圖的區域性座標轉換為父圖（或根圖）的全域性座標
        
        Args:
            local_bbox: 子圖座標系中的bbox
            parent_bbox: 子圖在父圖中的位置
            local_image_size: 子圖尺寸 (width, height)
            parent_image_size: 父圖尺寸 (width, height)
        
        Returns:
            在父圖座標系中的bbox
        """
        # 計算縮放比例（子圖實際畫素 vs 子圖在父圖中的bbox尺寸）
        scale_x = parent_bbox.width / local_image_size[0]
        scale_y = parent_bbox.height / local_image_size[1]
        
        # 先縮放到父圖bbox的尺寸
        scaled_bbox = local_bbox.scale(scale_x, scale_y)
        
        # 再平移到父圖bbox的位置
        global_bbox = scaled_bbox.translate(parent_bbox.x0, parent_bbox.y0)
        
        return global_bbox
    
    @staticmethod
    def global_to_local(
        global_bbox: BBox,
        parent_bbox: BBox,
        local_image_size: Tuple[int, int],
        parent_image_size: Tuple[int, int]
    ) -> BBox:
        """
        將父圖的全域性座標轉換為子圖的區域性座標（逆向對映）
        
        Args:
            global_bbox: 父圖座標系中的bbox
            parent_bbox: 子圖在父圖中的位置
            local_image_size: 子圖尺寸 (width, height)
            parent_image_size: 父圖尺寸 (width, height)
        
        Returns:
            在子圖座標系中的bbox
        """
        # 先平移（相對於parent_bbox的原點）
        translated_bbox = global_bbox.translate(-parent_bbox.x0, -parent_bbox.y0)
        
        # 再縮放
        scale_x = local_image_size[0] / parent_bbox.width
        scale_y = local_image_size[1] / parent_bbox.height
        
        local_bbox = translated_bbox.scale(scale_x, scale_y)
        
        return local_bbox

