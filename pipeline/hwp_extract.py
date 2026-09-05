"""HWP 5.0 본문 텍스트 추출기 (의존성 최소: olefile + zlib + struct).

한글(.hwp)은 OLE 복합파일. BodyText/SectionN 스트림에 문단 텍스트가 레코드로 저장됨
(FileHeader 압축 플래그면 raw-deflate). PARA_TEXT 레코드(tag 67)에서 UTF-16LE 텍스트를
인라인 제어문자를 건너뛰며 추출한다.

사용(모듈):
    from pipeline.hwp_extract import hwp_to_text
    text = hwp_to_text("파일.hwp")   # 또는 bytes 전달
"""
from __future__ import annotations
import struct
import zlib
import io

import olefile

HWPTAG_PARA_TEXT = 67  # HWPTAG_BEGIN(16) + 51
# 8워드(16바이트) 차지하는 제어문자
CTRL_EXT = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
# 1워드(2바이트) 제어문자 (줄바꿈류 포함)
CTRL_NL = {10, 13}


def _is_compressed(ole: "olefile.OleFileIO") -> bool:
    if not ole.exists("FileHeader"):
        return True
    with ole.openstream("FileHeader") as s:
        hdr = s.read()
    # offset 36: 속성 플래그(4바이트), bit0 = 압축
    flags = struct.unpack_from("<I", hdr, 36)[0]
    return bool(flags & 0x01)


def _parse_para_text(payload: bytes) -> str:
    out: list[str] = []
    j = 0
    n = len(payload)
    while j + 1 < n:
        wc = payload[j] | (payload[j + 1] << 8)
        if wc in CTRL_NL:
            out.append("\n")
            j += 2
        elif wc in CTRL_EXT:
            j += 16  # 제어 8워드 건너뜀
        elif wc < 32:
            j += 2
        else:
            out.append(chr(wc))
            j += 2
    return "".join(out)


def _iter_records(data: bytes):
    i, n = 0, len(data)
    while i + 4 <= n:
        header = struct.unpack_from("<I", data, i)[0]
        tag = header & 0x3FF
        size = (header >> 20) & 0xFFF
        i += 4
        if size == 0xFFF:
            size = struct.unpack_from("<I", data, i)[0]
            i += 4
        payload = data[i:i + size]
        i += size
        yield tag, payload


def hwp_to_text(src) -> str:
    """경로(str) 또는 bytes를 받아 본문 텍스트 반환."""
    ole = olefile.OleFileIO(src if isinstance(src, (str, bytes, io.BytesIO)) else src)
    try:
        compressed = _is_compressed(ole)
        # BodyText/SectionN 스트림 수집
        sections = []
        for entry in ole.listdir():
            if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section"):
                sections.append(entry)
        sections.sort(key=lambda e: int(e[1].replace("Section", "") or 0))
        parts: list[str] = []
        for entry in sections:
            with ole.openstream(entry) as s:
                raw = s.read()
            if compressed:
                try:
                    raw = zlib.decompress(raw, -15)
                except zlib.error:
                    pass
            for tag, payload in _iter_records(raw):
                if tag == HWPTAG_PARA_TEXT:
                    parts.append(_parse_para_text(payload))
        return "\n".join(parts)
    finally:
        ole.close()


def _hwpx_to_text(data: bytes) -> str:
    import zipfile, re as _re, html
    z = zipfile.ZipFile(io.BytesIO(data))
    names = sorted(n for n in z.namelist() if _re.search(r"Contents/section\d+\.xml", n))
    if not names:
        names = [n for n in z.namelist() if n.endswith(".xml")]
    texts = []
    for n in names:
        xml = z.read(n).decode("utf-8", "ignore")
        t = _re.findall(r"<hp:t[^>]*>(.*?)</hp:t>", xml, _re.S)
        texts.append("".join(t) if t else _re.sub(r"<[^>]+>", " ", xml))
    return html.unescape("\n".join(texts))


def _pdf_to_text(data: bytes) -> str:
    import fitz
    doc = fitz.open(stream=data, filetype="pdf")
    try:
        return "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()


def extract_document(data: bytes) -> tuple[str, str]:
    """바이트를 매직으로 판별해 (포맷, 텍스트) 반환. HWP/PDF/HWPX(zip) 지원."""
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return "hwp", hwp_to_text(io.BytesIO(data))
    if data[:4] == b"%PDF":
        return "pdf", _pdf_to_text(data)
    if data[:2] == b"PK":
        return "hwpx", _hwpx_to_text(data)
    return "unknown", ""


if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as fh:
        fmt, txt = extract_document(fh.read())
    print(f"[{fmt}]\n{txt[:3000]}")
