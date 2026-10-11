"""Amazon FILE writers — change files only, stdlib only (file-only architecture).

Writes NEW files; the original upload is never modified. The delta writer keeps
the SOURCE column order exactly and copies source values byte-for-byte, changing
only the approved fields. No network call exists in this module (asserted by
tools/test_no_amazon_linkage.py).

Formats: .xlsx (minimal OOXML written with ``zipfile``; verified openable with
openpyxl in the test suite) and .tsv (tab-delimited text templates).
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple

XLSX_CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
{sheet_overrides}
</Types>"""

XLSX_ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def _esc(v: Any) -> str:
    s = "" if v is None else str(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;").replace("'", "&apos;"))


def _col_letter(idx: int) -> str:
    out = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        out = chr(ord("A") + rem) + out
    return out


def _is_number(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str):
        return bool(re.fullmatch(r"-?\d+(\.\d+)?", v.strip()))
    return False


def write_xlsx(sheets: List[Dict[str, Any]]) -> bytes:
    """Write a minimal .xlsx: [{name, headers, rows}] with inline strings.

    Numbers are written as numbers; everything else as inline strings. The
    workbook is plain OOXML so Excel and openpyxl both open it.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        sheet_overrides = "\n".join(
            f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(len(sheets))
        )
        zf.writestr("[Content_Types].xml", XLSX_CONTENT_TYPES.format(sheet_overrides=sheet_overrides))
        zf.writestr("_rels/.rels", XLSX_ROOT_RELS)
        sheet_entries = "\n".join(
            f'<sheet name="{_esc((s.get("name") or f"Sheet{i+1}")[:31])}" sheetId="{i+1}" r:id="rId{i+1}"/>'
            for i, s in enumerate(sheets)
        )
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f"<sheets>{sheet_entries}</sheets></workbook>",
        )
        rels = "\n".join(
            f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i+1}.xml"/>'
            for i in range(len(sheets))
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f"{rels}</Relationships>",
        )
        for i, s in enumerate(sheets):
            headers = s.get("headers") or []
            rows = s.get("rows") or []
            xml_rows = []
            def emit(row_vals: List[Any], r_idx: int) -> None:
                cells = []
                for c_idx, val in enumerate(row_vals):
                    if val is None or val == "":
                        continue
                    ref = f"{_col_letter(c_idx)}{r_idx}"
                    if _is_number(val):
                        cells.append(f'<c r="{ref}"><v>{_esc(val)}</v></c>')
                    else:
                        cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_esc(val)}</t></is></c>')
                xml_rows.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
            emit(list(headers), 1)
            for r_idx, row in enumerate(rows, 2):
                emit(list(row), r_idx)
            zf.writestr(
                f"xl/worksheets/sheet{i+1}.xml",
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>",
            )
    return buf.getvalue()


def write_tsv(headers: List[Any], rows: List[List[Any]]) -> bytes:
    lines = ["\t".join("" if v is None else str(v) for v in headers)]
    for row in rows:
        lines.append("\t".join("" if v is None else str(v) for v in row))
    return ("\n".join(lines) + "\n").encode("utf-8")


def write_delta(
    source_sheets: List[Dict[str, Any]],
    approved: List[Dict[str, Any]],
    *,
    format: str = "xlsx",
) -> Dict[str, Any]:
    """Build the change file: the SOURCE header order, changed rows only.

    Each approved change carries {sheet, row_index, op, fields:{canon:value},
    op_column: canonical op column, op_value: the value to write}. Only the
    rows named by the approved changes appear; their cells are the source's own
    values with the approved fields replaced. The Operation cell is never left
    blank for an intended change (asserted below).
    """
    by_sheet: Dict[str, Dict[str, Any]] = {s["name"]: s for s in source_sheets}
    out_sheets: Dict[str, Dict[str, Any]] = {}
    written_rows = 0

    for ch in approved:
        sheet_name = ch["sheet"]
        src = by_sheet.get(sheet_name)
        if src is None:
            raise ValueError(f"unknown sheet in approved change: {sheet_name}")
        mapped = src.get("mapped") or {}
        raw_rows = src.get("rows") or []
        row_index = int(ch["row_index"])
        if row_index < 0 or row_index >= len(raw_rows):
            raise ValueError(f"row_index {row_index} is outside sheet {sheet_name}")
        out = out_sheets.setdefault(sheet_name, {
            "name": sheet_name,
            "headers": list(src.get("headers") or []),
            "rows": [],
        })
        row = [None] * len(out["headers"])
        src_row = raw_rows[row_index]
        for i in range(len(row)):
            row[i] = src_row[i] if i < len(src_row) else None
        for canon, value in (ch.get("fields") or {}).items():
            idx = mapped.get(canon)
            if idx is None:
                raise ValueError(f"field {canon} is not mapped in sheet {sheet_name}")
            row[idx] = value
        op_col = ch.get("op_column")
        op_value = ch.get("op_value")
        if op_col and op_value is not None:
            idx = mapped.get(op_col)
            if idx is None:
                raise ValueError(f"operation column {op_col} is not mapped in sheet {sheet_name}")
            row[idx] = op_value
        if not op_value:
            raise ValueError("refusing to write an intended change with a blank Operation")
        out["rows"].append(row)
        written_rows += 1

    sheets = list(out_sheets.values())
    if format == "xlsx":
        content = write_xlsx(sheets)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif format == "tsv":
        if len(sheets) != 1:
            raise ValueError("tsv output supports a single sheet")
        content = write_tsv(sheets[0]["headers"], sheets[0]["rows"])
        mime = "text/tab-separated-values"
    else:
        raise ValueError(f"unsupported change-file format: {format}")

    return {"content": content, "mime": mime, "format": format,
            "sheets": sheets, "row_count": written_rows}
