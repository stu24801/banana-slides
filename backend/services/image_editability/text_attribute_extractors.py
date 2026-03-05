"""
文字屬性提取器 - 從文字區域影象中提取文字的視覺屬性

包含：
- TextStyleResult: 文字樣式資料結構
- TextAttributeExtractor: 提取器抽象介面
- CaptionModelTextAttributeExtractor: 基於Caption Model的預設實現
- TextAttributeExtractorRegistry: 提取器登錄檔
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image
from services.prompts import get_text_attribute_extraction_prompt

logger = logging.getLogger(__name__)


@dataclass
class ColoredSegment:
    """
    帶顏色的文字片段
    
    用於表示一段文字及其顏色，支援 LaTeX 公式
    """
    text: str  # 文字內容（如果是公式則為 LaTeX 格式）
    color_rgb: Tuple[int, int, int] = (0, 0, 0)  # RGB顏色 (0-255)
    is_latex: bool = False  # 是否為 LaTeX 公式
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        result = {
            'text': self.text,
            'color': f"#{self.color_rgb[0]:02x}{self.color_rgb[1]:02x}{self.color_rgb[2]:02x}"
        }
        if self.is_latex:
            result['is_latex'] = True
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColoredSegment':
        """從字典建立例項"""
        text = data.get('text', '')
        color = data.get('color', '#000000')
        is_latex = bool(data.get('is_latex', False))
        
        # 解析顏色
        if isinstance(color, str):
            color = color.lstrip('#')
            if len(color) == 3:
                color = ''.join(c * 2 for c in color)
            try:
                r = int(color[0:2], 16)
                g = int(color[2:4], 16)
                b = int(color[4:6], 16)
                color_rgb = (r, g, b)
            except (ValueError, IndexError):
                color_rgb = (0, 0, 0)
        else:
            color_rgb = (0, 0, 0)
        return cls(text=text, color_rgb=color_rgb, is_latex=is_latex)


@dataclass
class TextStyleResult:
    """
    文字樣式資料結構
    
    包含從文字區域影象中提取的視覺屬性
    
    Note:
        字型大小不在此處提取，因為傳入的是裁剪後的子圖，無法準確估算。
        字型大小應由 PPTXBuilder.calculate_font_size 根據bbox計算。
    """
    # 字型顏色 RGB (0-255) - 預設顏色，用於整體顏色或兜底
    font_color_rgb: Tuple[int, int, int] = (0, 0, 0)
    
    # 帶顏色的文字片段列表 - 支援一行文字多種顏色
    # 如果有值，渲染時優先使用這個，文字內容也以這裡的為準
    colored_segments: List[ColoredSegment] = field(default_factory=list)
    
    # 是否粗體
    is_bold: bool = False
    
    # 是否斜體
    is_italic: bool = False
    
    # 是否有下劃線
    is_underline: bool = False
    
    # 文字對齊方式 - 可選 ('left', 'center', 'right', 'justify')
    text_alignment: Optional[str] = None
    
    # 置信度 (0.0-1.0)
    confidence: float = 1.0
    
    # 額外的後設資料
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        result = asdict(self)
        # 將 tuple 轉換為 list 以便 JSON 序列化
        result['font_color_rgb'] = list(self.font_color_rgb)
        # 轉換 colored_segments
        result['colored_segments'] = [seg.to_dict() if isinstance(seg, ColoredSegment) else seg for seg in self.colored_segments]
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TextStyleResult':
        """從字典建立例項"""
        if 'font_color_rgb' in data and isinstance(data['font_color_rgb'], list):
            data['font_color_rgb'] = tuple(data['font_color_rgb'])
        # 轉換 colored_segments
        if 'colored_segments' in data:
            data['colored_segments'] = [
                ColoredSegment.from_dict(seg) if isinstance(seg, dict) else seg 
                for seg in data['colored_segments']
            ]
        return cls(**data)
    
    def get_hex_color(self) -> str:
        """獲取十六進位制顏色值（預設顏色）"""
        r, g, b = self.font_color_rgb
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def get_full_text(self) -> str:
        """獲取完整的文字內容（從 colored_segments 拼接）"""
        if self.colored_segments:
            return ''.join(seg.text for seg in self.colored_segments)
        return ""
    
    def has_multi_color(self) -> bool:
        """是否有多種顏色"""
        if not self.colored_segments or len(self.colored_segments) <= 1:
            return False
        colors = set(seg.color_rgb for seg in self.colored_segments)
        return len(colors) > 1


class TextAttributeExtractor(ABC):
    """
    文字屬性提取器抽象介面
    
    用於從文字區域影象中提取文字的視覺屬性，支援接入多種實現：
    - CaptionModelTextAttributeExtractor: 使用視覺語言模型（如Gemini）分析影象
    - 未來可擴充套件：基於傳統CV的方法、專用OCR模型等
    """
    
    @abstractmethod
    def extract(
        self,
        image: Union[str, Image.Image],
        text_content: Optional[str] = None,
        **kwargs
    ) -> TextStyleResult:
        """
        從文字區域影象中提取文字樣式屬性
        
        Args:
            image: 文字區域的影象，可以是檔案路徑或PIL Image物件
            text_content: 文字內容（可選，某些實現可能用於輔助識別）
            **kwargs: 其他由具體實現自定義的引數
        
        Returns:
            TextStyleResult物件，包含提取的文字樣式屬性
        """
        pass
    
    @abstractmethod
    def supports_batch(self) -> bool:
        """
        是否支援批次處理
        
        Returns:
            如果支援批次處理返回True
        """
        pass
    
    def extract_batch(
        self,
        items: List[Tuple[Union[str, Image.Image], Optional[str]]],
        **kwargs
    ) -> List[TextStyleResult]:
        """
        批次提取文字樣式屬性
        
        預設實現：逐個呼叫extract方法
        子類可以覆蓋此方法以實現更高效的批次處理
        
        Args:
            items: 列表，每個元素是 (image, text_content) 元組
            **kwargs: 其他引數
        
        Returns:
            TextStyleResult列表
        """
        results = []
        for image, text_content in items:
            try:
                result = self.extract(image, text_content, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"批次提取文字屬性失敗: {e}")
                # 返回預設結果
                results.append(TextStyleResult(confidence=0.0))
        return results


class CaptionModelTextAttributeExtractor(TextAttributeExtractor):
    """
    基於Caption Model（視覺語言模型）的文字屬性提取器
    
    使用視覺語言模型（如Gemini）分析文字區域影象，
    透過生成JSON的方式獲取字型顏色、是否粗體、是否斜體等屬性。
    """
    @staticmethod
    def build_prompt(text_content: Optional[str] = None) -> str:
        """
        構建合併後的prompt
        如果text_content存在則插入提示，否則省略
        """
        if text_content:
            content_hint = f'圖片中的文字內容是: "{text_content}"'
        else:
            content_hint = ""
        return get_text_attribute_extraction_prompt(content_hint=content_hint)
    
    def __init__(self, ai_service, prompt_template: Optional[str] = None):
        """
        初始化Caption Model文字屬性提取器
        
        Args:
            ai_service: AIService例項（需要支援generate_json方法和圖片輸入）
            prompt_template: 自定義的prompt模板（可選），必須使用 {content_hint} 作為佔位符
        """
        self.ai_service = ai_service
        self.prompt_template = prompt_template
    
    def supports_batch(self) -> bool:
        """當前實現不支援批次處理"""
        return False
    
    def extract(
        self,
        image: Union[str, Image.Image],
        text_content: Optional[str] = None,
        **kwargs
    ) -> TextStyleResult:
        """
        使用Caption Model提取文字樣式屬性
        
        Args:
            image: 文字區域的影象
            text_content: 文字內容（可選，用於輔助識別）
            **kwargs: 
                - thinking_budget: int, 思考預算，預設500
        
        Returns:
            TextStyleResult物件
        """
        thinking_budget = kwargs.get('thinking_budget', 500)
        
        try:
            # 準備圖片
            if isinstance(image, str):
                pil_image = Image.open(image)
            else:
                pil_image = image
            
            # 構建prompt
            # 統一使用 content_hint 格式
            if text_content:
                content_hint = f'圖片中的文字內容是: "{text_content}"'
            else:
                content_hint = ""
            
            if self.prompt_template:
                # 自定義模板必須使用 {content_hint} 佔位符
                prompt = self.prompt_template.format(content_hint=content_hint)
            else:
                prompt = get_text_attribute_extraction_prompt(content_hint=content_hint)
            
            # 呼叫AI服務（需要支援圖片輸入的generate_json）
            # 這裡假設text_provider支援帶圖片的generate方法
            result_json = self._call_vision_model(pil_image, prompt, thinking_budget)
            
            # 解析結果
            return self._parse_result(result_json)
        
        except Exception as e:
            logger.error(f"CaptionModelTextAttributeExtractor提取失敗: {e}", exc_info=True)
            return TextStyleResult(confidence=0.0, metadata={'error': str(e)})
    
    def _call_vision_model(self, image: Image.Image, prompt: str, thinking_budget: int) -> Dict[str, Any]:
        """
        呼叫視覺語言模型，使用 ai_service.generate_json_with_image（帶重試機制）
        
        Args:
            image: PIL Image物件
            prompt: 提示詞
            thinking_budget: 思考預算
        
        Returns:
            解析後的JSON結果
        """
        import tempfile
        import os
        
        # 儲存臨時圖片檔案
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            tmp_path = tmp_file.name
            image.save(tmp_path)
        
        try:
            # 使用 ai_service.generate_json_with_image（帶重試機制）
            result = self.ai_service.generate_json_with_image(
                prompt=prompt,
                image_path=tmp_path,
                thinking_budget=thinking_budget
            )
            return result if isinstance(result, dict) else {}
        
        except ValueError as e:
            # text_provider 不支援圖片輸入
            logger.warning(f"text_provider不支援圖片輸入: {e}")
            return {}
        
        except Exception as e:
            # JSON 解析失敗（重試3次後仍失敗）
            logger.error(f"生成JSON失敗（已重試3次）: {e}")
            return {}
        
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        """
        將十六進位制顏色轉換為RGB元組
        
        Args:
            hex_color: 十六進位制顏色，如 "#FF6B6B" 或 "FF6B6B"
        
        Returns:
            RGB元組 (R, G, B)
        """
        # 移除 # 字首
        hex_color = hex_color.lstrip('#')
        
        # 處理簡寫格式 (如 #FFF -> #FFFFFF)
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        
        if len(hex_color) != 6:
            return (0, 0, 0)  # 無效格式，返回黑色
        
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return (r, g, b)
        except ValueError:
            return (0, 0, 0)
    
    def _parse_result(self, result_json: Dict[str, Any]) -> TextStyleResult:
        """
        解析AI返回的JSON結果
        
        Args:
            result_json: AI返回的JSON字典，支援兩種格式：
                - 新格式：包含 colored_segments 陣列（文字-顏色對）
                - 舊格式：包含 font_color 單一顏色
        
        Returns:
            TextStyleResult物件
        """
        if not result_json:
            return TextStyleResult(confidence=0.0)
        
        try:
            # 解析 colored_segments（新格式：支援一行多顏色）
            colored_segments = []
            segments_data = result_json.get('colored_segments', [])
            
            if segments_data and isinstance(segments_data, list):
                for seg in segments_data:
                    if isinstance(seg, dict):
                        colored_segments.append(ColoredSegment.from_dict(seg))
            
            # 計算預設顏色（從 segments 取第一個，或用舊格式的 font_color）
            if colored_segments:
                font_color_rgb = colored_segments[0].color_rgb
            else:
                # 相容舊格式
                font_color_hex = result_json.get('font_color', '#000000')
                if isinstance(font_color_hex, str):
                    font_color_rgb = self._hex_to_rgb(font_color_hex)
                else:
                    font_color_rgb = (0, 0, 0)
            
            # 解析布林值
            is_bold = bool(result_json.get('is_bold', False))
            is_italic = bool(result_json.get('is_italic', False))
            is_underline = bool(result_json.get('is_underline', False))
            
            # 解析文字對齊方式
            text_alignment = result_json.get('text_alignment')
            if text_alignment not in ('left', 'center', 'right', 'justify', None):
                text_alignment = None
            
            return TextStyleResult(
                font_color_rgb=font_color_rgb,
                colored_segments=colored_segments,
                is_bold=is_bold,
                is_italic=is_italic,
                is_underline=is_underline,
                text_alignment=text_alignment,
                confidence=0.9,  # 模型返回的結果給予較高置信度
                metadata={'source': 'caption_model', 'raw_response': result_json}
            )
        
        except Exception as e:
            logger.error(f"解析結果失敗: {e}")
            return TextStyleResult(confidence=0.0, metadata={'error': str(e)})
    
    def extract_batch_with_full_image(
        self,
        full_image: Union[str, Image.Image],
        text_elements: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, TextStyleResult]:
        """
        【新邏輯】使用全圖一次性提取所有文字元素的樣式屬性
        
        優勢：模型可以看到全域性上下文，提高分析準確性
        
        Args:
            full_image: 完整的頁面圖片，可以是檔案路徑或PIL Image物件
            text_elements: 文字元素列表，每個元素包含：
                - element_id: 元素唯一標識
                - bbox: 邊界框 [x0, y0, x1, y1]
                - content: 文字內容
            **kwargs:
                - thinking_budget: int, 思考預算，預設1000
        
        Returns:
            字典，key為element_id，value為TextStyleResult
        """
        import json
        import tempfile
        from services.prompts import get_batch_text_attribute_extraction_prompt
        
        thinking_budget = kwargs.get('thinking_budget', 1000)
        
        if not text_elements:
            return {}
        
        try:
            # 準備圖片
            if isinstance(full_image, str):
                pil_image = Image.open(full_image)
                tmp_path = full_image  # 如果已經是路徑，直接使用
                need_cleanup = False
            else:
                pil_image = full_image
                # 儲存臨時圖片檔案
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_path = tmp_file.name
                    pil_image.save(tmp_path)
                need_cleanup = True
            
            # 構建文字元素的 JSON 描述
            elements_for_prompt = []
            for elem in text_elements:
                elements_for_prompt.append({
                    'element_id': elem['element_id'],
                    'bbox': elem['bbox'],
                    'content': elem['content']
                })
            
            text_elements_json = json.dumps(elements_for_prompt, ensure_ascii=False, indent=2)
            
            # 構建 prompt
            prompt = get_batch_text_attribute_extraction_prompt(text_elements_json)
            
            # 呼叫 ai_service.generate_json_with_image（帶重試機制）
            try:
                result = self.ai_service.generate_json_with_image(
                    prompt=prompt,
                    image_path=tmp_path,
                    thinking_budget=thinking_budget
                )
                
                # 確保結果是列表
                if isinstance(result, list):
                    result_list = result
                elif isinstance(result, dict):
                    # 如果返回的是字典，嘗試獲取列表
                    result_list = result.get('results', [result])
                else:
                    result_list = []
                
                # 解析結果
                return self._parse_batch_result(result_list, text_elements)
            
            except ValueError as e:
                logger.warning(f"text_provider不支援圖片輸入: {e}")
                return {}
            
            except Exception as e:
                logger.error(f"批次提取JSON生成失敗（已重試3次）: {e}")
                return {}
                
            finally:
                if need_cleanup:
                    import os
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
        
        except Exception as e:
            logger.error(f"批次提取文字屬性失敗: {e}", exc_info=True)
            return {}
    
    def _parse_batch_result(
        self,
        result_list: List[Dict[str, Any]],
        original_elements: List[Dict[str, Any]]
    ) -> Dict[str, TextStyleResult]:
        """
        解析批次提取的 AI 返回結果
        
        Args:
            result_list: AI 返回的 JSON 列表，每個元素包含樣式屬性
            original_elements: 原始輸入的元素列表，用於匹配 element_id
        
        Returns:
            字典，key 為 element_id，value 為 TextStyleResult
        """
        results = {}
        
        # 建立 element_id 到原始元素的對映，用於回退
        original_map = {elem['element_id']: elem for elem in original_elements}
        
        for item in result_list:
            try:
                element_id = item.get('element_id')
                if not element_id:
                    continue
                
                # 解析顏色（十六進位制格式）
                font_color_hex = item.get('font_color', '#000000')
                if isinstance(font_color_hex, str):
                    font_color_rgb = self._hex_to_rgb(font_color_hex)
                else:
                    font_color_rgb = (0, 0, 0)
                
                # 解析布林值
                is_bold = bool(item.get('is_bold', False))
                is_italic = bool(item.get('is_italic', False))
                is_underline = bool(item.get('is_underline', False))
                
                # 解析文字對齊方式
                text_alignment = item.get('text_alignment')
                if text_alignment not in ('left', 'center', 'right', 'justify', None):
                    text_alignment = None
                
                results[element_id] = TextStyleResult(
                    font_color_rgb=font_color_rgb,
                    is_bold=is_bold,
                    is_italic=is_italic,
                    is_underline=is_underline,
                    text_alignment=text_alignment,
                    confidence=0.9,
                    metadata={'source': 'batch_caption_model', 'raw_response': item}
                )
                
            except Exception as e:
                logger.warning(f"解析元素 {item.get('element_id', 'unknown')} 的樣式失敗: {e}")
                continue
        
        logger.info(f"批次解析完成: 成功 {len(results)}/{len(original_elements)} 個元素")
        return results


class TextAttributeExtractorRegistry:
    """
    文字屬性提取器登錄檔
    
    管理不同元素型別應該使用哪個文字屬性提取器：
    - 普通文字 → CaptionModelTextAttributeExtractor
    - 標題文字 → 可使用不同配置的提取器
    - 其他型別 → 預設提取器
    
    使用方式：
        >>> registry = TextAttributeExtractorRegistry()
        >>> registry.register('text', caption_extractor)
        >>> registry.register('title', title_extractor)
        >>> registry.register_default(caption_extractor)
        >>> 
        >>> extractor = registry.get_extractor('text')
        >>> extractor = registry.get_extractor('unknown_type')  # 返回預設提取器
    """
    
    # 預定義的元素型別分組
    TEXT_TYPES = {'text', 'title', 'paragraph', 'heading', 'header', 'footer', 'list'}
    TABLE_TEXT_TYPES = {'table_cell'}
    
    def __init__(self):
        """初始化登錄檔"""
        self._type_mapping: Dict[str, TextAttributeExtractor] = {}
        self._default_extractor: Optional[TextAttributeExtractor] = None
    
    def register(self, element_type: str, extractor: TextAttributeExtractor) -> 'TextAttributeExtractorRegistry':
        """
        註冊元素型別到提取器的對映
        
        Args:
            element_type: 元素型別（如 'text', 'title' 等）
            extractor: 對應的提取器例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._type_mapping[element_type] = extractor
        logger.debug(f"註冊文字屬性提取器: {element_type} -> {extractor.__class__.__name__}")
        return self
    
    def register_types(self, element_types: List[str], extractor: TextAttributeExtractor) -> 'TextAttributeExtractorRegistry':
        """
        批次註冊多個元素型別到同一個提取器
        
        Args:
            element_types: 元素型別列表
            extractor: 對應的提取器例項
        
        Returns:
            self，支援鏈式呼叫
        """
        for t in element_types:
            self.register(t, extractor)
        return self
    
    def register_default(self, extractor: TextAttributeExtractor) -> 'TextAttributeExtractorRegistry':
        """
        註冊預設提取器（當沒有特定型別對映時使用）
        
        Args:
            extractor: 預設提取器例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._default_extractor = extractor
        logger.debug(f"註冊預設文字屬性提取器: {extractor.__class__.__name__}")
        return self
    
    def get_extractor(self, element_type: Optional[str]) -> Optional[TextAttributeExtractor]:
        """
        根據元素型別獲取對應的提取器
        
        Args:
            element_type: 元素型別，None表示使用預設提取器
        
        Returns:
            對應的提取器，如果沒有註冊則返回預設提取器
        """
        if element_type is None:
            return self._default_extractor
        
        # 先查詢精確匹配
        if element_type in self._type_mapping:
            return self._type_mapping[element_type]
        
        # 返回預設提取器
        return self._default_extractor
    
    def get_all_extractors(self) -> List[TextAttributeExtractor]:
        """
        獲取所有已註冊的提取器（去重）
        
        Returns:
            提取器列表
        """
        extractors = list(set(self._type_mapping.values()))
        if self._default_extractor and self._default_extractor not in extractors:
            extractors.append(self._default_extractor)
        return extractors
    
    @classmethod
    def create_default(
        cls,
        caption_extractor: Optional[TextAttributeExtractor] = None
    ) -> 'TextAttributeExtractorRegistry':
        """
        建立預設配置的登錄檔
        
        預設配置：
        - 所有文字型別 → CaptionModelTextAttributeExtractor
        - 其他型別 → 預設提取器
        
        Args:
            caption_extractor: Caption Model提取器例項
        
        Returns:
            配置好的登錄檔例項
        """
        registry = cls()
        
        if not caption_extractor:
            logger.warning("建立TextAttributeExtractorRegistry時未提供任何extractor")
            return registry
        
        # 設定預設提取器
        registry.register_default(caption_extractor)
        
        # 所有文字型別使用相同的提取器
        registry.register_types(list(cls.TEXT_TYPES), caption_extractor)
        registry.register_types(list(cls.TABLE_TEXT_TYPES), caption_extractor)
        
        logger.info(f"建立預設TextAttributeExtractorRegistry: "
                   f"預設提取器->{caption_extractor.__class__.__name__}")
        
        return registry

