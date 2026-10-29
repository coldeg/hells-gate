"""Pure Easywave coding primitives; no household dictionary or I/O."""

def crc8(data: bytes) -> int:
    value = 0
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value << 1 ^ 29) & 255 if value & 128 else value << 1 & 255
    return value

def integrity_variant(word: int) -> int:
    frame = word.to_bytes(4, 'big')
    predicted = crc8(frame[:3]) ^ 180
    check = frame[3]
    residue = crc8(frame)
    if check == predicted and residue == 24:
        return 0
    if check == predicted ^ 142 and residue == 152:
        return 1
    raise ValueError(f'word {word:08X} does not pass a known integrity class')

def word_bits(word: int) -> list[int]:
    return [word >> shift & 1 for shift in range(31, -1, -1)]

def manchester_encode(bits: list[int]) -> list[int]:
    chips: list[int] = []
    for bit in bits:
        chips.extend((0, 1) if bit == 0 else (1, 0))
    return chips

def pack_bits(bits: list[int]) -> bytes:
    if len(bits) % 8:
        raise ValueError('bit count must be a multiple of eight')
    packed = bytearray()
    for offset in range(0, len(bits), 8):
        value = 0
        for bit in bits[offset:offset + 8]:
            value = value << 1 | bit
        packed.append(value)
    return bytes(packed)
