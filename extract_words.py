import json, re, sys, os
from html.parser import HTMLParser

POS_LIST = ['n.', 'vt.', 'vi.', 'adj.', 'adv.', 'conj.', 'prep.', 'int.', 'pron.', 'art.', 'aux.', 'v.']
POS_RE = '(' + '|'.join(re.escape(p) for p in POS_LIST) + ')'


def parse_meaning(raw):
    """拆分释义: 'n.规模；等级vt.攀登' -> [{pos:'n.', meanings:['规模','等级']}, {pos:'vt.', meanings:['攀登']}]"""
    if not raw:
        return []
    segments = []
    last_end = 0
    for m in re.finditer(POS_RE, raw):
        if m.start() > last_end:
            text = raw[last_end:m.start()].strip().rstrip('；;。，,')
            if text:
                segments.append(("text", text))
        segments.append(("pos", m.group(0)))
        last_end = m.end()
    if last_end < len(raw):
        text = raw[last_end:].strip().rstrip('；;。，,')
        if text:
            segments.append(("text", text))

    result = []
    i = 0
    while i < len(segments):
        if segments[i][0] == "pos":
            pos_parts = [segments[i][1]]
            i += 1
            while i < len(segments) and segments[i][0] == "pos":
                pos_parts.append(segments[i][1])
                i += 1
            meanings_text = ""
            while i < len(segments) and segments[i][0] == "text":
                meanings_text += segments[i][1] + "；"
                i += 1
            meanings_text = meanings_text.rstrip('；;')
            meanings = [m.strip() for m in re.split(r'[；;]', meanings_text) if m.strip()]
            result.append({"pos": ''.join(pos_parts), "meanings": meanings})
        else:
            i += 1
    return result


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row = []
        self._cell = ""
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag in ("td", "th"):
            self._in_cell = True
            self._cell = ""

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self._in_cell = False
            self._row.append(self._cell.strip())
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = []

    def handle_data(self, data):
        if self._in_cell:
            self._cell += data


def is_english_word(s):
    return bool(re.match(r'^[a-zA-Z\-]+$', s)) and len(s) > 1


def has_chinese(s):
    return bool(re.search(r'[一-鿿]', s))


def extract_row(row):
    """从一行中提取英文单词和中文释义（按内容判定，适配7/8列）"""
    english = None
    chinese = None
    for cell in row:
        if not cell or cell == '☐':
            continue
        if is_english_word(cell):
            english = cell
        elif has_chinese(cell) or re.match(r'^[nvadcjipr]+\.', cell):
            chinese = cell
    return english, chinese


def extract_page(filepath):
    """从单页 OCR 结果 JSON 中提取单词列表"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("errorCode") != 0:
        return []

    try:
        md_text = data["result"]["layoutParsingResults"][0]["markdown"]["text"]
    except (KeyError, IndexError, TypeError):
        return []

    table_match = re.search(r'<table.*?</table>', md_text, re.DOTALL)
    if not table_match:
        return []

    tp = TableParser()
    tp.feed(table_match.group(0))

    words = []
    for row in tp.rows:
        eng, chn = extract_row(row)
        if eng and chn:
            words.append({
                "english": eng,
                "meanings": parse_meaning(chn)
            })
    return words


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else "ocr_results"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "红宝书词汇.json"

    files = sorted(
        f for f in os.listdir(src_dir) if f.endswith(".json")
    )
    print(f"找到 {len(files)} 个文件")

    all_words = []
    empty_pages = []

    for fname in files:
        page_num = int(re.search(r'(\d+)', fname).group(1))
        words = extract_page(os.path.join(src_dir, fname))
        for w in words:
            w["page"] = page_num
        all_words.extend(words)
        if not words:
            empty_pages.append(page_num)

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_words, f, ensure_ascii=False, indent=2)

    print(f"提取完成: {len(all_words)} 个单词 -> {out_file}")
    if empty_pages:
        print(f"空页 ({len(empty_pages)}): {empty_pages[:30]}{'...' if len(empty_pages) > 30 else ''}")


if __name__ == "__main__":
    main()
