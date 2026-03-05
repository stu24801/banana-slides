"""
AI Service Prompts - 集中管理所有 AI 服務的 prompt 模板
"""
import json
import logging
from textwrap import dedent
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from services.ai_service import ProjectContext

logger = logging.getLogger(__name__)


# 語言配置對映
LANGUAGE_CONFIG = {
    'zh': {
        'name': '中文',
        'instruction': '請使用全中文輸出。',
        'ppt_text': 'PPT文字請使用全中文。'
    },
    'ja': {
        'name': '日本語',
        'instruction': 'すべて日本語で出力してください。',
        'ppt_text': 'PPTのテキストは全て日本語で出力してください。'
    },
    'en': {
        'name': 'English',
        'instruction': 'Please output all in English.',
        'ppt_text': 'Use English for PPT text.'
    },
    'auto': {
        'name': '自動',
        'instruction': '',  # 自動模式不新增語言限制
        'ppt_text': ''
    }
}


def get_default_output_language() -> str:
    """
    獲取環境變數中配置的預設輸出語言
    
    Returns:
        語言程式碼: 'zh', 'ja', 'en', 'auto'
    """
    from config import Config
    return getattr(Config, 'OUTPUT_LANGUAGE', 'zh')


def get_language_instruction(language: str = None) -> str:
    """
    獲取語言限制指令文字
    
    Args:
        language: 語言程式碼，如果為 None 則使用預設語言
    
    Returns:
        語言限制指令，如果是自動模式則返回空字串
    """
    lang = language if language else get_default_output_language()
    config = LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG['zh'])
    return config['instruction']


def get_ppt_language_instruction(language: str = None) -> str:
    """
    獲取PPT文字語言限制指令
    
    Args:
        language: 語言程式碼，如果為 None 則使用預設語言
    
    Returns:
        PPT語言限制指令，如果是自動模式則返回空字串
    """
    lang = language if language else get_default_output_language()
    config = LANGUAGE_CONFIG.get(lang, LANGUAGE_CONFIG['zh'])
    return config['ppt_text']


def _format_reference_files_xml(reference_files_content: Optional[List[Dict[str, str]]]) -> str:
    """
    Format reference files content as XML structure
    
    Args:
        reference_files_content: List of dicts with 'filename' and 'content' keys
        
    Returns:
        Formatted XML string
    """
    if not reference_files_content:
        return ""
    
    xml_parts = ["<uploaded_files>"]
    for file_info in reference_files_content:
        filename = file_info.get('filename', 'unknown')
        content = file_info.get('content', '')
        xml_parts.append(f'  <file name="{filename}">')
        xml_parts.append('    <content>')
        xml_parts.append(content)
        xml_parts.append('    </content>')
        xml_parts.append('  </file>')
    xml_parts.append('</uploaded_files>')
    xml_parts.append('')  # Empty line after XML
    
    return '\n'.join(xml_parts)


def get_outline_generation_prompt(project_context: 'ProjectContext', language: str = None) -> str:
    """
    生成 PPT 大綱的 prompt
    
    Args:
        project_context: 專案上下文物件，包含所有原始資訊
        language: 輸出語言程式碼（'zh', 'ja', 'en', 'auto'），如果為 None 則使用預設語言
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    idea_prompt = project_context.idea_prompt or ""
    
    prompt = (f"""\
You are a helpful assistant that generates an outline for a ppt.

You can organize the content in two ways:

1. Simple format (for short PPTs without major sections):
[{{"title": "title1", "points": ["point1", "point2"]}}, {{"title": "title2", "points": ["point1", "point2"]}}]

2. Part-based format (for longer PPTs with major sections):
[
    {{
    "part": "Part 1: Introduction",
    "pages": [
        {{"title": "Welcome", "points": ["point1", "point2"]}},
        {{"title": "Overview", "points": ["point1", "point2"]}}
    ]
    }},
    {{
    "part": "Part 2: Main Content",
    "pages": [
        {{"title": "Topic 1", "points": ["point1", "point2"]}},
        {{"title": "Topic 2", "points": ["point1", "point2"]}}
    ]
    }}
]

Choose the format that best fits the content. Use parts when the PPT has clear major sections.
Unless otherwise specified, the first page should be kept simplest, containing only the title, subtitle, and presenter information.

The user's request: {idea_prompt}. Now generate the outline, don't include any other text.
{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_outline_generation_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_outline_parsing_prompt(project_context: 'ProjectContext', language: str = None ) -> str:
    """
    解析使用者提供的大綱文字的 prompt
    
    Args:
        project_context: 專案上下文物件，包含所有原始資訊
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    outline_text = project_context.outline_text or ""
    
    prompt = (f"""\
You are a helpful assistant that parses a user-provided PPT outline text into a structured format.

The user has provided the following outline text:

{outline_text}

Your task is to analyze this text and convert it into a structured JSON format WITHOUT modifying any of the original text content. 
You should only reorganize and structure the existing content, preserving all titles, points, and text exactly as provided.

You can organize the content in two ways:

1. Simple format (for short PPTs without major sections):
[{{"title": "title1", "points": ["point1", "point2"]}}, {{"title": "title2", "points": ["point1", "point2"]}}]

2. Part-based format (for longer PPTs with major sections):
[
    {{
    "part": "Part 1: Introduction",
    "pages": [
        {{"title": "Welcome", "points": ["point1", "point2"]}},
        {{"title": "Overview", "points": ["point1", "point2"]}}
    ]
    }},
    {{
    "part": "Part 2: Main Content",
    "pages": [
        {{"title": "Topic 1", "points": ["point1", "point2"]}},
        {{"title": "Topic 2", "points": ["point1", "point2"]}}
    ]
    }}
]

Important rules:
- DO NOT modify, rewrite, or change any text from the original outline
- DO NOT add new content that wasn't in the original text
- DO NOT remove any content from the original text
- Only reorganize the existing content into the structured format
- Preserve all titles, bullet points, and text exactly as they appear
- If the text has clear sections/parts, use the part-based format
- Extract titles and points from the original text, keeping them exactly as written

Now parse the outline text above into the structured format. Return only the JSON, don't include any other text.
{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_outline_parsing_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_page_description_prompt(project_context: 'ProjectContext', outline: list, 
                                page_outline: dict, page_index: int, 
                                part_info: str = "",
                                language: str = None) -> str:
    """
    生成單個頁面描述的 prompt
    
    Args:
        project_context: 專案上下文物件，包含所有原始資訊
        outline: 完整大綱
        page_outline: 當前頁面的大綱
        page_index: 頁面編號（從1開始）
        part_info: 可選的章節資訊
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    # 根據專案型別選擇最相關的原始輸入
    if project_context.creation_type == 'idea' and project_context.idea_prompt:
        original_input = project_context.idea_prompt
    elif project_context.creation_type == 'outline' and project_context.outline_text:
        original_input = f"使用者提供的大綱：\n{project_context.outline_text}"
    elif project_context.creation_type == 'descriptions' and project_context.description_text:
        original_input = f"使用者提供的描述：\n{project_context.description_text}"
    else:
        original_input = project_context.idea_prompt or ""
    
    prompt = (f"""\
我們正在為PPT的每一頁生成內容描述。
使用者的原始需求是：\n{original_input}\n
我們已經有了完整的大綱：\n{outline}\n{part_info}
現在請為第 {page_index} 頁生成描述：
{page_outline}
{"**除非特殊要求，第一頁的內容需要保持極簡，只放標題副標題以及演講人等（輸出到標題後）, 不新增任何素材。**" if page_index == 1 else ""}

【重要提示】生成的"頁面文字"部分會直接渲染到PPT頁面上，因此請務必注意：
1. 文字內容要簡潔精煉，每條要點控制在15-25字以內
2. 條理清晰，使用列表形式組織內容
3. 避免冗長的句子和複雜的表述
4. 確保內容可讀性強，適合在演示時展示
5. 不要包含任何額外的說明性文字或註釋

輸出格式示例：
頁面標題：原始社會：與自然共生
{"副標題：人類祖先和自然的相處之道" if page_index == 1 else ""}

頁面文字：
- 狩獵採集文明：人類活動規模小，對環境影響有限
- 依賴性強：生活完全依賴自然資源的直接供給
- 適應而非改造：透過觀察學習自然，發展生存技能
- 影響特點：區域性、短期、低強度，生態可自我恢復

其他頁面素材（如果檔案中存在請積極新增，包括markdown圖片連結、公式、表格等）

【關於圖片】如果參考檔案中包含以 /files/ 開頭的本地檔案URL圖片（例如 /files/mineru/xxx/image.png），請將這些圖片以markdown格式輸出，例如：![圖片描述](/files/mineru/xxx/image.png)。這些圖片會被包含在PPT頁面中。

{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_page_description_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_image_generation_prompt(page_desc: str, outline_text: str, 
                                current_section: str,
                                has_material_images: bool = False,
                                extra_requirements: str = None,
                                language: str = None,
                                has_template: bool = True,
                                page_index: int = 1) -> str:
    """
    生成圖片生成 prompt
    
    Args:
        page_desc: 頁面描述文字
        outline_text: 大綱文字
        current_section: 當前章節
        has_material_images: 是否有素材圖片
        extra_requirements: 額外的要求（可能包含風格描述）
        language: 輸出語言
        has_template: 是否有模板圖片（False表示無模板圖模式）
        
    Returns:
        格式化後的 prompt 字串
    """
    # 如果有素材圖片，在 prompt 中明確告知 AI
    material_images_note = ""
    if has_material_images:
        material_images_note = (
            "\n\n提示：" + ("除了模板參考圖片（用於風格參考）外，還提供了額外的素材圖片。" if has_template else "使用者提供了額外的素材圖片。") +
            "這些素材圖片是可供挑選和使用的元素，你可以從這些素材圖片中選擇合適的圖片、圖示、圖表或其他視覺元素"
            "直接整合到生成的PPT頁面中。請根據頁面內容的需要，智慧地選擇和組合這些素材圖片中的元素。"
        )
    
    # 新增額外要求到提示詞
    extra_req_text = ""
    if extra_requirements and extra_requirements.strip():
        extra_req_text = f"\n\n額外要求（請務必遵循）：\n{extra_requirements}\n"

    # 根據是否有模板生成不同的設計指南內容（保持原prompt要點順序）
    template_style_guideline = "- 配色和設計語言和模板圖片嚴格相似。" if has_template else "- 嚴格按照風格描述進行設計。"
    forbidden_template_text_guidline = "- 只參考風格設計，禁止出現模板中的文字。\n" if has_template else ""

    # 該處參考了@歸藏的A工具箱
    prompt = (f"""\
你是一位專家級UI UX演示設計師，專注於生成設計良好的PPT頁面。
當前PPT頁面的頁面描述如下:
<page_description>
{page_desc}
</page_description>

<reference_information>
整個PPT的大綱為：
{outline_text}

當前位於章節：{current_section}
</reference_information>


<design_guidelines>
- 要求文字清晰銳利, 畫面為4K解析度，16:9比例。
{template_style_guideline}
- 根據內容自動設計最完美的構圖，不重不漏地渲染"頁面描述"中的文字。
- 如非必要，禁止出現 markdown 格式符號（如 # 和 * 等）。
{forbidden_template_text_guidline}- 使用大小恰當的裝飾性圖形或插畫對空缺位置進行填補。
</design_guidelines>
{get_ppt_language_instruction(language)}
{material_images_note}{extra_req_text}

{"**注意：當前頁面為ppt的封面頁，請你採用專業的封面設計美學技巧，務必凸顯出頁面標題，分清主次，確保一下就能抓住觀眾的注意力。**" if page_index == 1 else ""}
""")
    
    logger.debug(f"[get_image_generation_prompt] Final prompt:\n{prompt}")
    return prompt


def get_image_edit_prompt(edit_instruction: str, original_description: str = None) -> str:
    """
    生成圖片編輯 prompt
    
    Args:
        edit_instruction: 編輯指令
        original_description: 原始頁面描述（可選）
        
    Returns:
        格式化後的 prompt 字串
    """
    if original_description:
        # 刪除"其他頁面素材："之後的內容，避免被前面的圖影響
        if "其他頁面素材" in original_description:
            original_description = original_description.split("其他頁面素材")[0].strip()
        
        prompt = (f"""\
該PPT頁面的原始頁面描述為：
{original_description}

現在，根據以下指令修改這張PPT頁面：{edit_instruction}

要求維持原有的文字內容和設計風格，只按照指令進行修改。提供的參考圖中既有新素材，也有使用者手動框選出的區域，請你根據原圖和參考圖的關係智慧判斷使用者意圖。
""")
    else:
        prompt = f"根據以下指令修改這張PPT頁面：{edit_instruction}\n保持原有的內容結構和設計風格，只按照指令進行修改。提供的參考圖中既有新素材，也有使用者手動框選出的區域，請你根據原圖和參考圖的關係智慧判斷使用者意圖。"
    
    logger.debug(f"[get_image_edit_prompt] Final prompt:\n{prompt}")
    return prompt


def get_description_to_outline_prompt(project_context: 'ProjectContext', language: str = None) -> str:
    """
    從描述文字解析出大綱的 prompt
    
    Args:
        project_context: 專案上下文物件，包含所有原始資訊
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    description_text = project_context.description_text or ""
    
    prompt = (f"""\
You are a helpful assistant that analyzes a user-provided PPT description text and extracts the outline structure from it.

The user has provided the following description text:

{description_text}

Your task is to analyze this text and extract the outline structure (titles and key points) for each page.
You should identify:
1. How many pages are described
2. The title for each page
3. The key points or content structure for each page

You can organize the content in two ways:

1. Simple format (for short PPTs without major sections):
[{{"title": "title1", "points": ["point1", "point2"]}}, {{"title": "title2", "points": ["point1", "point2"]}}]

2. Part-based format (for longer PPTs with major sections):
[
    {{
    "part": "Part 1: Introduction",
    "pages": [
        {{"title": "Welcome", "points": ["point1", "point2"]}},
        {{"title": "Overview", "points": ["point1", "point2"]}}
    ]
    }},
    {{
    "part": "Part 2: Main Content",
    "pages": [
        {{"title": "Topic 1", "points": ["point1", "point2"]}},
        {{"title": "Topic 2", "points": ["point1", "point2"]}}
    ]
    }}
]

Important rules:
- Extract the outline structure from the description text
- Identify page titles and key points
- If the text has clear sections/parts, use the part-based format
- Preserve the logical structure and organization from the original text
- The points should be concise summaries of the main content for each page

Now extract the outline structure from the description text above. Return only the JSON, don't include any other text.
{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_description_to_outline_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_description_split_prompt(project_context: 'ProjectContext', 
                                 outline: List[Dict], 
                                 language: str = None) -> str:
    """
    從描述文字切分出每頁描述的 prompt
    
    Args:
        project_context: 專案上下文物件，包含所有原始資訊
        outline: 已解析出的大綱結構
        
    Returns:
        格式化後的 prompt 字串
    """
    outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
    description_text = project_context.description_text or ""
    
    prompt = (f"""\
You are a helpful assistant that splits a complete PPT description text into individual page descriptions.

The user has provided a complete description text:

{description_text}

We have already extracted the outline structure:

{outline_json}

Your task is to split the description text into individual page descriptions based on the outline structure.
For each page in the outline, extract the corresponding description from the original text.

Return a JSON array where each element corresponds to a page in the outline (in the same order).
Each element should be a string containing the page description in the following format:

頁面標題：[頁面標題]

頁面文字：
- [要點1]
- [要點2]
...

Example output format:
[
    "頁面標題：人工智慧的誕生\\n頁面文字：\\n- 1950 年，圖靈提出"圖靈測試"...",
    "頁面標題：AI 的發展歷程\\n頁面文字：\\n- 1950年代：符號主義...",
    ...
]

Important rules:
- Split the description text according to the outline structure
- Each page description should match the corresponding page in the outline
- Preserve all important content from the original text
- Keep the format consistent with the example above
- If a page in the outline doesn't have a clear description in the text, create a reasonable description based on the outline

Now split the description text into individual page descriptions. Return only the JSON array, don't include any other text.
{get_language_instruction(language)}
""")
    
    logger.debug(f"[get_description_split_prompt] Final prompt:\n{prompt}")
    return prompt


def get_outline_refinement_prompt(current_outline: List[Dict], user_requirement: str,
                                   project_context: 'ProjectContext',
                                   previous_requirements: Optional[List[str]] = None,
                                   language: str = None) -> str:
    """
    根據使用者要求修改已有大綱的 prompt
    
    Args:
        current_outline: 當前的大綱結構
        user_requirement: 使用者的新要求
        project_context: 專案上下文物件，包含所有原始資訊
        previous_requirements: 之前的修改要求列表（可選）
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    
    # 處理空大綱的情況
    if not current_outline or len(current_outline) == 0:
        outline_text = "(當前沒有內容)"
    else:
        outline_text = json.dumps(current_outline, ensure_ascii=False, indent=2)
    
    # 構建之前的修改歷史記錄
    previous_req_text = ""
    if previous_requirements and len(previous_requirements) > 0:
        prev_list = "\n".join([f"- {req}" for req in previous_requirements])
        previous_req_text = f"\n\n之前使用者提出的修改要求：\n{prev_list}\n"
    
    # 構建原始輸入資訊（根據專案型別顯示不同的原始內容）
    original_input_text = "\n原始輸入資訊：\n"
    if project_context.creation_type == 'idea' and project_context.idea_prompt:
        original_input_text += f"- PPT構想：{project_context.idea_prompt}\n"
    elif project_context.creation_type == 'outline' and project_context.outline_text:
        original_input_text += f"- 使用者提供的大綱文字：\n{project_context.outline_text}\n"
    elif project_context.creation_type == 'descriptions' and project_context.description_text:
        original_input_text += f"- 使用者提供的頁面描述文字：\n{project_context.description_text}\n"
    elif project_context.idea_prompt:
        original_input_text += f"- 使用者輸入：{project_context.idea_prompt}\n"
    
    prompt = (f"""\
You are a helpful assistant that modifies PPT outlines based on user requirements.
{original_input_text}
當前的 PPT 大綱結構如下：

{outline_text}
{previous_req_text}
**使用者現在提出新的要求：{user_requirement}**

請根據使用者的要求修改和調整大綱。你可以：
- 新增、刪除或重新排列頁面
- 修改頁面標題和要點
- 調整頁面的組織結構
- 新增或刪除章節（part）
- 合併或拆分頁面
- 根據使用者要求進行任何合理的調整
- 如果當前沒有內容，請根據使用者要求和原始輸入資訊建立新的大綱

輸出格式可以選擇：

1. 簡單格式（適用於沒有主要章節的短 PPT）：
[{{"title": "title1", "points": ["point1", "point2"]}}, {{"title": "title2", "points": ["point1", "point2"]}}]

2. 基於章節的格式（適用於有明確主要章節的長 PPT）：
[
    {{
    "part": "第一部分：引言",
    "pages": [
        {{"title": "歡迎", "points": ["point1", "point2"]}},
        {{"title": "概述", "points": ["point1", "point2"]}}
    ]
    }},
    {{
    "part": "第二部分：主要內容",
    "pages": [
        {{"title": "主題1", "points": ["point1", "point2"]}},
        {{"title": "主題2", "points": ["point1", "point2"]}}
    ]
    }}
]

選擇最適合內容的格式。當 PPT 有清晰的主要章節時使用章節格式。

現在請根據使用者要求修改大綱，只輸出 JSON 格式的大綱，不要包含其他文字。
{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_outline_refinement_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_descriptions_refinement_prompt(current_descriptions: List[Dict], user_requirement: str,
                                       project_context: 'ProjectContext',
                                       outline: List[Dict] = None,
                                       previous_requirements: Optional[List[str]] = None,
                                       language: str = None) -> str:
    """
    根據使用者要求修改已有頁面描述的 prompt
    
    Args:
        current_descriptions: 當前的頁面描述列表，每個元素包含 {index, title, description_content}
        user_requirement: 使用者的新要求
        project_context: 專案上下文物件，包含所有原始資訊
        outline: 完整的大綱結構（可選）
        previous_requirements: 之前的修改要求列表（可選）
        
    Returns:
        格式化後的 prompt 字串
    """
    files_xml = _format_reference_files_xml(project_context.reference_files_content)
    
    # 構建之前的修改歷史記錄
    previous_req_text = ""
    if previous_requirements and len(previous_requirements) > 0:
        prev_list = "\n".join([f"- {req}" for req in previous_requirements])
        previous_req_text = f"\n\n之前使用者提出的修改要求：\n{prev_list}\n"
    
    # 構建原始輸入資訊
    original_input_text = "\n原始輸入資訊：\n"
    if project_context.creation_type == 'idea' and project_context.idea_prompt:
        original_input_text += f"- PPT構想：{project_context.idea_prompt}\n"
    elif project_context.creation_type == 'outline' and project_context.outline_text:
        original_input_text += f"- 使用者提供的大綱文字：\n{project_context.outline_text}\n"
    elif project_context.creation_type == 'descriptions' and project_context.description_text:
        original_input_text += f"- 使用者提供的頁面描述文字：\n{project_context.description_text}\n"
    elif project_context.idea_prompt:
        original_input_text += f"- 使用者輸入：{project_context.idea_prompt}\n"
    
    # 構建大綱文字
    outline_text = ""
    if outline:
        outline_json = json.dumps(outline, ensure_ascii=False, indent=2)
        outline_text = f"\n\n完整的 PPT 大綱：\n{outline_json}\n"
    
    # 構建所有頁面描述的彙總
    all_descriptions_text = "當前所有頁面的描述：\n\n"
    has_any_description = False
    for desc in current_descriptions:
        page_num = desc.get('index', 0) + 1
        title = desc.get('title', '未命名')
        content = desc.get('description_content', '')
        if isinstance(content, dict):
            content = content.get('text', '')
        
        if content:
            has_any_description = True
            all_descriptions_text += f"--- 第 {page_num} 頁：{title} ---\n{content}\n\n"
        else:
            all_descriptions_text += f"--- 第 {page_num} 頁：{title} ---\n(當前沒有內容)\n\n"
    
    if not has_any_description:
        all_descriptions_text = "當前所有頁面的描述：\n\n(當前沒有內容，需要基於大綱生成新的描述)\n\n"
    
    prompt = (f"""\
You are a helpful assistant that modifies PPT page descriptions based on user requirements.
{original_input_text}{outline_text}
{all_descriptions_text}
{previous_req_text}
**使用者現在提出新的要求：{user_requirement}**

請根據使用者的要求修改和調整所有頁面的描述。你可以：
- 修改頁面標題和內容
- 調整頁面文字的詳細程度
- 新增或刪除要點
- 調整描述的結構和表達
- 確保所有頁面描述都符合使用者的要求
- 如果當前沒有內容，請根據大綱和使用者要求建立新的描述

請為每個頁面生成修改後的描述，格式如下：

頁面標題：[頁面標題]

頁面文字：
- [要點1]
- [要點2]
...
其他頁面素材（如果有請加上，包括markdown圖片連結等）

提示：如果參考檔案中包含以 /files/ 開頭的本地檔案URL圖片（例如 /files/mineru/xxx/image.png），請將這些圖片以markdown格式輸出，例如：![圖片描述](/files/mineru/xxx/image.png)，而不是作為普通文字。

請返回一個 JSON 陣列，每個元素是一個字串，對應每個頁面的修改後描述（按頁面順序）。

示例輸出格式：
[
    "頁面標題：人工智慧的誕生\\n頁面文字：\\n- 1950 年，圖靈提出\\"圖靈測試\\"...",
    "頁面標題：AI 的發展歷程\\n頁面文字：\\n- 1950年代：符號主義...",
    ...
]

現在請根據使用者要求修改所有頁面描述，只輸出 JSON 陣列，不要包含其他文字。
{get_language_instruction(language)}
""")
    
    final_prompt = files_xml + prompt
    logger.debug(f"[get_descriptions_refinement_prompt] Final prompt:\n{final_prompt}")
    return final_prompt


def get_clean_background_prompt() -> str:
    """
    生成純背景圖的 prompt（去除文字和插畫）
    用於從完整的PPT頁面中提取純背景
    """
    prompt = """\
你是一位專業的圖片文字&圖片擦除專家。你的任務是從原始圖片中移除文字和配圖，輸出一張無任何文字和圖表內容、乾淨純淨的底板圖。
<requirements>
- 徹底移除頁面中的所有文字、插畫、圖表。必須確保所有文字都被完全去除。
- 保持原背景設計的完整性（包括漸變、紋理、圖案、線條、色塊等）。保留原圖的文字框和色塊。
- 對於被前景元素遮擋的背景區域，要智慧填補，使背景保持無縫和完整，就像被移除的元素從來沒有出現過。
- 輸出圖片的尺寸、風格、配色必須和原圖完全一致。
- 請勿新增任何元素。
</requirements>

注意，**任意位置的, 所有的**文字和圖表都應該被徹底移除，**輸出不應該包含任何文字和圖表。**
"""
    logger.debug(f"[get_clean_background_prompt] Final prompt:\n{prompt}")
    return prompt


def get_text_attribute_extraction_prompt(content_hint: str = "") -> str:
    """
    生成文字屬性提取的 prompt
    
    提取文字內容、顏色、公式等資訊。模型輸出的文字將替代 OCR 結果。
    
    Args:
        content_hint: 文字內容提示（OCR 結果參考），如果提供則會在 prompt 中包含
    
    Returns:
        格式化後的 prompt 字串
    """
    prompt = """你的任務是精確識別這張圖片中的文字內容和樣式，返回JSON格式的結果。

{content_hint}

## 核心任務
請仔細觀察圖片，精確識別：
1. **文字內容** - 輸出你實際看到的文字元號。
2. **顏色** - 每個字/詞的實際顏色
3. **空格** - 精確識別文字中空格的位置和數量
4. **公式** - 如果是數學公式，輸出 LaTeX 格式

## 注意事項
- **空格識別**：必須精確還原空格數量，多個連續空格要完整保留，不要合併或省略
- **顏色分割**：一行文字可能有多種顏色，按顏色分割成片段，一般來說只有兩種顏色。
- **公式識別**：如果片段是數學公式，設定 is_latex=true 並用 LaTeX 格式輸出
- **相鄰合併**：相同顏色的相鄰普通文字應合併為一個片段

## 輸出格式
- colored_segments: 文字片段陣列，每個片段包含：
  - text: 文字內容（公式時為 LaTeX 格式，如 "x^2"、"\\sum_{{i=1}}^n"）
  - color: 顏色，十六進位制格式 "#RRGGBB"
  - is_latex: 布林值，true 表示這是一個 LaTeX 公式片段（可選，預設 false）

只返回JSON物件，不要包含任何其他文字。
示例輸出：
```json
{{
    "colored_segments": [
        {{"text": "·  創新合成", "color": "#000000"}},
        {{"text": "1827個任務環境", "color": "#26397A"}},
        {{"text": "與", "color": "#000000"}},
        {{"text": "8.5萬提示詞", "color": "#26397A"}},
        {{"text": "突破資料瓶頸", "color": "#000000"}},
        {{"text": "x^2 + y^2 = z^2", "color": "#FF0000", "is_latex": true}}
    ]
}}
```
""".format(content_hint=content_hint)
    
    # logger.debug(f"[get_text_attribute_extraction_prompt] Final prompt:\n{prompt}")
    return prompt


def get_batch_text_attribute_extraction_prompt(text_elements_json: str) -> str:
    """
    生成批次文字屬性提取的 prompt
    
    新邏輯：給模型提供全圖和所有文字元素的 bbox 及內容，
    讓模型一次性分析所有文字的樣式屬性。
    
    Args:
        text_elements_json: 文字元素列表的 JSON 字串，每個元素包含：
            - element_id: 元素唯一標識
            - bbox: 邊界框 [x0, y0, x1, y1]
            - content: 文字內容
    
    Returns:
        格式化後的 prompt 字串
    """
    prompt = f"""你是一位專業的 PPT/文件排版分析專家。請分析這張圖片中所有標註的文字區域的樣式屬性。

我已經從圖片中提取了以下文字元素及其位置資訊：

```json
{text_elements_json}
```

請仔細觀察圖片，對比每個文字區域在圖片中的實際視覺效果，為每個元素分析以下屬性：

1. **font_color**: 字型顏色的十六進位制值，格式為 "#RRGGBB"
   - 請仔細觀察文字的實際顏色，不要只返回黑色
   - 常見顏色如：白色 "#FFFFFF"、藍色 "#0066CC"、紅色 "#FF0000" 等

2. **is_bold**: 是否為粗體 (true/false)
   - 觀察筆畫粗細，標題通常是粗體

3. **is_italic**: 是否為斜體 (true/false)

4. **is_underline**: 是否有下劃線 (true/false)

5. **text_alignment**: 文字對齊方式
   - "left": 左對齊
   - "center": 居中對齊
   - "right": 右對齊
   - "justify": 兩端對齊
   - 如果無法判斷，根據文字在其區域內的位置推測

請返回一個 JSON 陣列，陣列中每個物件對應輸入的一個元素（按相同順序），包含以下欄位：
- element_id: 與輸入相同的元素ID
- text_content: 文字內容
- font_color: 顏色十六進位制值
- is_bold: 布林值
- is_italic: 布林值
- is_underline: 布林值
- text_alignment: 對齊方式字串

只返回 JSON 陣列，不要包含其他文字：
```json
[
    {{
        "element_id": "xxx",
        "text_content": "文字內容",
        "font_color": "#RRGGBB",
        "is_bold": true/false,
        "is_italic": true/false,
        "is_underline": true/false,
        "text_alignment": "對齊方式"
    }},
    ...
]
```
"""
    
    # logger.debug(f"[get_batch_text_attribute_extraction_prompt] Final prompt:\n{prompt}")
    return prompt


def get_quality_enhancement_prompt(inpainted_regions: list = None) -> str:
    """
    生成畫質提升的 prompt
    用於在百度影象修復後，使用生成式模型提升整體畫質
    
    Args:
        inpainted_regions: 被修復區域列表，每個區域包含百分比座標：
            - left, top, right, bottom: 相對於圖片寬高的百分比 (0-100)
            - width_percent, height_percent: 區域寬高佔圖片的百分比
    """
    import json
    
    # 構建區域資訊
    regions_info = ""
    if inpainted_regions and len(inpainted_regions) > 0:
        regions_json = json.dumps(inpainted_regions, ensure_ascii=False, indent=2)
        regions_info = f"""
以下是被抹除工具處理過的具體區域（共 {len(inpainted_regions)} 個矩形區域），請重點修復這些位置：

```json
{regions_json}
```

座標說明（所有數值都是相對於圖片寬高的百分比，範圍0-100%）：
- left: 區域左邊緣距離圖片左邊緣的百分比
- top: 區域上邊緣距離圖片上邊緣的百分比  
- right: 區域右邊緣距離圖片左邊緣的百分比
- bottom: 區域下邊緣距離圖片上邊緣的百分比
- width_percent: 區域寬度佔圖片寬度的百分比
- height_percent: 區域高度佔圖片高度的百分比

例如：left=10 表示區域從圖片左側10%的位置開始。
"""
    
    prompt = f"""\
你是一位專業的影象修復專家。這張ppt頁面圖片剛剛經過了文字/物件抹除操作，抹除工具在指定區域留下了一些修復痕跡，包括：
- 色塊不均勻、顏色不連貫
- 模糊的斑塊或塗抹痕跡
- 與周圍背景不協調的區域，比如不和諧的漸變色塊
- 可能的紋理斷裂或圖案不連續
{regions_info}
你的任務是修復這些抹除痕跡，讓圖片看起來像從未有過物件抹除操作一樣自然。

要求：
- **重點修復上述標註的區域**：這些區域剛剛經過抹除處理，需要讓它們與周圍背景完美融合
- 保持紋理、顏色、圖案的連續性
- 提升整體畫質，消除模糊、噪點、偽影
- 保持圖片的原始構圖、佈局、色調風格
- 禁止新增任何文字、圖表、插畫、圖案、邊框等元素
- 除了上述區域，其他區域不要做任何修改，保持和原影象素級別地一致。
- 輸出圖片的尺寸必須與原圖一致

請輸出修復後的高畫質ppt頁面背景圖片，不要遺漏修復任何一個被塗抹的區域。
"""
#     prompt = f"""
# 你是一位專業的影象修復專家。請你修復上傳的影象，去除其中的塗抹痕跡，消除所有的模糊、噪點、偽影，輸出處理後的高畫質影象，其他區域保持和原圖**完全相同**，顏色、佈局、線條、裝飾需要完全一致.
# {regions_info}
# """
    return prompt
