"""
百度表格識別OCR Provider
提供基於百度AI的表格識別能力,支援精確到單元格級別的識別

API文件: https://ai.baidu.com/ai-doc/OCR/1k3h7y3db
"""
import logging
import base64
import requests
import urllib.parse
from typing import Dict, List, Any, Optional
from PIL import Image
import io
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class BaiduTableOCRProvider:
    """百度表格OCR Provider - 支援BCEv3簽名認證"""
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        """
        初始化百度表格OCR Provider
        
        Args:
            api_key: 百度API Key（BCEv3格式：bce-v3/ALTAK-...）或Access Token
            api_secret: 可選，如果提供則用於BCEv3簽名
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/table"
        
        if api_key.startswith('bce-v3/'):
            logger.info("✅ 初始化百度表格OCR Provider (使用BCEv3 API Key)")
        else:
            logger.info("✅ 初始化百度表格OCR Provider (使用Access Token)")
    
    @retry(
        stop=stop_after_attempt(3),  # 最多重試3次
        wait=wait_exponential(multiplier=0.5, min=1, max=5),  # 指數避讓: 1s, 2s, 4s
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def recognize_table(
        self,
        image_path: str,
        cell_contents: bool = True,  # 預設開啟，獲取單元格文字位置
        return_excel: bool = False
    ) -> Dict[str, Any]:
        """
        識別表格圖片（帶指數避讓重試）
        
        Args:
            image_path: 圖片路徑
            cell_contents: 是否識別單元格內容位置資訊，預設True
            return_excel: 是否返回Excel格式，預設False
            
        Returns:
            識別結果字典,包含:
            - log_id: 日誌ID
            - table_num: 表格數量
            - tables_result: 表格結果列表
            - cells: 解析後的單元格列表(扁平化)
            - image_size: 原始圖片尺
        """
        logger.info(f"🔍 開始識別表格圖片: {image_path}")
        
        try:
            # 讀取圖片並轉為base64
            original_width, original_height = 0, 0
            with Image.open(image_path) as img:
                # 獲取原始圖片尺寸
                original_width, original_height = img.size
                logger.info(f"📏 圖片尺寸: {original_width}x{original_height}")
                
                # 轉換為RGB模式
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 壓縮圖片(如果太大) - 最長邊不超過8192px，最短邊至少15px
                max_size = 8192
                min_size = 15
                width, height = img.size
                
                if width < min_size or height < min_size:
                    logger.warning(f"⚠️ 圖片太小: {width}x{height}, 最短邊需要至少{min_size}px")
                
                if width > max_size or height > max_size:
                    ratio = min(max_size / width, max_size / height)
                    new_size = (int(width * ratio), int(height * ratio))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                    logger.info(f"✂️ 壓縮圖片: {img.size}")
                
                # 轉為base64
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=95)
                image_bytes = buffer.getvalue()
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                
                # URL encode
                image_encoded = urllib.parse.quote(image_base64)
                logger.info(f"📦 圖片編碼完成: base64={len(image_base64)} bytes, urlencode={len(image_encoded)} bytes")
            
            # 構建請求頭
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }
            
            # 選擇認證方式
            if self.api_key.startswith('bce-v3/'):
                # 使用BCEv3簽名認證 (Authorization頭部)
                headers['Authorization'] = f'Bearer {self.api_key}'
                url = self.api_url
                logger.info(f"🔐 使用BCEv3簽名認證")
            else:
                # 使用Access Token (URL引數)
                url = f"{self.api_url}?access_token={self.api_key}"
                logger.info(f"🔐 使用Access Token認證")
            
            # 構建表單資料
            data = f"image={image_encoded}&cell_contents={'true' if cell_contents else 'false'}&return_excel={'true' if return_excel else 'false'}"
            
            logger.info(f"🌐 傳送請求到百度表格OCR API...")
            response = requests.post(url, headers=headers, data=data, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            
            # 檢查錯誤
            if 'error_code' in result:
                error_msg = result.get('error_msg', 'Unknown error')
                error_code = result.get('error_code')
                logger.error(f"❌ 百度API錯誤: [{error_code}] {error_msg}")
                raise Exception(f"Baidu API error [{error_code}]: {error_msg}")
            
            # 解析結果
            log_id = result.get('log_id', '')
            table_num = result.get('table_num', 0)
            tables_result = result.get('tables_result', [])
            excel_file = result.get('excel_file', None)
            
            logger.info(f"✅ 表格識別成功! log_id={log_id}, 識別到 {table_num} 個表格")
            
            # 解析單元格資訊(扁平化)
            cells = []
            for table_idx, table in enumerate(tables_result):
                table_location = table.get('table_location', [])
                header = table.get('header', [])
                body = table.get('body', [])
                footer = table.get('footer', [])
                
                logger.info(f"  表格 {table_idx + 1}: header={len(header)}, body={len(body)}, footer={len(footer)}")
                
                # 解析表頭
                for idx, header_cell in enumerate(header):
                    cell_info = {
                        'table_idx': table_idx,
                        'section': 'header',
                        'section_idx': idx,
                        'text': header_cell.get('words', ''),
                        'bbox': self._location_to_bbox(header_cell.get('location', [])),
                    }
                    cells.append(cell_info)
                
                # 解析表體
                for cell in body:
                    cell_info = {
                        'table_idx': table_idx,
                        'section': 'body',
                        'row_start': cell.get('row_start', 0),
                        'row_end': cell.get('row_end', 0),
                        'col_start': cell.get('col_start', 0),
                        'col_end': cell.get('col_end', 0),
                        'text': cell.get('words', ''),
                        'bbox': self._location_to_bbox(cell.get('cell_location', [])),
                        'contents': cell.get('contents', []),  # 單元格內文字分行資訊
                    }
                    cells.append(cell_info)
                
                # 解析表尾
                for idx, footer_cell in enumerate(footer):
                    cell_info = {
                        'table_idx': table_idx,
                        'section': 'footer',
                        'section_idx': idx,
                        'text': footer_cell.get('words', ''),
                        'bbox': self._location_to_bbox(footer_cell.get('location', [])),
                    }
                    cells.append(cell_info)
            
            return {
                'log_id': log_id,
                'table_num': table_num,
                'tables_result': tables_result,
                'cells': cells,
                'image_size': (original_width, original_height),
                'excel_file': excel_file,
            }
            
        except Exception as e:
            logger.error(f"❌ 表格識別失敗: {str(e)}")
            raise
    
    def _location_to_bbox(self, location: List[Dict[str, int]]) -> List[int]:
        """
        將四個角點座標轉換為bbox格式 [x0, y0, x1, y1]
        
        Args:
            location: 四個角點 [{x, y}, {x, y}, {x, y}, {x, y}]
            
        Returns:
            bbox [x0, y0, x1, y1]
        """
        if not location or len(location) < 2:
            return [0, 0, 0, 0]
        
        xs = [p['x'] for p in location]
        ys = [p['y'] for p in location]
        
        return [min(xs), min(ys), max(xs), max(ys)]
    
    def get_table_structure(self, cells: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        從單元格列表中提取表格結構
        
        Args:
            cells: 單元格列表
            
        Returns:
            表格結構資訊:
            - rows: 行數
            - cols: 列數
            - cells_by_position: {(row, col): cell_info}
        """
        if not cells:
            return {'rows': 0, 'cols': 0, 'cells_by_position': {}}
        
        max_row = max(cell['row_end'] for cell in cells)
        max_col = max(cell['col_end'] for cell in cells)
        
        cells_by_position = {}
        for cell in cells:
            # 使用起始位置作為key
            key = (cell['row_start'], cell['col_start'])
            cells_by_position[key] = cell
        
        return {
            'rows': max_row,
            'cols': max_col,
            'cells_by_position': cells_by_position,
        }


def create_baidu_table_ocr_provider(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> Optional[BaiduTableOCRProvider]:
    """
    建立百度表格OCR Provider例項
    
    Args:
        api_key: 百度API Key（BCEv3格式或Access Token），如果不提供則從環境變數讀取
        api_secret: 百度API Secret（可選），如果不提供則從環境變數讀取
        
    Returns:
        BaiduTableOCRProvider例項，如果api_key不可用則返回None
    """
    import os
    
    if not api_key:
        api_key = os.getenv('BAIDU_OCR_API_KEY')
    
    if not api_secret:
        api_secret = os.getenv('BAIDU_OCR_API_SECRET')
    
    if not api_key:
        logger.warning("⚠️ 未配置百度OCR API Key, 跳過百度表格識別")
        return None
    
    return BaiduTableOCRProvider(api_key, api_secret)

