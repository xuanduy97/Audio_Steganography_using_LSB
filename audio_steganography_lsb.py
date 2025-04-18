import sys
import os
import time
import math
import wave
import struct
import pygame
import librosa
import librosa.display
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
from tkinter import filedialog, messagebox, ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class SteganographyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Steganography with Hidden Length")
        self.root.geometry("800x500")

        # Biến lưu đường dẫn
        self.cover_path = tk.StringVar()
        self.stego_path = tk.StringVar()
        self.msg_path = tk.StringVar(value="data.txt")
        self.output_path = tk.StringVar(value="output.txt")
        self.msg_result = tk.StringVar(value="")
        self.progress_var = tk.DoubleVar(value=0)  # Biến điều khiển progressbar
        self.nlsb = tk.StringVar(value="1")
        self.continuous_duration = 0.2
        # Số bit cố định để lưu độ dài thông điệp (4 byte = 32 bit)
        self.length_bits = 32

        # Audio state
        self.audio_file = None
        self.audio_duration = 0
        self.start_time = 0
        self.is_paused = False
        self.is_playing = False

        # Giao diện
        self.create_widgets()

    def create_widgets(self):
        background_color = "gray90"
        # Tiêu đề
        tk.Label(self.root, text="Audio Steganography", font=("Arial", 16, "bold"), bg=background_color).pack(pady=10)
        style = ttk.Style()
        self.root.configure(bg=background_color)
        style.configure("TNotebook", background=background_color)
        style.configure("TNotebook.Tab",
                        padding=[10, 5], 
                        font=("Times New Roman", 16))  # Font mới cho tabbar
        notebook = ttk.Notebook(self.root)
        # Đặt notebook vào cửa sổ chính
        notebook.pack(fill="x", padx=10, pady=5)

        # Frame cho Encode
        encode_frame = tk.LabelFrame(notebook, text="Encode (Hide Message)", font=("Arial", 12), padx=10, pady=10)

        encode_sub_frame = tk.Frame(encode_frame)
        encode_sub_frame.pack()

        tk.Label(encode_sub_frame, text="Cover WAV File:").grid(row=0, column=0, sticky="w", pady=5)
        tk.Entry(encode_sub_frame, textvariable=self.cover_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(encode_sub_frame, text="Browse", command=self.browse_cover).grid(row=0, column=2, padx=5)

        tk.Label(encode_sub_frame, text="Message File (Text):").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(encode_sub_frame, textvariable=self.msg_path, width=40).grid(row=1, column=1, padx=5)
        tk.Button(encode_sub_frame, text="Browse", command=self.browse_msg).grid(row=1, column=2, padx=5)

        tk.Label(encode_sub_frame, text="Output Stego WAV File:").grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(encode_sub_frame, textvariable=self.stego_path, width=40).grid(row=2, column=1, padx=5)

        tk.Label(encode_sub_frame, text="Number of LSBs:").grid(row=3, column=0, sticky="w", pady=5)
        tk.Entry(encode_sub_frame, textvariable=self.nlsb, width=10).grid(row=3, column=1, sticky="w", padx=5)

        tk.Button(encode_frame, text="Encode", command=self.encode, bg="green", fg="white").pack(pady=10)

        tk.Label(encode_frame, textvariable=self.msg_result).pack(fill="x", padx=10, pady=5)
        ttk.Progressbar(encode_frame, variable=self.progress_var, maximum=100, length=300).pack(pady=10)
        
        # Frame cho Decode
        decode_frame = tk.LabelFrame(notebook, text="Decode (Extract Message)", font=("Arial", 12), padx=10, pady=10)
        decode_sub_frame = tk.Frame(decode_frame)
        decode_sub_frame.pack()

        tk.Label(decode_sub_frame, text="Stego WAV File:").grid(row=0, column=0, sticky="w", pady=5)

        tk.Entry(decode_sub_frame, textvariable=self.stego_path, width=40).grid(row=0, column=1, padx=5)
        tk.Button(decode_sub_frame, text="Browse", command=self.browse_stego).grid(row=0, column=2, padx=5)

        tk.Label(decode_sub_frame, text="Output Text File:").grid(row=1, column=0, sticky="w", pady=5)
        tk.Entry(decode_sub_frame, textvariable=self.output_path, width=40).grid(row=1, column=1, padx=5)

        tk.Label(decode_sub_frame, text="Number of LSBs:").grid(row=2, column=0, sticky="w", pady=5)
        tk.Entry(decode_sub_frame, textvariable=self.nlsb, width=10).grid(row=2, column=1, sticky="w", padx=5)

        tk.Button(decode_frame, text="Decode", command=self.decode, bg="blue", fg="white").pack(pady=10)

        tk.Label(decode_frame, textvariable=self.msg_result).pack(fill="x", padx=10, pady=5)
        ttk.Progressbar(decode_frame, variable=self.progress_var, maximum=100, length=300).pack(pady=10)

        # Frame cho Graph
        graph_frame = tk.LabelFrame(notebook, text="Graph (After Encode, Compair Audio)", font=("Arial", 12), padx=10, pady=10)
        graph_sub_frame = tk.Frame(graph_frame)
        graph_sub_frame.pack(pady=10)
        # Button to load audio file
        tk.Button(graph_sub_frame, text="Load WAV File (Ori & Stego)", command=self.load_audio_file).pack(side=tk.LEFT, padx=10)
        self.play_overplay = tk.Button(graph_sub_frame, text="Plot Overlay", command=self.plot_waveforms, state=tk.DISABLED)
        self.play_overplay.pack(side=tk.RIGHT, padx=10)
        # Create a Matplotlib figure
        self.figure, self.ax = plt.subplots(figsize=(10, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.get_tk_widget().pack()

        # Frame cho Play Audio
        play_frame = tk.LabelFrame(notebook, text="Play Audio (After Encode)", font=("Arial", 12), padx=10, pady=10)
        play_sub_frame_1 = tk.Frame(play_frame)
        play_sub_frame_2 = tk.Frame(play_frame)
        play_sub_frame_1.pack()
        play_sub_frame_2.pack()

        # Initialize pygame mixer
        pygame.mixer.init()

        tk.Button(play_sub_frame_1, text="Load Original File", command=self.load_ori_audio).pack(side=tk.LEFT, padx=10)
        tk.Button(play_sub_frame_1, text="Load Steganography File", command=self.load_stego_audio).pack(side=tk.RIGHT, padx=10)
        self.play_button = tk.Button(play_sub_frame_2, text="Play", command=self.play_audio, state=tk.DISABLED)
        self.play_button.grid(row=0, column=0, padx=5, pady=5)
        self.pause_button = tk.Button(play_sub_frame_2, text="Pause", command=self.pause_audio, state=tk.DISABLED)
        self.pause_button.grid(row=0, column=1, padx=5, pady=5)
        self.stop_button = tk.Button(play_sub_frame_2, text="Stop", command=self.stop_audio, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=2, padx=5, pady=5)

        # Progress bar (Scale widget)
        self.progress = tk.Scale(play_frame, from_=0, to=100, orient=tk.HORIZONTAL, length=300, label="Playback Time (seconds)", state=tk.DISABLED)
        self.progress.pack(pady=5)

        # Config notebook
        notebook.add(encode_frame, text="Encode")
        notebook.add(decode_frame, text="Decode")
        notebook.add(graph_frame, text="Graph")
        notebook.add(play_frame, text="Play Audio")

        notebook.bind("<<NotebookTabChanged>>", self.on_tab_change)

    def on_tab_change(self, event):
        self.msg_result.set("Result")
        self.progress_var.set(0)
        self.play_overplay.config(state=tk.DISABLED)
        self.disable_buttons()
        self.root.update_idletasks()
        self.stop_audio()
    
    def load_audio_file(self):
        file_path = self.cover_path.get()
        if os.path.exists(file_path):
            try:
                self.audio1, self.sr1 = librosa.load(file_path)
                
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to load Original audio: {str(e)}")
        else :
            tk.messagebox.showerror("Error", f"Original audio is not exists.")
        file_path = self.stego_path.get()
        if os.path.exists(file_path):
            try:
                self.audio2, self.sr2 = librosa.load(file_path)
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to load Steganography audio: {str(e)}")
        else :
            tk.messagebox.showerror("Error", f"Steganography audio is not exists.\nPlease encode to get Steganography audio.")
        self.play_overplay.config(state=tk.NORMAL)
        tk.messagebox.showinfo("Success", "Original audio & Steganography audio loaded.")

    def plot_waveforms(self):
        if self.audio1 is None or self.audio2 is None:
            tk.messagebox.showwarning("Warning", "Please load both audio files.")
            return

        try:
            # Ensure same sample rate
            if self.sr1 != self.sr2:
                tk.messagebox.showwarning("Warning", "Sample rates differ. Results may be inaccurate.")
                # Optionally resample one audio to match (uncomment if needed)
                # self.audio2 = librosa.resample(self.audio2, orig_sr=self.sr2, target_sr=self.sr1)
                # self.sr2 = self.sr1

            # Ensure same length by padding or truncating
            max_len = min(len(self.audio1), len(self.audio2))
            audio1 = self.audio1[:max_len]
            audio2 = self.audio2[:max_len]

            # Clear previous plot
            self.ax.clear()

            # Plot both waveforms overlaid
            librosa.display.waveshow(audio1, sr=self.sr1, ax=self.ax, alpha=0.5, color='r', label='Original')
            librosa.display.waveshow(audio2, sr=self.sr2, ax=self.ax, alpha=0.5, color='b', label='Steganography')
            self.ax.set_title("So sánh tín hiệu âm thanh (Original vs Steganography)")
            self.ax.set_xlabel("Thời gian (giây)")
            self.ax.set_ylabel("Biên độ")
            self.ax.legend()

            # Update canvas
            self.canvas.draw()

        except Exception as e:
            tk.messagebox.showerror("Error", f"Failed to plot waveforms: {str(e)}")
    
    def load_ori_audio(self):
        self.stop_audio()
        file_path = self.cover_path.get()
        if file_path and os.path.exists(file_path):
            try:
                # Load audio with pygame
                pygame.mixer.music.load(file_path)
                # Get duration with librosa
                self.audio_duration = librosa.get_duration(filename=file_path)
                self.audio_file = file_path
                self.progress.config(to=self.audio_duration, state=tk.NORMAL)
                self.progress.set(0)
                self.play_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.DISABLED)
                tk.messagebox.showinfo("Success", f"Original Audio loaded. Duration: {self.audio_duration:.1f} seconds")
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to load Original Audio: {str(e)}")
                self.audio_file = None
                self.disable_buttons()
        else:
            tk.messagebox.showwarning("Warning", "No file selected or file does not exist.")
            self.audio_file = None
            self.disable_buttons()
    
    def load_stego_audio(self):
        self.stop_audio()
        file_path = self.stego_path.get()
        if file_path and os.path.exists(file_path):
            try:
                # Load audio with pygame
                pygame.mixer.music.load(file_path)
                # Get duration with librosa
                self.audio_duration = librosa.get_duration(filename=file_path)
                self.audio_file = file_path
                self.progress.config(to=self.audio_duration, state=tk.NORMAL)
                self.progress.set(0)
                self.play_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.DISABLED)
                tk.messagebox.showinfo("Success", f"Steganography Audio loaded. Duration: {self.audio_duration:.1f} seconds")
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to load Steganography Audio: {str(e)}")
                self.audio_file = None
                self.disable_buttons()
        else:
            tk.messagebox.showwarning("Warning", "No file selected or file does not exist.")
            self.audio_file = None
            self.disable_buttons()

    def play_audio(self):
        if self.audio_file:
            try:
                if self.is_paused:
                    # Resume playback
                    pygame.mixer.music.unpause()
                    self.is_paused = False
                    self.start_time += time.time() - self.pause_time  # Adjust start time
                else:
                    # Start playback
                    pygame.mixer.music.load(self.audio_file)
                    pygame.mixer.music.play()
                    self.start_time = time.time()
                self.is_playing = True
                self.play_button.config(state=tk.DISABLED)
                self.pause_button.config(state=tk.NORMAL)
                self.stop_button.config(state=tk.NORMAL)
                # Start updating progress bar
                self.update_progress()
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to play audio: {str(e)}")
                self.disable_buttons()

    def pause_audio(self):
        if self.audio_file and not self.is_paused:
            try:
                pygame.mixer.music.pause()
                self.is_paused = True
                self.pause_time = time.time()
                self.is_playing = False
                self.play_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.NORMAL)
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to pause audio: {str(e)}")

    def stop_audio(self):
        if self.audio_file:
            try:
                pygame.mixer.music.stop()
                self.is_paused = False
                self.is_playing = False
                self.progress.set(0)
                self.play_button.config(state=tk.NORMAL)
                self.pause_button.config(state=tk.DISABLED)
                self.stop_button.config(state=tk.DISABLED)
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to stop audio: {str(e)}")

    def update_progress(self):
        if self.is_playing:
            # Estimate current time
            elapsed = time.time() - self.start_time
            if elapsed <= self.audio_duration:
                self.progress.set(elapsed)
            else:
                # Audio finished
                self.stop_audio()
            # Schedule next update
            self.root.after(100, self.update_progress)  # Update every 100ms

    def disable_buttons(self):
        self.play_button.config(state=tk.DISABLED)
        self.pause_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.DISABLED)
        self.progress.config(state=tk.DISABLED)
        self.progress.set(0)

    def browse_cover(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file_path:
            result_path = file_path.split('/')
            result_path = result_path[len(result_path) - 1].lower().replace('.wav', '_LSB.wav')
            self.cover_path.set(file_path)
            self.stego_path.set(result_path)

    def browse_msg(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if file_path:
            self.msg_path.set(file_path)

    def browse_stego(self):
        file_path = filedialog.askopenfilename(filetypes=[("WAV files", "*.wav")])
        if file_path:
            self.stego_path.set(file_path)

    def show_error_msg(self, error_msg):
        self.msg_result.set(f"Error: {error_msg}")
        self.root.update_idletasks()
        raise ValueError(f"{error_msg}")

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
            self.show_error_msg(f"Unsupported sample width: {self.sample_width} bits")

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
            self.show_error_msg(f"Unsupported sample width: {self.sample_width} bits")
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
            self.show_error_msg(f"Unsupported sample width: {self.sample_width} bits")

    def count_availaible_slots(self, rawdata):
        """Đếm số mẫu có thể dùng để nhúng dữ liệu."""
        cnt = 0
        for i in range(len(rawdata)):
            if rawdata[i] != self.minByte:
                cnt += 1
        return cnt

    def encode(self):
        self.msg_result.set("Progress...")
        self.progress_var.set(0)
        self.root.update_idletasks()
        try:
            if not self.cover_path.get():
                self.show_error_msg("Please select a cover WAV file.")
            if not self.msg_path.get():
                self.show_error_msg("Please select a message file.")
            if not self.stego_path.get():
                self.show_error_msg("Please specify an output stego WAV file.")

            self.nlsb_value = int(self.nlsb.get())
            if self.nlsb_value <= 0:
                self.show_error_msg("Number of LSBs must be positive.")

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

            self.progress_var.set(25)
            self.root.update_idletasks()

            # Kết hợp độ dài và nội dung thông điệp
            combined_bits = msg_length_bits + msg_bits
            total_bits = len(combined_bits)

            # Tính toán không gian khả dụng
            availaible = self.count_availaible_slots(rawdata)
            slot_len = self.frames_continuous(self.continuous_duration)
            nslots = math.ceil(total_bits / (slot_len * self.nlsb_value))
            skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
            print(f"slots: {nslots} slot_len: {slot_len} availaible: {availaible} skip: {skip}")

            cover_ind = 0
            bit_ind = 0
            res = []
            slot_ind = 0

            self.progress_var.set(50)
            self.root.update_idletasks()

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

            self.progress_var.set(75)
            self.root.update_idletasks()

            if bit_ind < total_bits:
                self.show_error_msg("Message length too long. Please increase Number of LSBs.")
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

            print(f"Steganography complete. Data hidden in file {self.stego_path.get()}")
            result_path = self.stego_path.get().split('/')
            result_path = result_path[len(result_path) - 1]
            self.msg_result.set(f"Steganography complete. Data hidden in file '{result_path}'")
            self.progress_var.set(100)
            self.root.update_idletasks()
            tk.messagebox.showinfo("Success", f"Steganography complete. Data hidden in file '{result_path}'")

        except Exception as e:
            self.msg_result.set(f"Error: {str(e)}.")
            messagebox.showerror("Error", str(e))
            if 'cover' in locals():
                cover.close()
            if 'steg' in locals():
                steg.close()

    def decode(self):
        self.msg_result.set("Progress...")
        self.progress_var.set(0)
        self.root.update_idletasks()
        try:
            if not self.stego_path.get():
                self.show_error_msg("Please select a stego WAV file.")
            if not self.output_path.get():
                self.show_error_msg("Please specify an output text file.")
            self.nlsb_value = int(self.nlsb.get())
            if self.nlsb_value <= 0:
                self.show_error_msg("Number of LSBs must be positive.")

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

            self.progress_var.set(25)
            self.root.update_idletasks()

            length_bits_extracted = length_bits_extracted[:self.length_bits]
            if len(length_bits_extracted) < self.length_bits:
                self.msg_result.set("Error: Not enough data to extract message length.")
                print("Error: Not enough data to extract message length.")
                return

            msg_length = int(length_bits_extracted, 2)  # Độ dài thông điệp (byte)
            size_bits = msg_length * 8  # Số bit của thông điệp
            print(f"Extracted message length: {msg_length} bytes ({size_bits} bits)")

            # Tính lại nslots và skip dựa trên độ dài thông điệp
            nslots = math.ceil((size_bits + self.length_bits) / (slot_len * self.nlsb_value))
            skip = (availaible - (nslots * slot_len)) // (nslots - 1) if nslots > 1 else 0
            print(f"slots:{nslots} skip: {skip}")

            self.progress_var.set(50)
            self.root.update_idletasks()

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

            self.progress_var.set(75)
            self.root.update_idletasks()

            # Cắt chuỗi bit đúng kích thước
            msg = msg[:size_bits]

            # Chuyển chuỗi bit thành ký tự
            val = len(msg) // 8
            if val == 0:
                self.show_error_msg("No message extracted.")
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
            print(f"The extracted message is written in: {self.output_path.get()}")
            self.msg_result.set(f"The extracted message is written in: {self.output_path.get()}")
            self.progress_var.set(100)
            self.root.update_idletasks()
            tk.messagebox.showinfo("Success", f"The extracted message is written in: {self.output_path.get()}")

        except Exception as e:
            self.msg_result.set(f"Error: {str(e)}.")
            messagebox.showerror("Error", str(e))
            if 'stego' in locals():
                stego.close()


if __name__ == "__main__":
    root = tk.Tk()
    app = SteganographyApp(root)
    root.mainloop()