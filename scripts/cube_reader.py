# SPDX-License-Identifier: GPL-2.0-only
# Darkslide-derived validation/parser portions: Copyright (C) 2026 LiorMoment.
"""Original Darkslide GR CUBE parser, GPL-2.0-only. See SOURCES.md."""
import math
import re

MAX_CUBE = 8 * 1024 * 1024
USER_ID = re.compile(r"user_lut_[0-9a-f]{12}\Z")


class FilmLutError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise FilmLutError(message)


def parse_cube(data):
    """(title, size, rows) of a 3D .cube; rows are (r, g, b) floats, red fastest."""
    _need(type(data) is bytes and 0 < len(data) <= MAX_CUBE, "LUT 文件为空或超过 8 MB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise FilmLutError("LUT 文件不是文本") from None
    title, size, rows, domain = "", None, [], ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head = line.split()[0].upper()
        if head == "TITLE":
            title = line[5:].strip().strip('"')[:80]
        elif head == "LUT_3D_SIZE":
            _need(size is None and re.fullmatch(r"LUT_3D_SIZE\s+\d{1,3}", line, re.I), "LUT_3D_SIZE 写法错误")
            size = int(line.split()[1])
            _need(2 <= size <= 65, "LUT 网格必须在 2–65 之间")
        elif head == "LUT_1D_SIZE":
            raise FilmLutError("只支持 3D LUT，不支持 1D LUT")
        elif head in ("DOMAIN_MIN", "DOMAIN_MAX"):
            v = _floats(line.split()[1:], "DOMAIN")
            _need(len(v) == 3, "DOMAIN 写法错误")
            domain = (v, domain[1]) if head == "DOMAIN_MIN" else (domain[0], v)
        elif head[0].isdigit() or head[0] in "-+.":
            v = _floats(line.split(), "数据行")
            _need(len(v) == 3, "LUT 数据行必须是三个数")
            rows.append(tuple(v))
        else:
            raise FilmLutError("无法识别的 LUT 行：%s" % line[:24])
    _need(size is not None, "缺少 LUT_3D_SIZE")
    _need(len(rows) == size ** 3, "LUT 数据行数与网格大小不符")
    _need(tuple(domain[0]) == (0.0, 0.0, 0.0) and tuple(domain[1]) == (1.0, 1.0, 1.0), "只支持 0–1 输入范围的 LUT")
    _need(all(-0.5 <= x <= 1.5 for row in rows for x in row), "LUT 输出超出正常范围")
    return title, size, rows


def _floats(parts, what):
    try:
        values = [float(p) for p in parts]
    except ValueError:
        raise FilmLutError("%s 不是数字" % what) from None
    _need(all(math.isfinite(v) for v in values), "%s 含有非有限数值" % what)
    return values
