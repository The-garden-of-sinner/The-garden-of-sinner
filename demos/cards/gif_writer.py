#!/usr/bin/env python3
"""手工组装 GIF89a：每帧完整画布 + 自实现 LZW，杜绝 Pillow 重排色表/差分帧。"""
import struct


def lzw_encode(indices, min_code_size=8):
    """GIF LZW 压缩，返回 (min_code_size, sub-blocks bytes)。"""
    clear = 1 << min_code_size
    eoi = clear + 1
    code_size = min_code_size + 1
    next_code = eoi + 1
    table = {}
    bits = 0
    nbits = 0
    out = bytearray()

    def emit(code):
        nonlocal bits, nbits
        bits |= code << nbits
        nbits += code_size
        while nbits >= 8:
            out.append(bits & 0xFF)
            bits >>= 8
            nbits -= 8

    emit(clear)
    w = (indices[0],)
    for k in indices[1:]:
        wk = w + (k,)
        if wk in table:
            w = wk
        else:
            emit(w[0] if len(w) == 1 else table[w])
            if next_code < 4096:
                table[wk] = next_code
                next_code += 1
                if next_code > (1 << code_size) and code_size < 12:
                    code_size += 1
            else:
                emit(clear)
                table = {}
                next_code = eoi + 1
                code_size = min_code_size + 1
            w = (k,)
    emit(w[0] if len(w) == 1 else table[w])
    emit(eoi)
    if nbits > 0:
        out.append(bits & 0xFF)

    # 切成 GIF 数据子块（每块 ≤255 字节）
    blocks = bytearray()
    for i in range(0, len(out), 255):
        chunk = out[i:i + 255]
        blocks.append(len(chunk))
        blocks.extend(chunk)
    blocks.append(0)
    return bytes([min_code_size]) + bytes(blocks)


def write_full_frame_gif(path, frames, palette, delays, loop=0):
    """frames: 完整画布 P-mode 图；palette: 扁平 768 字节 RGB 表。"""
    assert len(frames) == len(delays)
    W, H = frames[0].size
    pal = list(palette[:768]) + [0] * (768 - len(palette[:768]))
    with open(path, 'wb') as f:
        f.write(b'GIF89a')
        f.write(struct.pack('<HHBBB', W, H, 0xF7, 0, 0))   # GCT=1, 256 色
        f.write(bytes(pal[:768]))
        f.write(b'\x21\xFF\x0BNETSCAPE2.0\x03\x01' + struct.pack('<H', loop) + b'\x00')
        for im, delay in zip(frames, delays):
            assert im.size == (W, H)
            # disposal=2: 每帧都是完整画布，清屏后重画整帧 -> 零残影、无渲染器差异
            f.write(b'\x21\xF9\x04\x09' + struct.pack('<H', max(1, delay // 10)) + b'\x00\x00')
            f.write(b'\x2C' + struct.pack('<HHHHB', 0, 0, W, H, 0))
            f.write(lzw_encode(list(im.getdata()), 8))
        f.write(b'\x3B')
