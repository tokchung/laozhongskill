# -*- coding: utf-8 -*-
"""
转写稿归档核对 —— 桌面源 docx ↔ Claude\\_历史咨询转写稿\\*.txt 是否逐字一致。

用途：每场咨询归档转写稿后跑一遍，回答「到底漏没漏」这个问题。
      不再靠看字数、看内容特征去猜——逐字比对，差异点连上下文一起打出来。

用法：
    py verify_transcripts.py
    py verify_transcripts.py --src "D:\\某目录" --dst "C:\\某目录"
    py verify_transcripts.py --report "C:\\temp\\report.txt"

退出码：0 = 全部一致；1 = 有差异或有未配对（便于接进别的流程做闸门）
"""

import argparse
import difflib
import io
import os
import re
import sys
import tempfile
import unicodedata

try:  # Windows 控制台默认 GBK，中文会报错，强制走 UTF-8
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DEFAULT_SRC = os.path.join(os.path.expanduser("~"), "Desktop", "咨询和会议记录")
DEFAULT_DST = os.path.join(os.path.expanduser("~"), "Claude", "_历史咨询转写稿")

# 源目录里非咨询的文档，不参与配对（约定：不提取归档，留在原处）
NON_CONSULT = ("8.12会议记录", "张冉老师")


def docx_text(path):
    """提取 docx 全文（段落 + 表格），一行一段。"""
    from docx import Document

    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for row in t.rows:
            for cell in row.cells:
                parts.append(cell.text)
    return parts


def norm(s):
    """归一化：全角转半角 + 去掉所有空白。只比内容，不比排版。"""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", s))


def pair_up(src_files, dst_files):
    """按「日期 + 名字」配对。返回 (pairs, unmatched)。"""
    pairs, unmatched = [], []
    for dx in src_files:
        dates = re.findall(r"(\d{1,2}\.\d{1,2})", dx)
        stem = re.sub(r"咨询记录|（双音）|\(双音\)|\.docx", "", dx)
        hit = None
        for tx in dst_files:
            m = re.match(r"(\d{1,2}\.\d{1,2})_(.+)\.txt$", tx)
            if m and m.group(1) in dates and m.group(2) in stem:
                hit = tx
                break
        (pairs.append((dx, hit)) if hit else unmatched.append(dx))
    return pairs, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC, help="源 docx 目录")
    ap.add_argument("--dst", default=DEFAULT_DST, help="归档 txt 目录")
    ap.add_argument("--report", default=None, help="报告输出路径（默认写到临时目录）")
    args = ap.parse_args()

    docxs = sorted(f for f in os.listdir(args.src)
                   if f.endswith(".docx") and not any(k in f for k in NON_CONSULT))
    txts = sorted(f for f in os.listdir(args.dst) if f.endswith(".txt"))

    pairs, unmatched = pair_up(docxs, txts)
    matched_txt = {t for _, t in pairs}
    orphan_txt = [t for t in txts if t not in matched_txt]

    out = [f"源 docx（咨询类）= {len(docxs)}   归档 txt = {len(txts)}   配对 = {len(pairs)}", ""]
    if unmatched:
        out.append("✗ 无对应 txt 的 docx：" + "、".join(unmatched))
    if orphan_txt:
        out.append("✗ 无对应 docx 的 txt：" + "、".join(orphan_txt))
    if unmatched or orphan_txt:
        out.append("")

    out.append(f"{'docx':<32}{'txt':<18}{'docx字':>8}{'txt字':>8}{'差':>6}  判定")
    out.append("-" * 84)

    bad = []
    for dx, tx in pairs:
        try:
            a = norm("\n".join(docx_text(os.path.join(args.src, dx))))
            b = norm(io.open(os.path.join(args.dst, tx), encoding="utf-8").read())
        except Exception as e:  # 文件读不了也要报出来，不能让整轮核对挂掉
            bad.append((dx, tx, "", "", 0))
            out.append(f"{dx:<32}{tx:<18}{'—':>8}{'—':>8}{'—':>6}  读取失败：{type(e).__name__}: {e}")
            continue
        diff = len(a) - len(b)
        if a == b:
            out.append(f"{dx:<32}{tx:<18}{len(a):>8}{len(b):>8}{0:>+6}  一致")
            continue
        bad.append((dx, tx, a, b, diff))
        out.append(f"{dx:<32}{tx:<18}{len(a):>8}{len(b):>8}{diff:>+7}  不一致")

    out.append("")
    out.append(f"==> 逐字一致 {len(pairs) - len(bad)} / {len(pairs)} 对，不一致 {len(bad)} 对")

    for dx, tx, a, b, diff in bad:  # 差异点连上下文一起打出来，方便直接定位补
        out.append("")
        out.append(f"### {dx}  ↔  {tx}   （差 {diff:+d} 字）")
        for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if tag == "equal":
                continue
            out.append(f"  [{tag}] 源多出/不同：{a[i1:i2]!r}   txt：{b[j1:j2]!r}")
            out.append(f"      源上下文：…{a[max(0, i1 - 30):i2 + 30]}…")

    report = "\n".join(out)
    path = args.report or os.path.join(tempfile.gettempdir(), "转写稿核对报告.txt")
    io.open(path, "w", encoding="utf-8").write(report)

    # 控制台只打安全前缀 + 结论，正文细节看报告文件
    print(f"[verify] pairs={len(pairs)} bad={len(bad)} unmatched={len(unmatched)} orphan_txt={len(orphan_txt)}")
    print("[verify] report -> " + path)
    return 1 if (bad or unmatched or orphan_txt) else 0


if __name__ == "__main__":
    sys.exit(main())
