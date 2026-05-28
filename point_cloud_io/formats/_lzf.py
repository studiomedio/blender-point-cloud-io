"""Pure-Python LZF compressor and decompressor (libLZF stream format).

LZF is a tiny lossless byte-stream codec used by PCL for the PCD
`binary_compressed` mode. The format:

    block := literal | back_ref

    literal:
        ctrl   : 0..31           (literal length - 1)
        bytes  : ctrl+1 raw bytes

    back_ref:
        ctrl   : 0x20..0xFF
        len_hi  = ctrl >> 5      (3 bits; if 7, length is in the long form)
        off_hi  = ctrl & 0x1F    (5 bits, high 5 of offset)
        [extra byte if len_hi == 7]
        off_lo : 1 byte          (low 8 of offset)

        match length = len_hi == 7 ? (7 + extra + 2) : (len_hi + 2)   (2..264)
        offset       = ((off_hi << 8) | off_lo) + 1                   (1..8192)
        copy `length` bytes from `output_pos - offset` to current output

Pure Python is slow for very large buffers (tens of MB+); we keep things
honest with bytearray operations and slice-based copies whenever the
back-reference doesn't overlap the destination.
"""

__all__ = ['lzf_decompress', 'lzf_compress']


_MIN_MATCH = 3
_MAX_MATCH = 264
_MAX_OFFSET = 1 << 13  # 8192
_HASH_SIZE = 1 << 16   # 65536 entries, ~1 MB memory


def lzf_decompress(data, expected_length):
    """Decompress LZF-compressed bytes. Returns a bytes object of length `expected_length`."""
    out = bytearray(expected_length)
    in_pos = 0
    out_pos = 0
    n = len(data)

    while in_pos < n:
        ctrl = data[in_pos]
        in_pos += 1

        if ctrl < 32:
            # Literal run: copy (ctrl + 1) bytes from input to output.
            length = ctrl + 1
            if in_pos + length > n:
                raise ValueError("LZF stream truncated in literal run.")
            if out_pos + length > expected_length:
                raise ValueError("LZF output overflows expected length.")
            out[out_pos:out_pos + length] = data[in_pos:in_pos + length]
            in_pos += length
            out_pos += length
        else:
            # Back-reference.
            length = ctrl >> 5
            if length == 7:
                if in_pos >= n:
                    raise ValueError("LZF stream truncated in long-match length byte.")
                length += data[in_pos]
                in_pos += 1
            length += 2

            if in_pos >= n:
                raise ValueError("LZF stream truncated in offset byte.")
            offset = ((ctrl & 0x1F) << 8) | data[in_pos]
            in_pos += 1
            ref = out_pos - offset - 1

            if ref < 0:
                raise ValueError(f"LZF back-reference out of range (offset={offset}).")
            if out_pos + length > expected_length:
                raise ValueError("LZF back-reference overflows expected length.")

            # When the back-reference doesn't overlap the destination, slice-copy
            # is a single C-level memmove. When it overlaps (RLE-style runs), we
            # must copy byte-by-byte so the freshly-written bytes propagate.
            if ref + length <= out_pos:
                out[out_pos:out_pos + length] = out[ref:ref + length]
                out_pos += length
            else:
                for i in range(length):
                    out[out_pos] = out[ref + i]
                    out_pos += 1

    if out_pos != expected_length:
        raise ValueError(
            f"LZF stream produced {out_pos} bytes, expected {expected_length}."
        )
    return bytes(out)


def _emit_literal(out, literal_buf):
    if literal_buf:
        out.append(len(literal_buf) - 1)
        out.extend(literal_buf)
        literal_buf.clear()


def lzf_compress(data):
    """Compress bytes with LZF. Returns the compressed bytes.

    The output is always a valid LZF stream; we do not bail out on
    incompressible input (some encoders return None in that case — we always
    succeed because PCD writers expect a usable blob).
    """
    n = len(data)
    if n == 0:
        return b''

    out = bytearray()
    literal_buf = bytearray()
    hash_table = [-1] * _HASH_SIZE

    in_pos = 0
    end_match = n - _MIN_MATCH  # last position where a 3-byte match is possible

    while in_pos <= end_match:
        # 3-byte hash of the lookahead window.
        h = (
            (data[in_pos] << 16)
            ^ (data[in_pos + 1] << 8)
            ^ data[in_pos + 2]
        ) & (_HASH_SIZE - 1)
        ref = hash_table[h]
        hash_table[h] = in_pos

        if (
            ref >= 0
            and (in_pos - ref) <= _MAX_OFFSET
            and data[ref] == data[in_pos]
            and data[ref + 1] == data[in_pos + 1]
            and data[ref + 2] == data[in_pos + 2]
        ):
            # Found a candidate match — extend it as far as we can.
            offset = in_pos - ref - 1
            match_len = 3
            max_len = min(_MAX_MATCH, n - in_pos)
            while (
                match_len < max_len
                and data[ref + match_len] == data[in_pos + match_len]
            ):
                match_len += 1

            _emit_literal(out, literal_buf)

            if match_len < 9:
                out.append(((match_len - 2) << 5) | (offset >> 8))
                out.append(offset & 0xFF)
            else:
                out.append((7 << 5) | (offset >> 8))
                out.append(match_len - 9)
                out.append(offset & 0xFF)

            in_pos += match_len
            continue

        # No usable match: accumulate one literal byte.
        literal_buf.append(data[in_pos])
        if len(literal_buf) == 32:
            _emit_literal(out, literal_buf)
        in_pos += 1

    # Tail bytes that can't form a 3-byte match — flush as literals.
    while in_pos < n:
        literal_buf.append(data[in_pos])
        if len(literal_buf) == 32:
            _emit_literal(out, literal_buf)
        in_pos += 1

    _emit_literal(out, literal_buf)
    return bytes(out)
