"""Read selectable-text PDFs and map source units to exact original-page rectangles."""
import hashlib
import unicodedata
from pathlib import Path


def pdf_module():
    try:
        import pymupdf
        return pymupdf
    except ImportError as exc:
        raise ValueError('PDF 支持需要 PyMuPDF。请运行 python -m pip install -r requirements.txt') from exc


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if not c.isspace())


def read_pdf(path, image_dir=None):
    fitz = pdf_module()
    path = Path(path)
    if path.suffix.lower() != '.pdf':
        raise ValueError('原件对照首版只支持可选中文字的 PDF。请先将 Word 另存为 PDF。')
    try:
        doc = fitz.open(str(path))
    except Exception as exc:
        raise ValueError('无法打开 PDF，请检查文件是否完整：' + str(exc)) from exc
    try:
        if doc.needs_pass:
            raise ValueError('请先提供已解除密码保护的 PDF。')
        pages, characters, text = [], [], []
        if image_dir:
            Path(image_dir).mkdir(parents=True, exist_ok=True)
        for index, page in enumerate(doc):
            page_chars = 0
            for block in page.get_text('rawdict', sort=True)['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        for char in span['chars']:
                            rect = fitz.Rect(char['bbox']) * page.rotation_matrix
                            position = {'page': index + 1, 'rect': [
                                rect.x0 / page.rect.width, rect.y0 / page.rect.height,
                                rect.x1 / page.rect.width, rect.y1 / page.rect.height]}
                            for c in char['c']:
                                text.append(c)
                                characters.append(position)
                                if not c.isspace(): page_chars += 1
                    text.append('\n'); characters.append(None)
            if page_chars < 4 and page.get_images():
                raise ValueError(f'第 {index + 1} 页缺少可提取文字，可能是扫描件。首版请使用文字版 PDF。')
            entry = {'number': index + 1, 'width': page.rect.width, 'height': page.rect.height}
            if image_dir:
                name = f'page-{index + 1}.png'
                page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False).save(str(Path(image_dir) / name))
                entry['image'] = 'pages/' + name
            pages.append(entry)
        content = ''.join(text)
        if len(normalized(content)) < 12:
            raise ValueError('PDF 缺少足够的可提取文字。首版不支持扫描件或图片式 PDF。')
        return {'text': content, 'characters': characters, 'pages': pages,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    finally:
        doc.close()


def locate_units(document, units):
    stream, positions = [], []
    for c, position in zip(document['text'], document['characters']):
        for n in normalized(c):
            stream.append(n); positions.append(position)
    stream = ''.join(stream)
    # If the ledger is a lossless extraction, offsets disambiguate repeated sentences.
    mappings = {}
    for unit in units:
        needle = normalized(unit['text'])
        expected = len(normalized(document['text'][:unit['start']]))
        exact_offset = document['text'][unit['start']:unit['end']] == unit['text']
        if needle and exact_offset and stream[expected:expected + len(needle)] == needle:
            start = expected
        elif needle:
            start = stream.find(needle)
            if start >= 0 and stream.find(needle, start + 1) >= 0:
                mappings[unit['id']] = {'status': 'ambiguous', 'rects': []}
                continue
        else:
            start = -1
        if start < 0:
            mappings[unit['id']] = {'status': 'unmatched', 'rects': []}
            continue
        boxes = []
        for pos in positions[start:start + len(needle)]:
            if not pos: continue
            rect = [max(0, min(1, n)) for n in pos['rect']]
            if boxes and boxes[-1]['page'] == pos['page']:
                last = boxes[-1]['rect']
                if abs(last[1] - rect[1]) < .004 and abs(last[3] - rect[3]) < .006 and rect[0] >= last[0] and rect[0] - last[2] < .025:
                    last[2] = max(last[2], rect[2]); last[1] = min(last[1], rect[1]); last[3] = max(last[3], rect[3])
                    continue
            boxes.append({'page': pos['page'], 'rect': rect})
        mappings[unit['id']] = {'status': 'matched' if boxes else 'unmatched', 'rects': boxes}
    return mappings
