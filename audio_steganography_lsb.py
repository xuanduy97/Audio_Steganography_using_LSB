import tkinter as tk
from tkinter import filedialog, messagebox
import wave
import numpy as np
import math
import struct
import sys

class SteganographyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Steganography with Hidden Length")
        self.root.geometry("600x500")

        # Biến lưu đường dẫn
        self.cover_path = tk.StringVar()
        self.stego_path = tk.StringVar(value="stego_audio_LSB.wav")
        self.msg_path = tk.StringVar()
        self.output_path = tk.StringVar(value="output.txt")
        self.nlsb = tk.StringVar(value="2")
        self.continuous_duration = 0.2

        # Số bit cố định để lưu độ dài thông điệp (4 byte = 32 bit)
        self.length_bits = 32

        # Giao diện
        self.create_widgets()

    def create_widgets(self):
        # Tiêu đề
        tk.Label(self.root, text="Audio Steganography", font=("Arial", 16, "bold")).pack(pady=10)

        # Frame cho Encode
        encode_frame = tk.LabelFrame(self.root, text="Encode (Hide Message)", font=("Arial", 12), padx=10, pady=10)
        encode_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(encode_frame, text="Cover WAV File:").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(encode_frame, textvariable=self.cover_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(encode_frame, text="Browse", command=self.browse_cover).grid(row=0, column=2, padx=5)

        tk.Label(encode_frame, text="Message File (Text):").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(encode_frame, textvariable=self.msg_path, width=40).grid(row=1, column=1, padx=5)
        tk.Button(encode_frame, text="Browse", command=self.browse_msg).grid(row=1, column=2, padx=5)

        tk.Label(encode_frame, text="Output Stego WAV File:").grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(encode_frame, textvariable=self.stego_path, width=40).grid(row=2, column=1, padx=5)

        tk.Label(encode_frame, text="Number of LSBs:").grid(row=3, column=0, sticky="w", pady=5)
        tk.Entry(encode_frame, textvariable=self.nlsb, width=10).grid(row=3, column=1, sticky="w", padx=5)

        tk.Button(encode_frame, text="Encode", command=self.encode, bg="green", fg="white").grid(row=4, column=1, pady=10)

        # Frame cho Decode
        decode_frame = tk.LabelFrame(self.root, text="Decode (Extract Message)", font=("Arial", 12), padx=10, pady=10)
        decode_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(decode_frame, text="Stego WAV File:").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(decode_frame, textvariable=self.stego_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(decode_frame, text="Browse", command=self.browse_stego).grid(row=0, column=2, padx=5)

        tk.Label(decode_frame, text="Output Text File:").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(decode_frame, textvariable=self.output_path, width=40).grid(row=1, column=1, padx=5)

        tk.Label(decode_frame, text="Number of LSBs:").grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(decode_frame, textvariable=self.nlsb, width=10).grid(row=2, column=1, sticky="w", padx=5)

        tk.Button(decode_frame, text="Decode", command=self.decode, bg="blue", fg="white").grid(row=3, column=1, pady=10)

    def browse_cover(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file_path:
            self.cover_path.set(file_path)

    def browse_msg(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.msg_path.set(file_path)

    def browse_stego(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file_path:
            self.stego_path.set(file_path)

    def convertMsgToBin(self, m):
        """Chuyển thông điệp thành chuỗi bit nhị phân."""
        res = ''
        for i in m:
            x = str(format(ord(i), 'b'))
            x = ('0'*(8-len(x))) + x
            res = res + x
        return res

    def decimalToBinary(self, n):
        """Chuyển số thập phân thành chuỗi nhị phân."""
        binary = bin(n).replace("0b", "")
        return binary

    def frames_continuous(self, time):
        """Tính số frame tương ứng với thời gian (giây)."""
        return int(self.rate * time)
        
    def pre(self, _auido):
        """Lấy metadata từ file WAV và thiết lập các tham số."""
        self.para = _auido.getparams()
        self.channels = _auido.getnchannels()
        self.sample_width = _auido.getsampwidth() * 8  # Độ sâu bit (bit/mẫu)
        self.frames = _auido.getnframes()
        self.rate = _auido.getframerate()

        self.duration = self.frames / self.rate 
        self.samples = self.frames * self.channels  # Tổng số mẫu

        # Tính mask và minByte dựa trên độ sâu bit
        if self.sample_width == 8:
            self.mask = (1 << 7) - (1 << self.nlsb_value)  # Mask cho 8-bit (signed: -128 đến 127)
            self.minByte = -(1 << 7)  # -128
        elif self.sample_width == 16:
            self.mask = (1 << 15) - (1 << self.nlsb_value)  # Mask cho 16-bit
            self.minByte = -(1 << 15)  # -32,768
        elif self.sample_width == 24:
            self.mask = (1 << 23) - (1 << self.nlsb_value)  # Mask cho 24-bit
            self.minByte = -(1 << 23)  # -8,388,608
        else:
            raise ValueError(f"Unsupported sample width: {self.sample_width} bits")

    def read_raw_data(self, _auido):
        """Đọc dữ liệu thô từ file WAV và chuyển thành mảng số."""
        # Đọc toàn bộ dữ liệu thô
        data = _auido.readframes(self.frames)
        
        # Xử lý tùy theo độ sâu bit
        if self.sample_width == 8:
            # 8-bit: Dùng "B" (unsigned char), sau đó chuyển thành signed
            fmt = str(self.frames * self.channels) + "B"
            rawdata = list(struct.unpack(fmt, data))
            # Chuyển từ unsigned (0 đến 255) sang signed (-128 đến 127)
            rawdata = [x - 128 if x >= 128 else x - 128 for x in rawdata]
        elif self.sample_width == 16:
            # 16-bit: Dùng "h" (signed short)
            fmt = str(self.frames * self.channels) + "h"
            rawdata = list(struct.unpack(fmt, data))
        elif self.sample_width == 24:
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

    def pack_sample(self, value):
        """Chuyển giá trị số thành bytes để ghi vào file WAV."""
        if self.sample_width == 8:
            # 8-bit: Chuyển từ signed (-128 đến 127) sang unsigned (0 đến 255)
            value = value + 128
            return struct.pack("B", value)
        elif self.sample_width == 16:
            # 16-bit: Dùng "h"
            return struct.pack("h", value)
        elif self.sample_width == 24:
            # 24-bit: Chuyển thành 3 byte (little-endian)
            if value < 0:
                value += 2**24
            return struct.pack('<I', value)[:3]  # Lấy 3 byte thấp
        else:
            raise ValueError(f"Unsupported sample width: {self.sample_width} bits")

    def count_availaible_slots(self, rawdata):
        """Đếm số mẫu có thể dùng để nhúng dữ liệu."""
        cnt = 0
        for i in range(len(rawdata)):
            if rawdata[i] != self.minByte:
                cnt += 1
        return cnt

    def encode(self):
        try:
            if not self.cover_path.get():
                messagebox.showerror("Error", "Please select a cover WAV file.")
                return
            if not self.msg_path.get():
                messagebox.showerror("Error", "Please select a message file.")
                return
            if not self.stego_path.get():
                messagebox.showerror("Error", "Please specify an output stego WAV file.")
                return

            self.nlsb_value = int(self.nlsb.get())
            if self.nlsb_value <= 0:
                raise ValueError("Number of LSBs must be positive.")

            cover = wave.open(self.cover_path.get(), "r")
            with open(self.msg_path.get(), 'r') as file:
                msg = file.read()
            """Nhúng thông điệp vào file WAV bằng kỹ thuật LSB."""
            self.pre(cover)

            # Đọc dữ liệu thô
            rawdata = self.read_raw_data(cover)

            # Chuyển thông điệp thành chuỗi bit
            msg_bits = self.convertMsgToBin(msg)
            msg_length = len(msg)  # Độ dài thông điệp (byte)
            msg_length_bits = format(msg_length, '032b')  # Chuyển độ dài thành 32 bit

            # Kết hợp độ dài và nội dung thông điệp
            combined_bits = msg_length_bits + msg_bits
            total_bits = len(combined_bits)

            # Tính toán không gian khả dụng
            availaible = self.count_availaible_slots(rawdata)
            slot_len = self.frames_continuous(self.continuous_duration)
            nslots = math.ceil(total_bits / (slot_len * self.nlsb_value))
            skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
            print("\nnslots", nslots, "\nslot_len", slot_len, "\navailaible", availaible, "\nskip", skip)

            cover_ind = 0
            bit_ind = 0
            res = []
            slot_ind = 0

            # Nhúng dữ liệu (độ dài + thông điệp)
            while bit_ind < total_bits and cover_ind < len(rawdata):
                if rawdata[cover_ind] == self.minByte:
                    res.append(self.pack_sample(rawdata[cover_ind]))
                    cover_ind += 1
                    continue

                curr = ""
                while len(curr) < self.nlsb_value:
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
                to_append = ((rawdata[cover_ind] & self.mask) | curr) * sign
                res.append(self.pack_sample(to_append))
                cover_ind += 1
                slot_ind += 1

                # Chuyển sang slot tiếp theo nếu đủ số mẫu trong slot
                if slot_ind < slot_len:
                    continue

                i = 0
                while i < skip and cover_ind < len(rawdata):
                    if rawdata[cover_ind] != self.minByte:
                        i += 1
                    res.append(self.pack_sample(rawdata[cover_ind]))
                    cover_ind += 1
                slot_ind = 0

            if bit_ind < total_bits:
                print("\nMessage length too long. Terminating process")
                return 0

            # Ghi các mẫu còn lại
            while cover_ind < len(rawdata):
                res.append(self.pack_sample(rawdata[cover_ind]))
                cover_ind += 1

            # Tạo file WAV mới
            steg = wave.open(self.stego_path.get(), "w")
            steg.setparams(self.para)
            steg.writeframes(b"".join(res))
            steg.close()

            print("\nSteganography complete. Data hidden in file", self.stego_path.get())

        except Exception as e:
            messagebox.showerror("Error", str(e))
            if 'cover' in locals():
                cover.close()
            if 'steg' in locals():
                steg.close()

    def decode(self):
        try:
            if not self.stego_path.get():
                messagebox.showerror("Error", "Please select a stego WAV file.")
                return
            if not self.output_path.get():
                messagebox.showerror("Error", "Please specify an output text file.")
                return

            self.nlsb_value = int(self.nlsb.get())
            if self.nlsb_value <= 0:
                raise ValueError("Number of LSBs must be positive.")

            stego = wave.open(self.stego_path.get(), "r")
            """Trích xuất thông điệp từ file WAV, tự động đọc độ dài."""

            self.pre(stego)

            # Đọc dữ liệu thô
            rawdata = self.read_raw_data(stego)

            # Tính toán không gian khả dụng
            availaible = self.count_availaible_slots(rawdata)
            slot_len = self.frames_continuous(self.continuous_duration)

            # Tính mask để trích xuất nlsb bit thấp nhất
            self.mask = (1 << self.nlsb_value) - 1

            # Trích xuất độ dài thông điệp (32 bit đầu tiên)
            length_bits_extracted = ""
            stego_index = 0
            bit_count = 0

            while bit_count < self.length_bits and stego_index < len(rawdata):
                if rawdata[stego_index] != self.minByte:
                    curr = self.decimalToBinary(abs(rawdata[stego_index]) & self.mask)
                    curr = ('0' * (self.nlsb_value - len(curr))) + curr
                    length_bits_extracted += curr
                    bit_count += self.nlsb_value
                stego_index += 1

            length_bits_extracted = length_bits_extracted[:self.length_bits]
            if len(length_bits_extracted) < self.length_bits:
                print("Error: Not enough data to extract message length.")
                return

            msg_length = int(length_bits_extracted, 2)  # Độ dài thông điệp (byte)
            size_bits = msg_length * 8  # Số bit của thông điệp
            print(f"Extracted message length: {msg_length} bytes ({size_bits} bits)")

            # Tính lại nslots và skip dựa trên độ dài thông điệp
            nslots = math.ceil((size_bits + self.length_bits) / (slot_len * self.nlsb_value))
            skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
            print("nslots", nslots, "skip", skip)

            # Trích xuất nội dung thông điệp
            msg = ""
            msg_index = 0
            slot_ind = 0
            
            while msg_index < size_bits and stego_index < len(rawdata):
                if rawdata[stego_index] != self.minByte:
                    # Trích xuất nlsb bit thấp nhất
                    curr = self.decimalToBinary(abs(rawdata[stego_index]) & self.mask)
                    curr = ('0' * (self.nlsb_value - len(curr))) + curr  # Đệm số 0 nếu cần
                    msg += curr
                    msg_index += self.nlsb_value
                    slot_ind += 1

                stego_index += 1

                # Chuyển sang slot tiếp theo nếu đủ số mẫu trong slot
                if slot_ind < slot_len:
                    continue

                i = 0
                while i < skip and stego_index < len(rawdata):
                    if rawdata[stego_index] != self.minByte:
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
            with open(self.output_path.get(), 'w', encoding='utf-8') as file:
                file.write(dec_msg)
            print("\nThe extracted message is written in", self.output_path.get())

        except Exception as e:
            messagebox.showerror("Error", str(e))
            if 'stego' in locals():
                stego.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = SteganographyApp(root)
    root.mainloop()