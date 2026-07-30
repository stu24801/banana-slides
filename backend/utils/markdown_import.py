"""
Markdown 結構化投影片稿解析

支援使用者以「頁面標題：／頁面文字：」標記手寫的多頁投影片稿，
解析成可直接建立專案頁面（description_content）的結構，不觸發任何 AI 生成。

主要格式（每頁一個 H2 區塊）：

    # 簡報總標題
    ## 第一張｜區塊名稱
    頁面標題：這一頁的標題
    頁面文字：
    （表格 / 程式碼 / 條列等 Markdown 內容）
    ---

沒有 `頁面標題：` 標記的 H2 區塊（前言、版本資訊等）會被略過。
若整份文件都沒有標記，則退回相容模式：把每個 H2 標題當頁標題、其內容當描述
（對應本系統自身「匯出頁面描述」的格式，可 round-trip 再匯入）。
"""
import re

# 頁標題 / 頁內容的標記詞（繁簡 + 常見別名）
_TITLE_MARKERS = ('頁面標題', '页面标题', '頁標題', '页标题')
_BODY_MARKERS = ('頁面文字', '页面文字', '頁面內容', '页面内容', '頁面描述', '页面描述')
# 這些 H2 區塊不是投影片頁，直接略過
_SKIP_HEADING_KEYWORDS = ('版本資訊', '版本资讯', '版本信息', '修訂', '修订', 'changelog', 'version history')

_TITLE_RE = re.compile(r'^\**\s*(?:%s)\s*[:：]\s*(.*)$' % '|'.join(_TITLE_MARKERS))
_BODY_RE = re.compile(r'^\**\s*(?:%s)\s*[:：]\s*(.*)$' % '|'.join(_BODY_MARKERS))
# 相容模式下，把「第 N 頁: / 第一張｜」之類的前綴從標題移除
_HEADING_PREFIX_RE = re.compile(r'^第\s*[\d一二三四五六七八九十百零]+\s*[頁張页张]\s*[:：｜|]?\s*')


def _strip_separators(text: str) -> str:
    """去掉區塊首尾的水平線（---）與空白行。"""
    lines = text.split('\n')
    while lines and lines[0].strip() in ('', '---', '***', '___'):
        lines.pop(0)
    while lines and lines[-1].strip() in ('', '---', '***', '___'):
        lines.pop()
    return '\n'.join(lines).strip()


def _has_marker_line(body_lines) -> bool:
    """是否存在「行首」的頁面標題/頁面文字標記行（避免誤判內文中提到的字樣）。"""
    for line in body_lines:
        s = line.strip()
        if _TITLE_RE.match(s) or _BODY_RE.match(s):
            return True
    return False


def _extract_marked(body_lines):
    """從一個含標記的區塊取出 (title, description)。"""
    title = None
    for i, line in enumerate(body_lines):
        stripped = line.strip()
        if title is None:
            m = _TITLE_RE.match(stripped)
            if m:
                title = m.group(1).strip().strip('*').strip()
                continue
        m2 = _BODY_RE.match(stripped)
        if m2:
            inline = m2.group(1).strip()
            rest = body_lines[i + 1:]
            desc = (inline + '\n' + '\n'.join(rest)) if inline else '\n'.join(rest)
            return title, _strip_separators(desc)
    # 有頁面標題但沒有頁面文字標記：描述 = 區塊內容扣掉標題那行
    if title is not None:
        filtered = [l for l in body_lines if not _TITLE_RE.match(l.strip())]
        return title, _strip_separators('\n'.join(filtered))
    return None, _strip_separators('\n'.join(body_lines))


def parse_markdown_to_pages(md_text: str):
    """
    解析 Markdown 稿為 (deck_title, pages)。

    Returns:
        deck_title: str | None  —— 第一個 H1 標題（作為專案顯示名）
        pages: List[{'title': str, 'description': str, 'part': str | None}]

    Raises:
        ValueError: 內容為空或解析不到任何頁
    """
    if not md_text or not md_text.strip():
        raise ValueError('Markdown 內容為空')

    lines = md_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')

    deck_title = None
    sections = []          # list[(heading, [body lines])]
    cur_head = None
    cur_body = []
    for line in lines:
        if deck_title is None and re.match(r'^#\s+\S', line):
            deck_title = re.sub(r'^#\s+', '', line).strip()
            continue
        if line.startswith('## '):          # 只切 H2（### 之後留在同一頁）
            if cur_head is not None:
                sections.append((cur_head, cur_body))
            cur_head = line[3:].strip()
            cur_body = []
        elif cur_head is not None:
            cur_body.append(line)
        # H1 之後、第一個 H2 之前的內容（前言）忽略

    if cur_head is not None:
        sections.append((cur_head, cur_body))

    doc_uses_markers = any(_has_marker_line(b) for _, b in sections)

    pages = []
    for heading, body_lines in sections:
        if any(k.lower() in heading.lower() for k in _SKIP_HEADING_KEYWORDS):
            continue
        body = '\n'.join(body_lines)

        if _has_marker_line(body_lines):
            title, desc = _extract_marked(body_lines)
            # 標記格式下標題以頁面標題行為準；若省略則退回用 H2 標題
            if not title:
                title = _HEADING_PREFIX_RE.sub('', heading).strip() or heading
        elif doc_uses_markers:
            # 這份文件是「標記格式」，但此區塊沒有真正的標記行 → 前言/雜項，略過
            continue
        else:
            # 相容模式：H2 標題即頁標題、其內容即描述
            title = _HEADING_PREFIX_RE.sub('', heading).strip() or heading
            desc = _strip_separators(body)

        title = (title or '').strip()
        desc = (desc or '').strip()
        if not title and not desc:
            continue
        pages.append({'title': title, 'description': desc, 'part': None})

    if not pages:
        raise ValueError('未解析到任何投影片頁；請確認每頁包含「頁面標題：」與「頁面文字：」，或參考範例格式檔案')

    return deck_title, pages
