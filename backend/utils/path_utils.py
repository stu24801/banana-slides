"""
Path utilities for handling MinerU file paths and prefix matching
"""
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def convert_mineru_path_to_local(mineru_path: str, project_root: Optional[Path] = None) -> Optional[Path]:
    """
    將 /files/mineru/{extract_id}/{rel_path} 格式的路徑轉換為本地檔案系統路徑
    
    Args:
        mineru_path: MinerU URL 路徑，格式為 /files/mineru/{extract_id}/{rel_path}
        project_root: 專案根目錄路徑（如果為 None，則自動計算）
        
    Returns:
        本地檔案系統路徑（Path 物件），如果轉換失敗則返回 None
    """
    try:
        if not mineru_path.startswith('/files/mineru/'):
            return None
        
        # Remove '/files/mineru/' prefix
        rel_path = mineru_path.replace('/files/mineru/', '')
        
        # Get project root if not provided
        if project_root is None:
            # Navigate to project root (assuming this file is in backend/utils/)
            current_file = Path(__file__).resolve()
            backend_dir = current_file.parent.parent
            project_root = backend_dir.parent
        
        # Construct full path: {project_root}/uploads/mineru_files/{rel_path}
        local_path = project_root / 'uploads' / 'mineru_files' / rel_path
        
        return local_path
    except Exception as e:
        logger.warning(f"Failed to convert MinerU path to local: {mineru_path}, error: {str(e)}")
        return None


def find_mineru_file_with_prefix(mineru_path: str, project_root: Optional[Path] = None) -> Optional[Path]:
    """
    查詢 MinerU 檔案，支援字首匹配
    
    首先嚐試直接路徑匹配，如果失敗則嘗試字首匹配。
    字首匹配邏輯：如果檔名看起來像是一個字首+副檔名（字首長度 >= 5），
    則在目錄中查詢以該字首開頭的檔案。
    
    Args:
        mineru_path: MinerU URL 路徑，格式為 /files/mineru/{extract_id}/{rel_path}
        project_root: 專案根目錄路徑（如果為 None，則自動計算）
        
    Returns:
        找到的檔案路徑（Path 物件），如果未找到則返回 None
    """
    # First try direct path conversion
    local_path = convert_mineru_path_to_local(mineru_path, project_root)
    
    if local_path is None:
        return None
    
    # Direct file matching
    if local_path.exists() and local_path.is_file():
        return local_path
    
    # Try prefix match using the generic function
    return find_file_with_prefix(local_path)


def find_file_with_prefix(file_path: Path) -> Optional[Path]:
    """
    查詢檔案，支援字首匹配
    
    首先檢查檔案是否存在，如果不存在則嘗試字首匹配。
    字首匹配邏輯：如果檔名看起來像是一個字首+副檔名（字首長度 >= 5），
    則在目錄中查詢以該字首開頭的檔案。
    
    Args:
        file_path: 要查詢的檔案路徑（Path 物件）
        
    Returns:
        找到的檔案路徑（Path 物件），如果未找到則返回 None
    """
    # Direct file matching
    if file_path.exists() and file_path.is_file():
        return file_path
    
    # Try prefix match if not found and filename looks like a prefix with extension
    filename = file_path.name
    dirpath = file_path.parent
    
    if '.' in filename and dirpath.exists() and dirpath.is_dir():
        prefix, ext = os.path.splitext(filename)
        if len(prefix) >= 5:
            try:
                for fname in os.listdir(dirpath):
                    fp, fe = os.path.splitext(fname)
                    if fp.lower().startswith(prefix.lower()) and fe.lower() == ext.lower():
                        matched_path = dirpath / fname
                        if matched_path.is_file():
                            logger.debug(f"Prefix match found: {file_path} -> {matched_path}")
                            return matched_path
            except OSError as e:
                logger.warning(f"Failed to list directory {dirpath}: {str(e)}")
    
    return None

