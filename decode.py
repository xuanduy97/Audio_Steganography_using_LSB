import wave
import numpy as np
import math
import struct
import sys

# Đường dẫn file
stego_path = "24_bit_fixed_LSB.WAV"
output_path = "output.txt"
continuous_duration = 0.2

def decimalToBinary(n):
    """Chuyển số thập phân thành chuỗi nhị phân."""
    binary = bin(n).replace("0b", "")
    return binary

def frames_continuous(time):
    """Tính số frame tương ứng với thời gian (giây)."""
    global rate
    return int(rate * time)

def pre(stego):
    """Lấy metadata từ file WAV và thiết lập các tham số."""
    global para, channels, sample_width, frames, samples, minByte, rate

    # Lấy metadata
    para = stego.getparams()
    channels = stego.getnchannels()
    sample_width = stego.getsampwidth() * 8  # Độ sâu bit (bit/mẫu)
    frames = stego.getnframes()
    rate = stego.getframerate()

    duration = frames / rate 
    samples = frames * channels  # Tổng số mẫu

    # Tính minByte dựa trên độ sâu bit
    if sample_width == 8:
        minByte = -(1 << 7)  # -128
    elif sample_width == 16:
        minByte = -(1 << 15)  # -32,768
    elif sample_width == 24:
        minByte = -(1 << 23)  # -8,388,608
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bits")

def read_raw_data(stego):
    """Đọc dữ liệu thô từ file WAV và chuyển thành mảng số."""
    global sample_width, frames, channels

    # Đọc toàn bộ dữ liệu thô
    data = stego.readframes(frames)
    
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

def count_availaible_slots(rawdata):
    """Đếm số mẫu có thể dùng để trích xuất dữ liệu."""
    global minByte

    cnt = 0
    for i in range(len(rawdata)):
        if rawdata[i] != minByte:
            cnt += 1
    return cnt

def extract(stego, nlsb, size_in_bytes):
    """Trích xuất thông điệp từ file WAV."""
    global frames, samples, minByte, rate

    pre(stego)

    # Đọc dữ liệu thô
    rawdata = read_raw_data(stego)

    # Tính toán không gian khả dụng
    availaible = count_availaible_slots(rawdata)
    slot_len = frames_continuous(continuous_duration)
    size = size_in_bytes * 8  # Số bit cần trích xuất
    nslots = math.ceil(size / (slot_len * nlsb))
    skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
    print("\nnslots", nslots, "\nslot_len", slot_len, "\navailaible frames", availaible, "\nskip", skip)

    # Tính mask để trích xuất nlsb bit thấp nhất
    global sample_width
    mask = (1 << nlsb) - 1  # Ví dụ: nlsb = 2 → mask = 0b11

    msg = ""
    stego_index = 0
    msg_index = 0
    slot_ind = 0

    # Trích xuất dữ liệu
    while msg_index < size and stego_index < len(rawdata):
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
    msg = msg[:size]

    # Chuyển chuỗi bit thành ký tự
    val = len(msg) // 8
    if val == 0:
        print("Error: No message extracted.")
        return

    chunks, chunk_size = len(msg), len(msg) // val
    new_string = [msg[i:i + chunk_size] for i in range(0, chunks, chunk_size)]
    dec_msg = ''
    for i in new_string:
        dec_msg += chr(int(i, 2))

    # Ghi thông điệp vào file
    with open(output_path, 'w') as file:
        file.write(dec_msg)
    print("\nThe extracted message is written in", output_path)

if __name__ == "__main__":
    try:
        stego = wave.open(stego_path, "r")
    except FileNotFoundError:
        print(f"Error: File {stego_path} not found.")
        sys.exit(1)

    print("Enter number of LSBs used: ")
    try:
        nlsb = int(input())
        if nlsb <= 0:
            raise ValueError("Number of LSBs must be positive.")
    except ValueError as e:
        print(f"Error: {e}")
        stego.close()
        sys.exit(1)

    print("Enter size of data in bytes: ")
    try:
        size = int(input())
        if size <= 0:
            raise ValueError("Size of data must be positive.")
    except ValueError as e:
        print(f"Error: {e}")
        stego.close()
        sys.exit(1)

    extract(stego, nlsb, size)
    stego.close()