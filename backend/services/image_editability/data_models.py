"""
資料模型 - 圖片可編輯化服務的核心資料結構
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class BBox:
    """邊界框座標"""
    x0: float
    y0: float
    x1: float
    y1: float
    
    @property
    def width(self) -> float:
        return self.x1 - self.x0
    
    @property
    def height(self) -> float:
        return self.y1 - self.y0
    
    @property
    def area(self) -> float:
        return self.width * self.height
    
    def to_tuple(self) -> Tuple[float, float, float, float]:
        """轉換為元組格式 (x0, y0, x1, y1)"""
        return (self.x0, self.y0, self.x1, self.y1)
    
    def to_dict(self) -> Dict[str, float]:
        """轉換為字典格式"""
        return {
            'x0': self.x0,
            'y0': self.y0,
            'x1': self.x1,
            'y1': self.y1
        }
    
    def scale(self, scale_x: float, scale_y: float) -> 'BBox':
        """縮放bbox"""
        return BBox(
            x0=self.x0 * scale_x,
            y0=self.y0 * scale_y,
            x1=self.x1 * scale_x,
            y1=self.y1 * scale_y
        )
    
    def translate(self, offset_x: float, offset_y: float) -> 'BBox':
        """平移bbox"""
        return BBox(
            x0=self.x0 + offset_x,
            y0=self.y0 + offset_y,
            x1=self.x1 + offset_x,
            y1=self.y1 + offset_y
        )


@dataclass
class EditableElement:
    """可編輯元素"""
    element_id: str  # 唯一標識
    element_type: str  # text, image, table, figure, equation等
    bbox: BBox  # 在父容器（EditableImage）座標系中的位置
    bbox_global: BBox  # 在根圖片（最頂層EditableImage）座標系中的位置（預計算儲存，避免前端/後續使用時重新遍歷計算）
    content: Optional[str] = None  # 文字內容、HTML表格等
    image_path: Optional[str] = None  # 圖片路徑（MinerU提取的）
    
    # 遞迴子元素（如果是圖片或圖表，可能有子元素）
    children: List['EditableElement'] = field(default_factory=list)
    
    # 子圖的inpaint背景（如果此元素是遞迴分析的圖片/圖表）
    inpainted_background_path: Optional[str] = None
    
    # 後設資料
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（可序列化）"""
        result = {
            'element_id': self.element_id,
            'element_type': self.element_type,
            'bbox': self.bbox.to_dict(),
            'bbox_global': self.bbox_global.to_dict(),
            'content': self.content,
            'image_path': self.image_path,
            'inpainted_background_path': self.inpainted_background_path,
            'metadata': self.metadata,
            'children': [child.to_dict() for child in self.children]
        }
        return result


@dataclass
class EditableImage:
    """可編輯化的圖片結構"""
    image_id: str  # 唯一標識
    image_path: str  # 原始圖片路徑
    width: int  # 圖片寬度
    height: int  # 圖片高度
    
    # 所有提取的元素
    elements: List[EditableElement] = field(default_factory=list)
    
    # Inpaint後的背景圖（消除所有元素）
    clean_background: Optional[str] = None
    
    # 遞迴層級
    depth: int = 0
    
    # 父圖片ID（如果是子圖）
    parent_id: Optional[str] = None
    
    # 後設資料
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典（可序列化）"""
        return {
            'image_id': self.image_id,
            'image_path': self.image_path,
            'width': self.width,
            'height': self.height,
            'elements': [elem.to_dict() for elem in self.elements],
            'clean_background': self.clean_background,
            'depth': self.depth,
            'parent_id': self.parent_id,
            'metadata': self.metadata
        }

