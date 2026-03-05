"""Settings Controller - handles application settings endpoints"""

import logging
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager
from flask import Blueprint, request, current_app
from PIL import Image
from models import db, Settings, Task
from utils import success_response, error_response, bad_request
from config import Config, PROJECT_ROOT
from services.ai_service import AIService
from services.file_parser_service import FileParserService
from services.ai_providers.ocr.baidu_accurate_ocr_provider import create_baidu_accurate_ocr_provider
from services.ai_providers.image.baidu_inpainting_provider import create_baidu_inpainting_provider
from services.task_manager import task_manager

logger = logging.getLogger(__name__)

settings_bp = Blueprint(
    "settings", __name__, url_prefix="/api/settings"
)


@contextmanager
def temporary_settings_override(settings_override: dict):
    """
    臨時應用設定覆蓋的上下文管理器

    使用示例:
        with temporary_settings_override({"api_key": "test-key"}):
            # 在這裡使用臨時設定
            result = some_test_function()

    Args:
        settings_override: 要臨時應用的設定字典

    Yields:
        None
    """
    original_values = {}

    try:
        # 應用覆蓋設定
        if settings_override.get("api_key"):
            original_values["GOOGLE_API_KEY"] = current_app.config.get("GOOGLE_API_KEY")
            original_values["OPENAI_API_KEY"] = current_app.config.get("OPENAI_API_KEY")
            current_app.config["GOOGLE_API_KEY"] = settings_override["api_key"]
            current_app.config["OPENAI_API_KEY"] = settings_override["api_key"]

        if settings_override.get("api_base_url"):
            original_values["GOOGLE_API_BASE"] = current_app.config.get("GOOGLE_API_BASE")
            original_values["OPENAI_API_BASE"] = current_app.config.get("OPENAI_API_BASE")
            current_app.config["GOOGLE_API_BASE"] = settings_override["api_base_url"]
            current_app.config["OPENAI_API_BASE"] = settings_override["api_base_url"]

        if settings_override.get("ai_provider_format"):
            original_values["AI_PROVIDER_FORMAT"] = current_app.config.get("AI_PROVIDER_FORMAT")
            current_app.config["AI_PROVIDER_FORMAT"] = settings_override["ai_provider_format"]

        if settings_override.get("text_model"):
            original_values["TEXT_MODEL"] = current_app.config.get("TEXT_MODEL")
            current_app.config["TEXT_MODEL"] = settings_override["text_model"]

        if settings_override.get("image_model"):
            original_values["IMAGE_MODEL"] = current_app.config.get("IMAGE_MODEL")
            current_app.config["IMAGE_MODEL"] = settings_override["image_model"]

        if settings_override.get("image_caption_model"):
            original_values["IMAGE_CAPTION_MODEL"] = current_app.config.get("IMAGE_CAPTION_MODEL")
            current_app.config["IMAGE_CAPTION_MODEL"] = settings_override["image_caption_model"]

        if settings_override.get("mineru_api_base"):
            original_values["MINERU_API_BASE"] = current_app.config.get("MINERU_API_BASE")
            current_app.config["MINERU_API_BASE"] = settings_override["mineru_api_base"]

        if settings_override.get("mineru_token"):
            original_values["MINERU_TOKEN"] = current_app.config.get("MINERU_TOKEN")
            current_app.config["MINERU_TOKEN"] = settings_override["mineru_token"]

        if settings_override.get("baidu_ocr_api_key"):
            original_values["BAIDU_OCR_API_KEY"] = current_app.config.get("BAIDU_OCR_API_KEY")
            current_app.config["BAIDU_OCR_API_KEY"] = settings_override["baidu_ocr_api_key"]

        if settings_override.get("image_resolution"):
            original_values["DEFAULT_RESOLUTION"] = current_app.config.get("DEFAULT_RESOLUTION")
            current_app.config["DEFAULT_RESOLUTION"] = settings_override["image_resolution"]

        if "enable_text_reasoning" in settings_override:
            original_values["ENABLE_TEXT_REASONING"] = current_app.config.get("ENABLE_TEXT_REASONING")
            current_app.config["ENABLE_TEXT_REASONING"] = settings_override["enable_text_reasoning"]

        if "text_thinking_budget" in settings_override:
            original_values["TEXT_THINKING_BUDGET"] = current_app.config.get("TEXT_THINKING_BUDGET")
            current_app.config["TEXT_THINKING_BUDGET"] = settings_override["text_thinking_budget"]

        if "enable_image_reasoning" in settings_override:
            original_values["ENABLE_IMAGE_REASONING"] = current_app.config.get("ENABLE_IMAGE_REASONING")
            current_app.config["ENABLE_IMAGE_REASONING"] = settings_override["enable_image_reasoning"]

        if "image_thinking_budget" in settings_override:
            original_values["IMAGE_THINKING_BUDGET"] = current_app.config.get("IMAGE_THINKING_BUDGET")
            current_app.config["IMAGE_THINKING_BUDGET"] = settings_override["image_thinking_budget"]

        yield

    finally:
        # 恢復原始配置
        for key, value in original_values.items():
            if value is not None:
                current_app.config[key] = value
            else:
                current_app.config.pop(key, None)


@settings_bp.route("/", methods=["GET"], strict_slashes=False)
def get_settings():
    """
    GET /api/settings - Get application settings
    """
    try:
        settings = Settings.get_settings()
        return success_response(settings.to_dict())
    except Exception as e:
        logger.error(f"Error getting settings: {str(e)}")
        return error_response(
            "GET_SETTINGS_ERROR",
            f"Failed to get settings: {str(e)}",
            500,
        )


@settings_bp.route("/", methods=["PUT"], strict_slashes=False)
def update_settings():
    """
    PUT /api/settings - Update application settings

    Request Body:
        {
            "api_base_url": "https://api.example.com",
            "api_key": "your-api-key",
            "image_resolution": "2K",
            "image_aspect_ratio": "16:9"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return bad_request("Request body is required")

        settings = Settings.get_settings()

        # Update AI provider format configuration
        if "ai_provider_format" in data:
            provider_format = data["ai_provider_format"]
            if provider_format not in ["openai", "gemini"]:
                return bad_request("AI provider format must be 'openai' or 'gemini'")
            settings.ai_provider_format = provider_format

        # Update API configuration
        if "api_base_url" in data:
            raw_base_url = data["api_base_url"]
            # Empty string from frontend means "clear override, fall back to env/default"
            if raw_base_url is None:
                settings.api_base_url = None
            else:
                value = str(raw_base_url).strip()
                settings.api_base_url = value if value != "" else None

        if "api_key" in data:
            settings.api_key = data["api_key"]

        # Update image generation configuration
        if "image_resolution" in data:
            resolution = data["image_resolution"]
            if resolution not in ["1K", "2K", "4K"]:
                return bad_request("Resolution must be 1K, 2K, or 4K")
            settings.image_resolution = resolution

        if "image_aspect_ratio" in data:
            aspect_ratio = data["image_aspect_ratio"]
            settings.image_aspect_ratio = aspect_ratio

        # Update worker configuration
        if "max_description_workers" in data:
            workers = int(data["max_description_workers"])
            if workers < 1 or workers > 20:
                return bad_request(
                    "Max description workers must be between 1 and 20"
                )
            settings.max_description_workers = workers

        if "max_image_workers" in data:
            workers = int(data["max_image_workers"])
            if workers < 1 or workers > 20:
                return bad_request(
                    "Max image workers must be between 1 and 20"
                )
            settings.max_image_workers = workers

        # Update model & MinerU configuration (optional, empty values fall back to Config)
        if "text_model" in data:
            settings.text_model = (data["text_model"] or "").strip() or None

        if "image_model" in data:
            settings.image_model = (data["image_model"] or "").strip() or None

        if "mineru_api_base" in data:
            settings.mineru_api_base = (data["mineru_api_base"] or "").strip() or None

        if "mineru_token" in data:
            settings.mineru_token = data["mineru_token"]

        if "image_caption_model" in data:
            settings.image_caption_model = (data["image_caption_model"] or "").strip() or None

        if "output_language" in data:
            language = data["output_language"]
            if language in ["zh", "en", "ja", "auto"]:
                settings.output_language = language
            else:
                return bad_request("Output language must be 'zh', 'en', 'ja', or 'auto'")

        # Update reasoning mode configuration (separate for text and image)
        if "enable_text_reasoning" in data:
            settings.enable_text_reasoning = bool(data["enable_text_reasoning"])
        
        if "text_thinking_budget" in data:
            budget = int(data["text_thinking_budget"])
            if budget < 1 or budget > 8192:
                return bad_request("Text thinking budget must be between 1 and 8192")
            settings.text_thinking_budget = budget
        
        if "enable_image_reasoning" in data:
            settings.enable_image_reasoning = bool(data["enable_image_reasoning"])
        
        if "image_thinking_budget" in data:
            budget = int(data["image_thinking_budget"])
            if budget < 1 or budget > 8192:
                return bad_request("Image thinking budget must be between 1 and 8192")
            settings.image_thinking_budget = budget

        # Update Baidu OCR configuration
        if "baidu_ocr_api_key" in data:
            settings.baidu_ocr_api_key = data["baidu_ocr_api_key"] or None

        settings.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        # Sync to app.config
        _sync_settings_to_config(settings)

        logger.info("Settings updated successfully")
        return success_response(
            settings.to_dict(), "Settings updated successfully"
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating settings: {str(e)}")
        return error_response(
            "UPDATE_SETTINGS_ERROR",
            f"Failed to update settings: {str(e)}",
            500,
        )


@settings_bp.route("/reset", methods=["POST"], strict_slashes=False)
def reset_settings():
    """
    POST /api/settings/reset - Reset settings to default values
    """
    try:
        settings = Settings.get_settings()

        # Reset to default values from Config / .env
        # Priority logic:
        # - Check AI_PROVIDER_FORMAT
        # - If "openai" -> use OPENAI_API_BASE / OPENAI_API_KEY
        # - Otherwise (default "gemini") -> use GOOGLE_API_BASE / GOOGLE_API_KEY
        settings.ai_provider_format = Config.AI_PROVIDER_FORMAT

        if (Config.AI_PROVIDER_FORMAT or "").lower() == "openai":
            default_api_base = Config.OPENAI_API_BASE or None
            default_api_key = Config.OPENAI_API_KEY or None
        else:
            default_api_base = Config.GOOGLE_API_BASE or None
            default_api_key = Config.GOOGLE_API_KEY or None

        settings.api_base_url = default_api_base
        settings.api_key = default_api_key
        settings.text_model = Config.TEXT_MODEL
        settings.image_model = Config.IMAGE_MODEL
        settings.mineru_api_base = Config.MINERU_API_BASE
        settings.mineru_token = Config.MINERU_TOKEN
        settings.image_caption_model = Config.IMAGE_CAPTION_MODEL
        settings.output_language = 'zh'  # 重置為預設中文
        # 重置推理模式配置
        settings.enable_text_reasoning = False
        settings.text_thinking_budget = 1024
        settings.enable_image_reasoning = False
        settings.image_thinking_budget = 1024
        settings.baidu_ocr_api_key = Config.BAIDU_OCR_API_KEY or None
        settings.image_resolution = Config.DEFAULT_RESOLUTION
        settings.image_aspect_ratio = Config.DEFAULT_ASPECT_RATIO
        settings.max_description_workers = Config.MAX_DESCRIPTION_WORKERS
        settings.max_image_workers = Config.MAX_IMAGE_WORKERS
        settings.updated_at = datetime.now(timezone.utc)

        db.session.commit()

        # Sync to app.config
        _sync_settings_to_config(settings)

        logger.info("Settings reset to defaults")
        return success_response(
            settings.to_dict(), "Settings reset to defaults"
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error resetting settings: {str(e)}")
        return error_response(
            "RESET_SETTINGS_ERROR",
            f"Failed to reset settings: {str(e)}",
            500,
        )


@settings_bp.route("/verify", methods=["POST"], strict_slashes=False)
def verify_api_key():
    """
    POST /api/settings/verify - 驗證API key是否可用
    透過呼叫一個輕量的gemini-3-flash-preview測試請求（思考budget=0）來判斷

    Returns:
        {
            "data": {
                "available": true/false,
                "message": "提示資訊"
            }
        }
    """
    try:
        # 獲取當前設定
        settings = Settings.get_settings()
        if not settings:
            return success_response({
                "available": False,
                "message": "使用者設定未找到"
            })

        # 準備設定覆蓋字典
        settings_override = {}
        if settings.api_key:
            settings_override["api_key"] = settings.api_key
        if settings.api_base_url:
            settings_override["api_base_url"] = settings.api_base_url
        if settings.ai_provider_format:
            settings_override["ai_provider_format"] = settings.ai_provider_format

        # 使用上下文管理器臨時應用使用者配置進行驗證
        with temporary_settings_override(settings_override):
            from services.ai_providers import get_text_provider

            # 使用 gemini-3-flash-preview 模型進行驗證（思考budget=0，最小開銷）
            verification_model = "gemini-3-flash-preview"

            # 嘗試建立provider並呼叫一個簡單的測試請求
            try:
                provider = get_text_provider(model=verification_model)
                # 呼叫一個簡單的測試請求（思考budget=0，最小開銷）
                response = provider.generate_text("Hello", thinking_budget=0)

                logger.info("API key verification successful")
                return success_response({
                    "available": True,
                    "message": "API key 可用"
                })

            except ValueError as ve:
                # API key未配置
                logger.warning(f"API key not configured: {str(ve)}")
                return success_response({
                    "available": False,
                    "message": "API key 未配置，請在設定中配置 API key 和 API Base URL"
                })
            except Exception as e:
                # API呼叫失敗（可能是key無效、餘額不足等）
                error_msg = str(e)
                logger.warning(f"API key verification failed: {error_msg}")

                # 根據錯誤資訊判斷具體原因
                if "401" in error_msg or "unauthorized" in error_msg.lower() or "invalid" in error_msg.lower():
                    message = "API key 無效或已過期，請在設定中檢查 API key 配置"
                elif "429" in error_msg or "quota" in error_msg.lower() or "limit" in error_msg.lower():
                    message = "API 呼叫超限或餘額不足，請在設定中檢查配置"
                elif "403" in error_msg or "forbidden" in error_msg.lower():
                    message = "API 訪問被拒絕，請在設定中檢查 API key 許可權"
                elif "timeout" in error_msg.lower():
                    message = "API 呼叫超時，請在設定中檢查網路連線和 API Base URL"
                else:
                    message = f"API 呼叫失敗，請在設定中檢查配置: {error_msg}"

                return success_response({
                    "available": False,
                    "message": message
                })

    except Exception as e:
        logger.error(f"Error verifying API key: {str(e)}")
        return error_response(
            "VERIFY_API_KEY_ERROR",
            f"驗證 API key 時出錯: {str(e)}",
            500,
        )


def _sync_settings_to_config(settings: Settings):
    """Sync settings to Flask app config and clear AI service cache if needed"""
    # Track if AI-related settings changed
    ai_config_changed = False
    
    # Sync AI provider format (always sync, has default value)
    if settings.ai_provider_format:
        old_format = current_app.config.get("AI_PROVIDER_FORMAT")
        if old_format != settings.ai_provider_format:
            ai_config_changed = True
            logger.info(f"AI provider format changed: {old_format} -> {settings.ai_provider_format}")
        current_app.config["AI_PROVIDER_FORMAT"] = settings.ai_provider_format
    
    # Sync API configuration (sync to both GOOGLE_* and OPENAI_* to ensure DB settings override env vars)
    if settings.api_base_url is not None:
        old_base = current_app.config.get("GOOGLE_API_BASE")
        if old_base != settings.api_base_url:
            ai_config_changed = True
            logger.info(f"API base URL changed: {old_base} -> {settings.api_base_url}")
        current_app.config["GOOGLE_API_BASE"] = settings.api_base_url
        current_app.config["OPENAI_API_BASE"] = settings.api_base_url
    else:
        # Remove overrides, fall back to env variables or defaults
        if "GOOGLE_API_BASE" in current_app.config or "OPENAI_API_BASE" in current_app.config:
            ai_config_changed = True
            logger.info("API base URL cleared, falling back to defaults")
        current_app.config.pop("GOOGLE_API_BASE", None)
        current_app.config.pop("OPENAI_API_BASE", None)

    if settings.api_key is not None:
        old_key = current_app.config.get("GOOGLE_API_KEY")
        # Compare actual values to detect any change (but don't log the keys for security)
        if old_key != settings.api_key:
            ai_config_changed = True
            logger.info("API key updated")
        current_app.config["GOOGLE_API_KEY"] = settings.api_key
        current_app.config["OPENAI_API_KEY"] = settings.api_key
    else:
        # Remove overrides, fall back to env variables or defaults
        if "GOOGLE_API_KEY" in current_app.config or "OPENAI_API_KEY" in current_app.config:
            ai_config_changed = True
            logger.info("API key cleared, falling back to defaults")
        current_app.config.pop("GOOGLE_API_KEY", None)
        current_app.config.pop("OPENAI_API_KEY", None)
    
    # Check model changes
    if settings.text_model is not None:
        old_model = current_app.config.get("TEXT_MODEL")
        if old_model != settings.text_model:
            ai_config_changed = True
            logger.info(f"Text model changed: {old_model} -> {settings.text_model}")
        current_app.config["TEXT_MODEL"] = settings.text_model
    
    if settings.image_model is not None:
        old_model = current_app.config.get("IMAGE_MODEL")
        if old_model != settings.image_model:
            ai_config_changed = True
            logger.info(f"Image model changed: {old_model} -> {settings.image_model}")
        current_app.config["IMAGE_MODEL"] = settings.image_model

    # Sync image generation settings
    current_app.config["DEFAULT_RESOLUTION"] = settings.image_resolution
    current_app.config["DEFAULT_ASPECT_RATIO"] = settings.image_aspect_ratio

    # Sync worker settings
    current_app.config["MAX_DESCRIPTION_WORKERS"] = settings.max_description_workers
    current_app.config["MAX_IMAGE_WORKERS"] = settings.max_image_workers
    logger.info(f"Updated worker settings: desc={settings.max_description_workers}, img={settings.max_image_workers}")

    # Sync MinerU settings (optional, fall back to Config defaults if None)
    if settings.mineru_api_base:
        current_app.config["MINERU_API_BASE"] = settings.mineru_api_base
        logger.info(f"Updated MINERU_API_BASE to: {settings.mineru_api_base}")
    if settings.mineru_token is not None:
        current_app.config["MINERU_TOKEN"] = settings.mineru_token
        logger.info("Updated MINERU_TOKEN from settings")
    if settings.image_caption_model:
        current_app.config["IMAGE_CAPTION_MODEL"] = settings.image_caption_model
        logger.info(f"Updated IMAGE_CAPTION_MODEL to: {settings.image_caption_model}")
    if settings.output_language:
        current_app.config["OUTPUT_LANGUAGE"] = settings.output_language
        logger.info(f"Updated OUTPUT_LANGUAGE to: {settings.output_language}")
    
    # Sync reasoning mode settings (separate for text and image)
    # Check if reasoning configuration changed (requires AIService cache clear)
    old_text_reasoning = current_app.config.get("ENABLE_TEXT_REASONING")
    old_text_budget = current_app.config.get("TEXT_THINKING_BUDGET")
    old_image_reasoning = current_app.config.get("ENABLE_IMAGE_REASONING")
    old_image_budget = current_app.config.get("IMAGE_THINKING_BUDGET")
    
    if (old_text_reasoning != settings.enable_text_reasoning or 
        old_text_budget != settings.text_thinking_budget or
        old_image_reasoning != settings.enable_image_reasoning or
        old_image_budget != settings.image_thinking_budget):
        ai_config_changed = True
        logger.info(f"Reasoning config changed: text={old_text_reasoning}({old_text_budget})->{settings.enable_text_reasoning}({settings.text_thinking_budget}), image={old_image_reasoning}({old_image_budget})->{settings.enable_image_reasoning}({settings.image_thinking_budget})")
    
    current_app.config["ENABLE_TEXT_REASONING"] = settings.enable_text_reasoning
    current_app.config["TEXT_THINKING_BUDGET"] = settings.text_thinking_budget
    current_app.config["ENABLE_IMAGE_REASONING"] = settings.enable_image_reasoning
    current_app.config["IMAGE_THINKING_BUDGET"] = settings.image_thinking_budget
    
    # Sync Baidu OCR settings
    if settings.baidu_ocr_api_key:
        current_app.config["BAIDU_OCR_API_KEY"] = settings.baidu_ocr_api_key
        logger.info("Updated BAIDU_OCR_API_KEY from settings")
    
    # Clear AI service cache if AI-related configuration changed
    if ai_config_changed:
        try:
            from services.ai_service_manager import clear_ai_service_cache
            clear_ai_service_cache()
            logger.warning("AI configuration changed - AIService cache cleared. New providers will be created on next request.")
        except Exception as e:
            logger.error(f"Failed to clear AI service cache: {e}")


def _get_test_image_path() -> Path:
    test_image = Path(PROJECT_ROOT) / "assets" / "test_img.png"
    if not test_image.exists():
        raise FileNotFoundError("未找到 test_img.png，請確認已放在專案根目錄 assets 下")
    return test_image


def _get_baidu_credentials():
    """獲取百度 API 憑證"""
    api_key = current_app.config.get("BAIDU_OCR_API_KEY") or Config.BAIDU_OCR_API_KEY
    api_secret = current_app.config.get("BAIDU_OCR_API_SECRET") or Config.BAIDU_OCR_API_SECRET
    if not api_key:
        raise ValueError("未配置 BAIDU_OCR_API_KEY")
    return api_key, api_secret


def _create_file_parser():
    """建立 FileParserService 例項"""
    return FileParserService(
        mineru_token=current_app.config.get("MINERU_TOKEN", ""),
        mineru_api_base=current_app.config.get("MINERU_API_BASE", ""),
        google_api_key=current_app.config.get("GOOGLE_API_KEY", ""),
        google_api_base=current_app.config.get("GOOGLE_API_BASE", ""),
        openai_api_key=current_app.config.get("OPENAI_API_KEY", ""),
        openai_api_base=current_app.config.get("OPENAI_API_BASE", ""),
        image_caption_model=current_app.config.get("IMAGE_CAPTION_MODEL", Config.IMAGE_CAPTION_MODEL),
        provider_format=current_app.config.get("AI_PROVIDER_FORMAT", "gemini"),
    )


# 測試函式 - 每個測試一個獨立函式
def _test_baidu_ocr():
    """測試百度 OCR 服務"""
    api_key, api_secret = _get_baidu_credentials()
    provider = create_baidu_accurate_ocr_provider(api_key, api_secret)
    if not provider:
        raise ValueError("百度 OCR Provider 初始化失敗")

    test_image_path = _get_test_image_path()
    result = provider.recognize(str(test_image_path), language_type="CHN_ENG")
    recognized_text = provider.get_full_text(result, separator=" ")

    return {
        "recognized_text": recognized_text,
        "words_result_num": result.get("words_result_num", 0),
    }, "百度 OCR 測試成功"


def _test_text_model():
    """測試文字生成模型"""
    ai_service = AIService()
    reply = ai_service.text_provider.generate_text("請只回復 OK。", thinking_budget=64)
    return {"reply": reply.strip()}, "文字模型測試成功"


def _test_caption_model():
    """測試圖片識別模型"""
    upload_folder = Path(current_app.config.get("UPLOAD_FOLDER", Config.UPLOAD_FOLDER))
    mineru_root = upload_folder / "mineru_files"
    mineru_root.mkdir(parents=True, exist_ok=True)
    extract_id = datetime.now(timezone.utc).strftime("test-%Y%m%d%H%M%S")
    image_dir = mineru_root / extract_id
    image_dir.mkdir(parents=True, exist_ok=True)
    image_path = image_dir / "caption_test.png"

    try:
        test_image_path = _get_test_image_path()
        shutil.copyfile(test_image_path, image_path)

        parser = _create_file_parser()
        image_url = f"/files/mineru/{extract_id}/{image_path.name}"
        caption = parser._generate_single_caption(image_url).strip()

        if not caption:
            raise ValueError("圖片識別模型返回空結果")

        return {"caption": caption}, "圖片識別模型測試成功"
    finally:
        if image_path.exists():
            image_path.unlink()
        if image_dir.exists():
            try:
                image_dir.rmdir()
            except OSError:
                pass


def _test_baidu_inpaint():
    """測試百度影象修復"""
    api_key, api_secret = _get_baidu_credentials()
    provider = create_baidu_inpainting_provider(api_key, api_secret)
    if not provider:
        raise ValueError("百度影象修復 Provider 初始化失敗")

    test_image_path = _get_test_image_path()
    with Image.open(test_image_path) as image:
        width, height = image.size
        rect_width = max(1, int(width * 0.3))
        rect_height = max(1, int(height * 0.3))
        left = max(0, int(width * 0.35))
        top = max(0, int(height * 0.35))
        rectangles = [{
            "left": left,
            "top": top,
            "width": min(rect_width, width - left),
            "height": min(rect_height, height - top),
        }]
        result = provider.inpaint(image, rectangles)

    if result is None:
        raise ValueError("百度影象修復返回空結果")

    return {"image_size": result.size}, "百度影象修復測試成功"


def _test_image_model():
    """測試影象生成模型"""
    ai_service = AIService()
    test_image_path = _get_test_image_path()
    prompt = "生成一張簡潔、明亮、適合簡報的背景圖。"
    result = ai_service.generate_image(
        prompt=prompt,
        ref_image_path=str(test_image_path),
        aspect_ratio="16:9",
        resolution="1K"
    )

    if result is None:
        raise ValueError("影象生成模型返回空結果")

    return {"image_size": result.size}, "影象生成模型測試成功"


def _test_mineru_pdf():
    """測試 MinerU PDF 解析"""
    mineru_token = current_app.config.get("MINERU_TOKEN", "")
    if not mineru_token:
        raise ValueError("未配置 MINERU_TOKEN")

    parser = _create_file_parser()
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_file = Path(tmp.name)
        test_image_path = _get_test_image_path()
        with Image.open(test_image_path) as image:
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(tmp_file, format="PDF")

        batch_id, upload_url, error = parser._get_upload_url("mineru-test.pdf")
        if error:
            raise ValueError(error)

        upload_error = parser._upload_file(str(tmp_file), upload_url)
        if upload_error:
            raise ValueError(upload_error)

        markdown_content, extract_id, poll_error = parser._poll_result(batch_id, max_wait_time=30)
        if poll_error:
            if "timeout" in poll_error.lower():
                return {
                    "batch_id": batch_id,
                    "status": "processing",
                    "message": "服務正常，檔案正在處理中"
                }, "MinerU 服務可用（處理中）"
            else:
                raise ValueError(poll_error)
        else:
            content_preview = (markdown_content or "").strip()[:120]
            return {
                "batch_id": batch_id,
                "extract_id": extract_id,
                "content_preview": content_preview,
            }, "MinerU 解析測試成功"
    finally:
        if tmp_file and tmp_file.exists():
            tmp_file.unlink()


# 測試函式對映
TEST_FUNCTIONS = {
    "baidu-ocr": _test_baidu_ocr,
    "text-model": _test_text_model,
    "caption-model": _test_caption_model,
    "baidu-inpaint": _test_baidu_inpaint,
    "image-model": _test_image_model,
    "mineru-pdf": _test_mineru_pdf,
}


def _run_test_async(task_id: str, test_name: str, test_settings: dict, app):
    """
    在後臺非同步執行測試任務

    Args:
        task_id: 任務ID
        test_name: 測試名稱
        test_settings: 測試設定
        app: Flask app 例項
    """
    with app.app_context():
        try:
            # 更新狀態為執行中
            task = Task.query.get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.status = 'PROCESSING'
            db.session.commit()

            # 應用測試設定並執行測試
            with temporary_settings_override(test_settings):
                # 查詢並執行對應的測試函式
                test_func = TEST_FUNCTIONS.get(test_name)
                if not test_func:
                    raise ValueError(f"未知測試型別: {test_name}")

                result_data, message = test_func()

                # 更新任務狀態為完成
                task = Task.query.get(task_id)
                if task:
                    task.status = 'COMPLETED'
                    task.completed_at = datetime.now(timezone.utc)
                    task.set_progress({
                        'result': result_data,
                        'message': message
                    })
                    db.session.commit()
                    logger.info(f"Test task {task_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Test task {task_id} failed: {error_msg}", exc_info=True)
            task = Task.query.get(task_id)
            if task:
                task.status = 'FAILED'
                task.error_message = error_msg
                task.completed_at = datetime.now(timezone.utc)
                db.session.commit()



@settings_bp.route("/tests/<test_name>", methods=["POST"], strict_slashes=False)
def run_settings_test(test_name: str):
    """
    POST /api/settings/tests/<test_name> - 啟動非同步服務測試

    Request Body (optional):
        可選的設定覆蓋引數，用於測試未儲存的配置
        {
            "api_key": "test-key",
            "api_base_url": "https://test.api.com",
            "text_model": "test-model",
            ...
        }

    Returns:
        {
            "data": {
                "task_id": "uuid",
                "status": "PENDING"
            }
        }
    """
    try:
        # 獲取請求體中的測試設定覆蓋（如果有）
        test_settings = request.get_json() or {}

        # 建立任務記錄（使用特殊的 project_id='settings-test'）
        task = Task(
            project_id='settings-test',  # 特殊標記，表示這是設定測試任務
            task_type=f'TEST_{test_name.upper().replace("-", "_")}',
            status='PENDING'
        )
        db.session.add(task)
        db.session.commit()

        task_id = task.id

        # 使用 TaskManager 提交後臺任務
        task_manager.submit_task(
            task_id,
            _run_test_async,
            test_name,
            test_settings,
            current_app._get_current_object()
        )

        logger.info(f"Started test task {task_id} for {test_name}")

        return success_response({
            'task_id': task_id,
            'status': 'PENDING'
        }, '測試任務已啟動')

    except Exception as e:
        logger.error(f"Failed to start test: {str(e)}", exc_info=True)
        return error_response(
            "SETTINGS_TEST_ERROR",
            f"啟動測試失敗: {str(e)}",
            500
        )


@settings_bp.route("/tests/<task_id>/status", methods=["GET"], strict_slashes=False)
def get_test_status(task_id: str):
    """
    GET /api/settings/tests/<task_id>/status - 查詢測試任務狀態

    Returns:
        {
            "data": {
                "status": "PENDING|PROCESSING|COMPLETED|FAILED",
                "result": {...},  # 僅當 status=COMPLETED 時存在
                "error": "...",   # 僅當 status=FAILED 時存在
                "message": "..."
            }
        }
    """
    try:
        task = Task.query.get(task_id)
        if not task:
            return error_response("TASK_NOT_FOUND", "測試任務不存在", 404)

        # 構建響應資料
        response_data = {
            'status': task.status,
            'task_type': task.task_type,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
        }

        # 如果任務完成，包含結果和訊息
        if task.status == 'COMPLETED':
            progress = task.get_progress()
            response_data['result'] = progress.get('result', {})
            response_data['message'] = progress.get('message', '測試完成')

        # 如果任務失敗，包含錯誤資訊
        elif task.status == 'FAILED':
            response_data['error'] = task.error_message

        return success_response(response_data)

    except Exception as e:
        logger.error(f"Failed to get test status: {str(e)}", exc_info=True)
        return error_response(
            "GET_TEST_STATUS_ERROR",
            f"獲取測試狀態失敗: {str(e)}",
            500
        )
