"""
LaTeX 工具模組 - 處理 LaTeX 公式轉換

提供以下功能：
1. 簡單 LaTeX 轉文字（跳脫字元、簡單符號）
2. LaTeX 轉 MathML
3. MathML 轉 OMML（用於 PPTX）
"""
import re
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# LaTeX 跳脫字元對映
LATEX_ESCAPES = {
    r'\%': '%',
    r'\$': '$',
    r'\&': '&',
    r'\#': '#',
    r'\_': '_',
    r'\{': '{',
    r'\}': '}',
    r'\ ': ' ',
    r'\,': ' ',  # thin space
    r'\;': ' ',  # thick space
    r'\!': '',   # negative thin space
    r'\quad': '  ',
    r'\qquad': '    ',
}

# 常用 LaTeX 符號到 Unicode 對映
LATEX_SYMBOLS = {
    # 希臘字母
    r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
    r'\epsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η', r'\theta': 'θ',
    r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ', r'\mu': 'μ',
    r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π', r'\rho': 'ρ',
    r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ', r'\phi': 'φ',
    r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
    r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
    r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Phi': 'Φ',
    r'\Psi': 'Ψ', r'\Omega': 'Ω',
    # 數學運算子
    r'\times': '×', r'\div': '÷', r'\pm': '±', r'\mp': '∓',
    r'\cdot': '·', r'\ast': '∗', r'\star': '☆',
    r'\leq': '≤', r'\geq': '≥', r'\neq': '≠', r'\approx': '≈',
    r'\equiv': '≡', r'\sim': '∼', r'\propto': '∝',
    r'\infty': '∞', r'\partial': '∂', r'\nabla': '∇',
    r'\sum': '∑', r'\prod': '∏', r'\int': '∫',
    r'\sqrt': '√', r'\angle': '∠', r'\degree': '°',
    # 箭頭
    r'\leftarrow': '←', r'\rightarrow': '→', r'\leftrightarrow': '↔',
    r'\Leftarrow': '⇐', r'\Rightarrow': '⇒', r'\Leftrightarrow': '⇔',
    # 其他
    r'\ldots': '…', r'\cdots': '⋯', r'\vdots': '⋮',
    r'\forall': '∀', r'\exists': '∃', r'\in': '∈', r'\notin': '∉',
    r'\subset': '⊂', r'\supset': '⊃', r'\cup': '∪', r'\cap': '∩',
}

# 上標數字對映
SUPERSCRIPT_MAP = {
    '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴',
    '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹',
    '+': '⁺', '-': '⁻', '=': '⁼', '(': '⁽', ')': '⁾',
    'n': 'ⁿ', 'i': 'ⁱ',
}

# 下標數字對映
SUBSCRIPT_MAP = {
    '0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄',
    '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉',
    '+': '₊', '-': '₋', '=': '₌', '(': '₍', ')': '₎',
    'a': 'ₐ', 'e': 'ₑ', 'o': 'ₒ', 'x': 'ₓ',
    'i': 'ᵢ', 'j': 'ⱼ', 'n': 'ₙ', 'm': 'ₘ',
}


def is_simple_latex(latex: str) -> bool:
    """
    判斷是否是簡單的 LaTeX（可以直接轉換為文字）
    
    簡單 LaTeX 包括：
    - 純跳脫字元（如 10\%）
    - 簡單符號（如 \alpha）
    - 簡單上下標（如 x^2, x_1）
    """
    # 移除所有已知的簡單模式
    test = latex
    
    # 移除跳脫字元
    for escape in LATEX_ESCAPES:
        test = test.replace(escape, '')
    
    # 移除符號
    for symbol in LATEX_SYMBOLS:
        test = test.replace(symbol, '')
    
    # 移除簡單上下標 ^{...} 或 ^x
    test = re.sub(r'\^{[^{}]*}', '', test)
    test = re.sub(r'\^[0-9a-zA-Z]', '', test)
    
    # 移除簡單下標 _{...} 或 _x
    test = re.sub(r'_{[^{}]*}', '', test)
    test = re.sub(r'_[0-9a-zA-Z]', '', test)
    
    # 如果剩餘的都是普通字元，則是簡單 LaTeX
    remaining = test.strip()
    # 檢查是否還有未處理的 LaTeX 命令
    if '\\' in remaining and not remaining.replace('\\', '').isalnum():
        return False
    
    return True


def latex_to_text(latex: str) -> str:
    """
    將簡單 LaTeX 轉換為 Unicode 文字
    
    Args:
        latex: LaTeX 字串
    
    Returns:
        轉換後的文字
    """
    result = latex
    
    # 1. 處理跳脫字元
    for escape, char in LATEX_ESCAPES.items():
        result = result.replace(escape, char)
    
    # 2. 處理符號
    for symbol, char in LATEX_SYMBOLS.items():
        result = result.replace(symbol, char)
    
    # 3. 處理上標 ^{...} 或 ^x
    def convert_superscript(match):
        content = match.group(1) if match.group(1) else match.group(2)
        return ''.join(SUPERSCRIPT_MAP.get(c, c) for c in content)
    
    result = re.sub(r'\^{([^{}]*)}|\^([0-9a-zA-Z])', convert_superscript, result)
    
    # 4. 處理下標 _{...} 或 _x
    def convert_subscript(match):
        content = match.group(1) if match.group(1) else match.group(2)
        return ''.join(SUBSCRIPT_MAP.get(c, c) for c in content)
    
    result = re.sub(r'_{([^{}]*)}|_([0-9a-zA-Z])', convert_subscript, result)
    
    # 5. 移除剩餘的 LaTeX 命令（如 \text{}, \mathrm{} 等）
    result = re.sub(r'\\(?:text|mathrm|mathbf|mathit|mathbb|mathcal){([^{}]*)}', r'\1', result)
    
    # 6. 清理多餘的空格和花括號
    result = result.replace('{', '').replace('}', '')
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result


def latex_to_mathml(latex: str) -> Optional[str]:
    """
    將 LaTeX 轉換為 MathML
    
    Args:
        latex: LaTeX 字串
    
    Returns:
        MathML 字串，失敗返回 None
    """
    try:
        import latex2mathml.converter
        mathml = latex2mathml.converter.convert(latex)
        return mathml
    except Exception as e:
        logger.warning(f"LaTeX to MathML conversion failed: {e}")
        return None


def mathml_to_omml(mathml: str) -> Optional[str]:
    """
    將 MathML 轉換為 OMML (Office Math Markup Language)
    
    使用 Microsoft 的 MML2OMML.xsl 樣式表進行轉換
    
    Args:
        mathml: MathML 字串
    
    Returns:
        OMML 字串，失敗返回 None
    """
    try:
        from lxml import etree
        import os
        
        # MML2OMML.xsl 樣式表路徑
        xsl_path = os.path.join(os.path.dirname(__file__), 'MML2OMML.xsl')
        
        if not os.path.exists(xsl_path):
            logger.warning(f"MML2OMML.xsl not found at {xsl_path}")
            return None
        
        # 解析 MathML
        mathml_tree = etree.fromstring(mathml.encode('utf-8'))
        
        # 載入 XSLT
        xslt_tree = etree.parse(xsl_path)
        transform = etree.XSLT(xslt_tree)
        
        # 轉換
        omml_tree = transform(mathml_tree)
        return etree.tostring(omml_tree, encoding='unicode')
    
    except ImportError:
        logger.warning("lxml not installed, cannot convert to OMML")
        return None
    except Exception as e:
        logger.warning(f"MathML to OMML conversion failed: {e}")
        return None


def convert_latex_for_pptx(latex: str) -> Tuple[str, Optional[str]]:
    """
    為 PPTX 轉換 LaTeX 公式
    
    Args:
        latex: LaTeX 字串
    
    Returns:
        (text_fallback, omml) 元組
        - text_fallback: 文字回退方案（總是有值）
        - omml: OMML 字串（如果轉換成功）
    """
    # 總是生成文字回退
    text_fallback = latex_to_text(latex)
    
    # 對於簡單 LaTeX，不需要 OMML
    if is_simple_latex(latex):
        return text_fallback, None
    
    # 嘗試生成 OMML
    mathml = latex_to_mathml(latex)
    if mathml:
        omml = mathml_to_omml(mathml)
        if omml:
            return text_fallback, omml
    
    return text_fallback, None

