"""
Page Controller - handles page-related endpoints
"""
import logging
from flask import Blueprint, request, current_app
from models import db, Project, Page, PageImageVersion, Task
from utils import success_response, error_response, not_found, bad_request
from services import FileService, ProjectContext
from services.ai_service_manager import get_ai_service
from services.task_manager import task_manager, generate_single_page_image_task, edit_page_image_task
from datetime import datetime
from pathlib import Path
from werkzeug.utils import secure_filename
import shutil
import tempfile
import json

logger = logging.getLogger(__name__)

page_bp = Blueprint('pages', __name__, url_prefix='/api/projects')


@page_bp.route('/<project_id>/pages', methods=['POST'])
def create_page(project_id):
    """
    POST /api/projects/{project_id}/pages - Add new page
    
    Request body:
    {
        "order_index": 2,
        "part": "optional",
        "outline_content": {"title": "...", "points": [...]}
    }
    """
    try:
        project = Project.query.get(project_id)
        
        if not project:
            return not_found('Project')
        
        data = request.get_json()
        
        if not data or 'order_index' not in data:
            return bad_request("order_index is required")
        
        # Create new page
        page = Page(
            project_id=project_id,
            order_index=data['order_index'],
            part=data.get('part'),
            status='DRAFT'
        )
        
        if 'outline_content' in data:
            page.set_outline_content(data['outline_content'])
        
        db.session.add(page)
        
        # Update other pages' order_index if necessary
        other_pages = Page.query.filter(
            Page.project_id == project_id,
            Page.order_index >= data['order_index']
        ).all()
        
        for p in other_pages:
            if p.id != page.id:
                p.order_index += 1
        
        project.updated_at = datetime.utcnow()
        db.session.commit()
        
        return success_response(page.to_dict(), status_code=201)
    
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_bp.route('/<project_id>/pages/<page_id>', methods=['DELETE'])
def delete_page(project_id, page_id):
    """
    DELETE /api/projects/{project_id}/pages/{page_id} - Delete page
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        # Delete page image if exists
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        file_service.delete_page_image(project_id, page_id)
        
        # Delete page
        db.session.delete(page)
        
        # Update project
        project = Project.query.get(project_id)
        if project:
            project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(message="Page deleted successfully")
    
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_bp.route('/<project_id>/pages/<page_id>/outline', methods=['PUT'])
def update_page_outline(project_id, page_id):
    """
    PUT /api/projects/{project_id}/pages/{page_id}/outline - Edit page outline
    
    Request body:
    {
        "outline_content": {"title": "...", "points": [...]}
    }
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        data = request.get_json()
        
        if not data or 'outline_content' not in data:
            return bad_request("outline_content is required")
        
        page.set_outline_content(data['outline_content'])
        page.updated_at = datetime.utcnow()
        
        # Update project
        project = Project.query.get(project_id)
        if project:
            project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_bp.route('/<project_id>/pages/<page_id>/description', methods=['PUT'])
def update_page_description(project_id, page_id):
    """
    PUT /api/projects/{project_id}/pages/{page_id}/description - Edit description
    
    Request body:
    {
        "description_content": {
            "title": "...",
            "text_content": ["...", "..."],
            "layout_suggestion": "..."
        }
    }
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        data = request.get_json()
        
        if not data or 'description_content' not in data:
            return bad_request("description_content is required")
        
        page.set_description_content(data['description_content'])
        page.updated_at = datetime.utcnow()
        
        # Update project
        project = Project.query.get(project_id)
        if project:
            project.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)


@page_bp.route('/<project_id>/pages/<page_id>/generate/description', methods=['POST'])
def generate_page_description(project_id, page_id):
    """
    POST /api/projects/{project_id}/pages/{page_id}/generate/description - Generate single page description
    
    Request body:
    {
        "force_regenerate": false
    }
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        project = Project.query.get(project_id)
        if not project:
            return not_found('Project')
        
        data = request.get_json() or {}
        force_regenerate = data.get('force_regenerate', False)
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Check if already generated
        if page.get_description_content() and not force_regenerate:
            return bad_request("Description already exists. Set force_regenerate=true to regenerate")
        
        # Get outline content
        outline_content = page.get_outline_content()
        if not outline_content:
            return bad_request("Page must have outline content first")
        
        # Reconstruct full outline
        all_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        outline = []
        for p in all_pages:
            oc = p.get_outline_content()
            if oc:
                page_data = oc.copy()
                if p.part:
                    page_data['part'] = p.part
                outline.append(page_data)
        
        # Initialize AI service
        ai_service = get_ai_service()
        
        # Get reference files content and create project context
        from controllers.project_controller import _get_project_reference_files_content
        reference_files_content = _get_project_reference_files_content(project_id)
        project_context = ProjectContext(project, reference_files_content)
        
        # Generate description
        page_data = outline_content.copy()
        if page.part:
            page_data['part'] = page.part
        
        desc_text = ai_service.generate_page_description(
            project_context,
            outline,
            page_data,
            page.order_index + 1,
            language=language
        )
        
        # Save description
        desc_content = {
            "text": desc_text,
            "generated_at": datetime.utcnow().isoformat()
        }
        
        page.set_description_content(desc_content)
        page.status = 'DESCRIPTION_GENERATED'
        page.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(page.to_dict())
    
    except Exception as e:
        db.session.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@page_bp.route('/<project_id>/pages/<page_id>/generate/image', methods=['POST'])
def generate_page_image(project_id, page_id):
    """
    POST /api/projects/{project_id}/pages/{page_id}/generate/image - Generate single page image
    
    Request body:
    {
        "use_template": true,
        "force_regenerate": false
    }
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        project = Project.query.get(project_id)
        if not project:
            return not_found('Project')
        
        data = request.get_json() or {}
        use_template = data.get('use_template', True)
        force_regenerate = data.get('force_regenerate', False)
        language = data.get('language', current_app.config.get('OUTPUT_LANGUAGE', 'zh'))
        
        # Check if already generated
        if page.generated_image_path and not force_regenerate:
            return bad_request("Image already exists. Set force_regenerate=true to regenerate")
        
        # Get description content
        desc_content = page.get_description_content()
        if not desc_content:
            return bad_request("Page must have description content first")
        
        # Reconstruct full outline with part structure
        all_pages = Page.query.filter_by(project_id=project_id).order_by(Page.order_index).all()
        outline = []
        current_part = None
        current_part_pages = []
        
        for p in all_pages:
            oc = p.get_outline_content()
            if not oc:
                continue
                
            page_data = oc.copy()
            
            # 如果當前頁面屬於一個 part
            if p.part:
                # 如果這是新的 part，先儲存之前的 part（如果有）
                if current_part and current_part != p.part:
                    outline.append({
                        "part": current_part,
                        "pages": current_part_pages
                    })
                    current_part_pages = []
                
                current_part = p.part
                # 移除 part 欄位，因為它在頂層
                if 'part' in page_data:
                    del page_data['part']
                current_part_pages.append(page_data)
            else:
                # 如果當前頁面不屬於任何 part，先儲存之前的 part（如果有）
                if current_part:
                    outline.append({
                        "part": current_part,
                        "pages": current_part_pages
                    })
                    current_part = None
                    current_part_pages = []
                
                # 直接新增頁面
                outline.append(page_data)
        
        # 儲存最後一個 part（如果有）
        if current_part:
            outline.append({
                "part": current_part,
                "pages": current_part_pages
            })
        
        # Initialize services
        ai_service = get_ai_service()
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        
        # Get template path
        ref_image_path = None
        if use_template:
            ref_image_path = file_service.get_template_path(project_id)
        
        # 檢查是否有模板圖片或風格描述
        # 如果都沒有，則返回錯誤
        if not ref_image_path and not project.template_style:
            return bad_request("No template image or style description found for project")
        
        # Generate prompt
        page_data = page.get_outline_content() or {}
        if page.part:
            page_data['part'] = page.part
        
        # 獲取描述文字（可能是 text 欄位或 text_content 陣列）
        desc_text = desc_content.get('text', '')
        if not desc_text and desc_content.get('text_content'):
            # 如果 text 欄位不存在，嘗試從 text_content 陣列獲取
            text_content = desc_content.get('text_content', [])
            if isinstance(text_content, list):
                desc_text = '\n'.join(text_content)
            else:
                desc_text = str(text_content)
        
        # 從當前頁面的描述內容中提取圖片 URL（在生成 prompt 之前提取，以便告知 AI）
        additional_ref_images = []
        has_material_images = False
        
        # 從描述文字中提取圖片
        if desc_text:
            image_urls = ai_service.extract_image_urls_from_markdown(desc_text)
            if image_urls:
                logger.info(f"Found {len(image_urls)} image(s) in page {page_id} description")
                additional_ref_images = image_urls
                has_material_images = True
        
        # 合併額外要求和風格描述
        combined_requirements = project.extra_requirements or ""
        if project.template_style:
            style_requirement = f"\n\nppt頁面風格描述：\n\n{project.template_style}"
            combined_requirements = combined_requirements + style_requirement
        
        # Create async task for image generation
        task = Task(
            project_id=project_id,
            task_type='GENERATE_PAGE_IMAGE',
            status='PENDING'
        )
        task.set_progress({
            'total': 1,
            'completed': 0,
            'failed': 0
        })
        db.session.add(task)
        db.session.commit()
        
        # Get app instance for background task
        app = current_app._get_current_object()
        
        # Submit background task
        task_manager.submit_task(
            task.id,
            generate_single_page_image_task,
            project_id,
            page_id,
            ai_service,
            file_service,
            outline,
            use_template,
            current_app.config['DEFAULT_ASPECT_RATIO'],
            current_app.config['DEFAULT_RESOLUTION'],
            app,
            combined_requirements if combined_requirements.strip() else None,
            language
        )
        
        # Return task_id immediately
        return success_response({
            'task_id': task.id,
            'page_id': page_id,
            'status': 'PENDING'
        }, status_code=202)
    
    except Exception as e:
        db.session.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)


@page_bp.route('/<project_id>/pages/<page_id>/edit/image', methods=['POST'])
def edit_page_image(project_id, page_id):
    """
    POST /api/projects/{project_id}/pages/{page_id}/edit/image - Edit page image
    
    Request body (JSON or multipart/form-data):
    {
        "edit_instruction": "更改文字框樣式為虛線",
        "context_images": {
            "use_template": true,  // 是否使用template圖片
            "desc_image_urls": ["url1", "url2"],  // desc中的圖片URL列表
            "uploaded_image_ids": ["file1", "file2"]  // 上傳的圖片檔案ID列表（在multipart中）
        }
    }
    
    For multipart/form-data:
    - edit_instruction: text field
    - use_template: text field (true/false)
    - desc_image_urls: JSON array string
    - context_images: file uploads (multiple files with key "context_images")
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        if not page.generated_image_path:
            return bad_request("Page must have generated image first")
        
        project = Project.query.get(project_id)
        if not project:
            return not_found('Project')
        
        # Initialize services
        ai_service = get_ai_service()
        
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        
        # Parse request data (support both JSON and multipart/form-data)
        if request.is_json:
            data = request.get_json()
            uploaded_files = []
        else:
            # multipart/form-data
            data = request.form.to_dict()
            # Get uploaded files
            uploaded_files = request.files.getlist('context_images')
            # Parse JSON fields
            if 'desc_image_urls' in data and data['desc_image_urls']:
                try:
                    data['desc_image_urls'] = json.loads(data['desc_image_urls'])
                except:
                    data['desc_image_urls'] = []
            else:
                data['desc_image_urls'] = []
        
        if not data or 'edit_instruction' not in data:
            return bad_request("edit_instruction is required")
        
        # Get current image path
        current_image_path = file_service.get_absolute_path(page.generated_image_path)
        
        # Get original description if available
        original_description = None
        desc_content = page.get_description_content()
        if desc_content:
            # Extract text from description_content
            original_description = desc_content.get('text') or ''
            # If text is not available, try to construct from text_content
            if not original_description and desc_content.get('text_content'):
                if isinstance(desc_content['text_content'], list):
                    original_description = '\n'.join(desc_content['text_content'])
                else:
                    original_description = str(desc_content['text_content'])
        
        # Collect additional reference images
        additional_ref_images = []
        
        # 1. Add template image if requested
        context_images = data.get('context_images', {})
        if isinstance(context_images, dict):
            use_template = context_images.get('use_template', False)
        else:
            use_template = data.get('use_template', 'false').lower() == 'true'
        
        if use_template:
            template_path = file_service.get_template_path(project_id)
            if template_path:
                additional_ref_images.append(template_path)
        
        # 2. Add desc image URLs if provided
        if isinstance(context_images, dict):
            desc_image_urls = context_images.get('desc_image_urls', [])
        else:
            desc_image_urls = data.get('desc_image_urls', [])
        
        if desc_image_urls:
            if isinstance(desc_image_urls, str):
                try:
                    desc_image_urls = json.loads(desc_image_urls)
                except:
                    desc_image_urls = []
            if isinstance(desc_image_urls, list):
                additional_ref_images.extend(desc_image_urls)
        
        # 3. Save and add uploaded files to a persistent location
        temp_dir = None
        if uploaded_files:
            # Create a temporary directory in the project's upload folder
            import tempfile
            import shutil
            from werkzeug.utils import secure_filename
            temp_dir = Path(tempfile.mkdtemp(dir=current_app.config['UPLOAD_FOLDER']))
            try:
                for uploaded_file in uploaded_files:
                    if uploaded_file.filename:
                        # Save to temp directory
                        temp_path = temp_dir / secure_filename(uploaded_file.filename)
                        uploaded_file.save(str(temp_path))
                        additional_ref_images.append(str(temp_path))
            except Exception as e:
                # Clean up temp directory on error
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir)
                raise e
        
        # Check for brush mask inpaint mode
        current_app.logger.info(f"[inpaint] content_type={request.content_type} is_json={request.is_json} form_keys={list(request.form.keys())} files={list(request.files.keys())}")
        use_inpaint = str(data.get('use_inpaint', 'false')).lower() == 'true'
        current_app.logger.info(f"[inpaint] use_inpaint={use_inpaint}")
        bbox_raw = data.get('bbox', None)
        bbox = None
        if bbox_raw:
            if isinstance(bbox_raw, str):
                try:
                    bbox = json.loads(bbox_raw)
                except Exception:
                    bbox = None
            elif isinstance(bbox_raw, dict):
                bbox = bbox_raw
        mask_file = request.files.get('mask_image') if not request.is_json else None

        if use_inpaint and (mask_file or bbox) and page.generated_image_path:
            # Save mask to temp file for async task
            import os as _os, io as _io, base64 as _b64, tempfile as _tmp
            from PIL import Image as _PILImage

            current_abs = file_service.get_absolute_path(page.generated_image_path)
            orig_img = _PILImage.open(current_abs).convert("RGBA")
            iw, ih = orig_img.size

            if mask_file:
                mask_img = _PILImage.open(mask_file.stream).convert("RGBA")
                mask = mask_img.resize((iw, ih), _PILImage.Resampling.LANCZOS)
            else:
                bx = max(0, int(bbox.get('x', 0)))
                by = max(0, int(bbox.get('y', 0)))
                bw = min(int(bbox.get('width', iw)), iw - bx)
                bh = min(int(bbox.get('height', ih)), ih - by)
                mask = _PILImage.new("RGBA", (iw, ih), (255, 255, 255, 255))
                for px in range(bx, bx + bw):
                    for py in range(by, by + bh):
                        mask.putpixel((px, py), (0, 0, 0, 0))

            # Persist mask to temp file so background thread can read it
            mask_tmp = _tmp.NamedTemporaryFile(suffix='.png', delete=False)
            mask.save(mask_tmp.name, format='PNG')
            mask_tmp.close()

            # Create async task
            task = Task(project_id=project_id, task_type='EDIT_PAGE_IMAGE', status='PENDING')
            db.session.add(task)
            db.session.commit()

            app = current_app._get_current_object()

            def _best_gpt_image_size(w, h):
                """Pick the gpt-image-2 supported size closest to the original aspect ratio."""
                SIZES = ["1024x1024", "1536x1024", "1024x1536", "2048x2048"]
                ratio = w / h
                return min(SIZES, key=lambda s: abs(int(s.split('x')[0]) / int(s.split('x')[1]) - ratio))

            def inpaint_task(task_id_arg, proj_id, pg_id, prompt, mask_path, orig_path, _app):
                import httpx as _httpx2, base64 as _b642, io as _io2, os as _os2
                from PIL import Image as _PILImage2, ImageFilter as _ImageFilter2
                with _app.app_context():
                    from models import Task as _Task, db as _db, Page as _Page
                    _task = _Task.query.get(task_id_arg)
                    if not _task: return
                    try:
                        _task.status = 'PROCESSING'
                        _db.session.commit()

                        # load original + mask
                        orig = _PILImage2.open(orig_path).convert("RGBA")
                        img_buf2 = _io2.BytesIO()
                        orig.save(img_buf2, format='PNG')
                        img_buf2.seek(0)

                        # Convert mask: white(255)=edit -> alpha=0 (transparent) for gpt-image-2
                        import numpy as _np2
                        mask_img = _PILImage2.open(mask_path).convert("L")
                        if mask_img.size != orig.size:
                            mask_img = mask_img.resize(orig.size, _PILImage2.Resampling.LANCZOS)
                        # Create RGBA: all black, alpha=255 where keep (dark), alpha=0 where edit (bright)
                        mask_arr = _np2.array(mask_img)
                        alpha = _np2.where(mask_arr > 128, 0, 255).astype(_np2.uint8)
                        rgba_mask = _np2.zeros((*mask_arr.shape, 4), dtype=_np2.uint8)
                        rgba_mask[:, :, 3] = alpha
                        mask_png = _PILImage2.fromarray(rgba_mask, 'RGBA')
                        mask_buf_io = _io2.BytesIO()
                        mask_png.save(mask_buf_io, format='PNG')
                        mask_buf_io.seek(0)
                        mask_buf2 = mask_buf_io.read()

                        api_base2 = (_os2.environ.get('OPENAI_API_BASE', 'http://host.docker.internal:9000/v1')).rstrip('/')
                        proxy_token2 = _os2.environ.get('PROXY_TOKEN', 'internal-change-me')

                        _app.logger.info(f"[inpaint_task] calling proxy {api_base2}/images/edits")
                        files2 = [
                            ("image", ("original.png", img_buf2, "image/png")),
                            ("mask", ("mask.png", _io2.BytesIO(mask_buf2), "image/png")),
                            ("prompt", (None, prompt)),
                            ("model", (None, "gpt-image-2")),
                            ("size", (None, _best_gpt_image_size(orig.width, orig.height))),
                            ("n", (None, "1")),
                        ]
                        with _httpx2.Client(timeout=300) as hc:
                            resp2 = hc.post(f"{api_base2}/images/edits",
                                            headers={"Authorization": f"Bearer {proxy_token2}"},
                                            files=files2)
                        _app.logger.info(f"[inpaint_task] proxy response: {resp2.status_code}")
                        resp2.raise_for_status()

                        result_data2 = resp2.json()
                        b64_str2 = result_data2["data"][0]["b64_json"]
                        result_img2 = _PILImage2.open(_io2.BytesIO(_b642.b64decode(b64_str2))).convert("RGBA")

                        # Composite: only use generated result in masked (edit) area, keep original elsewhere
                        orig2 = _PILImage2.open(orig_path).convert("RGBA")
                        # Re-read the original white/black mask as the composite mask
                        comp_mask = _PILImage2.open(mask_path).convert("L")
                        if result_img2.size != orig2.size:
                            result_img2 = result_img2.resize(orig2.size, _PILImage2.Resampling.LANCZOS)
                        if comp_mask.size != orig2.size:
                            comp_mask = comp_mask.resize(orig2.size, _PILImage2.Resampling.LANCZOS)
                        # Feather edges for smooth blending
                        comp_mask = comp_mask.filter(_ImageFilter2.GaussianBlur(radius=12))
                        # White(255)=use generated, Black(0)=keep original
                        final_img = _PILImage2.composite(result_img2, orig2, comp_mask).convert("RGB")
                        _app.logger.info(f"[inpaint_task] composited with feathered mask")

                        from services.file_service import FileService as _FS
                        from services.task_manager import save_image_with_version as _siv
                        _fs = _FS(_app.config['UPLOAD_FOLDER'])
                        _pg = _Page.query.get(pg_id)
                        _siv(final_img, proj_id, pg_id, _fs, page_obj=_pg)

                        _task.status = 'COMPLETED'
                        _task.result = '{"completed":1,"failed":0,"total":1}'
                        _db.session.commit()
                        _app.logger.info(f"[inpaint_task] COMPLETED page {pg_id}")
                    except Exception as e2:
                        import traceback as _tb
                        _app.logger.error(f"[inpaint_task] FAILED: {e2}\n{_tb.format_exc()}")
                        _task.status = 'FAILED'
                        _task.error = str(e2)
                        _db.session.commit()
                    finally:
                        try: _os2.unlink(mask_path)
                        except: pass

            task_manager.submit_task(task.id, inpaint_task,
                project_id, page_id,
                data['edit_instruction'], mask_tmp.name,
                current_abs, app)

            return success_response({
                'task_id': task.id,
                'page_id': page_id,
                'status': 'PENDING'
            }, status_code=202)

        # Create async task for image editing
        task = Task(
            project_id=project_id,
            task_type='EDIT_PAGE_IMAGE',
            status='PENDING'
        )
        task.set_progress({
            'total': 1,
            'completed': 0,
            'failed': 0
        })
        db.session.add(task)
        db.session.commit()
        
        # Get app instance for background task
        app = current_app._get_current_object()
        
        # Submit background task
        task_manager.submit_task(
            task.id,
            edit_page_image_task,
            project_id,
            page_id,
            data['edit_instruction'],
            ai_service,
            file_service,
            current_app.config['DEFAULT_ASPECT_RATIO'],
            current_app.config['DEFAULT_RESOLUTION'],
            original_description,
            additional_ref_images if additional_ref_images else None,
            str(temp_dir) if temp_dir else None,
            app
        )
        
        # Return task_id immediately
        return success_response({
            'task_id': task.id,
            'page_id': page_id,
            'status': 'PENDING'
        }, status_code=202)
    
    except Exception as e:
        db.session.rollback()
        return error_response('AI_SERVICE_ERROR', str(e), 503)



@page_bp.route('/<project_id>/pages/<page_id>/image-versions', methods=['GET'])
def get_page_image_versions(project_id, page_id):
    """
    GET /api/projects/{project_id}/pages/{page_id}/image-versions - Get all image versions for a page
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        versions = PageImageVersion.query.filter_by(page_id=page_id)\
            .order_by(PageImageVersion.version_number.desc()).all()
        
        return success_response({
            'versions': [v.to_dict() for v in versions]
        })
    
    except Exception as e:
        return error_response('SERVER_ERROR', str(e), 500)


@page_bp.route('/<project_id>/pages/<page_id>/image-versions/<version_id>/set-current', methods=['POST'])
def set_current_image_version(project_id, page_id, version_id):
    """
    POST /api/projects/{project_id}/pages/{page_id}/image-versions/{version_id}/set-current
    Set a specific version as the current one
    """
    try:
        page = Page.query.get(page_id)
        
        if not page or page.project_id != project_id:
            return not_found('Page')
        
        version = PageImageVersion.query.get(version_id)
        
        if not version or version.page_id != page_id:
            return not_found('Image Version')
        
        # Mark all versions as not current
        PageImageVersion.query.filter_by(page_id=page_id).update({'is_current': False})

        # Set this version as current
        version.is_current = True
        page.generated_image_path = version.image_path

        # 更新 cached_image_path，指向該版本的快取圖（如果存在）
        file_service = FileService(current_app.config['UPLOAD_FOLDER'])
        cached_relative_path = file_service.get_cached_image_path(project_id, page_id, version.version_number)
        if file_service.file_exists(cached_relative_path):
            page.cached_image_path = cached_relative_path
        else:
            # 快取檔案不存在，設定為 None，to_dict() 會回退到原圖
            page.cached_image_path = None

        page.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return success_response(page.to_dict(include_versions=True))
    
    except Exception as e:
        db.session.rollback()
        return error_response('SERVER_ERROR', str(e), 500)
