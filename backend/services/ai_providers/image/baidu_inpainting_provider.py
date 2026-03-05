"""
百度影象修復 Provider
基於百度AI的影象修復能力，在指定矩形區域去除遮擋物並用背景內容填充

API文件: https://ai.baidu.com/ai-doc/IMAGEPROCESS/Mk4i6o3w3
"""
import logging
import base64
import requests
import json
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import io
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class BaiduInpaintingProvider:
    """
    百度影象修復 Provider
    
    在圖片中指定位置框定一個或多個規則矩形，去掉不需要的遮擋物，並用背景內容填充。
    
    特點：
    - 支援多個矩形區域同時修復
    - 使用背景內容智慧填充
    - 快速響應，適合批次處理
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None):
        """
        初始化百度影象修復 Provider
        
        Args:
            api_key: 百度API Key（BCEv3格式：bce-v3/ALTAK-...）或Access Token
            api_secret: 可選，如果提供則用於BCEv3簽名
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_url = "https://aip.baidubce.com/rest/2.0/image-process/v1/inpainting"
        
        if api_key.startswith('bce-v3/'):
            logger.info("✅ 初始化百度影象修復 Provider (使用BCEv3 API Key)")
        else:
            logger.info("✅ 初始化百度影象修復 Provider (使用Access Token)")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=1, max=5),
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def inpaint(
        self,
        image: Image.Image,
        rectangles: List[Dict[str, int]]
    ) -> Optional[Image.Image]:
        """
        修復圖片中指定的矩形區域
        
        Args:
            image: PIL Image物件
            rectangles: 矩形區域列表，每個矩形包含:
                - left: 左上角x座標
                - top: 左上角y座標
                - width: 寬度
                - height: 高度
        
        Returns:
            修復後的PIL Image物件，失敗返回None
        """
        if not rectangles:
            logger.warning("沒有提供矩形區域，返回原圖")
            return image.copy()
        
        logger.info(f"🔧 開始百度影象修復，共 {len(rectangles)} 個區域")
        
        try:
            # 轉換圖片為RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            original_width, original_height = image.size
            logger.info(f"📏 圖片尺寸: {original_width}x{original_height}")
            
            # 檢查並調整圖片大小（最長邊不超過5000px）
            max_size = 5000
            scale = 1.0
            if original_width > max_size or original_height > max_size:
                scale = min(max_size / original_width, max_size / original_height)
                new_size = (int(original_width * scale), int(original_height * scale))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"✂️ 壓縮圖片: {image.size}")
                
                # 同時縮放矩形區域
                rectangles = [
                    {
                        'left': int(r['left'] * scale),
                        'top': int(r['top'] * scale),
                        'width': int(r['width'] * scale),
                        'height': int(r['height'] * scale)
                    }
                    for r in rectangles
                ]
            
            # 過濾掉無效的矩形（寬或高為0）
            valid_rectangles = [
                r for r in rectangles 
                if r['width'] > 0 and r['height'] > 0
            ]
            
            if not valid_rectangles:
                logger.warning("過濾後沒有有效的矩形區域，返回原圖")
                return image.copy()
            
            # 轉為base64
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=95)
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            logger.info(f"📦 圖片編碼完成: {len(image_base64)} bytes, {len(valid_rectangles)} 個矩形區域")
            
            # 構建請求頭
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            
            # 選擇認證方式
            if self.api_key.startswith('bce-v3/'):
                headers['Authorization'] = f'Bearer {self.api_key}'
                url = self.api_url
                logger.info("🔐 使用BCEv3簽名認證")
            else:
                url = f"{self.api_url}?access_token={self.api_key}"
                logger.info("🔐 使用Access Token認證")
            
            # 構建請求體
            request_body = {
                'image': image_base64,
                'rectangle': valid_rectangles
            }
            
            logger.info("🌐 傳送請求到百度影象修復API...")
            response = requests.post(
                url, 
                headers=headers, 
                json=request_body, 
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 檢查錯誤 - 丟擲異常以觸發 @retry 裝飾器
            if 'error_code' in result:
                error_msg = result.get('error_msg', 'Unknown error')
                error_code = result.get('error_code')
                logger.error(f"❌ 百度API錯誤: [{error_code}] {error_msg}")
                raise Exception(f"Baidu API error [{error_code}]: {error_msg}")
            
            # 解析結果
            result_image_base64 = result.get('image')
            if not result_image_base64:
                logger.error("❌ 百度API返回結果中沒有圖片")
                return None
            
            # 解碼返回的圖片
            result_image_bytes = base64.b64decode(result_image_base64)
            result_image = Image.open(io.BytesIO(result_image_bytes))
            
            # 如果之前縮放過，恢復到原始尺寸
            if scale < 1.0:
                result_image = result_image.resize(
                    (original_width, original_height), 
                    Image.Resampling.LANCZOS
                )
                logger.info(f"📐 恢復圖片尺寸: {result_image.size}")
            
            logger.info(f"✅ 百度影象修復完成!")
            return result_image
            
        except Exception as e:
            logger.error(f"❌ 百度影象修復失敗: {str(e)}")
            raise
    
    def inpaint_bboxes(
        self,
        image: Image.Image,
        bboxes: List[Tuple[float, float, float, float]],
        expand_pixels: int = 2
    ) -> Optional[Image.Image]:
        """
        使用bbox格式修復圖片
        
        Args:
            image: PIL Image物件
            bboxes: bbox列表，每個bbox格式為 (x0, y0, x1, y1)
            expand_pixels: 擴充套件畫素數，預設2
        
        Returns:
            修復後的PIL Image物件
        """
        # 將bbox轉換為rectangle格式
        rectangles = []
        for bbox in bboxes:
            x0, y0, x1, y1 = bbox
            # 擴充套件區域
            x0 = max(1, x0 - expand_pixels)
            y0 = max(1, y0 - expand_pixels)
            x1 = min(image.width - 1, x1 + expand_pixels)
            y1 = min(image.height - 1, y1 + expand_pixels)
            
            rectangles.append({
                'left': int(x0),
                'top': int(y0),
                'width': int(x1 - x0),
                'height': int(y1 - y0)
            })
        
        return self.inpaint(image, rectangles)


def create_baidu_inpainting_provider(
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None
) -> Optional[BaiduInpaintingProvider]:
    """
    建立百度影象修復 Provider 例項
    
    Args:
        api_key: 百度API Key，如果不提供則從 config.py 讀取
        api_secret: 百度API Secret（可選），如果不提供則從 config.py 讀取
        
    Returns:
        BaiduInpaintingProvider例項，如果api_key不可用則返回None
    """
    from config import Config
    
    if not api_key:
        api_key = Config.BAIDU_OCR_API_KEY
    
    if not api_secret:
        api_secret = Config.BAIDU_OCR_API_SECRET
    
    if not api_key:
        logger.warning("⚠️ 未配置百度API Key (BAIDU_OCR_API_KEY), 跳過百度影象修復")
        return None
    
    return BaiduInpaintingProvider(api_key, api_secret)

