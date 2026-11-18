# SPDX-License-Identifier: GPL-2.0-only
"""Decode and validate GR III 2.10 firmware containers."""
from pathlib import Path
import struct, hashlib, json, argparse, os, datetime
FACTORY = 'd6a3c9c288d784080e7b283222ecdd8752adfeed6faa36dab44f73115354bfd4'
DECODED = '53da690797f35ad6dc2c429d8ca1d0de8e333c211ed959816813982cd093b703'
ROOT = Path(__file__).resolve().parents[1]
sha = lambda b: hashlib.sha256(b).hexdigest()
u32 = lambda b, o: struct.unpack_from('<I', b, o)[0]

def need(ok, message):
    if not ok:
        raise ValueError(message)

def sum32(b):
    need(len(b) % 4 == 0, 'Unaligned checksum data')
    return sum((v[0] for v in struct.iter_unpack('<I', b))) & 4294967295

def checksum(b):
    b = bytearray(b)
    struct.pack_into('<I', b, len(b) - 4, 0)
    struct.pack_into('<I', b, len(b) - 4, -sum32(b) & 4294967295)
    return bytes(b)

def decode(s):
    p = 128
    data = bytearray()
    frames = []
    while True:
        begin = p
        need(p + 2 <= len(s) - 24, 'Missing frame terminator')
        prefix = int.from_bytes(s[p:p + 2], 'big')
        p += 2
        if prefix == 0:
            break
        n = prefix & 32767
        end = p + n
        old = len(data)
        need(end <= len(s) - 24, 'Frame crosses footer')
        if prefix & 32768:
            data.extend(s[p:end])
            p = end
        else:
            while p < end:
                need(p + 2 <= end, 'Truncated flags')
                bits = int.from_bytes(s[p:p + 2], 'big')
                p += 2
                for i in range(16):
                    if p >= end:
                        break
                    if not bits & 1 << 15 - i:
                        data.append(s[p])
                        p += 1
                        continue
                    need(p + 2 <= end, 'Truncated reference')
                    tag, lo = s[p:p + 2]
                    p += 2
                    length = tag & 7
                    offset = (tag & 248) << 5 | lo
                    if length == 7:
                        while True:
                            need(p < end, 'Truncated extended length')
                            ext = s[p]
                            p += 1
                            length += ext
                            if ext != 255:
                                break
                    if offset == 0:
                        p = end
                        break
                    need(offset <= len(data), 'Reference before decoded start')
                    length += 3
                    seq = bytes(data[-offset:])
                    data.extend((seq * ((length + offset - 1) // offset))[:length])
            need(p == end, 'Bad frame length')
        frames.append((begin, end, old, len(data)))
    return (bytes(data), frames, p)

def verify_package(b):
    need(len(b) >= 154 and len(b) % 4 == 0, 'Invalid package size')
    f = b[-24:]
    prod = u32(b, 48)
    need(prod == 588 and u32(b, 120) == prod | prod << 16, 'Wrong GR III product marker')
    need(u32(b, 124) == 2774162085 and f[:8] == b[120:128], 'Header/footer magic mismatch')
    need(u32(f, 8) == 2, 'Wrong firmware type')
    need(sum32(b) == 0, 'Encoded checksum mismatch')
    d, frames, p = decode(b)
    need(u32(f, 12) in (p - 128, p - 130), 'Compressed-length mismatch')
    need(0 <= len(b) - 24 - p <= 3 and (not any(b[p:-24])), 'Unexpected footer padding')
    need(len(d) == u32(f, 16), 'Decoded-length mismatch')
    need(sum32(d) == 0, 'Decoded checksum mismatch')
    return (d, frames)

def blocks(d):
    out = {}
    pos = 0
    while True:
        need(pos + 16 <= len(d) - 4, 'Truncated container header')
        name = d[pos:pos + 8].split(b'\x00')[0].decode('ascii')
        typ, ident, n = struct.unpack_from('<HHI', d, pos + 8)
        start = pos + 16
        end = start + n
        if name == 'RES':
            end = start
            for _ in range(n):
                need(end + 36 <= len(d) - 4, 'Truncated resource')
                end += 36 + u32(d, end + 32)
        need(end <= len(d) - 4, 'Block out of bounds')
        need(name not in out, 'Duplicate block')
        out[name] = (pos, start, end, typ, ident)
        if name == 'RES':
            need(end == len(d) - 4, 'Unexpected container tail')
            break
        pos = end
    return out
