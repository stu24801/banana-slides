"""
元素提取器 - 抽象不同的元素識別方法

包含：
- ElementExtractor: 提取器抽象介面
- MinerUElementExtractor: MinerU版面分析提取器
- BaiduOCRElementExtractor: 百度表格OCR提取器
- BaiduAccurateOCRElementExtractor: 百度高精度OCR提取器（文字識別）
- ExtractorRegistry: 元素型別到提取器的對映登錄檔
"""
import os
import json
import logging
import tempfile
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Type
from pathlib import Path
from PIL import Image

logger = logging.getLogger(__name__)


class ExtractionContext:
    """提取上下文 - 提取器可能需要的額外資訊"""
    
    def __init__(
        self,
        result_dir: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Args:
            result_dir: 結果目錄（如MinerU的輸出目錄）
            metadata: 其他後設資料
        """
        self.result_dir = result_dir
        self.metadata = metadata or {}


class ExtractionResult:
    """提取結果"""
    
    def __init__(
        self,
        elements: List[Dict[str, Any]],
        context: Optional[ExtractionContext] = None
    ):
        """
        Args:
            elements: 提取的元素列表
            context: 提取上下文（用於後續遞迴處理）
        """
        self.elements = elements
        self.context = context or ExtractionContext()


class ElementExtractor(ABC):
    """
    元素提取器抽象介面
    
    用於抽象不同的元素識別方法，支援接入多種實現：
    - MinerU解析器（當前預設）
    - 百度OCR（用於表格）
    - PaddleOCR
    - Tesseract OCR
    - 其他自定義識別服務
    """
    
    @abstractmethod
    def extract(
        self,
        image_path: str,
        element_type: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        從影象中提取元素
        
        Args:
            image_path: 影象檔案路徑
            element_type: 元素型別提示（如 'table', 'text', 'image'等），可選
            **kwargs: 其他由具體實現自定義的引數
        
        Returns:
            ExtractionResult物件，包含：
            - elements: 元素字典列表，每個字典包含：
                - bbox: List[float] - 邊界框 [x0, y0, x1, y1]
                - type: str - 元素型別（'text', 'image', 'table', 'title'等）
                - content: Optional[str] - 文字內容
                - image_path: Optional[str] - 圖片相對路徑
                - metadata: Dict[str, Any] - 其他後設資料
            - context: 提取上下文（用於後續遞迴處理）
        """
        pass
    
    @abstractmethod
    def supports_type(self, element_type: Optional[str]) -> bool:
        """
        檢查提取器是否支援指定的元素型別
        
        Args:
            element_type: 元素型別（如 'table', 'image'等），None表示通用
        
        Returns:
            是否支援該型別
        """
        pass


class MinerUElementExtractor(ElementExtractor):
    """
    基於MinerU的元素提取器（預設實現）
    
    從MinerU的解析結果中提取文字、圖片、表格等元素
    自包含：自己處理PDF轉換、MinerU解析、結果提取
    """
    
    def __init__(self, parser_service, upload_folder: Path):
        """
        初始化MinerU提取器
        
        Args:
            parser_service: FileParserService例項
            upload_folder: 上傳資料夾路徑
        """
        self._parser_service = parser_service
        self._upload_folder = upload_folder
    
    def supports_type(self, element_type: Optional[str]) -> bool:
        """MinerU支援所有通用型別（除了特殊的表格單元格）"""
        return element_type != 'table_cell'
    
    def extract(
        self,
        image_path: str,
        element_type: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        從影象中提取元素（自動處理PDF轉換和MinerU解析）
        
        支援的kwargs:
        - depth: int, 遞迴深度（用於日誌）
        """
        depth = kwargs.get('depth', 0)
        
        # 獲取圖片尺寸
        img = Image.open(image_path)
        image_size = img.size  # (width, height)
        
        # 1. 檢查快取
        cached_dir = self._find_cache(image_path)
        if cached_dir:
            logger.info(f"{'  ' * depth}使用MinerU快取")
            mineru_result_dir = cached_dir
        else:
            # 2. 解析圖片
            mineru_result_dir = self._parse_image(image_path, depth)
            if not mineru_result_dir:
                return ExtractionResult(elements=[])
        
        # 3. 提取元素
        elements = self._extract_from_result(
            mineru_result_dir=mineru_result_dir,
            target_image_size=image_size,
            depth=depth
        )
        
        # 4. 返回結果（帶上下文）
        context = ExtractionContext(
            result_dir=mineru_result_dir,
            metadata={'source': 'mineru', 'image_size': image_size}
        )
        
        return ExtractionResult(elements=elements, context=context)
    
    def _find_cache(self, image_path: str) -> Optional[str]:
        """查詢快取的MinerU結果"""
        try:
            import hashlib
            import time
            
            img_path = Path(image_path)
            if not img_path.exists():
                return None
            
            mineru_files_dir = self._upload_folder / 'mineru_files'
            if not mineru_files_dir.exists():
                return None
            
            # 簡單策略：不使用快取（更安全）
            return None
            
        except Exception as e:
            logger.debug(f"查詢快取失敗: {e}")
            return None
    
    def _parse_image(self, image_path: str, depth: int) -> Optional[str]:
        """解析圖片，返回MinerU結果目錄"""
        from services.export_service import ExportService
        
        # 轉換為PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_pdf:
            pdf_path = tmp_pdf.name
        
        try:
            ExportService.create_pdf_from_images([image_path], output_file=pdf_path)
            
            # 呼叫MinerU解析
            image_id = str(uuid.uuid4())[:8]
            batch_id, markdown_content, extract_id, error_message, failed_image_count = \
                self._parser_service.parse_file(pdf_path, f"image_{image_id}.pdf")
            
            if error_message or not extract_id:
                logger.error(f"{'  ' * depth}MinerU解析失敗: {error_message}")
                return None
            
            mineru_result_dir = (self._upload_folder / 'mineru_files' / extract_id).resolve()
            if not mineru_result_dir.exists():
                logger.error(f"{'  ' * depth}MinerU結果目錄不存在")
                return None
            
            return str(mineru_result_dir)
        
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)
    
    def _extract_from_result(
        self,
        mineru_result_dir: str,
        target_image_size: Tuple[int, int],
        depth: int
    ) -> List[Dict[str, Any]]:
        """從MinerU結果目錄中提取元素"""
        elements = []
        
        try:
            mineru_dir = Path(mineru_result_dir)
            
            # 載入layout.json和content_list.json
            layout_file = mineru_dir / 'layout.json'
            content_list_files = list(mineru_dir.glob("*_content_list.json"))
            
            if not layout_file.exists() or not content_list_files:
                logger.warning(f"layout.json或content_list.json不存在")
                return []
            
            with open(layout_file, 'r', encoding='utf-8') as f:
                layout_data = json.load(f)
            
            with open(content_list_files[0], 'r', encoding='utf-8') as f:
                content_list = json.load(f)
            
            # 從layout.json提取元素
            if 'pdf_info' not in layout_data or not layout_data['pdf_info']:
                return []
            
            page_info = layout_data['pdf_info'][0]
            source_page_size = page_info.get('page_size', target_image_size)
            
            # 計算縮放比例
            scale_x = target_image_size[0] / source_page_size[0]
            scale_y = target_image_size[1] / source_page_size[1]
            
            # 處理塊的通用函式
            def process_block(block):
                bbox = block.get('bbox')
                block_type = block.get('type', 'text')
                
                if not bbox or len(bbox) != 4:
                    return None
                
                # 過濾掉 type 為 header/footer 且內容僅為 "#" 的特殊標記
                if block_type in ['header', 'footer']:
                    if block.get('lines'):
                        # 提取所有文字內容
                        all_text = []
                        for line in block['lines']:
                            for span in line.get('spans', []):
                                if span.get('type') == 'text' and span.get('content'):
                                    all_text.append(span['content'])
                        # 如果所有文字合併後僅為"#"，則跳過此塊
                        combined_text = ''.join(all_text).strip()
                        if combined_text == '#':
                            return None
                
                # 縮放bbox到目標尺寸
                scaled_bbox = [
                    bbox[0] * scale_x,
                    bbox[1] * scale_y,
                    bbox[2] * scale_x,
                    bbox[3] * scale_y
                ]
                
                # 對於 header/footer，需要根據實際內容判斷型別
                actual_content_type = block_type
                if block_type in ['header', 'footer']:
                    # 檢查是否包含圖片
                    has_image = False
                    if block.get('blocks'):
                        for sub_block in block['blocks']:
                            if sub_block.get('type') == 'image_body':
                                has_image = True
                                break
                    
                    # 檢查是否包含文字
                    has_text = False
                    if block.get('lines'):
                        for line in block['lines']:
                            for span in line.get('spans', []):
                                if span.get('type') in ['text', 'inline_equation'] and span.get('content', '').strip():
                                    has_text = True
                                    break
                            if has_text:
                                break
                    
                    # 根據內容判斷實際型別
                    if has_image and not has_text:
                        actual_content_type = 'image'
                    elif has_text:
                        actual_content_type = 'text'  # 將 header/footer 轉換為 text
                    else:
                        # 預設當作文字處理
                        actual_content_type = 'text'
                
                # 輔助函式：從 lines 提取文字
                def extract_text_from_lines(lines):
                    """從 lines 陣列提取所有文字內容"""
                    line_texts = []
                    for line in lines:
                        span_texts = []
                        for span in line.get('spans', []):
                            span_type = span.get('type', '')
                            span_content = span.get('content', '')
                            
                            if span_type == 'text' and span_content:
                                span_texts.append(span_content)
                            elif span_type == 'inline_equation' and span_content:
                                from utils.latex_utils import latex_to_text
                                converted = latex_to_text(span_content)
                                span_texts.append(converted)
                        
                        if span_texts:
                            line_text = ''.join(span_texts)
                            line_texts.append(line_text)
                    return line_texts
                
                # 提取content（文字）- 包括 caption 型別
                content = None
                if actual_content_type in ['text', 'title', 'table_caption', 'image_caption']:
                    if block.get('lines'):
                        line_texts = extract_text_from_lines(block['lines'])
                        if line_texts:
                            content = '\n'.join(line_texts).strip()
                
                elif actual_content_type == 'list':
                    # list 型別包含 blocks 子陣列，每個 block 有 lines
                    if block.get('blocks'):
                        all_line_texts = []
                        for sub_block in block['blocks']:
                            if sub_block.get('lines'):
                                sub_texts = extract_text_from_lines(sub_block['lines'])
                                all_line_texts.extend(sub_texts)
                        if all_line_texts:
                            content = '\n'.join(all_line_texts).strip()
                
                # 提取img_path（圖片/表格）- 轉換為絕對路徑
                img_path = None
                if actual_content_type in ['image', 'table']:
                    if block.get('blocks'):
                        for sub_block in block['blocks']:
                            for line in sub_block.get('lines', []):
                                for span in line.get('spans', []):
                                    if span.get('image_path'):
                                        relative_path = span['image_path']
                                        if not relative_path.startswith('images/'):
                                            relative_path = 'images/' + relative_path
                                        # 轉換為絕對路徑
                                        abs_path = mineru_dir / relative_path
                                        if abs_path.exists():
                                            img_path = str(abs_path)
                                        break
                                if img_path:
                                    break
                            if img_path:
                                break
                
                return {
                    'bbox': scaled_bbox,
                    'type': actual_content_type,  # 使用實際內容型別而不是原始型別
                    'content': content,
                    'image_path': img_path,  # 現在是絕對路徑
                    'metadata': {
                        **block,
                        'original_type': block_type  # 保留原始型別（header/footer）在metadata中
                    }
                }
            
            # 處理主要內容塊（para_blocks）
            for block in page_info.get('para_blocks', []):
                element = process_block(block)
                if element:
                    elements.append(element)
                # 遞迴處理子塊（table_caption, image_caption 等）
                # 注意：list 型別的子塊已在 process_block 中處理，不需要再遞迴
                block_type = block.get('type', '')
                if block_type != 'list':
                    for sub_block in block.get('blocks', []):
                        sub_elem = process_block(sub_block)
                        if sub_elem:
                            elements.append(sub_elem)
            
            # 處理頁首頁尾（discarded_blocks）
            for block in page_info.get('discarded_blocks', []):
                element = process_block(block)
                if element:
                    elements.append(element)
                # 遞迴處理子塊
                # 注意：list 型別的子塊已在 process_block 中處理，不需要再遞迴
                block_type = block.get('type', '')
                if block_type != 'list':
                    for sub_block in block.get('blocks', []):
                        sub_elem = process_block(sub_block)
                        if sub_elem:
                            elements.append(sub_elem)
            
            logger.info(f"MinerU提取了 {len(elements)} 個元素")
        
        except Exception as e:
            logger.error(f"MinerU提取元素失敗: {e}", exc_info=True)
        
        return elements


class BaiduOCRElementExtractor(ElementExtractor):
    """
    基於百度OCR的元素提取器
    
    專門用於表格識別，提取表格單元格
    自包含：自己處理OCR呼叫和單元格提取
    """
    
    def __init__(self, baidu_table_ocr_provider):
        """
        初始化百度OCR提取器
        
        Args:
            baidu_table_ocr_provider: 百度表格OCR Provider例項
        """
        self._ocr_provider = baidu_table_ocr_provider
    
    def supports_type(self, element_type: Optional[str]) -> bool:
        """百度OCR主要支援表格型別"""
        return element_type in ['table', 'table_cell', None]
    
    def extract(
        self,
        image_path: str,
        element_type: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        從表格圖片中提取單元格
        
        支援的kwargs:
        - depth: int, 遞迴深度（用於日誌）
        - shrink_cells: bool, 是否收縮單元格以避免重疊，預設True
        """
        depth = kwargs.get('depth', 0)
        shrink_cells = kwargs.get('shrink_cells', True)
        
        elements = []
        
        try:
            # 呼叫百度OCR識別表格
            ocr_result = self._ocr_provider.recognize_table(
                image_path,
                cell_contents=True
            )
            
            table_cells = ocr_result.get('cells', [])
            # OCR結果通常會包含image_size，如果沒有則自己獲取
            table_img_size = ocr_result.get('image_size')
            if not table_img_size:
                img = Image.open(image_path)
                table_img_size = img.size
            
            logger.info(f"{'  ' * depth}百度OCR識別到 {len(table_cells)} 個單元格")
            
            # 只處理body單元格
            body_cells = [cell for cell in table_cells if cell.get('section') == 'body']
            valid_cells = [cell for cell in body_cells if cell.get('text', '').strip()]
            
            if not valid_cells:
                logger.warning(f"{'  ' * depth}沒有有效的單元格")
                return ExtractionResult(elements=elements)
            
            # 處理單元格（可選擇性收縮）
            cell_bboxes = []
            if shrink_cells:
                cell_bboxes = self._shrink_cells_to_avoid_overlap(valid_cells, depth)
            else:
                cell_bboxes = [cell.get('bbox', [0, 0, 0, 0]) for cell in valid_cells]
            
            # 構建元素列表
            for idx, (cell, bbox) in enumerate(zip(valid_cells, cell_bboxes)):
                elements.append({
                    'bbox': bbox,
                    'type': 'table_cell',
                    'content': cell.get('text', ''),
                    'image_path': None,
                    'metadata': {
                        'row_start': cell.get('row_start'),
                        'row_end': cell.get('row_end'),
                        'col_start': cell.get('col_start'),
                        'col_end': cell.get('col_end'),
                        'table_idx': cell.get('table_idx', 0)
                    }
                })
            
            logger.info(f"{'  ' * depth}百度OCR提取了 {len(elements)} 個單元格元素")
        
        except Exception as e:
            logger.error(f"{'  ' * depth}百度OCR識別失敗: {e}", exc_info=True)
        
        # 百度OCR不需要result_dir（表格單元格不會有子元素）
        return ExtractionResult(elements=elements)
    
    def _shrink_cells_to_avoid_overlap(
        self,
        valid_cells: List[Dict],
        depth: int
    ) -> List[List[float]]:
        """收縮單元格以避免重疊（演算法同原實現）"""
        TARGET_MIN_GAP = 6
        SHRINK_STEP = 0.02
        MIN_SIZE_RATIO = 0.4
        MAX_ITERATIONS = 20
        
        cell_data = []
        for cell in valid_cells:
            bbox = cell.get('bbox', [0, 0, 0, 0])
            x0, y0, x1, y1 = bbox
            cell_data.append({
                'cell': cell,
                'original_bbox': bbox,
                'current_bbox': [float(x0), float(y0), float(x1), float(y1)],
                'original_width': x1 - x0,
                'original_height': y1 - y0
            })
        
        def calculate_min_gap(cell_data):
            if len(cell_data) <= 1:
                return float('inf')
            
            min_gap = float('inf')
            for i, data1 in enumerate(cell_data):
                x0_1, y0_1, x1_1, y1_1 = data1['current_bbox']
                for j, data2 in enumerate(cell_data):
                    if i >= j:
                        continue
                    x0_2, y0_2, x1_2, y1_2 = data2['current_bbox']
                    
                    x_overlap = not (x1_1 <= x0_2 or x1_2 <= x0_1)
                    y_overlap = not (y1_1 <= y0_2 or y1_2 <= y0_1)
                    
                    if x_overlap and y_overlap:
                        overlap_x = min(x1_1, x1_2) - max(x0_1, x0_2)
                        overlap_y = min(y1_1, y1_2) - max(y0_1, y0_2)
                        min_gap = min(min_gap, -min(overlap_x, overlap_y))
                    elif x_overlap:
                        gap = y0_2 - y1_1 if y1_1 <= y0_2 else y0_1 - y1_2
                        min_gap = min(min_gap, gap)
                    elif y_overlap:
                        gap = x0_2 - x1_1 if x1_1 <= x0_2 else x0_1 - x1_2
                        min_gap = min(min_gap, gap)
            
            return min_gap
        
        iteration = 0
        total_shrink_ratio = 0
        
        while iteration < MAX_ITERATIONS:
            current_min_gap = calculate_min_gap(cell_data)
            
            if current_min_gap >= TARGET_MIN_GAP:
                if iteration == 0:
                    logger.info(f"{'  ' * depth}單元格間距已滿足要求（最小={current_min_gap:.1f}px），無需收縮")
                else:
                    logger.info(f"{'  ' * depth}收縮完成：{iteration}次迭代，最小間距={current_min_gap:.1f}px")
                break
            
            all_cells_can_shrink = True
            for data in cell_data:
                x0, y0, x1, y1 = data['current_bbox']
                current_width = x1 - x0
                current_height = y1 - y0
                
                min_width = data['original_width'] * MIN_SIZE_RATIO
                min_height = data['original_height'] * MIN_SIZE_RATIO
                
                if current_width <= min_width or current_height <= min_height:
                    all_cells_can_shrink = False
                    break
                
                shrink_x = max(0.5, current_width * SHRINK_STEP)
                shrink_y = max(0.5, current_height * SHRINK_STEP)
                
                new_x0 = x0 + shrink_x
                new_y0 = y0 + shrink_y
                new_x1 = x1 - shrink_x
                new_y1 = y1 - shrink_y
                
                if (new_x1 - new_x0) < min_width:
                    new_x0 = x0 + (current_width - min_width) / 2
                    new_x1 = x1 - (current_width - min_width) / 2
                if (new_y1 - new_y0) < min_height:
                    new_y0 = y0 + (current_height - min_height) / 2
                    new_y1 = y1 - (current_height - min_height) / 2
                
                data['current_bbox'] = [new_x0, new_y0, new_x1, new_y1]
            
            if not all_cells_can_shrink:
                logger.warning(f"{'  ' * depth}達到最小尺寸限制，當前最小間距={current_min_gap:.1f}px")
                break
            
            total_shrink_ratio += SHRINK_STEP
            iteration += 1
        
        if iteration >= MAX_ITERATIONS:
            current_min_gap = calculate_min_gap(cell_data)
            logger.warning(f"{'  ' * depth}達到最大迭代次數，當前最小間距={current_min_gap:.1f}px")
        
        return [data['current_bbox'] for data in cell_data]


class BaiduAccurateOCRElementExtractor(ElementExtractor):
    """
    基於百度高精度OCR的元素提取器
    
    專門用於文字識別，提取文字行元素
    支援多語種、高精度識別，返回文字位置資訊
    """
    
    def __init__(self, baidu_accurate_ocr_provider):
        """
        初始化百度高精度OCR提取器
        
        Args:
            baidu_accurate_ocr_provider: 百度高精度OCR Provider例項
        """
        self._ocr_provider = baidu_accurate_ocr_provider
    
    def supports_type(self, element_type: Optional[str]) -> bool:
        """百度高精度OCR主要支援文字型別"""
        return element_type in ['text', 'title', 'paragraph', None]
    
    def extract(
        self,
        image_path: str,
        element_type: Optional[str] = None,
        **kwargs
    ) -> ExtractionResult:
        """
        從圖片中提取文字元素
        
        支援的kwargs:
        - depth: int, 遞迴深度（用於日誌）
        - language_type: str, 識別語言型別，預設'CHN_ENG'
        - recognize_granularity: str, 是否定位單字元位置，'big'或'small'
        - detect_direction: bool, 是否檢測影象朝向
        - paragraph: bool, 是否輸出段落資訊
        """
        depth = kwargs.get('depth', 0)
        language_type = kwargs.get('language_type', 'CHN_ENG')
        recognize_granularity = kwargs.get('recognize_granularity', 'big')
        detect_direction = kwargs.get('detect_direction', False)
        paragraph = kwargs.get('paragraph', False)
        
        elements = []
        
        try:
            # 呼叫百度高精度OCR識別
            ocr_result = self._ocr_provider.recognize(
                image_path,
                language_type=language_type,
                recognize_granularity=recognize_granularity,
                detect_direction=detect_direction,
                paragraph=paragraph,
                probability=True,  # 獲取置信度
            )
            
            text_lines = ocr_result.get('text_lines', [])
            image_size = ocr_result.get('image_size', (0, 0))
            direction = ocr_result.get('direction', None)
            
            logger.info(f"{'  ' * depth}百度高精度OCR識別到 {len(text_lines)} 行文字")
            
            # 只處理有內容的文字行
            valid_lines = [line for line in text_lines if line.get('text', '').strip()]
            
            if not valid_lines:
                logger.warning(f"{'  ' * depth}沒有識別到有效的文字")
                return ExtractionResult(elements=elements)
            
            # 構建元素列表
            for idx, line in enumerate(valid_lines):
                bbox = line.get('bbox', [0, 0, 0, 0])
                text = line.get('text', '')
                
                element = {
                    'bbox': bbox,
                    'type': 'text',
                    'content': text,
                    'image_path': None,
                    'metadata': {
                        'line_idx': idx,
                        'source': 'baidu_accurate_ocr',
                    }
                }
                
                # 新增置信度資訊
                if 'probability' in line:
                    element['metadata']['probability'] = line['probability']
                
                # 新增單字元資訊
                if 'chars' in line:
                    element['metadata']['chars'] = line['chars']
                
                # 新增外接多邊形頂點
                if 'vertexes_location' in line:
                    element['metadata']['vertexes_location'] = line['vertexes_location']
                
                elements.append(element)
            
            logger.info(f"{'  ' * depth}百度高精度OCR提取了 {len(elements)} 個文字元素")
            
            # 新增圖片方向資訊到上下文
            context = ExtractionContext(
                metadata={
                    'source': 'baidu_accurate_ocr',
                    'image_size': image_size,
                    'direction': direction,
                }
            )
            
            return ExtractionResult(elements=elements, context=context)
        
        except Exception as e:
            logger.error(f"{'  ' * depth}百度高精度OCR識別失敗: {e}", exc_info=True)
        
        return ExtractionResult(elements=elements)


class ExtractorRegistry:
    """
    元素型別到提取器的對映登錄檔
    
    用於管理不同元素型別應該使用哪個提取器進行子元素提取：
    - 圖片/圖表元素 → MinerU 版面分析
    - 表格元素 → 百度表格OCR
    - 其他型別 → 預設提取器
    
    使用方式：
        >>> registry = ExtractorRegistry()
        >>> registry.register('table', baidu_ocr_extractor)
        >>> registry.register('image', mineru_extractor)
        >>> registry.register_default(mineru_extractor)
        >>> 
        >>> extractor = registry.get_extractor('table')  # 返回 baidu_ocr_extractor
        >>> extractor = registry.get_extractor('chart')  # 返回 mineru_extractor (預設)
    """
    
    # 預定義的元素型別分組
    TABLE_TYPES = {'table', 'table_cell'}
    IMAGE_TYPES = {'image', 'figure', 'chart', 'diagram'}
    TEXT_TYPES = {'text', 'title', 'paragraph', 'header', 'footer', 'list'}
    
    def __init__(self):
        """初始化登錄檔"""
        self._type_mapping: Dict[str, ElementExtractor] = {}
        self._default_extractor: Optional[ElementExtractor] = None
    
    def register(self, element_type: str, extractor: ElementExtractor) -> 'ExtractorRegistry':
        """
        註冊元素型別到提取器的對映
        
        Args:
            element_type: 元素型別（如 'table', 'image' 等）
            extractor: 對應的提取器例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._type_mapping[element_type] = extractor
        logger.debug(f"註冊提取器: {element_type} -> {extractor.__class__.__name__}")
        return self
    
    def register_types(self, element_types: List[str], extractor: ElementExtractor) -> 'ExtractorRegistry':
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
    
    def register_default(self, extractor: ElementExtractor) -> 'ExtractorRegistry':
        """
        註冊預設提取器（當沒有特定型別對映時使用）
        
        Args:
            extractor: 預設提取器例項
        
        Returns:
            self，支援鏈式呼叫
        """
        self._default_extractor = extractor
        logger.debug(f"註冊預設提取器: {extractor.__class__.__name__}")
        return self
    
    def get_extractor(self, element_type: Optional[str]) -> Optional[ElementExtractor]:
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
    
    def get_all_extractors(self) -> List[ElementExtractor]:
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
        mineru_extractor: ElementExtractor,
        baidu_ocr_extractor: Optional[ElementExtractor] = None,
        baidu_accurate_ocr_extractor: Optional[ElementExtractor] = None
    ) -> 'ExtractorRegistry':
        """
        建立預設配置的登錄檔
        
        預設配置：
        - 表格型別 → 百度表格OCR（如果可用）
        - 文字型別 → 百度高精度OCR（如果可用），否則MinerU
        - 圖片型別 → MinerU
        - 其他型別 → MinerU（預設）
        
        Args:
            mineru_extractor: MinerU提取器例項
            baidu_ocr_extractor: 百度表格OCR提取器例項（可選）
            baidu_accurate_ocr_extractor: 百度高精度OCR提取器例項（可選）
        
        Returns:
            配置好的登錄檔例項
        """
        registry = cls()
        
        # 設定預設提取器
        registry.register_default(mineru_extractor)
        
        # 圖片型別使用MinerU
        registry.register_types(list(cls.IMAGE_TYPES), mineru_extractor)
        
        # 表格型別使用百度表格OCR（如果可用），否則使用MinerU
        table_extractor = baidu_ocr_extractor if baidu_ocr_extractor else mineru_extractor
        registry.register_types(list(cls.TABLE_TYPES), table_extractor)
        
        # 文字型別使用百度高精度OCR（如果可用），否則使用MinerU
        text_extractor = baidu_accurate_ocr_extractor if baidu_accurate_ocr_extractor else mineru_extractor
        registry.register_types(list(cls.TEXT_TYPES), text_extractor)
        
        logger.info(f"建立預設ExtractorRegistry: "
                   f"表格->{table_extractor.__class__.__name__}, "
                   f"文字->{text_extractor.__class__.__name__}, "
                   f"圖片->{mineru_extractor.__class__.__name__}")
        
        return registry

