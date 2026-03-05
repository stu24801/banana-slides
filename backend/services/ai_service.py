"""
AI Service - handles all AI model interactions
Based on demo.py and gemini_genai.py
TODO: use structured output API
"""
import os
import json
import re
import logging
import requests
from typing import List, Dict, Optional, Union
from textwrap import dedent
from PIL import Image
from tenacity import retry, stop_after_attempt, retry_if_exception_type
from .prompts import (
    get_outline_generation_prompt,
    get_outline_parsing_prompt,
    get_page_description_prompt,
    get_image_generation_prompt,
    get_image_edit_prompt,
    get_description_to_outline_prompt,
    get_description_split_prompt,
    get_outline_refinement_prompt,
    get_descriptions_refinement_prompt
)
from .ai_providers import get_text_provider, get_image_provider, TextProvider, ImageProvider
from config import get_config

logger = logging.getLogger(__name__)


class ProjectContext:
    """專案上下文資料類，統一管理 AI 需要的所有專案資訊"""
    
    def __init__(self, project_or_dict, reference_files_content: Optional[List[Dict[str, str]]] = None):
        """
        Args:
            project_or_dict: 專案物件（Project model）或專案字典（project.to_dict()）
            reference_files_content: 參考檔案內容列表
        """
        # 支援直接傳入 Project 物件，避免 to_dict() 呼叫，提升效能
        if hasattr(project_or_dict, 'idea_prompt'):
            # 是 Project 物件
            self.idea_prompt = project_or_dict.idea_prompt
            self.outline_text = project_or_dict.outline_text
            self.description_text = project_or_dict.description_text
            self.creation_type = project_or_dict.creation_type or 'idea'
        else:
            # 是字典
            self.idea_prompt = project_or_dict.get('idea_prompt')
            self.outline_text = project_or_dict.get('outline_text')
            self.description_text = project_or_dict.get('description_text')
            self.creation_type = project_or_dict.get('creation_type', 'idea')
        
        self.reference_files_content = reference_files_content or []
    
    def to_dict(self) -> Dict:
        """轉換為字典，方便傳遞"""
        return {
            'idea_prompt': self.idea_prompt,
            'outline_text': self.outline_text,
            'description_text': self.description_text,
            'creation_type': self.creation_type,
            'reference_files_content': self.reference_files_content
        }


class AIService:
    """Service for AI model interactions using pluggable providers"""
    
    def __init__(self, text_provider: TextProvider = None, image_provider: ImageProvider = None):
        """
        Initialize AI service with providers
        
        Args:
            text_provider: Optional pre-configured TextProvider. If None, created from factory.
            image_provider: Optional pre-configured ImageProvider. If None, created from factory.
        """
        config = get_config()

        # 優先使用 Flask app.config（可由 Settings 覆蓋），否則回退到 Config 預設值
        try:
            from flask import current_app, has_app_context
        except ImportError:
            current_app = None  # type: ignore
            has_app_context = lambda: False  # type: ignore

        if has_app_context() and current_app and hasattr(current_app, "config"):
            self.text_model = current_app.config.get("TEXT_MODEL", config.TEXT_MODEL)
            self.image_model = current_app.config.get("IMAGE_MODEL", config.IMAGE_MODEL)
            # 分離的文字和影象推理配置
            self.enable_text_reasoning = current_app.config.get("ENABLE_TEXT_REASONING", False)
            self.text_thinking_budget = current_app.config.get("TEXT_THINKING_BUDGET", 1024)
            self.enable_image_reasoning = current_app.config.get("ENABLE_IMAGE_REASONING", False)
            self.image_thinking_budget = current_app.config.get("IMAGE_THINKING_BUDGET", 1024)
        else:
            self.text_model = config.TEXT_MODEL
            self.image_model = config.IMAGE_MODEL
            self.enable_text_reasoning = False
            self.text_thinking_budget = 1024
            self.enable_image_reasoning = False
            self.image_thinking_budget = 1024
        
        # Use provided providers or create from factory based on AI_PROVIDER_FORMAT (from Flask config or env var)
        self.text_provider = text_provider or get_text_provider(model=self.text_model)
        self.image_provider = image_provider or get_image_provider(model=self.image_model)
    
    def _get_text_thinking_budget(self) -> int:
        """
        獲取文字生成的思考負載
        
        Returns:
            如果啟用文字推理則返回配置的 budget，否則返回 0
        """
        return self.text_thinking_budget if self.enable_text_reasoning else 0
    
    def _get_image_thinking_budget(self) -> int:
        """
        獲取影象生成的思考負載
        
        Returns:
            如果啟用影象推理則返回配置的 budget，否則返回 0
        """
        return self.image_thinking_budget if self.enable_image_reasoning else 0
    
    @staticmethod
    def extract_image_urls_from_markdown(text: str) -> List[str]:
        """
        從 markdown 文字中提取圖片 URL
        
        Args:
            text: Markdown 文字，可能包含 ![](url) 格式的圖片
            
        Returns:
            圖片 URL 列表（包括 http/https URL 和 /files/ 開頭的本地路徑）
        """
        if not text:
            return []
        
        # 匹配 markdown 圖片語法: ![](url) 或 ![alt](url)
        pattern = r'!\[.*?\]\((.*?)\)'
        matches = re.findall(pattern, text)
        
        # 過濾掉空字串，支援 http/https URL 和 /files/ 開頭的本地路徑（包括 mineru、materials 等）
        urls = []
        for url in matches:
            url = url.strip()
            if url and (url.startswith('http://') or url.startswith('https://') or url.startswith('/files/')):
                urls.append(url)
        
        return urls
    
    @staticmethod
    def remove_markdown_images(text: str) -> str:
        """
        從文字中移除 Markdown 圖片連結，只保留 alt text（描述文字）
        
        Args:
            text: 包含 Markdown 圖片語法的文字
            
        Returns:
            移除圖片連結後的文字，保留描述文字
        """
        if not text:
            return text
        
        # 將 ![描述文字](url) 替換為 描述文字
        # 如果沒有描述文字（空的 alt text），則完全刪除該圖片連結
        def replace_image(match):
            alt_text = match.group(1).strip()
            # 如果有描述文字，保留它；否則刪除整個連結
            return alt_text if alt_text else ''
        
        pattern = r'!\[(.*?)\]\([^\)]+\)'
        cleaned_text = re.sub(pattern, replace_image, text)
        
        # 清理可能產生的多餘空行
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text)
        
        return cleaned_text
    
    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((json.JSONDecodeError, ValueError)),
        reraise=True
    )
    def generate_json(self, prompt: str, thinking_budget: int = 1000) -> Union[Dict, List]:
        """
        生成並解析JSON，如果解析失敗則重新生成
        
        Args:
            prompt: 生成提示詞
            thinking_budget: 思考預算（會根據 enable_text_reasoning 配置自動調整）
            
        Returns:
            解析後的JSON物件（字典或列表）
            
        Raises:
            json.JSONDecodeError: JSON解析失敗（重試3次後仍失敗）
        """
        # 呼叫AI生成文字（根據 enable_text_reasoning 配置調整 thinking_budget）
        actual_budget = self._get_text_thinking_budget()
        response_text = self.text_provider.generate_text(prompt, thinking_budget=actual_budget)
        
        # 清理響應文字：移除markdown程式碼塊標記和多餘空白
        cleaned_text = response_text.strip().strip("```json").strip("```").strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失敗，將重新生成。原始文字: {cleaned_text[:200]}... 錯誤: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((json.JSONDecodeError, ValueError)),
        reraise=True
    )
    def generate_json_with_image(self, prompt: str, image_path: str, thinking_budget: int = 1000) -> Union[Dict, List]:
        """
        帶圖片輸入的JSON生成，如果解析失敗則重新生成（最多重試3次）
        
        Args:
            prompt: 生成提示詞
            image_path: 圖片檔案路徑
            thinking_budget: 思考預算（會根據 enable_text_reasoning 配置自動調整）
            
        Returns:
            解析後的JSON物件（字典或列表）
            
        Raises:
            json.JSONDecodeError: JSON解析失敗（重試3次後仍失敗）
            ValueError: text_provider 不支援圖片輸入
        """
        # 呼叫AI生成文字（帶圖片），根據 enable_text_reasoning 配置調整 thinking_budget
        actual_budget = self._get_text_thinking_budget()
        if hasattr(self.text_provider, 'generate_with_image'):
            response_text = self.text_provider.generate_with_image(
                prompt=prompt,
                image_path=image_path,
                thinking_budget=actual_budget
            )
        elif hasattr(self.text_provider, 'generate_text_with_images'):
            response_text = self.text_provider.generate_text_with_images(
                prompt=prompt,
                images=[image_path],
                thinking_budget=actual_budget
            )
        else:
            raise ValueError("text_provider 不支援圖片輸入")
        
        # 清理響應文字：移除markdown程式碼塊標記和多餘空白
        cleaned_text = response_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失敗（帶圖片），將重新生成。原始文字: {cleaned_text[:200]}... 錯誤: {str(e)}")
            raise
    
    @staticmethod
    def _convert_mineru_path_to_local(mineru_path: str) -> Optional[str]:
        """
        將 /files/mineru/{extract_id}/{rel_path} 格式的路徑轉換為本地檔案系統路徑（支援字首匹配）
        
        Args:
            mineru_path: MinerU URL 路徑，格式為 /files/mineru/{extract_id}/{rel_path}
            
        Returns:
            本地檔案系統路徑，如果轉換失敗則返回 None
        """
        from utils.path_utils import find_mineru_file_with_prefix
        
        matched_path = find_mineru_file_with_prefix(mineru_path)
        return str(matched_path) if matched_path else None
    
    @staticmethod
    def download_image_from_url(url: str) -> Optional[Image.Image]:
        """
        從 URL 下載圖片並返回 PIL Image 物件
        
        Args:
            url: 圖片 URL
            
        Returns:
            PIL Image 物件，如果下載失敗則返回 None
        """
        try:
            logger.debug(f"Downloading image from URL: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            
            # 從響應內容建立 PIL Image
            image = Image.open(response.raw)
            # 確保圖片被載入
            image.load()
            logger.debug(f"Successfully downloaded image: {image.size}, {image.mode}")
            return image
        except Exception as e:
            logger.error(f"Failed to download image from {url}: {str(e)}")
            return None
    
    def generate_outline(self, project_context: ProjectContext, language: str = None) -> List[Dict]:
        """
        Generate PPT outline from idea prompt
        Based on demo.py gen_outline()
        
        Args:
            project_context: 專案上下文物件，包含所有原始資訊
            
        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        outline_prompt = get_outline_generation_prompt(project_context, language)
        outline = self.generate_json(outline_prompt, thinking_budget=1000)
        return outline
    
    def parse_outline_text(self, project_context: ProjectContext, language: str = None) -> List[Dict]:
        """
        Parse user-provided outline text into structured outline format
        This method analyzes the text and splits it into pages without modifying the original text
        
        Args:
            project_context: 專案上下文物件，包含所有原始資訊
        
        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        parse_prompt = get_outline_parsing_prompt(project_context, language)
        outline = self.generate_json(parse_prompt, thinking_budget=1000)
        return outline
    
    def flatten_outline(self, outline: List[Dict]) -> List[Dict]:
        """
        Flatten outline structure to page list
        Based on demo.py flatten_outline()
        """
        pages = []
        for item in outline:
            if "part" in item and "pages" in item:
                # This is a part, expand its pages
                for page in item["pages"]:
                    page_with_part = page.copy()
                    page_with_part["part"] = item["part"]
                    pages.append(page_with_part)
            else:
                # This is a direct page
                pages.append(item)
        return pages
    
    def generate_page_description(self, project_context: ProjectContext, outline: List[Dict], 
                                 page_outline: Dict, page_index: int, language='zh') -> str:
        """
        Generate description for a single page
        Based on demo.py gen_desc() logic
        
        Args:
            project_context: 專案上下文物件，包含所有原始資訊
            outline: Complete outline
            page_outline: Outline for this specific page
            page_index: Page number (1-indexed)
        
        Returns:
            Text description for the page
        """
        part_info = f"\nThis page belongs to: {page_outline['part']}" if 'part' in page_outline else ""
        
        desc_prompt = get_page_description_prompt(
            project_context=project_context,
            outline=outline,
            page_outline=page_outline,
            page_index=page_index,
            part_info=part_info,
            language=language
        )
        
        # 根據 enable_text_reasoning 配置調整 thinking_budget
        actual_budget = self._get_text_thinking_budget()
        response_text = self.text_provider.generate_text(desc_prompt, thinking_budget=actual_budget)
        
        return dedent(response_text)
    
    def generate_outline_text(self, outline: List[Dict]) -> str:
        """
        Convert outline to text format for prompts
        Based on demo.py gen_outline_text()
        """
        text_parts = []
        for i, item in enumerate(outline, 1):
            if "part" in item and "pages" in item:
                text_parts.append(f"{i}. {item['part']}")
            else:
                text_parts.append(f"{i}. {item.get('title', 'Untitled')}")
        result = "\n".join(text_parts)
        return dedent(result)
    
    def generate_image_prompt(self, outline: List[Dict], page: Dict, 
                            page_desc: str, page_index: int, 
                            has_material_images: bool = False,
                            extra_requirements: Optional[str] = None,
                            language='zh',
                            has_template: bool = True) -> str:
        """
        Generate image generation prompt for a page
        Based on demo.py gen_prompts()
        
        Args:
            outline: Complete outline
            page: Page outline data
            page_desc: Page description text
            page_index: Page number (1-indexed)
            has_material_images: 是否有素材圖片（從專案描述中提取的圖片）
            extra_requirements: Optional extra requirements to apply to all pages
            language: Output language
            has_template: 是否有模板圖片（False表示無模板圖模式）
        
        Returns:
            Image generation prompt
        """
        outline_text = self.generate_outline_text(outline)
        
        # Determine current section
        if 'part' in page:
            current_section = page['part']
        else:
            current_section = f"{page.get('title', 'Untitled')}"
        
        # 在傳給文生圖模型之前，移除 Markdown 圖片連結
        # 圖片本身已經透過 additional_ref_images 傳遞，只保留文字描述
        cleaned_page_desc = self.remove_markdown_images(page_desc)
        
        prompt = get_image_generation_prompt(
            page_desc=cleaned_page_desc,
            outline_text=outline_text,
            current_section=current_section,
            has_material_images=has_material_images,
            extra_requirements=extra_requirements,
            language=language,
            has_template=has_template,
            page_index=page_index
        )
        
        return prompt
    
    def generate_image(self, prompt: str, ref_image_path: Optional[str] = None, 
                      aspect_ratio: str = "16:9", resolution: str = "2K",
                      additional_ref_images: Optional[List[Union[str, Image.Image]]] = None) -> Optional[Image.Image]:
        """
        Generate image using configured image provider
        Based on gemini_genai.py gen_image()
        
        Args:
            prompt: Image generation prompt
            ref_image_path: Path to reference image (optional). If None, will generate based on prompt only.
            aspect_ratio: Image aspect ratio
            resolution: Image resolution (note: OpenAI format only supports 1K)
            additional_ref_images: 額外的參考圖片列表，可以是本地路徑、URL 或 PIL Image 物件
        
        Returns:
            PIL Image object or None if failed
        
        Raises:
            Exception with detailed error message if generation fails
        """
        try:
            logger.debug(f"Reference image: {ref_image_path}")
            if additional_ref_images:
                logger.debug(f"Additional reference images: {len(additional_ref_images)}")
            logger.debug(f"Config - aspect_ratio: {aspect_ratio}, resolution: {resolution}")

            # 構建參考圖片列表
            ref_images = []
            
            # 新增主參考圖片（如果提供了路徑）
            if ref_image_path:
                if not os.path.exists(ref_image_path):
                    raise FileNotFoundError(f"Reference image not found: {ref_image_path}")
                main_ref_image = Image.open(ref_image_path)
                ref_images.append(main_ref_image)
            
            # 新增額外的參考圖片
            if additional_ref_images:
                for ref_img in additional_ref_images:
                    if isinstance(ref_img, Image.Image):
                        # 已經是 PIL Image 物件
                        ref_images.append(ref_img)
                    elif isinstance(ref_img, str):
                        # 可能是本地路徑或 URL
                        if os.path.exists(ref_img):
                            # 本地路徑
                            ref_images.append(Image.open(ref_img))
                        elif ref_img.startswith('http://') or ref_img.startswith('https://'):
                            # URL，需要下載
                            downloaded_img = self.download_image_from_url(ref_img)
                            if downloaded_img:
                                ref_images.append(downloaded_img)
                            else:
                                logger.warning(f"Failed to download image from URL: {ref_img}, skipping...")
                        elif ref_img.startswith('/files/mineru/'):
                            # MinerU 本地檔案路徑，需要轉換為檔案系統路徑（支援字首匹配）
                            local_path = self._convert_mineru_path_to_local(ref_img)
                            if local_path and os.path.exists(local_path):
                                ref_images.append(Image.open(local_path))
                                logger.debug(f"Loaded MinerU image from local path: {local_path}")
                            else:
                                logger.warning(f"MinerU image file not found (with prefix matching): {ref_img}, skipping...")
                        else:
                            logger.warning(f"Invalid image reference: {ref_img}, skipping...")
            
            logger.debug(f"Calling image provider for generation with {len(ref_images)} reference images...")
            logger.debug(f"Enable image reasoning/thinking: {self.enable_image_reasoning}, budget: {self._get_image_thinking_budget()}")
            
            # 使用 image_provider 生成圖片
            # 根據 enable_image_reasoning 配置控制影象生成的思考模式
            return self.image_provider.generate_image(
                prompt=prompt,
                ref_images=ref_images if ref_images else None,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                enable_thinking=self.enable_image_reasoning,
                thinking_budget=self._get_image_thinking_budget()
            )
            
        except Exception as e:
            error_detail = f"Error generating image: {type(e).__name__}: {str(e)}"
            logger.error(error_detail, exc_info=True)
            raise Exception(error_detail) from e
    
    def edit_image(self, prompt: str, current_image_path: str,
                  aspect_ratio: str = "16:9", resolution: str = "2K",
                  original_description: str = None,
                  additional_ref_images: Optional[List[Union[str, Image.Image]]] = None) -> Optional[Image.Image]:
        """
        Edit existing image with natural language instruction
        Uses current image as reference
        
        Args:
            prompt: Edit instruction
            current_image_path: Path to current page image
            aspect_ratio: Image aspect ratio
            resolution: Image resolution
            original_description: Original page description to include in prompt
            additional_ref_images: 額外的參考圖片列表，可以是本地路徑、URL 或 PIL Image 物件
        
        Returns:
            PIL Image object or None if failed
        """
        # Build edit instruction with original description if available
        edit_instruction = get_image_edit_prompt(
            edit_instruction=prompt,
            original_description=original_description
        )
        return self.generate_image(edit_instruction, current_image_path, aspect_ratio, resolution, additional_ref_images)
    
    def parse_description_to_outline(self, project_context: ProjectContext, language='zh') -> List[Dict]:
        """
        從描述文字解析出大綱結構
        
        Args:
            project_context: 專案上下文物件，包含所有原始資訊
        
        Returns:
            List of outline items (may contain parts with pages or direct pages)
        """
        parse_prompt = get_description_to_outline_prompt(project_context, language)
        outline = self.generate_json(parse_prompt, thinking_budget=1000)
        return outline
    
    def parse_description_to_page_descriptions(self, project_context: ProjectContext, 
                                               outline: List[Dict],
                                               language='zh') -> List[str]:
        """
        從描述文字切分出每頁描述
        
        Args:
            project_context: 專案上下文物件，包含所有原始資訊
            outline: 已解析出的大綱結構
        
        Returns:
            List of page descriptions (strings), one for each page in the outline
        """
        split_prompt = get_description_split_prompt(project_context, outline, language)
        descriptions = self.generate_json(split_prompt, thinking_budget=1000)
        
        # 確保返回的是字串列表
        if isinstance(descriptions, list):
            return [str(desc) for desc in descriptions]
        else:
            raise ValueError("Expected a list of page descriptions, but got: " + str(type(descriptions)))
    
    def refine_outline(self, current_outline: List[Dict], user_requirement: str,
                      project_context: ProjectContext,
                      previous_requirements: Optional[List[str]] = None,
                      language='zh') -> List[Dict]:
        """
        根據使用者要求修改已有大綱
        
        Args:
            current_outline: 當前的大綱結構
            user_requirement: 使用者的新要求
            project_context: 專案上下文物件，包含所有原始資訊
            previous_requirements: 之前的修改要求列表（可選）
        
        Returns:
            修改後的大綱結構
        """
        refinement_prompt = get_outline_refinement_prompt(
            current_outline=current_outline,
            user_requirement=user_requirement,
            project_context=project_context,
            previous_requirements=previous_requirements,
            language=language
        )
        outline = self.generate_json(refinement_prompt, thinking_budget=1000)
        return outline
    
    def refine_descriptions(self, current_descriptions: List[Dict], user_requirement: str,
                           project_context: ProjectContext,
                           outline: List[Dict] = None,
                           previous_requirements: Optional[List[str]] = None,
                           language='zh') -> List[str]:
        """
        根據使用者要求修改已有頁面描述
        
        Args:
            current_descriptions: 當前的頁面描述列表，每個元素包含 {index, title, description_content}
            user_requirement: 使用者的新要求
            project_context: 專案上下文物件，包含所有原始資訊
            outline: 完整的大綱結構（可選）
            previous_requirements: 之前的修改要求列表（可選）
        
        Returns:
            修改後的頁面描述列表（字串列表）
        """
        refinement_prompt = get_descriptions_refinement_prompt(
            current_descriptions=current_descriptions,
            user_requirement=user_requirement,
            project_context=project_context,
            outline=outline,
            previous_requirements=previous_requirements,
            language=language
        )
        descriptions = self.generate_json(refinement_prompt, thinking_budget=1000)
        
        # 確保返回的是字串列表
        if isinstance(descriptions, list):
            return [str(desc) for desc in descriptions]
        else:
            raise ValueError("Expected a list of page descriptions, but got: " + str(type(descriptions)))

