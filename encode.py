import wave
import numpy as np
import math
import struct

# Đường dẫn file
cover_path = "24_bit_fixed.wav"
stego_path = "24_bit_fixed_LSB.wav"
msg_path = "data.txt"
continuous_duration = 0.2

def convertMsgToBin(m):
    """Chuyển thông điệp thành chuỗi bit nhị phân."""
    res = ''
    for i in m:
        x = str(format(ord(i), 'b'))
        x = ('0'*(8-len(x))) + x
        res = res + x
    return res

def frames_continuous(time):
    """Tính số frame tương ứng với thời gian (giây)."""
    global rate
    return int(rate * time)

def pre(cover):
    """Lấy metadata từ file WAV và thiết lập các tham số."""
    global para, channels, sample_width, frames, samples, mask, minByte, rate

    # Lấy metadata
    para = cover.getparams()
    channels = cover.getnchannels()
    sample_width = cover.getsampwidth() * 8  # Độ sâu bit (bit/mẫu)
    frames = cover.getnframes()
    rate = cover.getframerate()

    duration = frames / rate 
    samples = frames * channels  # Tổng số mẫu

    # Tính mask và minByte dựa trên độ sâu bit
    if sample_width == 8:
        mask = (1 << 7) - (1 << nlsb)  # Mask cho 8-bit (signed: -128 đến 127)
        minByte = -(1 << 7)
    elif sample_width == 16:
        mask = (1 << 15) - (1 << nlsb)  # Mask cho 16-bit
        minByte = -(1 << 15)
    elif sample_width == 24:
        mask = (1 << 23) - (1 << nlsb)  # Mask cho 24-bit
        minByte = -(1 << 23)
    else:
        raise ValueError(f"Unsupported sample width: {sample_width} bits")

def read_raw_data(cover):
    """Đọc dữ liệu thô từ file WAV và chuyển thành mảng số."""
    global sample_width, frames, channels

    # Đọc toàn bộ dữ liệu thô
    data = cover.readframes(frames)
    
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

def stego(cover, msg, nlsb):
    """Nhúng thông điệp vào file WAV bằng kỹ thuật LSB."""
    global para, channels, sample_width, frames, samples, mask, minByte, rate
    pre(cover)

    # Đọc dữ liệu thô
    rawdata = read_raw_data(cover)

    # Tính toán không gian khả dụng
    availaible = count_availaible_slots(rawdata)
    slot_len = frames_continuous(continuous_duration)
    nslots = math.ceil(len(msg) / (slot_len * nlsb))
    skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
    print("\nnslots", nslots, "\nslot_len", slot_len, "\navailaible", availaible, "\nskip", skip)

    cover_ind = 0
    msg_ind = 0
    res = []
    slot_ind = 0

    # Nhúng dữ liệu
    while msg_ind < len(msg) and cover_ind < len(rawdata):
        if rawdata[cover_ind] == minByte:
            res.append(pack_sample(rawdata[cover_ind]))
            cover_ind += 1
            continue

        # Lấy nlsb bit từ thông điệp
        curr = ""
        while len(curr) < nlsb:
            if msg_ind < len(msg):
                curr += msg[msg_ind]
            else:
                curr += "0"
            msg_ind += 1
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

    # Kiểm tra nếu thông điệp quá dài
    if msg_ind < len(msg):
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

    print("\nStegonography complete. Data hidden in file", stego_path)
    return 1

if __name__ == "__main__":
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
    msg = convertMsgToBin(msg)
    print("Length of message in bits: ", len(msg))

    print("\nEnter number of LSBs to be used:")
    try:
        nlsb = int(input())
        if nlsb <= 0:
            raise ValueError("Number of LSBs must be positive.")
    except ValueError as e:
        print(f"Error: {e}")
        cover.close()
        sys.exit(1)

    success = stego(cover, msg, nlsb)
    cover.close()

    if not success:
        sys.exit(1)