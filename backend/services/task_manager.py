"""
Task Manager - handles background tasks using ThreadPoolExecutor
No need for Celery or Redis, uses in-memory task tracking
"""
import logging
import threading
import os
import base64
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Dict, Any
from datetime import datetime
from sqlalchemy import func
from models import db, Task, Page, Material, PageImageVersion
from utils import get_filtered_pages
from pathlib import Path

logger = logging.getLogger(__name__)


def detect_text_regions(image_path: str, api_base: str, api_key: str, model: str = "gpt-4o") -> list:
    """
    使用 vision API 分析投影片圖，偵測每個文字區塊的 bounding box。
    返回格式：[{"text": str, "x0": float, "y0": float, "x1": float, "y1": float, "type": str}, ...]
    座標為 0~1 之間的比例值（相對圖片寬高）。
    type 可為 "title" / "bullet" / "label" / "other"
    """
    try:
        with open(image_path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()

        prompt = """Analyze this presentation slide image. Identify ALL visible text regions.
For each text region, return a JSON array with objects containing:
- "text": the exact text content
- "x0": left edge (0.0 to 1.0, relative to image width)
- "y0": top edge (0.0 to 1.0, relative to image height)  
- "x1": right edge (0.0 to 1.0, relative to image width)
- "y1": bottom edge (0.0 to 1.0, relative to image height)
- "type": one of "title", "bullet", "label", "other"

Rules:
- Title: the main heading, usually large font at top
- Bullet: body text, list items, paragraph text
- Label: small captions, footnotes, decorative text
- Other: anything else

Return ONLY a valid JSON array, no explanation. Example:
[{"text": "Main Title", "x0": 0.05, "y0": 0.05, "x1": 0.90, "y1": 0.20, "type": "title"},
 {"text": "• First point", "x0": 0.05, "y0": 0.30, "x1": 0.85, "y1": 0.42, "type": "bullet"}]

If there are no text regions, return [].
"""

        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]
            }],
            "max_tokens": 2000
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        base = api_base.rstrip('/')
        resp = requests.post(f"{base}/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()

        content = resp.json()['choices'][0]['message']['content']

        # 清理 markdown code block
        content = content.strip()
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        regions = json.loads(content)
        if not isinstance(regions, list):
            return []

        # 驗證並夾緊座標
        valid = []
        for r in regions:
            if not isinstance(r, dict):
                continue
            try:
                valid.append({
                    "text": str(r.get("text", "")),
                    "x0": max(0.0, min(1.0, float(r.get("x0", 0)))),
                    "y0": max(0.0, min(1.0, float(r.get("y0", 0)))),
                    "x1": max(0.0, min(1.0, float(r.get("x1", 1)))),
                    "y1": max(0.0, min(1.0, float(r.get("y1", 1)))),
                    "type": r.get("type", "other"),
                })
            except (TypeError, ValueError):
                continue

        return valid

    except Exception as e:
        logger.warning(f"detect_text_regions failed: {e}")
        return []


class TaskManager:
    """Simple task manager using ThreadPoolExecutor"""
    
    def __init__(self, max_workers: int = 4):
        """Initialize task manager"""
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = {}  # task_id -> Future
        self.lock = threading.Lock()
    
    def submit_task(self, task_id: str, func: Callable, *args, **kwargs):
        """Submit a background task"""
        future = self.executor.submit(func, task_id, *args, **kwargs)
        
        with self.lock:
            self.active_tasks[task_id] = future
        
        # Add callback to clean up when done and log exceptions
        future.add_done_callback(lambda f: self._task_done_callback(task_id, f))
    
    def _task_done_callback(self, task_id: str, future):
        """Handle task completion and log any exceptions"""
        try:
            # Check if task raised an exception
            exception = future.exception()
            if exception:
                logger.error(f"Task {task_id} failed with exception: {exception}", exc_info=exception)
        except Exception as e:
            logger.error(f"Error in task callback for {task_id}: {e}", exc_info=True)
        finally:
            self._cleanup_task(task_id)
    
    def _cleanup_task(self, task_id: str):
        """Clean up completed task"""
        with self.lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    def is_task_active(self, task_id: str) -> bool:
        """Check if task is still running"""
        with self.lock:
            return task_id in self.active_tasks
    
    def shutdown(self):
        """Shutdown the executor"""
        self.executor.shutdown(wait=True)


# Global task manager instance
task_manager = TaskManager(max_workers=4)


def save_image_with_version(image, project_id: str, page_id: str, file_service,
                            page_obj=None, image_format: str = 'PNG') -> tuple[str, int]:
    """
    儲存圖片並建立歷史版本記錄的公共函式

    Args:
        image: PIL Image 物件
        project_id: 專案ID
        page_id: 頁面ID
        file_service: FileService 例項
        page_obj: Page 物件（可選，如果提供則更新頁面狀態）
        image_format: 圖片格式，預設 PNG

    Returns:
        tuple: (image_path, version_number) - 圖片路徑和版本號

    這個函式會：
    1. 計算下一個版本號（使用 MAX 查詢確保安全）
    2. 標記所有舊版本為非當前版本
    3. 儲存圖片到最終位置
    4. 生成並儲存壓縮的快取圖片
    5. 建立新版本記錄
    6. 如果提供了 page_obj，更新頁面狀態和圖片路徑
    """
    # 使用 MAX 查詢確保版本號安全（即使有版本被刪除也不會重複）
    max_version = db.session.query(func.max(PageImageVersion.version_number)).filter_by(page_id=page_id).scalar() or 0
    next_version = max_version + 1

    # 批次更新：標記所有舊版本為非當前版本（使用單條 SQL 更高效）
    PageImageVersion.query.filter_by(page_id=page_id).update({'is_current': False})

    # 儲存原圖到最終位置（使用版本號）
    image_path = file_service.save_generated_image(
        image, project_id, page_id,
        version_number=next_version,
        image_format=image_format
    )

    # 生成並儲存壓縮的快取圖片（用於前端快速顯示）
    cached_image_path = file_service.save_cached_image(
        image, project_id, page_id,
        version_number=next_version,
        quality=85
    )

    # 建立新版本記錄
    new_version = PageImageVersion(
        page_id=page_id,
        image_path=image_path,
        version_number=next_version,
        is_current=True
    )
    db.session.add(new_version)

    # 如果提供了 page_obj，更新頁面狀態和圖片路徑
    if page_obj:
        page_obj.generated_image_path = image_path
        page_obj.cached_image_path = cached_image_path
        page_obj.status = 'COMPLETED'
        page_obj.updated_at = datetime.utcnow()

    # 提交事務
    db.session.commit()

    logger.debug(f"Page {page_id} image saved as version {next_version}: {image_path}, cached: {cached_image_path}")

    return image_path, next_version


def generate_descriptions_task(task_id: str, project_id: str, ai_service, 
                               project_context, outline: List[Dict], 
                               max_workers: int = 5, app=None,
                               language: str = None):
    """
    Background task for generating page descriptions
    Based on demo.py gen_desc() with parallel processing
    
    Note: app instance MUST be passed from the request context
    
    Args:
        task_id: Task ID
        project_id: Project ID
        ai_service: AI service instance
        project_context: ProjectContext object containing all project information
        outline: Complete outline structure
        max_workers: Maximum number of parallel workers
        app: Flask app instance
        language: Output language (zh, en, ja, auto)
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    # 在整個任務中保持應用上下文
    with app.app_context():
        try:
            # 重要：在後臺執行緒開始時就獲取task和設定狀態
            task = Task.query.get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return
            
            task.status = 'PROCESSING'
            db.session.commit()
            logger.info(f"Task {task_id} status updated to PROCESSING")
            
            # Flatten outline to get pages
            pages_data = ai_service.flatten_outline(outline)
            
            # Get all pages for this project
            pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
            
            if len(pages) != len(pages_data):
                raise ValueError("Page count mismatch")
            
            # Initialize progress
            task.set_progress({
                "total": len(pages),
                "completed": 0,
                "failed": 0
            })
            db.session.commit()
            
            # Generate descriptions in parallel
            completed = 0
            failed = 0
            
            def generate_single_desc(page_id, page_outline, page_index):
                """
                Generate description for a single page
                注意：只傳遞 page_id（字串），不傳遞 ORM 物件，避免跨執行緒會話問題
                """
                # 關鍵修復：在子執行緒中也需要應用上下文
                with app.app_context():
                    try:
                        # Get singleton AI service instance
                        from services.ai_service_manager import get_ai_service
                        ai_service = get_ai_service()
                        
                        desc_text = ai_service.generate_page_description(
                            project_context, outline, page_outline, page_index,
                            language=language
                        )
                        
                        # Parse description into structured format
                        # This is a simplified version - you may want more sophisticated parsing
                        desc_content = {
                            "text": desc_text,
                            "generated_at": datetime.utcnow().isoformat()
                        }
                        
                        return (page_id, desc_content, None)
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        logger.error(f"Failed to generate description for page {page_id}: {error_detail}")
                        return (page_id, None, str(e))
            
            # Use ThreadPoolExecutor for parallel generation
            # 關鍵：提前提取 page.id，不要傳遞 ORM 物件到子執行緒
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(generate_single_desc, page.id, page_data, i)
                    for i, (page, page_data) in enumerate(zip(pages, pages_data), 1)
                ]
                
                # Process results as they complete
                for future in as_completed(futures):
                    page_id, desc_content, error = future.result()
                    
                    db.session.expire_all()
                    
                    # Update page in database
                    page = Page.query.get(page_id)
                    if page:
                        if error:
                            page.status = 'FAILED'
                            failed += 1
                        else:
                            page.set_description_content(desc_content)
                            page.status = 'DESCRIPTION_GENERATED'
                            completed += 1
                        
                        db.session.commit()
                    
                    # Update task progress
                    task = Task.query.get(task_id)
                    if task:
                        task.update_progress(completed=completed, failed=failed)
                        db.session.commit()
                        logger.info(f"Description Progress: {completed}/{len(pages)} pages completed")
            
            # Mark task as completed
            task = Task.query.get(task_id)
            if task:
                task.status = 'COMPLETED'
                task.completed_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Task {task_id} COMPLETED - {completed} pages generated, {failed} failed")
            
            # Update project status
            from models import Project
            project = Project.query.get(project_id)
            if project and failed == 0:
                project.status = 'DESCRIPTIONS_GENERATED'
                db.session.commit()
                logger.info(f"Project {project_id} status updated to DESCRIPTIONS_GENERATED")
        
        except Exception as e:
            # Mark task as failed
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()


def generate_images_task(task_id: str, project_id: str, ai_service, file_service,
                        outline: List[Dict], use_template: bool = True, 
                        max_workers: int = 8, aspect_ratio: str = "16:9",
                        resolution: str = "2K", app=None,
                        extra_requirements: str = None,
                        language: str = None,
                        page_ids: list = None):
    """
    Background task for generating page images
    Based on demo.py gen_images_parallel()
    
    Note: app instance MUST be passed from the request context
    
    Args:
        language: Output language (zh, en, ja, auto)
        page_ids: Optional list of page IDs to generate (if not provided, generates all pages)
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    with app.app_context():
        try:
            # Update task status to PROCESSING
            task = Task.query.get(task_id)
            if not task:
                return
            
            task.status = 'PROCESSING'
            db.session.commit()
            
            # Get pages for this project (filtered by page_ids if provided)
            pages = get_filtered_pages(project_id, page_ids)
            pages_data = ai_service.flatten_outline(outline)
            
            # 注意：不在任務開始時獲取模板路徑，而是在每個子執行緒中動態獲取
            # 這樣可以確保即使使用者在上傳新模板後立即生成，也能使用最新模板
            
            # Initialize progress
            task.set_progress({
                "total": len(pages),
                "completed": 0,
                "failed": 0
            })
            db.session.commit()
            
            # Generate images in parallel
            completed = 0
            failed = 0
            
            def generate_single_image(page_id, page_data, page_index):
                """
                Generate image for a single page
                注意：只傳遞 page_id（字串），不傳遞 ORM 物件，避免跨執行緒會話問題
                """
                # 關鍵修復：在子執行緒中也需要應用上下文
                with app.app_context():
                    try:
                        logger.debug(f"Starting image generation for page {page_id}, index {page_index}")
                        # Get page from database in this thread
                        page_obj = Page.query.get(page_id)
                        if not page_obj:
                            raise ValueError(f"Page {page_id} not found")
                        
                        # Update page status
                        page_obj.status = 'GENERATING'
                        db.session.commit()
                        logger.debug(f"Page {page_id} status updated to GENERATING")
                        
                        # Get description content
                        desc_content = page_obj.get_description_content()
                        if not desc_content:
                            raise ValueError("No description content for page")
                        
                        # 獲取描述文字（可能是 text 欄位或 text_content 陣列）
                        desc_text = desc_content.get('text', '')
                        if not desc_text and desc_content.get('text_content'):
                            # 如果 text 欄位不存在，嘗試從 text_content 陣列獲取
                            text_content = desc_content.get('text_content', [])
                            if isinstance(text_content, list):
                                desc_text = '\n'.join(text_content)
                            else:
                                desc_text = str(text_content)
                        
                        logger.debug(f"Got description text for page {page_id}: {desc_text[:100]}...")
                        
                        # 從當前頁面的描述內容中提取圖片 URL
                        page_additional_ref_images = []
                        has_material_images = False
                        
                        # 從描述文字中提取圖片
                        if desc_text:
                            image_urls = ai_service.extract_image_urls_from_markdown(desc_text)
                            if image_urls:
                                logger.info(f"Found {len(image_urls)} image(s) in page {page_id} description")
                                page_additional_ref_images = image_urls
                                has_material_images = True
                        
                        # 在子執行緒中動態獲取模板路徑，確保使用最新模板
                        page_ref_image_path = None
                        if use_template:
                            page_ref_image_path = file_service.get_template_path(project_id)
                            # 注意：如果有風格描述，即使沒有模板圖片也允許生成
                            # 這個檢查已經在 controller 層完成，這裡不再檢查
                        
                        # Generate image prompt
                        prompt = ai_service.generate_image_prompt(
                            outline, page_data, desc_text, page_index,
                            has_material_images=has_material_images,
                            extra_requirements=extra_requirements,
                            language=language,
                            has_template=use_template
                        )
                        logger.debug(f"Generated image prompt for page {page_id}")
                        
                        # Generate image
                        logger.info(f"🎨 Calling AI service to generate image for page {page_index}/{len(pages)}...")
                        image = ai_service.generate_image(
                            prompt, page_ref_image_path, aspect_ratio, resolution,
                            additional_ref_images=page_additional_ref_images if page_additional_ref_images else None
                        )
                        logger.info(f"✅ Image generated successfully for page {page_index}")
                        
                        if not image:
                            raise ValueError("Failed to generate image")
                        
                        # 最佳化：直接在子執行緒中計算版本號並儲存到最終位置
                        # 每個頁面獨立，使用資料庫事務保證版本號原子性，避免臨時檔案
                        image_path, next_version = save_image_with_version(
                            image, project_id, page_id, file_service, page_obj=page_obj
                        )

                        # ── 生成無文字背景圖（供 PPTX 匯出用）─────────────────────
                        try:
                            from services.prompts import get_clean_background_prompt
                            bg_prompt = get_clean_background_prompt()
                            logger.info(f"🖼️ Generating text-free background for page {page_index}...")
                            bg_image = ai_service.generate_image(
                                bg_prompt,
                                ref_image_path=file_service.get_absolute_path(image_path),
                                aspect_ratio=aspect_ratio,
                                resolution=resolution,
                            )
                            if bg_image:
                                abs_img_path = file_service.get_absolute_path(image_path)
                                import os
                                bg_filename = os.path.basename(abs_img_path).replace('.png', '_bg.png')
                                bg_dir = os.path.dirname(abs_img_path)
                                bg_abs_path = os.path.join(bg_dir, bg_filename)
                                bg_image.save(bg_abs_path, format='PNG')
                                # 轉換為相對路徑（與 image_path 格式相同）
                                bg_rel_path = image_path.replace(
                                    os.path.basename(abs_img_path), bg_filename
                                )
                                # 更新資料庫（已在 app_context 內）
                                _p = Page.query.get(page_id)
                                if _p:
                                    _p.bg_image_path = bg_rel_path
                                    db.session.commit()
                                logger.info(f"✅ Background image saved: {bg_abs_path}")
                            else:
                                logger.warning(f"Background image generation returned None for page {page_index}")
                        except Exception as bg_err:
                            logger.warning(f"Background image generation failed (non-critical): {bg_err}")

                        # ── Vision 分析：偵測文字區塊 bbox（供 PPTX 匯出用）──────────
                        try:
                            from config import get_config
                            cfg = get_config()
                            _api_base = getattr(cfg, 'OPENAI_API_BASE', None) or os.environ.get('OPENAI_API_BASE', '')
                            _api_key = getattr(cfg, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY', '')
                            if _api_base and _api_key:
                                _analyze_path = bg_abs_path if ('bg_abs_path' in dir() and os.path.exists(bg_abs_path)) else file_service.get_absolute_path(image_path)
                                logger.info(f"🔍 Detecting text regions for page {page_index}...")
                                regions = detect_text_regions(_analyze_path, _api_base, _api_key)
                                if regions:
                                    _p2 = Page.query.get(page_id)
                                    if _p2:
                                        _p2.text_regions = json.dumps(regions, ensure_ascii=False)
                                        db.session.commit()
                                    logger.info(f"✅ Detected {len(regions)} text regions for page {page_index}")
                                else:
                                    logger.warning(f"No text regions detected for page {page_index}")
                        except Exception as vis_err:
                            logger.warning(f"Text region detection failed (non-critical): {vis_err}")
                        # ────────────────────────────────────────────────────────────

                        return (page_id, image_path, None)
                        
                    except Exception as e:
                        import traceback
                        error_detail = traceback.format_exc()
                        logger.error(f"Failed to generate image for page {page_id}: {error_detail}")
                        return (page_id, None, str(e))
            
            # Use ThreadPoolExecutor for parallel generation
            # 關鍵：提前提取 page.id，不要傳遞 ORM 物件到子執行緒
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(generate_single_image, page.id, page_data, i)
                    for i, (page, page_data) in enumerate(zip(pages, pages_data), 1)
                ]
                
                # Process results as they complete
                for future in as_completed(futures):
                    page_id, image_path, error = future.result()
                    
                    db.session.expire_all()
                    
                    # Update page in database (主要是為了更新失敗狀態)
                    page = Page.query.get(page_id)
                    if page:
                        if error:
                            page.status = 'FAILED'
                            failed += 1
                            db.session.commit()
                        else:
                            # 圖片已在子執行緒中儲存並建立版本記錄，這裡只需要更新計數
                            completed += 1
                            # 重新整理頁面物件以獲取最新狀態
                            db.session.refresh(page)
                    
                    # Update task progress
                    task = Task.query.get(task_id)
                    if task:
                        task.update_progress(completed=completed, failed=failed)
                        db.session.commit()
                        logger.info(f"Image Progress: {completed}/{len(pages)} pages completed")
            
            # Mark task as completed
            task = Task.query.get(task_id)
            if task:
                task.status = 'COMPLETED'
                task.completed_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"Task {task_id} COMPLETED - {completed} images generated, {failed} failed")
            
            # Update project status
            from models import Project
            project = Project.query.get(project_id)
            if project and failed == 0:
                project.status = 'COMPLETED'
                db.session.commit()
                logger.info(f"Project {project_id} status updated to COMPLETED")
        
        except Exception as e:
            # Mark task as failed
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()


def generate_single_page_image_task(task_id: str, project_id: str, page_id: str, 
                                    ai_service, file_service, outline: List[Dict],
                                    use_template: bool = True, aspect_ratio: str = "16:9",
                                    resolution: str = "2K", app=None,
                                    extra_requirements: str = None,
                                    language: str = None):
    """
    Background task for generating a single page image
    
    Note: app instance MUST be passed from the request context
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    with app.app_context():
        try:
            # Update task status to PROCESSING
            task = Task.query.get(task_id)
            if not task:
                return
            
            task.status = 'PROCESSING'
            db.session.commit()
            
            # Get page from database
            page = Page.query.get(page_id)
            if not page or page.project_id != project_id:
                raise ValueError(f"Page {page_id} not found")
            
            # Update page status
            page.status = 'GENERATING'
            db.session.commit()
            
            # Get description content
            desc_content = page.get_description_content()
            if not desc_content:
                raise ValueError("No description content for page")
            
            # 獲取描述文字（可能是 text 欄位或 text_content 陣列）
            desc_text = desc_content.get('text', '')
            if not desc_text and desc_content.get('text_content'):
                text_content = desc_content.get('text_content', [])
                if isinstance(text_content, list):
                    desc_text = '\n'.join(text_content)
                else:
                    desc_text = str(text_content)
            
            # 從描述文字中提取圖片 URL
            additional_ref_images = []
            has_material_images = False
            
            if desc_text:
                image_urls = ai_service.extract_image_urls_from_markdown(desc_text)
                if image_urls:
                    logger.info(f"Found {len(image_urls)} image(s) in page {page_id} description")
                    additional_ref_images = image_urls
                    has_material_images = True
            
            # Get template path if use_template
            ref_image_path = None
            if use_template:
                ref_image_path = file_service.get_template_path(project_id)
                # 注意：如果有風格描述，即使沒有模板圖片也允許生成
                # 這個檢查已經在 controller 層完成，這裡不再檢查
            
            # Generate image prompt
            page_data = page.get_outline_content() or {}
            if page.part:
                page_data['part'] = page.part
            
            prompt = ai_service.generate_image_prompt(
                outline, page_data, desc_text, page.order_index + 1,
                has_material_images=has_material_images,
                extra_requirements=extra_requirements,
                language=language,
                has_template=use_template
            )
            
            # Generate image
            logger.info(f"🎨 Generating image for page {page_id}...")
            image = ai_service.generate_image(
                prompt, ref_image_path, aspect_ratio, resolution,
                additional_ref_images=additional_ref_images if additional_ref_images else None
            )
            
            if not image:
                raise ValueError("Failed to generate image")
            
            # 儲存圖片並建立歷史版本記錄
            image_path, next_version = save_image_with_version(
                image, project_id, page_id, file_service, page_obj=page
            )
            
            # Mark task as completed
            task.status = 'COMPLETED'
            task.completed_at = datetime.utcnow()
            task.set_progress({
                "total": 1,
                "completed": 1,
                "failed": 0
            })
            db.session.commit()
            
            logger.info(f"✅ Task {task_id} COMPLETED - Page {page_id} image generated")
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"Task {task_id} FAILED: {error_detail}")
            
            # Mark task as failed
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
            
            # Update page status
            page = Page.query.get(page_id)
            if page:
                page.status = 'FAILED'
                db.session.commit()


def edit_page_image_task(task_id: str, project_id: str, page_id: str,
                         edit_instruction: str, ai_service, file_service,
                         aspect_ratio: str = "16:9", resolution: str = "2K",
                         original_description: str = None,
                         additional_ref_images: List[str] = None,
                         temp_dir: str = None, app=None):
    """
    Background task for editing a page image
    
    Note: app instance MUST be passed from the request context
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    with app.app_context():
        try:
            # Update task status to PROCESSING
            task = Task.query.get(task_id)
            if not task:
                return
            
            task.status = 'PROCESSING'
            db.session.commit()
            
            # Get page from database
            page = Page.query.get(page_id)
            if not page or page.project_id != project_id:
                raise ValueError(f"Page {page_id} not found")
            
            if not page.generated_image_path:
                raise ValueError("Page must have generated image first")
            
            # Update page status
            page.status = 'GENERATING'
            db.session.commit()
            
            # Get current image path
            current_image_path = file_service.get_absolute_path(page.generated_image_path)
            
            # Edit image
            logger.info(f"🎨 Editing image for page {page_id}...")
            try:
                image = ai_service.edit_image(
                    edit_instruction,
                    current_image_path,
                    aspect_ratio,
                    resolution,
                    original_description=original_description,
                    additional_ref_images=additional_ref_images if additional_ref_images else None
                )
            finally:
                # Clean up temp directory if created
                if temp_dir:
                    import shutil
                    from pathlib import Path
                    temp_path = Path(temp_dir)
                    if temp_path.exists():
                        shutil.rmtree(temp_dir)
            
            if not image:
                raise ValueError("Failed to edit image")
            
            # 儲存編輯後的圖片並建立歷史版本記錄
            image_path, next_version = save_image_with_version(
                image, project_id, page_id, file_service, page_obj=page
            )
            
            # Mark task as completed
            task.status = 'COMPLETED'
            task.completed_at = datetime.utcnow()
            task.set_progress({
                "total": 1,
                "completed": 1,
                "failed": 0
            })
            db.session.commit()
            
            logger.info(f"✅ Task {task_id} COMPLETED - Page {page_id} image edited")
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"Task {task_id} FAILED: {error_detail}")
            
            # Clean up temp directory on error
            if temp_dir:
                import shutil
                from pathlib import Path
                temp_path = Path(temp_dir)
                if temp_path.exists():
                    shutil.rmtree(temp_dir)
            
            # Mark task as failed
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
            
            # Update page status
            page = Page.query.get(page_id)
            if page:
                page.status = 'FAILED'
                db.session.commit()


def generate_material_image_task(task_id: str, project_id: str, prompt: str,
                                 ai_service, file_service,
                                 ref_image_path: str = None,
                                 additional_ref_images: List[str] = None,
                                 aspect_ratio: str = "16:9",
                                 resolution: str = "2K",
                                 temp_dir: str = None, app=None):
    """
    Background task for generating a material image
    複用核心的generate_image邏輯，但儲存到Material表而不是Page表
    
    Note: app instance MUST be passed from the request context
    project_id can be None for global materials (but Task model requires a project_id,
    so we use a special value 'global' for task tracking)
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    with app.app_context():
        try:
            # Update task status to PROCESSING
            task = Task.query.get(task_id)
            if not task:
                return
            
            task.status = 'PROCESSING'
            db.session.commit()
            
            # Generate image (複用核心邏輯)
            logger.info(f"🎨 Generating material image with prompt: {prompt[:100]}...")
            image = ai_service.generate_image(
                prompt=prompt,
                ref_image_path=ref_image_path,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                additional_ref_images=additional_ref_images or None,
            )
            
            if not image:
                raise ValueError("Failed to generate image")
            
            # 處理project_id：如果為'global'或None，轉換為None
            actual_project_id = None if (project_id == 'global' or project_id is None) else project_id
            
            # Save generated material image
            relative_path = file_service.save_material_image(image, actual_project_id)
            relative = Path(relative_path)
            filename = relative.name
            
            # Construct frontend-accessible URL
            image_url = file_service.get_file_url(actual_project_id, 'materials', filename)
            
            # Save material info to database
            material = Material(
                project_id=actual_project_id,
                filename=filename,
                relative_path=relative_path,
                url=image_url
            )
            db.session.add(material)
            
            # Mark task as completed
            task.status = 'COMPLETED'
            task.completed_at = datetime.utcnow()
            task.set_progress({
                "total": 1,
                "completed": 1,
                "failed": 0,
                "material_id": material.id,
                "image_url": image_url
            })
            db.session.commit()
            
            logger.info(f"✅ Task {task_id} COMPLETED - Material {material.id} generated")
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"Task {task_id} FAILED: {error_detail}")
            
            # Mark task as failed
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
        
        finally:
            # Clean up temp directory
            if temp_dir:
                import shutil
                temp_path = Path(temp_dir)
                if temp_path.exists():
                    shutil.rmtree(temp_dir, ignore_errors=True)


def export_editable_pptx_with_recursive_analysis_task(
    task_id: str, 
    project_id: str, 
    filename: str,
    file_service,
    page_ids: list = None,
    max_depth: int = 2,
    max_workers: int = 4,
    export_extractor_method: str = 'hybrid',
    export_inpaint_method: str = 'hybrid',
    app=None
):
    """
    使用遞迴圖片可編輯化分析匯出可編輯PPTX的後臺任務
    
    這是新的架構方法，使用ImageEditabilityService進行遞迴版面分析。
    與舊方法的區別：
    - 不再假設圖片是16:9
    - 支援任意尺寸和解析度
    - 遞迴分析圖片中的子圖和圖表
    - 更智慧的座標對映和元素提取
    - 不需要 ai_service（使用 ImageEditabilityService 和 MinerU）
    
    Args:
        task_id: 任務ID
        project_id: 專案ID
        filename: 輸出檔名
        file_service: 檔案服務例項
        page_ids: 可選的頁面ID列表（如果提供，只匯出這些頁面）
        max_depth: 最大遞迴深度
        max_workers: 併發處理數
        export_extractor_method: 元件提取方法 ('mineru' 或 'hybrid')
        export_inpaint_method: 背景修復方法 ('generative', 'baidu', 'hybrid')
        app: Flask應用例項
    """
    logger.info(f"🚀 Task {task_id} started: export_editable_pptx_with_recursive_analysis (project={project_id}, depth={max_depth}, workers={max_workers}, extractor={export_extractor_method}, inpaint={export_inpaint_method})")
    
    if app is None:
        raise ValueError("Flask app instance must be provided")
    
    with app.app_context():
        import os
        from datetime import datetime
        from PIL import Image
        from models import Project
        from services.export_service import ExportService
        
        logger.info(f"開始遞迴分析匯出任務 {task_id} for project {project_id}")
        
        try:
            # Get project
            project = Project.query.get(project_id)
            if not project:
                raise ValueError(f'Project {project_id} not found')
            
            # Get pages (filtered by page_ids if provided)
            pages = get_filtered_pages(project_id, page_ids)
            if not pages:
                raise ValueError('No pages found for project')
            
            image_paths = []
            for page in pages:
                if page.generated_image_path:
                    img_path = file_service.get_absolute_path(page.generated_image_path)
                    if os.path.exists(img_path):
                        image_paths.append(img_path)
            
            if not image_paths:
                raise ValueError('No generated images found for project')
            
            logger.info(f"找到 {len(image_paths)} 張圖片")
            
            # 初始化任務進度（包含訊息日誌）
            task = Task.query.get(task_id)
            task.set_progress({
                "total": 100,  # 使用百分比
                "completed": 0,
                "failed": 0,
                "current_step": "準備中...",
                "percent": 0,
                "messages": ["🚀 開始匯出可編輯PPTX..."]  # 訊息日誌
            })
            db.session.commit()
            
            # 進度回撥函式 - 更新資料庫中的進度
            progress_messages = ["🚀 開始匯出可編輯PPTX..."]
            max_messages = 10  # 最多保留最近10條訊息
            
            def progress_callback(step: str, message: str, percent: int):
                """更新任務進度到資料庫"""
                nonlocal progress_messages
                try:
                    # 新增新訊息到日誌
                    new_message = f"[{step}] {message}"
                    progress_messages.append(new_message)
                    # 只保留最近的訊息
                    if len(progress_messages) > max_messages:
                        progress_messages = progress_messages[-max_messages:]
                    
                    # 更新資料庫
                    task = Task.query.get(task_id)
                    if task:
                        task.set_progress({
                            "total": 100,
                            "completed": percent,
                            "failed": 0,
                            "current_step": message,
                            "percent": percent,
                            "messages": progress_messages.copy()
                        })
                        db.session.commit()
                except Exception as e:
                    logger.warning(f"更新進度失敗: {e}")
            
            # Step 1: 準備工作
            logger.info("Step 1: 準備工作...")
            progress_callback("準備", f"找到 {len(image_paths)} 張幻燈片圖片", 2)
            
            # 準備輸出路徑
            exports_dir = os.path.join(app.config['UPLOAD_FOLDER'], project_id, 'exports')
            os.makedirs(exports_dir, exist_ok=True)
            
            # Handle filename collision
            if not filename.endswith('.pptx'):
                filename += '.pptx'
            
            output_path = os.path.join(exports_dir, filename)
            if os.path.exists(output_path):
                base_name = filename.rsplit('.', 1)[0]
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                filename = f"{base_name}_{timestamp}.pptx"
                output_path = os.path.join(exports_dir, filename)
                logger.info(f"檔名衝突，使用新檔名: {filename}")
            
            # 獲取第一張圖片的尺寸作為參考
            first_img = Image.open(image_paths[0])
            slide_width, slide_height = first_img.size
            first_img.close()
            
            logger.info(f"幻燈片尺寸: {slide_width}x{slide_height}")
            logger.info(f"遞迴深度: {max_depth}, 併發數: {max_workers}")
            progress_callback("準備", f"幻燈片尺寸: {slide_width}×{slide_height}", 3)
            
            # Step 2: 建立文字屬性提取器
            from services.image_editability import TextAttributeExtractorFactory
            text_attribute_extractor = TextAttributeExtractorFactory.create_caption_model_extractor()
            progress_callback("準備", "文字屬性提取器已初始化", 5)
            
            # Step 3: 呼叫匯出方法（使用專案的匯出設定）
            logger.info(f"Step 3: 建立可編輯PPTX (extractor={export_extractor_method}, inpaint={export_inpaint_method})...")
            progress_callback("配置", f"提取方法: {export_extractor_method}, 背景修復: {export_inpaint_method}", 6)
            
            _, export_warnings = ExportService.create_editable_pptx_with_recursive_analysis(
                image_paths=image_paths,
                output_file=output_path,
                slide_width_pixels=slide_width,
                slide_height_pixels=slide_height,
                max_depth=max_depth,
                max_workers=max_workers,
                text_attribute_extractor=text_attribute_extractor,
                progress_callback=progress_callback,
                export_extractor_method=export_extractor_method,
                export_inpaint_method=export_inpaint_method
            )
            
            logger.info(f"✓ 可編輯PPTX已建立: {output_path}")
            
            # Step 4: 標記任務完成
            download_path = f"/files/{project_id}/exports/{filename}"
            
            # 新增完成訊息
            progress_messages.append("✅ 匯出完成！")
            
            # 新增警告資訊（如果有）
            warning_messages = []
            if export_warnings and export_warnings.has_warnings():
                warning_messages = export_warnings.to_summary()
                progress_messages.extend(warning_messages)
                logger.warning(f"匯出有 {len(warning_messages)} 條警告")
            
            task = Task.query.get(task_id)
            if task:
                task.status = 'COMPLETED'
                task.completed_at = datetime.utcnow()
                task.set_progress({
                    "total": 100,
                    "completed": 100,
                    "failed": 0,
                    "current_step": "✓ 匯出完成",
                    "percent": 100,
                    "messages": progress_messages,
                    "download_url": download_path,
                    "filename": filename,
                    "method": "recursive_analysis",
                    "max_depth": max_depth,
                    "warnings": warning_messages,  # 單獨的警告列表
                    "warning_details": export_warnings.to_dict() if export_warnings else {}  # 詳細警告資訊
                })
                db.session.commit()
                logger.info(f"✓ 任務 {task_id} 完成 - 遞迴分析匯出成功（深度={max_depth}）")
        
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logger.error(f"✗ 任務 {task_id} 失敗: {error_detail}")
            
            # 標記任務失敗
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = str(e)
                task.completed_at = datetime.utcnow()
                db.session.commit()
