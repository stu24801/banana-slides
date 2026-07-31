"""
內容圖形抽取（供「套用母版匯出」使用）

流程：
  1. 用視覺模型偵測 AI 生成頁面上的「內容型圖形」（插畫 / icon / 圖表 / 示意圖 / 照片）
     的 bbox，排除整頁背景、純色/漸層、角落 logo、純文字。
  2. 逐塊裁切，並用 OpenCV GrabCut 去背成透明 PNG，方便貼到母版上。

視覺模型透過 llm-proxy 呼叫；proxy 已支援 Claude 視覺（含圖請求走 Anthropic）。
去背做成可抽換函式，日後可換 rembg 等提升品質。
"""
import base64
import io
import json
import logging
import re
from typing import List, Dict, Optional

from PIL import Image

logger = logging.getLogger(__name__)

try:
    import numpy as np
    import cv2
    _HAS_CV2 = True
except Exception:  # pragma: no cover
    _HAS_CV2 = False


_VISION_PROMPT = (
    "你是投影片版面分析器。這是一頁 AI 生成的簡報圖。請找出頁面上「內容型視覺圖形」"
    "（插畫、icon 圖示、圖表、示意圖、流程圖、照片）。\n"
    "務必**排除**：整頁背景、純色或漸層色塊、頁面四角或頁首頁尾的 logo/浮水印、以及純文字（標題與內文）。\n"
    "以 JSON 陣列回傳，每個元素為 "
    '{"label": 簡述, "is_logo": true/false, "x0":,"y0":,"x1":,"y1":}，'
    "座標為 0~1 相對比例（左上為原點，x 向右、y 向下）。若你認為某物是 logo/浮水印，"
    "請照樣列出但把 is_logo 設為 true。只回 JSON，不要任何多餘文字或註解。"
)

# label 命中這些關鍵字者視為 logo / 浮水印，予以排除
_LOGO_KEYWORDS = ("logo", "浮水印", "watermark", "商標", "品牌標")


def _extract_json_array(text: str) -> Optional[list]:
    """從模型回覆中盡量取出 JSON 陣列。"""
    if not text:
        return None
    # 去掉 ```json ... ``` 圍欄
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = fenced.group(1) if fenced else None
    if raw is None:
        m = re.search(r"\[.*\]", text, re.DOTALL)
        raw = m.group(0) if m else None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else None
    except Exception:
        return None


def detect_content_graphics(image: Image.Image, client, model: str,
                            max_tokens: int = 2000) -> List[Dict]:
    """呼叫視覺模型，回傳內容圖形 bbox 清單（已濾除 logo、已夾到 0~1）。

    Args:
        image: 整頁 PIL 圖
        client: OpenAI 相容 client（指向 llm-proxy）
        model:  視覺可用模型（例如 claude-sonnet-4-6）

    Returns:
        List[{'label': str, 'x0','y0','x1','y1': float}]
    """
    buf = io.BytesIO()
    rgb = image.convert("RGB")
    rgb.save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": _VISION_PROMPT},
        ]}],
        temperature=0.1,
        max_tokens=max_tokens,
    )
    text = resp.choices[0].message.content
    items = _extract_json_array(text)
    if not items:
        logger.warning("視覺模型未回傳可解析的圖形 bbox；原始回覆前 200 字：%s", (text or "")[:200])
        return []

    result: List[Dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        label = str(it.get("label", "")).strip()
        if it.get("is_logo") is True:
            continue
        if any(k in label.lower() for k in _LOGO_KEYWORDS):
            continue
        try:
            x0 = max(0.0, min(1.0, float(it["x0"])))
            y0 = max(0.0, min(1.0, float(it["y0"])))
            x1 = max(0.0, min(1.0, float(it["x1"])))
            y1 = max(0.0, min(1.0, float(it["y1"])))
        except (KeyError, TypeError, ValueError):
            continue
        if x1 <= x0 or y1 <= y0:
            continue
        # 過濾掉幾乎整頁的框（多半是把背景當成圖形）
        if (x1 - x0) >= 0.92 and (y1 - y0) >= 0.92:
            continue
        result.append({"label": label, "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return result


_LOGO_PROMPT = (
    "你是投影片品牌標記偵測器。這是一頁 AI 生成的簡報圖。請只找出「品牌 logo / 浮水印 / "
    "商標圖示」——通常出現在頁面四角或頁首/頁尾，屬於整份簡報重複出現的識別標記"
    "（例如公司標誌、山峰/圖形商標）。\n"
    "不要框選內文插畫、資料圖表、與內容相關的示意圖。\n"
    "以 JSON 陣列回傳，元素為 "
    '{"label": 簡述, "x0":,"y0":,"x1":,"y1":}，座標 0~1 相對比例（左上為原點）。'
    "若整頁沒有 logo，回傳空陣列 []。只回 JSON。"
)


def detect_logos(image: Image.Image, client, model: str, max_tokens: int = 1000) -> List[Dict]:
    """偵測頁面上的品牌 logo / 浮水印 bbox（供擦除，避免與母版 logo 重複）。"""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    b64 = base64.b64encode(buf.getvalue()).decode()
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            {"type": "text", "text": _LOGO_PROMPT},
        ]}],
        temperature=0.0,
        max_tokens=max_tokens,
    )
    items = _extract_json_array(resp.choices[0].message.content) or []
    out: List[Dict] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            x0 = max(0.0, min(1.0, float(it["x0"]))); y0 = max(0.0, min(1.0, float(it["y0"])))
            x1 = max(0.0, min(1.0, float(it["x1"]))); y1 = max(0.0, min(1.0, float(it["y1"])))
        except (KeyError, TypeError, ValueError):
            continue
        if x1 <= x0 or y1 <= y0:
            continue
        # 安全上限：logo 一般不大；框超過半頁者視為誤判，略過
        if (x1 - x0) > 0.5 or (y1 - y0) > 0.5:
            continue
        out.append({"label": str(it.get("label", "")), "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return out


def erase_regions_to_transparent(image: Image.Image, boxes: List[Dict],
                                 pad_ratio: float = 0.006) -> Image.Image:
    """把指定區塊擦成透明（alpha=0），回傳 RGBA。用於移除與母版重複的 logo。"""
    rgba = image.convert("RGBA")
    if not boxes:
        return rgba
    W, H = rgba.size
    px = rgba.load()
    for b in boxes:
        x0 = int(max(0, (b["x0"] - pad_ratio) * W))
        y0 = int(max(0, (b["y0"] - pad_ratio) * H))
        x1 = int(min(W, (b["x1"] + pad_ratio) * W))
        y1 = int(min(H, (b["y1"] + pad_ratio) * H))
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                r, g, bl, _ = px[xx, yy]
                px[xx, yy] = (r, g, bl, 0)
    return rgba


def _remove_background_grabcut(crop: Image.Image, margin: int = 6) -> Image.Image:
    """用 GrabCut 去背，回傳 RGBA。失敗或無 cv2 時回傳原圖轉 RGBA。"""
    if not _HAS_CV2:
        return crop.convert("RGBA")
    try:
        rgb = crop.convert("RGB")
        arr = np.array(rgb)
        h, w = arr.shape[:2]
        if h < 20 or w < 20:
            return crop.convert("RGBA")
        mask = np.zeros((h, w), np.uint8)
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)
        # 以外緣 margin 當背景、內部矩形當可能前景
        m = max(2, min(margin, w // 6, h // 6))
        rect = (m, m, w - 2 * m, h - 2 * m)
        cv2.grabCut(arr, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
        fg = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
        # 若前景比例過小（<8%）或過大（>98%），視為去背失敗，保留原圖不透明
        ratio = fg.mean() / 255.0
        if ratio < 0.08 or ratio > 0.98:
            return crop.convert("RGBA")
        rgba = np.dstack([arr, fg])
        return Image.fromarray(rgba, mode="RGBA")
    except Exception as e:  # pragma: no cover
        logger.warning("GrabCut 去背失敗，保留原圖：%s", e)
        return crop.convert("RGBA")


def extract_graphics(image: Image.Image, boxes: List[Dict],
                     remove_bg: bool = True, pad_ratio: float = 0.01) -> List[Dict]:
    """依 bbox 從整頁裁出圖形（可選去背），回傳含 RGBA 圖與相對座標的清單。"""
    W, H = image.size
    out: List[Dict] = []
    for b in boxes:
        px0 = int(max(0, (b["x0"] - pad_ratio) * W))
        py0 = int(max(0, (b["y0"] - pad_ratio) * H))
        px1 = int(min(W, (b["x1"] + pad_ratio) * W))
        py1 = int(min(H, (b["y1"] + pad_ratio) * H))
        if px1 <= px0 or py1 <= py0:
            continue
        crop = image.crop((px0, py0, px1, py1))
        rgba = _remove_background_grabcut(crop) if remove_bg else crop.convert("RGBA")
        out.append({
            "label": b.get("label", ""),
            "image": rgba,
            # 用實際裁切後的像素反推相對座標，定位更準
            "x0": px0 / W, "y0": py0 / H, "x1": px1 / W, "y1": py1 / H,
        })
    return out
