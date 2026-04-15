# -*- coding: utf-8 -*-
"""
文本处理工具

复用 BettaFish InsightEngine 的文本清理和 JSON 解析逻辑。
"""

import re
import json
from typing import Dict, Any


def clean_json_tags(text: str) -> str:
    """清理文本中的 JSON/Markdown 代码块标签"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = re.sub(r'```', '', text)
    return text.strip()


def remove_reasoning_from_output(text: str) -> str:
    """移除输出中的推理过程文本，保留 JSON"""
    for i, char in enumerate(text):
        if char in '{[':
            return text[i:].strip()
    return text.strip()


def fix_incomplete_json(text: str) -> str:
    """修复不完整的 JSON 响应"""
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')

    if open_braces > close_braces:
        text += '}' * (open_braces - close_braces)
    if open_brackets > close_brackets:
        text += ']' * (open_brackets - close_brackets)

    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        return ""


def extract_clean_response(text: str) -> Dict[str, Any]:
    """提取并清理响应中的 JSON 内容，多策略容错"""
    cleaned_text = clean_json_tags(text)
    cleaned_text = remove_reasoning_from_output(cleaned_text)

    # 策略1: 直接解析
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        pass

    # 策略2: 修复不完整 JSON
    fixed_text = fix_incomplete_json(cleaned_text)
    if fixed_text:
        try:
            return json.loads(fixed_text)
        except json.JSONDecodeError:
            pass

    # 策略3: 正则查找 JSON 对象
    match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # 策略4: 正则查找 JSON 数组
    match = re.search(r'\[.*\]', cleaned_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {"error": "JSON解析失败", "raw_text": cleaned_text[:500]}
