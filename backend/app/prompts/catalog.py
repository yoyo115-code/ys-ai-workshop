def resume_prompt(text: str) -> str:
    return (
        "请优化以下简历内容，突出量化成果、专业能力和岗位匹配度，"
        f"并给出结构清晰的中文版本：\n\n{text}"
    )


def copywrite_prompt(scene: str) -> str:
    return (
        "请根据以下场景描述生成高质量中文文案，保留事实，提升吸引力，"
        f"并直接给出成稿：\n\n{scene}"
    )


def translate_prompt(text: str) -> str:
    return (
        "请准确翻译以下内容。自动判断源语言：中文翻译为自然英文，"
        f"其他语言翻译为自然中文。只输出译文：\n\n{text}"
    )


def pdf_summary_prompt(text: str) -> str:
    return (
        "请总结以下 PDF 内容，输出核心结论、关键数据和行动建议，"
        f"使用清晰的小标题：\n\n{text}"
    )


def csv_analysis_prompt(row_count: int, sample: str) -> str:
    return (
        "请分析以下 CSV 数据样本。说明字段含义、数据规模、质量问题、"
        f"明显趋势和建议的后续分析：\n\n总行数：{row_count}\n样本：\n{sample}"
    )
