import tkinter as tk
from tkinter import filedialog, messagebox
import wave
import numpy as np
import math
import struct
import sys

# Đường dẫn file
cover_path = "cover_audio.wav"
stego_path = "24_bit_fixed_LSB.wav"
msg_path = "data.txt"
output_path = "output.txt"
continuous_duration = 0.2
length_bits = 32  # Số bit dùng để lưu độ dài thông điệp (4 byte)

def convertMsgToBin(m):
    """Chuyển thông điệp thành chuỗi bit nhị phân."""
    res = ''
    for i in m:
        x = str(format(ord(i), 'b'))
        x = ('0'*(8-len(x))) + x
        res = res + x
    return res

def decimalToBinary(n):
    """Chuyển số thập phân thành chuỗi nhị phân."""
    binary = bin(n).replace("0b", "")
    return binary

def frames_continuous(time):
    """Tính số frame tương ứng với thời gian (giây)."""
    global rate
    return int(rate * time)
    
def pre(_auido):
    """Lấy metadata từ file WAV và thiết lập các tham số."""
    global para, channels, sample_width, frames, samples, mask, minByte, rate, nlsb

    para = _auido.getparams()
    channels = _auido.getnchannels()
    sample_width = _auido.getsampwidth() * 8  # Độ sâu bit (bit/mẫu)
    frames = _auido.getnframes()
    rate = _auido.getframerate()

    duration = frames / rate 
    samples = frames * channels  # Tổng số mẫu

    # Tính mask và minByte dựa trên độ sâu bit
    if sample_width == 8:
        mask = (1 << 7) - (1 << nlsb)  # Mask cho 8-bit (signed: -128 đến 127)
        minByte = -(1 << 7)  # -128
    elif sample_width == 16:
        mask = (1 << 15) - (1 << nlsb)  # Mask cho 16-bit
        minByte = -(1 << 15)  # -32,768
    elif sample_width == 24:
        mask = (1 << 23) - (1 << nlsb)  # Mask cho 24-bit
        minByte = -(1 << 23)  # -8,388,608
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bits")

def read_raw_data(_auido):
    """Đọc dữ liệu thô từ file WAV và chuyển thành mảng số."""
    global sample_width, frames, channels

    # Đọc toàn bộ dữ liệu thô
    data = _auido.readframes(frames)
    
    # Xử lý tùy theo độ sâu bit
    if sample_width == 8:
        # 8-bit: Dùng "B" (unsigned char), sau đó chuyển thành signed
        fmt = str(frames * channels) + "B"
        rawdata = list(struct.unpack(fmt, data))
        # Chuyển từ unsigned (0 đến 255) sang signed (-128 đến 127)
        rawdata = [x - 128 if x >= 128 else x - 128 for x in rawdata]
    elif sample_width == 16:
        # 16-bit: Dùng "h" (signed short)
        fmt = str(frames * channels) + "h"
        rawdata = list(struct.unpack(fmt, data))
    elif sample_width == 24:
        # 24-bit: Xử lý thủ công (3 byte/mẫu)
        data_array = np.frombuffer(data, dtype=np.uint8)
        data_array = data_array.reshape(-1, 3)  # Mỗi mẫu 3 byte
        rawdata = np.zeros(len(data_array), dtype=np.int32)
        for i in range(len(data_array)):
            rawdata[i] = (data_array[i][2] << 16) | (data_array[i][1] << 8) | data_array[i][0]
            if rawdata[i] >= 2**23:
                rawdata[i] -= 2**24
        rawdata = rawdata.tolist()
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bits")

    return rawdata

def pack_sample(value):
    """Chuyển giá trị số thành bytes để ghi vào file WAV."""
    global sample_width

    if sample_width == 8:
        # 8-bit: Chuyển từ signed (-128 đến 127) sang unsigned (0 đến 255)
        value = value + 128
        return struct.pack("B", value)
    elif sample_width == 16:
        # 16-bit: Dùng "h"
        return struct.pack("h", value)
    elif sample_width == 24:
        # 24-bit: Chuyển thành 3 byte (little-endian)
        if value < 0:
            value += 2**24
        return struct.pack('<I', value)[:3]  # Lấy 3 byte thấp
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bits")

def count_availaible_slots(rawdata):
    """Đếm số mẫu có thể dùng để nhúng dữ liệu."""
    global minByte

    cnt = 0
    for i in range(len(rawdata)):
        if rawdata[i] != minByte:
            cnt += 1
    return cnt

def encode(cover, msg, nlsb):
    """Nhúng thông điệp vào file WAV bằng kỹ thuật LSB."""
    global para, channels, sample_width, frames, samples, mask, minByte, rate, length_bits

    pre(cover)

    # Đọc dữ liệu thô
    rawdata = read_raw_data(cover)

    # Chuyển thông điệp thành chuỗi bit
    msg_bits = convertMsgToBin(msg)
    msg_length = len(msg)  # Độ dài thông điệp (byte)
    msg_length_bits = format(msg_length, '032b')  # Chuyển độ dài thành 32 bit

    # Kết hợp độ dài và nội dung thông điệp
    combined_bits = msg_length_bits + msg_bits
    total_bits = len(combined_bits)

    # Tính toán không gian khả dụng
    availaible = count_availaible_slots(rawdata)
    slot_len = frames_continuous(continuous_duration)
    nslots = math.ceil(total_bits / (slot_len * nlsb))
    skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
    print("\nnslots", nslots, "\nslot_len", slot_len, "\navailaible", availaible, "\nskip", skip)

    cover_ind = 0
    bit_ind = 0
    res = []
    slot_ind = 0

    # Nhúng dữ liệu (độ dài + thông điệp)
    while bit_ind < total_bits and cover_ind < len(rawdata):
        if rawdata[cover_ind] == minByte:
            res.append(pack_sample(rawdata[cover_ind]))
            cover_ind += 1
            continue

        curr = ""
        while len(curr) < nlsb:
            if bit_ind < total_bits:
                curr += combined_bits[bit_ind]
            else:
                curr += "0"
            bit_ind += 1
        curr = int(curr, 2)

        # Xử lý dấu và nhúng dữ liệu
        sign = 1
        if rawdata[cover_ind] < 0:
            rawdata[cover_ind] *= -1
            sign = -1
        to_append = ((rawdata[cover_ind] & mask) | curr) * sign
        res.append(pack_sample(to_append))
        cover_ind += 1
        slot_ind += 1

        # Chuyển sang slot tiếp theo nếu đủ số mẫu trong slot
        if slot_ind < slot_len:
            continue

        i = 0
        while i < skip and cover_ind < len(rawdata):
            if rawdata[cover_ind] != minByte:
                i += 1
            res.append(pack_sample(rawdata[cover_ind]))
            cover_ind += 1
        slot_ind = 0

    if bit_ind < total_bits:
        print("\nMessage length too long. Terminating process")
        return 0

    # Ghi các mẫu còn lại
    while cover_ind < len(rawdata):
        res.append(pack_sample(rawdata[cover_ind]))
        cover_ind += 1

    # Tạo file WAV mới
    steg = wave.open(stego_path, "w")
    steg.setparams(para)
    steg.writeframes(b"".join(res))
    steg.close()

    print("\nSteganography complete. Data hidden in file", stego_path)
    return 1

def decode(stego, nlsb):
    """Trích xuất thông điệp từ file WAV, tự động đọc độ dài."""
    global frames, samples, minByte, rate, length_bits, sample_width

    pre(stego)

    # Đọc dữ liệu thô
    rawdata = read_raw_data(stego)

    # Tính toán không gian khả dụng
    availaible = count_availaible_slots(rawdata)
    slot_len = frames_continuous(continuous_duration)

    # Tính mask để trích xuất nlsb bit thấp nhất
    mask = (1 << nlsb) - 1

    # Trích xuất độ dài thông điệp (32 bit đầu tiên)
    length_bits_extracted = ""
    stego_index = 0
    bit_count = 0

    while bit_count < length_bits and stego_index < len(rawdata):
        if rawdata[stego_index] != minByte:
            curr = decimalToBinary(abs(rawdata[stego_index]) & mask)
            curr = ('0' * (nlsb - len(curr))) + curr
            length_bits_extracted += curr
            bit_count += nlsb
        stego_index += 1

    length_bits_extracted = length_bits_extracted[:length_bits]
    if len(length_bits_extracted) < length_bits:
        print("Error: Not enough data to extract message length.")
        return

    msg_length = int(length_bits_extracted, 2)  # Độ dài thông điệp (byte)
    size_bits = msg_length * 8  # Số bit của thông điệp
    print(f"Extracted message length: {msg_length} bytes ({size_bits} bits)")

    # Tính lại nslots và skip dựa trên độ dài thông điệp
    nslots = math.ceil((size_bits + length_bits) / (slot_len * nlsb))
    skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
    print("nslots", nslots, "skip", skip)

    # Trích xuất nội dung thông điệp
    msg = ""
    msg_index = 0
    slot_ind = 0
    
    while msg_index < size_bits and stego_index < len(rawdata):
        if rawdata[stego_index] != minByte:
            # Trích xuất nlsb bit thấp nhất
            curr = decimalToBinary(abs(rawdata[stego_index]) & mask)
            curr = ('0' * (nlsb - len(curr))) + curr  # Đệm số 0 nếu cần
            msg += curr
            msg_index += nlsb
            slot_ind += 1

        stego_index += 1

        # Chuyển sang slot tiếp theo nếu đủ số mẫu trong slot
        if slot_ind < slot_len:
            continue

        i = 0
        while i < skip and stego_index < len(rawdata):
            if rawdata[stego_index] != minByte:
                i += 1
            stego_index += 1
        slot_ind = 0

    # Cắt chuỗi bit đúng kích thước
    msg = msg[:size_bits]

    # Chuyển chuỗi bit thành ký tự
    val = len(msg) // 8
    if val == 0:
        print("Error: No message extracted.")
        return

    chunks, chunk_size = len(msg), len(msg) // val
    new_string = [msg[i:i + chunk_size] for i in range(0, chunks, chunk_size)]
    dec_msg = ''
    for i in new_string:
        try:
            char_code = int(i, 2)
            # Chỉ thêm ký tự nếu nó nằm trong phạm vi ASCII hợp lệ (0-127)
            if 0 <= char_code <= 127:
                dec_msg += chr(char_code)
            else:
                dec_msg += '?'  # Thay thế ký tự không hợp lệ bằng '?'
        except ValueError:
            dec_msg += '?'  # Thay thế nếu không chuyển đổi được

    # Ghi thông điệp vào file với encoding utf-8
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(dec_msg)
    print("\nThe extracted message is written in", output_path)


if __name__ == "__main__":
    print("\nSelect endcode or decode: \n 1. Encode \n 2.Decode")
    _type = int(input())
    if (1 == _type):
        try:
            cover = wave.open(cover_path, "r")
        except FileNotFoundError:
            print(f"Error: File {cover_path} not found.")
            sys.exit(1)

        try:
            with open(msg_path, 'r') as file:
                msg = file.read()
        except FileNotFoundError:
            print(f"Error: File {msg_path} not found.")
            cover.close()
            sys.exit(1)

        print("Size of message in bytes: ", len(msg))
        print("Length of message in bits: ", len(msg) * 8)

        print("\nEnter number of LSBs to be used:")
        try:
            nlsb = int(input())
            if nlsb <= 0:
                raise ValueError("Number of LSBs must be positive.")
        except ValueError as e:
            print(f"Error: {e}")
            cover.close()
            sys.exit(1)

        success = encode(cover, msg, nlsb)
        cover.close()

        if not success:
            sys.exit(1)
    elif 2 == _type:
        try:
            stego = wave.open(stego_path, "r")
        except FileNotFoundError:
            print(f"Error: File {stego_path} not found.")
            sys.exit(1)

        print("\nEnter number of LSBs used: ")
        try:
            nlsb = int(input())
            if nlsb <= 0:
                raise ValueError("Number of LSBs must be positive.")
        except ValueError as e:
            print(f"Error: {e}")
            stego.close()
            sys.exit(1)

        decode(stego, nlsb)
        stego.close()
    else:
        sys.exit(1)