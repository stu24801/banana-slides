"""
Gemini Inpainting 消除服務提供者
使用 Gemini 2.5 Flash Image Preview 模型進行基於 mask 的影象編輯
"""
import logging
from typing import Optional
from PIL import Image, ImageDraw
import numpy as np
from tenacity import retry, stop_after_attempt, wait_exponential
from .genai_provider import GenAIImageProvider
from config import get_config

logger = logging.getLogger(__name__)


class GeminiInpaintingProvider:
    """Gemini Inpainting 消除服務（使用 Gemini 2.5 Flash）"""
    
    # DEFAULT_MODEL = "gemini-2.5-flash-image"
    DEFAULT_MODEL = "gemini-3-pro-image-preview"
    DEFAULT_PROMPT = """\
你是一個專業的圖片前景元素去除專家，以極高的精度進行前景元素的去除工作。
現在使用者向你提供了兩張不同的圖片：
1. 原始圖片
2. 使用黑色矩形遮罩標註後的圖片，黑色矩形區域表示要移除的前景元素，你只需要處理這些區域。

你需要根據原始圖片和黑色遮罩資訊，重新繪製黑色遮罩標註的區域，去除前景元素，使得這些區域無縫融入周圍的畫面，就好像前景元素從來沒有出現過。如果一個區域被整體標註，請你將其作為一個整體進行移除，而不是隻移除其內部的內容。

禁止遺漏任何一個黑色矩形標註的區域。

"""
    
    def __init__(
        self, 
        api_key: str, 
        api_base: str = None,
        model: str = None,
        timeout: int = 60
    ):
        """
        初始化 Gemini Inpainting 提供者
        
        Args:
            api_key: Google API key
            api_base: API base URL (for proxies like aihubmix)
            model: Model name to use (default: gemini-2.5-flash-image)
            timeout: API 請求超時時間（秒）
        """
        self.model = model or self.DEFAULT_MODEL
        self.timeout = timeout
        
        # 複用 GenAIImageProvider 的底層實現
        self.genai_provider = GenAIImageProvider(
            api_key=api_key,
            api_base=api_base,
            model=self.model
        )
        
        logger.info(f"✅ Gemini Inpainting Provider 初始化 (model={self.model})")
    
    @staticmethod
    def create_marked_image(original_image: Image.Image, mask_image: Image.Image) -> Image.Image:
        """
        在原圖上用純黑色框標註需要修復的區域
        
        Args:
            original_image: 原始影象
            mask_image: 掩碼影象（白色=需要移除的區域）
            
        Returns:
            標註後的影象（原圖 + 純黑色矩形覆蓋）
        """
        # 確保 mask 和原圖尺寸一致
        if mask_image.size != original_image.size:
            mask_image = mask_image.resize(original_image.size, Image.LANCZOS)
        
        # 轉換為 RGB 模式
        if original_image.mode != 'RGB':
            original_image = original_image.convert('RGB')
        if mask_image.mode != 'RGB':
            mask_image = mask_image.convert('RGB')
        
        # 建立一個副本用於標註
        marked_image = original_image.copy()
        
        # 將 mask 轉換為 numpy array 以便處理
        mask_array = np.array(mask_image)
        marked_array = np.array(marked_image)
        
        # 找到白色區域（需要標註的區域）
        # 白色畫素的 RGB 值都接近 255
        white_threshold = 200
        mask_regions = np.all(mask_array > white_threshold, axis=2)
        
        # 用純黑色 (0, 0, 0) 完全覆蓋標註區域
        black_overlay = np.array([0, 0, 0], dtype=np.uint8)
        marked_array[mask_regions] = black_overlay
        
        # 轉回 PIL Image
        marked_image = Image.fromarray(marked_array)
        
        logger.debug(f"✅ 已建立標註影象，用純黑色覆蓋了 {np.sum(mask_regions)} 個畫素")
        
        return marked_image
    
    @retry(
        stop=stop_after_attempt(3),  # 最多重試3次
        wait=wait_exponential(multiplier=1, min=2, max=10),  # 指數避讓: 2s, 4s, 8s
        reraise=True
    )
    def inpaint_image(
        self,
        original_image: Image.Image,
        mask_image: Image.Image,
        inpaint_mode: str = "remove",
        custom_prompt: Optional[str] = None,
        full_page_image: Optional[Image.Image] = None,
        crop_box: Optional[tuple] = None
    ) -> Optional[Image.Image]:
        """
        使用 Gemini 和掩碼進行影象編輯
        
        Args:
            original_image: 原始影象
            mask_image: 掩碼影象（白色=消除，黑色=保留）
            inpaint_mode: 修復模式（未使用，保留相容性）
            custom_prompt: 自定義 prompt（如果為 None 則使用預設）
            full_page_image: 完整的 PPT 頁面影象（16:9），如果提供則直接使用
            crop_box: 裁剪框 (x0, y0, x1, y1)，指定從完整頁面結果中裁剪的區域
            
        Returns:
            處理後的影象，失敗返回 None
        """
        try:
            logger.info("🚀 開始呼叫 Gemini inpainting（標註模式）")
            
            working_image = full_page_image
            
            # 1. 擴充套件 mask 到完整頁面大小
            result_crop_box = crop_box  # 儲存傳入的 crop_box
            
            # 直接使用完整頁面影象
            final_image = working_image
            
            # 擴充套件 mask 到完整頁面大小
            # 建立與完整頁面同樣大小的黑色 mask
            full_mask = Image.new('RGB', final_image.size, (0, 0, 0))
            # 將原 mask 貼上到正確的位置
            x0, y0, x1, y1 = crop_box
            # 確保 mask 尺寸匹配
            mask_resized = mask_image.resize((x1 - x0, y1 - y0), Image.LANCZOS)
            full_mask.paste(mask_resized, (x0, y0))
            final_mask = full_mask
            logger.info(f"📷 完整頁面模式: 頁面={final_image.size}, mask擴充套件到={final_mask.size}, 貼上位置={crop_box}")

            # 2. 建立標註影象（在原圖上用純黑色框標註需要修復的區域）
            logger.info("🎨 建立標註影象（純黑色框標註需要移除的區域）...")
            marked_image = self.create_marked_image(final_image, final_mask)
            logger.info(f"✅ 標註影象建立完成: {marked_image.size}")
            
            # 3. 構建 prompt
            prompt = custom_prompt or self.DEFAULT_PROMPT
            logger.info(f"📝 Prompt: {prompt[:100]}...")
            
            # 4. 呼叫 GenAI Provider 生成影象（只傳標註後的影象，不傳 mask）
            logger.info("🌐 呼叫 GenAI Provider 進行 inpainting（僅傳標註圖）...")
            
            result_image = self.genai_provider.generate_image(
                prompt=prompt,
                ref_images=[full_page_image, marked_image],  
                aspect_ratio="16:9",
                resolution="1K"
            )
            
            if result_image is None:
                logger.error("❌ Gemini Inpainting 失敗：未返回影象")
                return None
            
            # 5. 轉換為 PIL Image（如果需要）
            # GenAI SDK 返回的是 google.genai.types.Image 物件，需要轉換為 PIL Image
            if hasattr(result_image, '_pil_image'):
                logger.debug("🔄 轉換 GenAI Image 為 PIL Image")
                result_image = result_image._pil_image
            
            logger.info(f"✅ Gemini Inpainting 成功！API返回尺寸: {result_image.size}, {result_image.mode}")
            
            # 6. Resize 到原圖尺寸
            if result_image.size != final_image.size:
                logger.info(f"🔄 Resize 從 {result_image.size} 到 {final_image.size}")
                result_image = result_image.resize(final_image.size, Image.LANCZOS)
            
            # 7. 合成影象：只在mask區域使用inpaint結果，其他區域保留原圖
            logger.info("🎨 合成影象：將inpaint結果與原圖按mask合併...")
            
            # 確保所有影象都是RGB模式
            if result_image.mode != 'RGB':
                result_image = result_image.convert('RGB')
            if final_image.mode != 'RGB':
                final_image = final_image.convert('RGB')
            
            # 將mask轉換為灰度圖（L模式）
            mask_for_composite = final_mask.convert('L')
            
            # 使用PIL的composite方法合成
            # mask中白色(255)區域使用inpainting結果，黑色(0)區域使用原圖
            composited_image = Image.composite(result_image, final_image, mask_for_composite)
            logger.info(f"✅ 影象合成完成！尺寸: {composited_image.size}")
            
            # 8. 裁剪回目標尺寸
            cropped_result = composited_image.crop(result_crop_box)
            logger.info(f"✂️  從完整頁面裁剪: {composited_image.size} -> {cropped_result.size}")
            return cropped_result
            
        except Exception as e:
            logger.error(f"❌ Gemini Inpainting 失敗: {e}", exc_info=True)
            raise
