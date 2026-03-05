"""
火山引擎 Inpainting 消除服務提供者
直接HTTP呼叫，完全繞過SDK限制
"""
import logging
import base64
import json
import requests
from datetime import datetime
from io import BytesIO
from typing import Optional
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class VolcengineInpaintingProvider:
    """火山引擎 Inpainting 消除服務（直接HTTP呼叫）"""
    
    API_URL = "https://visual.volcengineapi.com"
    SERVICE = "cv"
    REGION = "cn-north-1"
    
    def __init__(self, access_key: str, secret_key: str, timeout: int = 60):
        """
        初始化火山引擎 Inpainting 提供者
        
        Args:
            access_key: 火山引擎 Access Key  
            secret_key: 火山引擎 Secret Key
            timeout: API 請求超時時間（秒）
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.timeout = timeout
        logger.info("火山引擎 Inpainting Provider 初始化（直接HTTP模式）")
        
    def _encode_image_to_base64(self, image: Image.Image, is_mask: bool = False) -> str:
        """
        將 PIL Image 編碼為 base64 字串
        
        Args:
            image: PIL Image物件
            is_mask: 是否是mask圖（mask需要特殊處理）
        """
        buffered = BytesIO()
        
        if is_mask:
            # Mask要求：單通道灰度圖，或RGB值相等的三通道圖
            # 轉換為灰度圖以確保正確
            if image.mode != 'L':
                image = image.convert('L')
            # 儲存為PNG（文件要求8bit PNG，不嵌入ICC Profile）
            image.save(buffered, format="PNG", optimize=True)
        else:
            # 原圖：轉換為 RGB
            if image.mode in ('RGBA', 'LA', 'P'):
                if image.mode == 'RGBA':
                    background = Image.new('RGB', image.size, (255, 255, 255))
                    background.paste(image, mask=image.split()[3])
                    image = background
                else:
                    image = image.convert('RGB')
            # 儲存為 JPEG 減小大小
            image.save(buffered, format="JPEG", quality=85)
        
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    @retry(
        stop=stop_after_attempt(3),  # 最多重試3次
        wait=wait_exponential(multiplier=1, min=2, max=10),  # 指數避讓: 2s, 4s, 8s
        retry=retry_if_exception_type((requests.exceptions.RequestException, Exception)),
        reraise=True
    )
    def inpaint_image(
        self,
        original_image: Image.Image,
        mask_image: Image.Image,
        inpaint_mode: str = "remove",
        full_page_image: Optional[Image.Image] = None,
        crop_box: Optional[tuple] = None
    ) -> Optional[Image.Image]:
        """
        使用掩碼消除影象中的指定區域（帶指數避讓重試）
        
        Args:
            original_image: 原始影象
            mask_image: 掩碼影象（白色=消除，黑色=保留）
            inpaint_mode: 修復模式
            
        Returns:
            處理後的影象，失敗返回 None
        """
        try:
            logger.info("🚀 開始呼叫火山引擎 inpainting（直接HTTP）")
            
            # 1. 壓縮圖片（火山引擎限制5MB）
            max_dimension = 2048
            if max(original_image.size) > max_dimension:
                ratio = max_dimension / max(original_image.size)
                new_size = tuple(int(dim * ratio) for dim in original_image.size)
                original_image = original_image.resize(new_size, Image.LANCZOS)
                mask_image = mask_image.resize(new_size, Image.LANCZOS)
                logger.info(f"✂️ 壓縮圖片: {original_image.size}")
            
            # 2. 編碼為base64（mask要特殊處理為灰度圖）
            logger.info("📦 編碼圖片為base64...")
            original_base64 = self._encode_image_to_base64(original_image, is_mask=False)
            mask_base64 = self._encode_image_to_base64(mask_image, is_mask=True)
            logger.info(f"✅ 編碼完成: 原圖={len(original_base64)} bytes, mask={len(mask_base64)} bytes")
            
            # 3. 構建請求引數（按官方文件）
            # 參考：https://www.volcengine.com/docs/86081/1804489
            # mask要求：黑色(0)=保留，白色(255)=消除
            request_body = {
                "req_key": "i2i_inpainting",
                "binary_data_base64": [original_base64, mask_base64],
                "dilate_size": 10,  # mask膨脹半徑，幫助完整消除
                "quality": "H",  # 高質量模式（最高質量）
                "steps": 50,  # 取樣步數，越大效果越好但耗時更長（預設30）
                "strength": 0.85  # 控制強度，越大越接近文字控制（預設0.8）
            }
            
            # 4. 構建請求URL
            url = f"{self.API_URL}/?Action=CVProcess&Version=2022-08-31"
            
            # 5. 構建請求頭（簡化版，使用AK/SK直接認證）
            headers = {
                "Content-Type": "application/json",
                "X-Date": datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
            }
            
            logger.info(f"🌐 傳送請求到: {url}")
            logger.debug(f"請求體大小: {len(json.dumps(request_body))} bytes")
            
            # 6. 使用SDK（它會處理簽名）
            from volcengine.visual.VisualService import VisualService
            service = VisualService()
            service.set_ak(self.access_key)
            service.set_sk(self.secret_key)
            
            # 使用SDK的json_handler方法（這個方法會處理簽名）
            logger.info("使用SDK傳送請求（帶正確簽名）")
            
            try:
                # 使用SDK的通用API呼叫方法
                response = service.json(
                    "CVProcess",
                    {},  # query params
                    json.dumps(request_body)  # body
                )
                
                # 解析響應
                if isinstance(response, str):
                    response = json.loads(response)
                    
            except Exception as e:
                error_str = str(e)
                logger.error(f"SDK呼叫錯誤: {error_str}")
                
                # 嘗試從錯誤資訊中提取JSON響應
                if error_str.startswith("b'") and error_str.endswith("'"):
                    try:
                        response_text = error_str[2:-1]  # 去掉 b' 和 '
                        response = json.loads(response_text)
                    except:
                        logger.error("無法解析錯誤響應")
                        return None
                else:
                    return None
            
            # 8. 解析響應
            logger.debug(f"API響應: {json.dumps(response, ensure_ascii=False)[:300]}")
            
            if response.get("code") == 10000 or response.get("status") == 10000:
                data = response.get("data", {})
                
                # 嘗試多種響應格式
                result_base64 = None
                if "binary_data_base64" in data and data["binary_data_base64"]:
                    result_base64 = data["binary_data_base64"][0]
                elif "image_base64" in data:
                    result_base64 = data["image_base64"]
                elif "result_image" in data:
                    result_base64 = data["result_image"]
                
                if result_base64:
                    image_data = base64.b64decode(result_base64)
                    inpainted_image = Image.open(BytesIO(image_data))
                    logger.info(f"✅ Inpainting成功！結果: {inpainted_image.size}, {inpainted_image.mode}")
                    
                    # 合成：只取inpainting結果的mask區域，其他區域用原圖覆蓋
                    # 確保尺寸一致
                    if inpainted_image.size != original_image.size:
                        logger.warning(f"尺寸不一致，調整inpainting結果: {inpainted_image.size} -> {original_image.size}")
                        inpainted_image = inpainted_image.resize(original_image.size, Image.LANCZOS)
                    
                    # 確保mask尺寸一致
                    if mask_image.size != original_image.size:
                        mask_image = mask_image.resize(original_image.size, Image.LANCZOS)
                    
                    # 確保inpainted_image是RGB模式
                    if inpainted_image.mode != 'RGB':
                        inpainted_image = inpainted_image.convert('RGB')
                    if original_image.mode != 'RGB':
                        original_image = original_image.convert('RGB')
                    
                    # 確保mask是L模式（灰度圖）
                    mask_for_composite = mask_image.convert('L')
                    
                    # 使用PIL的composite方法合成影象
                    # mask中白色(255)區域使用inpainting結果，黑色(0)區域使用原圖
                    # 注意：Image.composite使用mask，其中白色表示使用image1，黑色表示使用image2
                    # 所以這裡image1是inpainting結果，image2是原圖
                    result_image = Image.composite(inpainted_image, original_image, mask_for_composite)
                    
                    logger.info(f"✅ 影象合成完成！最終尺寸: {result_image.size}, {result_image.mode}")
                    return result_image
                else:
                    logger.error(f"❌ 響應中無影象資料，keys: {list(data.keys())}")
                    return None
            else:
                code = response.get("code") or response.get("status")
                message = response.get("message", "未知錯誤")
                logger.error(f"❌ API錯誤: code={code}, message={message}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Inpainting失敗: {str(e)}", exc_info=True)
            return None
    
