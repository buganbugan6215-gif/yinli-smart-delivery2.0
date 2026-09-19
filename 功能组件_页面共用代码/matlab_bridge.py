from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
from typing import Tuple


ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT.parent / "matlab求解第一问"
MATLAB_EXE = Path(os.getenv("YL_MATLAB_EXE", "matlab"))


def run_noodle_model() -> Tuple[bool, str]:
    """运行团队已核验的第一问 MATLAB 程序，不替换为页面内快速初算。"""
    script = MODEL_DIR / "solve_first_question_noodle.m"
    matlab_command = str(MATLAB_EXE) if MATLAB_EXE.is_file() else shutil.which(str(MATLAB_EXE))
    if not matlab_command:
        return False, "未找到本机 MATLAB，无法运行正式模型。"
    if not script.is_file():
        return False, "未找到正式鲜面条 MATLAB 求解程序。"
    command = f"cd('{str(MODEL_DIR).replace(chr(92), '/') }'); solve_first_question_noodle"
    try:
        result = subprocess.run([matlab_command, "-batch", command], cwd=MODEL_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        return False, "MATLAB 求解超过 15 分钟仍未结束，请在本机 MATLAB 中继续查看。"
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()[-700:]
        return False, f"MATLAB 求解失败：{detail}"
    output = MODEL_DIR / "第一问_鲜面条配送优化结果.xlsx"
    if not output.is_file():
        return False, "MATLAB 已结束，但未找到预期的结果工作簿。"
    return True, f"正式 MATLAB 模型已完成，结果保存在：{output}"
