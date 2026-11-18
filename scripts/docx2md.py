#!/usr/bin/env python3
"""将 .docx 转成 Markdown（标题 / 列表 / 表格 / 粗斜体 / 图片），仅依赖标准库。

用法:
    python3 scripts/docx2md.py <input.docx> [-o docs/output.md] [--images-dir docs/images]
"""
import argparse
import html
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "v": "urn:schemas-microsoft-com:vml",
}
W = "{%s}" % NS["w"]
R = "{%s}" % NS["r"]


def q(tag):
    prefix, name = tag.split(":")
    return "{%s}%s" % (NS[prefix], name)


class CodeLine(str):
    pass


class Plain(str):
    raw = ""


SEED_CODE = re.compile(
    r"(npm|npx|pnpm|yarn) \S|[├└│]|<[A-Za-z/!]|import (.+ from |['\"])|export default|VITE_\w+=|"
    r"- (name|uses|run):|[A-Za-z][\w-]*:$|(name|on|jobs|runs-on|steps|uses|with|folder|branch|run|push|branches):( |$)"
)


def looks_like_code(plain):
    raw = plain.raw
    if not raw.strip():
        return False
    if re.match(r"\s*(//|/\*|\*/|#\s|[├└│]|src/$)", raw):
        return True
    if SEED_CODE.match(raw.lstrip()):
        return True
    head = code_head(raw)
    if re.search(r"[，。：；！？、（）]", head):
        return False
    if re.fullmatch(r"\s*[\w$.]+,?\s*", head) and all(ord(c) < 128 for c in head):
        return True
    if re.match(r"\s*(return|else|break|continue)\b", head):
        return True
    if re.match(r"\s*['\"]?[\w$.-]+['\"]?:\s*\S", head) and all(ord(c) < 128 for c in head):
        return True
    return bool(re.search(r"[<>{}()=;\[\]]", head)) or bool(re.search(r",$", head.rstrip()))


def code_head(raw):
    return re.split(r"\s+(?://|#)\s", raw)[0]


def sandwiched_text(plain):
    """两侧都是代码时，不含全角标点的短文本行（如模板里的文案）也算代码。"""
    return bool(plain.raw.strip()) and not re.search(r"[，。：；！？、（）]", code_head(plain.raw))


def guess_lang(code):
    lines = [l for l in code.split("\n") if l.strip() and not l.startswith("# ")]
    first = lines[0].lstrip() if lines else ""
    if re.match(r"(npm|npx|cd|pnpm|yarn)\b", first):
        return "bash"
    if re.match(r"VITE_\w+=", first):
        return "ini"
    if re.match(r"(name|on|jobs):", first):
        return "yaml"
    if re.match(r"</?(template|script|style|div|header|li|ul|main)\b", first):
        return "vue"
    if re.match(r"(import|export|const|let|function|//|/\*|defineProps|plugins:|build:|router\.)", first):
        return "js"
    return ""


class Docx:
    def __init__(self, path, images_dir, image_ref):
        self.zip = zipfile.ZipFile(path)
        self.images_dir = images_dir
        self.image_ref = image_ref
        self.rels = self._load_rels()
        self.styles = self._load_styles()
        self.numbering = self._load_numbering()
        self.image_count = 0
        self.counters = {}
        self.image_cache = {}

    def _xml(self, name):
        return ET.fromstring(self.zip.read(name))

    def _load_rels(self):
        root = self._xml("word/_rels/document.xml.rels")
        return {r.get("Id"): r.get("Target") for r in root}

    def _load_styles(self):
        """styleId -> (name, basedOn)"""
        styles = {}
        if "word/styles.xml" not in self.zip.namelist():
            return styles
        for s in self._xml("word/styles.xml").findall(q("w:style")):
            name = s.find(q("w:name"))
            based = s.find(q("w:basedOn"))
            styles[s.get(W + "styleId")] = (
                name.get(W + "val") if name is not None else "",
                based.get(W + "val") if based is not None else None,
            )
        return styles

    def _load_numbering(self):
        """(numId, ilvl) -> numFmt ('bullet' / 'decimal' / ...)"""
        if "word/numbering.xml" not in self.zip.namelist():
            return {}
        root = self._xml("word/numbering.xml")
        abstract = {}
        for an in root.findall(q("w:abstractNum")):
            lvls = {}
            for lvl in an.findall(q("w:lvl")):
                fmt = lvl.find(q("w:numFmt"))
                lvls[int(lvl.get(W + "ilvl"))] = fmt.get(W + "val") if fmt is not None else "bullet"
            abstract[an.get(W + "abstractNumId")] = lvls
        result = {}
        for num in root.findall(q("w:num")):
            aid = num.find(q("w:abstractNumId")).get(W + "val")
            for ilvl, fmt in abstract.get(aid, {}).items():
                result[(num.get(W + "numId"), ilvl)] = fmt
        return result

    def heading_level(self, style_id):
        seen = set()
        while style_id and style_id not in seen:
            seen.add(style_id)
            name, based = self.styles.get(style_id, ("", None))
            m = re.fullmatch(r"(?i)heading\s*(\d)", name.strip())
            if m:
                return int(m.group(1))
            if name.strip().lower() == "title":
                return 1
            style_id = based
        return 0

    def save_image(self, rid):
        if rid not in self.image_cache:
            self.image_cache[rid] = self._save_image(rid)
        return self.image_cache[rid]

    def _save_image(self, rid):
        target = self.rels.get(rid)
        if not target:
            return ""
        src = "word/" + target.lstrip("/").removeprefix("word/")
        if src not in self.zip.namelist():
            return ""
        self.image_count += 1
        ext = Path(src).suffix
        name = "image%d%s" % (self.image_count, ext)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        (self.images_dir / name).write_bytes(self.zip.read(src))
        return "![%s](%s/%s)" % (name, self.image_ref, name)

    def run_text(self, run):
        out = []
        for el in run:
            if el.tag == q("w:t"):
                out.append(el.text or "")
            elif el.tag == q("w:tab"):
                out.append("\t")
            elif el.tag in (q("w:br"), q("w:cr")):
                out.append("  \n" if el.get(W + "type") != "page" else "")
            elif el.tag == q("w:drawing"):
                for blip in el.iter(q("a:blip")):
                    out.append(self.save_image(blip.get(R + "embed")))
            elif el.tag == q("w:pict"):
                for im in el.iter(q("v:imagedata")):
                    out.append(self.save_image(im.get(R + "id")))
        return "".join(out)

    @staticmethod
    def is_code_run(run):
        rpr = run.find(q("w:rPr"))
        if rpr is None:
            return False
        color = rpr.find(q("w:color"))
        if color is not None and color.get(W + "val", "").upper() == "FF0000":
            return True
        fonts = rpr.find(q("w:rFonts"))
        return fonts is not None and fonts.get(W + "ascii") == "Consolas"

    def runs(self, p):
        return [n for n in p.iter() if n.tag == q("w:r")]

    def raw_line(self, p):
        line = "".join(self.run_text(r) for r in self.runs(p)).replace("\u00a0", " ").rstrip()
        return re.sub(r"&#x?[0-9a-fA-F]+;", lambda m: html.unescape(m.group(0)), line)

    def code_line(self, p):
        """首个非空 run 是代码样式则整段视为代码，返回保留缩进的原文。"""
        line = self.raw_line(p)
        if not line.strip() or "![" in line:
            return None
        for run in self.runs(p):
            if self.run_text(run).strip():
                return line if self.is_code_run(run) else None
        return None

    def paragraph_inline(self, p):
        parts = []
        for node in self.runs(p):
            text = self.run_text(node)
            if not text:
                continue
            rpr = node.find(q("w:rPr"))
            bold = italic = False
            if rpr is not None:
                b, i = rpr.find(q("w:b")), rpr.find(q("w:i"))
                bold = b is not None and b.get(W + "val") not in ("0", "false")
                italic = i is not None and i.get(W + "val") not in ("0", "false")
            code = self.is_code_run(node)
            if text.strip() and not text.startswith("!["):
                lead = text[: len(text) - len(text.lstrip())]
                trail = text[len(text.rstrip()):]
                core = text.strip()
                if code:
                    core = "`%s`" % core
                elif bold:
                    core = "**%s**" % core
                if italic and not code:
                    core = "*%s*" % core
                text = lead + core + trail
            parts.append(text)
        merged = "".join(parts)
        merged = re.sub(r"`(\s*)`", r"\1", merged)
        return re.sub(r"\*\*\*\*|(?<=\*\*) (?=\*\*)", "", merged).strip().replace("\u00a0", " ")

    def paragraph(self, p):
        text = self.paragraph_inline(p)
        ppr = p.find(q("w:pPr"))
        style_id, num = None, None
        if ppr is not None:
            ps = ppr.find(q("w:pStyle"))
            style_id = ps.get(W + "val") if ps is not None else None
            num = ppr.find(q("w:numPr"))
        if not text:
            return None
        level = self.heading_level(style_id)
        if level:
            return "#" * min(level, 6) + " " + text
        in_list = False
        if num is not None:
            nid = num.find(q("w:numId"))
            in_list = nid is not None and nid.get(W + "val") != "0"
        if not in_list:
            line = self.code_line(p)
            if line is not None:
                return CodeLine(line)
            plain = Plain(text)
            plain.raw = self.raw_line(p)
            return plain
        if num is not None:
            nid = num.find(q("w:numId"))
            lvl = num.find(q("w:ilvl"))
            nid = nid.get(W + "val") if nid is not None else "0"
            ilvl = int(lvl.get(W + "val")) if lvl is not None else 0
            if nid != "0":
                fmt = self.numbering.get((nid, ilvl), "bullet")
                indent = "  " * ilvl
                if fmt == "bullet":
                    return "%s- %s" % (indent, text)
                key = (nid, ilvl)
                self.counters[key] = self.counters.get(key, 0) + 1
                for k in [k for k in self.counters if k[0] == nid and k[1] > ilvl]:
                    del self.counters[k]
                return "%s%d. %s" % (indent, self.counters[key], text)
        return text

    def table(self, tbl):
        rows = []
        for tr in tbl.findall(q("w:tr")):
            cells = []
            for tc in tr.findall(q("w:tc")):
                texts = [self.paragraph_inline(p) for p in tc.iter(q("w:p"))]
                cells.append("<br>".join(t for t in texts if t).replace("|", "\\|"))
            rows.append(cells)
        if not rows:
            return None
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return "\n".join(lines)

    def convert(self):
        body = self._xml("word/document.xml").find(q("w:body"))
        items = []
        for el in body:
            if el.tag == q("w:p"):
                md = self.paragraph(el)
            elif el.tag == q("w:tbl"):
                md = self.table(el)
            else:
                continue
            if md is not None:
                items.append(md)

        changed = True
        while changed:
            changed = False
            for i, it in enumerate(items):
                if not isinstance(it, Plain):
                    continue
                near = [items[j] for j in (i - 1, i + 1) if 0 <= j < len(items)]
                if len(near) == 2 and all(isinstance(n, CodeLine) for n in near) and sandwiched_text(it):
                    items[i] = CodeLine(it.raw)
                    changed = True
                    continue
                if not looks_like_code(it):
                    continue
                if SEED_CODE.match(it.raw.lstrip()):
                    items[i] = CodeLine(it.raw)
                    changed = True
                    continue
                if any(isinstance(n, CodeLine) for n in near):
                    items[i] = CodeLine(it.raw)
                    changed = True

        blocks, prev_kind = [], None
        for md in items:
            if isinstance(md, CodeLine):
                kind = "code"
            elif re.match(r"\s*(- |\d+\. )", md):
                kind = "list"
            else:
                kind = "text"
            if kind == "code" and prev_kind == "code":
                blocks[-1].append(str(md))
            elif kind == "code":
                blocks.append([str(md)])
            elif kind == "list" and prev_kind == "list":
                blocks[-1] += "\n" + md
            else:
                blocks.append(str(md))
            prev_kind = kind
        out = []
        for b in blocks:
            if isinstance(b, list):
                code = "\n".join(b)
                out.append("```%s\n%s\n```" % (guess_lang(code), code))
            else:
                out.append(b)
        return "\n\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="docx -> markdown (含图片提取)")
    ap.add_argument("input", type=Path)
    ap.add_argument("-o", "--output", type=Path, help="输出 md 路径，默认与输入同名")
    ap.add_argument("--images-dir", type=Path, help="图片输出目录，默认 <output 同级>/images")
    args = ap.parse_args()

    if not args.input.is_file():
        sys.exit("找不到文件: %s" % args.input)
    out = args.output or args.input.with_suffix(".md")
    images_dir = args.images_dir or out.parent / "images"
    out.parent.mkdir(parents=True, exist_ok=True)
    if images_dir.exists():
        shutil.rmtree(images_dir)
    try:
        rel = images_dir.resolve().relative_to(out.parent.resolve()).as_posix()
    except ValueError:
        rel = images_dir.resolve().as_posix()

    doc = Docx(args.input, images_dir, rel)
    out.write_text(doc.convert(), encoding="utf-8")
    print("已生成 %s（图片 %d 张 -> %s）" % (out, doc.image_count, images_dir))


if __name__ == "__main__":
    main()
