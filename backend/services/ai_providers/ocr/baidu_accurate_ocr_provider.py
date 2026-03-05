"""
百度通用文字識別（高精度含位置版）OCR Provider
提供多場景、多語種、高精度的整圖文字檢測和識別服務，支援返回文字位置資訊

API文件: https://ai.baidu.com/ai-doc/OCR/1k3h7y3db
"""
import logging
import base64
import requests
import urllib.parse
from typing import Dict, List, Any, Optional, Literal
from PIL import Image
import io
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


# 支援的語言型別
LanguageType = Literal[
    'auto_detect',  # 自動檢測語言
    'CHN_ENG',      # 中英文混合
    'ENG',          # 英文
    'JAP',          # 日語
    'KOR',          # 韓語
    'FRE',          # 法語
    'SPA',          # 西班牙語
    'POR',          # 葡萄牙語
    'GER',          # 德語
    'ITA',          # 義大利語
    'RUS',          # 俄語
    'DAN',          # 丹麥語
    'DUT',          # 荷蘭語
    'MAL',          # 馬來語
    'SWE',          # 瑞典語
    'IND',          # 印尼語
    'POL',          # 波蘭語
    'ROM',          # 羅馬尼亞語
    'TUR',          # 土耳其語
    'GRE',          # 希臘語
    'HUN',          # 匈牙利語
    'THA',          # 泰語
    'VIE',          # 越南語
    'ARA',          # 阿拉伯語
    'HIN',          # 印地語
]


class BaiduAccurateOCRProvider:
    """
    百度高精度OCR Provider - 通用文字識別（高精度含位置版）
    
    特點:
    - 高精度文字識別
    - 支援25種語言
    - 返回文字位置資訊（支援行級別和字元級別）
    - 支援圖片朝向檢測
    - 支援段落輸出
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        """
        初始化百度高精度OCR Provider
        
        Args:
            api_key: 百度API Key（BCEv3格式：bce-v3/ALTAK-...）或Access Token
            api_secret: 可選，如果提供則用於BCEv3簽名
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate"
        
        if api_key.startswith('bce-v3/'):
            logger.info("✅ 初始化百度高精度OCR Provider (使用BCEv3 API Key)")
        else:
            logger.info("✅ 初始化百度高精度OCR Provider (使用Access Token)")
    
    @retry(
        stop=stop_after_attempt(3),  # 最多重試3次
        wait=wait_exponential(multiplier=0.5, min=1, max=5),  # 指數避讓: 1s, 2s, 4s
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def recognize(
        self,
        image_path: str,
        language_type: LanguageType = 'CHN_ENG',
        recognize_granularity: Literal['big', 'small'] = 'big',
        detect_direction: bool = False,
        vertexes_location: bool = False,
        paragraph: bool = False,
        probability: bool = False,
        char_probability: bool = False,
        multidirectional_recognize: bool = False,
        eng_granularity: Optional[Literal['word', 'letter']] = None,
    ) -> Dict[str, Any]:
        """
        識別圖片中的文字（高精度含位置版）
        
        Args:
            image_path: 圖片路徑
            language_type: 識別語言型別，預設中英文混合
            recognize_granularity: 是否定位單字元位置，big=不定位，small=定位
            detect_direction: 是否檢測影象朝向
            vertexes_location: 是否返回文字外接多邊形頂點位置
            paragraph: 是否輸出段落資訊
            probability: 是否返回每一行的置信度
            char_probability: 是否返回單字元置信度（需要recognize_granularity=small）
            multidirectional_recognize: 是否開啟行級別的多方向文字識別
            eng_granularity: 英文單字元結果維度（word/letter），當recognize_granularity=small時生效
            
        Returns:
            識別結果字典，包含:
            - log_id: 唯一日誌ID
            - words_result_num: 識別結果數
            - words_result: 識別結果陣列
                - words: 識別的文字
                - location: 位置資訊 {left, top, width, height}
                - chars: 單字元結果（當recognize_granularity=small時）
                - probability: 置信度（當probability=true時）
                - vertexes_location: 外接多邊形頂點（當vertexes_location=true時）
            - direction: 影象方向（當detect_direction=true時）
            - paragraphs_result: 段落結果（當paragraph=true時）
            - image_size: 原始圖片尺寸
        """
        logger.info(f"🔍 開始高精度OCR識別: {image_path}")
        
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
                logger.info(f"📦 圖片編碼完成: base64={len(image_base64)} bytes")
            
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
                logger.info("🔐 使用BCEv3簽名認證")
            else:
                # 使用Access Token (URL引數)
                url = f"{self.api_url}?access_token={self.api_key}"
                logger.info("🔐 使用Access Token認證")
            
            # 構建表單資料
            form_data = {
                'image': image_encoded,
                'language_type': language_type,
                'recognize_granularity': recognize_granularity,
                'detect_direction': 'true' if detect_direction else 'false',
                'vertexes_location': 'true' if vertexes_location else 'false',
                'paragraph': 'true' if paragraph else 'false',
                'probability': 'true' if probability else 'false',
                'multidirectional_recognize': 'true' if multidirectional_recognize else 'false',
            }
            
            if recognize_granularity == 'small' and char_probability:
                form_data['char_probability'] = 'true'
            
            if recognize_granularity == 'small' and eng_granularity:
                form_data['eng_granularity'] = eng_granularity
            
            # 轉換為URL編碼的表單資料
            data = '&'.join([f"{k}={v}" for k, v in form_data.items()])
            
            logger.info("🌐 傳送請求到百度高精度OCR API...")
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
            words_result_num = result.get('words_result_num', 0)
            words_result = result.get('words_result', [])
            direction = result.get('direction', None)
            paragraphs_result_num = result.get('paragraphs_result_num', 0)
            paragraphs_result = result.get('paragraphs_result', [])
            
            logger.info(f"✅ 高精度OCR識別成功! log_id={log_id}, 識別到 {words_result_num} 行文字")
            
            # 解析文字行資訊
            text_lines = []
            for line in words_result:
                line_info = {
                    'text': line.get('words', ''),
                    'location': line.get('location', {}),
                    'bbox': self._location_to_bbox(line.get('location', {})),
                }
                
                # 單字元結果
                if 'chars' in line:
                    line_info['chars'] = []
                    for char in line['chars']:
                        char_info = {
                            'char': char.get('char', ''),
                            'location': char.get('location', {}),
                            'bbox': self._location_to_bbox(char.get('location', {})),
                        }
                        if 'char_prob' in char:
                            char_info['probability'] = char['char_prob']
                        line_info['chars'].append(char_info)
                
                # 置信度
                if 'probability' in line:
                    line_info['probability'] = line['probability']
                
                # 外接多邊形頂點
                if 'vertexes_location' in line:
                    line_info['vertexes_location'] = line['vertexes_location']
                
                if 'finegrained_vertexes_location' in line:
                    line_info['finegrained_vertexes_location'] = line['finegrained_vertexes_location']
                
                if 'min_finegrained_vertexes_location' in line:
                    line_info['min_finegrained_vertexes_location'] = line['min_finegrained_vertexes_location']
                
                text_lines.append(line_info)
            
            # 解析段落資訊
            paragraphs = []
            if paragraphs_result:
                for para in paragraphs_result:
                    para_info = {
                        'words_result_idx': para.get('words_result_idx', []),
                    }
                    if 'finegrained_vertexes_location' in para:
                        para_info['finegrained_vertexes_location'] = para['finegrained_vertexes_location']
                    if 'min_finegrained_vertexes_location' in para:
                        para_info['min_finegrained_vertexes_location'] = para['min_finegrained_vertexes_location']
                    paragraphs.append(para_info)
            
            return {
                'log_id': log_id,
                'words_result_num': words_result_num,
                'words_result': words_result,  # 原始結果
                'text_lines': text_lines,  # 解析後的文字行
                'direction': direction,
                'paragraphs_result_num': paragraphs_result_num,
                'paragraphs_result': paragraphs_result,  # 原始段落結果
                'paragraphs': paragraphs,  # 解析後的段落
                'image_size': (original_width, original_height),
            }
            
        except Exception as e:
            logger.error(f"❌ 高精度OCR識別失敗: {str(e)}")
            raise
    
    def _location_to_bbox(self, location: Dict[str, int]) -> List[int]:
        """
        將location格式轉換為bbox格式 [x0, y0, x1, y1]
        
        Args:
            location: {left, top, width, height}
            
        Returns:
            bbox [x0, y0, x1, y1]
        """
        if not location:
            return [0, 0, 0, 0]
        
        left = location.get('left', 0)
        top = location.get('top', 0)
        width = location.get('width', 0)
        height = location.get('height', 0)
        
        return [left, top, left + width, top + height]
    
    def get_full_text(self, result: Dict[str, Any], separator: str = '\n') -> str:
        """
        從識別結果中提取完整文字
        
        Args:
            result: recognize()返回的結果
            separator: 行分隔符，預設換行
            
        Returns:
            完整的文字字串
        """
        text_lines = result.get('text_lines', [])
        return separator.join([line.get('text', '') for line in text_lines])
    
    def get_text_with_positions(self, result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        獲取帶位置資訊的文字列表
        
        Args:
            result: recognize()返回的結果
            
        Returns:
            文字位置列表，每項包含 text 和 bbox
        """
        text_lines = result.get('text_lines', [])
        return [
            {
                'text': line.get('text', ''),
                'bbox': line.get('bbox', [0, 0, 0, 0]),
            }
            for line in text_lines
        ]


def create_baidu_accurate_ocr_provider(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> Optional[BaiduAccurateOCRProvider]:
    """
    建立百度高精度OCR Provider例項
    
    Args:
        api_key: 百度API Key（BCEv3格式或Access Token），如果不提供則從環境變數讀取
        api_secret: 百度API Secret（可選），如果不提供則從環境變數讀取
        
    Returns:
        BaiduAccurateOCRProvider例項，如果api_key不可用則返回None
    """
    import os
    
    if not api_key:
        api_key = os.getenv('BAIDU_OCR_API_KEY')
    
    if not api_secret:
        api_secret = os.getenv('BAIDU_OCR_API_SECRET')
    
    if not api_key:
        logger.warning("⚠️ 未配置百度OCR API Key, 跳過百度高精度OCR")
        return None
    
    return BaiduAccurateOCRProvider(api_key, api_secret)

