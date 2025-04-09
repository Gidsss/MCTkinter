import sys
import os
import time
import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tqdm import tqdm

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# Dynamically add the root directory to the Python path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(root_dir)

# Import the compiled Cython module and database utilities
from thesis_toolkit import (
    build_model, file_to_bitstream, bitstream_to_file, validate_bitstreams,
    ExistingEncoder, ExistingDecoder, EnhancedEncoder, EnhancedDecoder
)
from db_utils import init_db, save_file_record, get_all_files, get_encoded_text

MODEL_DIR = "markov_models"
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Initialize the database
init_db()

# Pre-load the Markov model at startup
model = build_model("markov_models/legal_corpus.json")
logging.info("Markov model loaded successfully.")

class SteganographyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Markov Chain-Based Steganography")
        self.root.geometry("900x600")

        # Variables
        self.algorithm = tk.StringVar(value="Existing Algorithm")
        self.file_path = None

        # Algorithm Selection
        self.algorithm_label = tk.Label(root, text="Select Algorithm:")
        self.algorithm_label.pack(pady=5)
        self.algorithm_dropdown = ttk.Combobox(root, textvariable=self.algorithm, state="readonly",
                                               values=["Existing Algorithm", "Enhanced Algorithm"])
        self.algorithm_dropdown.pack(pady=5)

        # Upload and Encode Button
        self.upload_button = tk.Button(root, text="Upload", command=self.upload_and_encode)
        self.upload_button.pack(pady=5)

        # File Table (Treeview)
        self.file_table = ttk.Treeview(root, columns=("Name", "Algorithm", "Operation", "Timestamp", "Action"), show="headings")
        self.file_table.heading("Name", text="File Name")
        self.file_table.heading("Algorithm", text="Algorithm")
        self.file_table.heading("Operation", text="Operation")
        self.file_table.heading("Timestamp", text="Timestamp")
        self.file_table.heading("Action", text="Action")
        self.file_table.pack(pady=10, fill=tk.BOTH, expand=True)

        # View/Decode Button
        self.decode_button = tk.Button(root, text="View", command=self.decode_selected)
        self.decode_button.pack(pady=5)

        # Populate file table on startup
        self.load_file_table()

    def load_file_table(self):
        """Load file records into the table."""
        self.file_table.delete(*self.file_table.get_children())
        for record in get_all_files():
            self.file_table.insert("", "end", values=(record[1], record[2], record[3], record[4], "View/Decode"))

    # def encode_with_progress(self, encoder, progress_bar, time_label, start_time):
    #     """Encode with real-time progress updates."""
    #     while not encoder.finished:
    #         encoder.step()
    #         elapsed = time.time() - start_time
    #         progress = min(int((elapsed / 30) * 100), 100)  # Approximation
    #         progress_bar['value'] = progress
    #         time_label.config(text=f"Time Elapsed: {elapsed:.2f} seconds")
    #         progress_bar.update()
    #     return encoder.output, time.time() - start_time

    # def encode_existing(self, model, bitstream, progress_bar, time_label):
    #     """Encode using the Existing Algorithm with progress."""
    #     start_time = time.time()
    #     encoder = ExistingEncoder(model, bitstream)
    #     return self.encode_with_progress(encoder, progress_bar, time_label, start_time)

    # def encode_enhanced(self, model, bitstream, progress_bar, time_label):
    #     """Encode using the Enhanced Algorithm with progress."""
    #     start_time = time.time()
    #     encoder = EnhancedEncoder(model, bitstream)
    #     return self.encode_with_progress(encoder, progress_bar, time_label, start_time)

    def upload_and_encode(self):
        """Upload a file and start encoding."""
        self.file_path = filedialog.askopenfilename(
            title="Select a File",
            filetypes=(("Text, DOCX, PDF files", "*.txt *.docx *.pdf"), ("All files", "*.*"))
        )
        if self.file_path:
            try:
                algorithm = self.algorithm.get()
                file_name = os.path.basename(self.file_path)
                logging.info(f"File selected: {file_name}")
                bitstream = file_to_bitstream(self.file_path)

                # Create progress window
                progress_window = tk.Toplevel(self.root)
                progress_window.title("Encoding Progress")
                progress_window.geometry("400x150")

                progress_label = tk.Label(progress_window, text="Encoding in progress...")
                progress_label.pack(pady=5)

                time_label = tk.Label(progress_window, text="Time Elapsed: 0.00 seconds | 0%")
                time_label.pack(pady=5)

                progress_bar = ttk.Progressbar(progress_window, length=300, mode="determinate")
                progress_bar.pack(pady=10)

                start_time = time.time()
                progress = {
                    'value': 0,
                    'finished': False,
                    'finished_ui': False,
                    'started': True,
                    'paused_at_99': False
                }

                def update_progress_bar():
                    if not progress.get('started') or not progress_window.winfo_exists():
                        return

                    elapsed = time.time() - start_time
                    current_value = progress_bar['value']
                    target_value = progress['value']

                    if target_value > current_value:
                        # Pause at 99% 
                        if target_value == 100 and current_value >= 98 and not progress['paused_at_99']:
                            progress['paused_at_99'] = True
                            progress_bar['value'] = 99
                            time_label.config(text=f"Time Elapsed: {elapsed:.2f} seconds | 99%")

                            def resume_to_100():
                                if progress_window.winfo_exists():
                                    progress_bar['value'] = 100
                                    time_label.config(text=f"Time Elapsed: {time.time() - start_time:.2f} seconds | 100%")
                                    progress_window.update_idletasks()

                                    # Delay UI finalization and messagebox slightly to show 100%
                                    def finalize():
                                        if progress_window.winfo_exists():
                                            messagebox.showinfo("Encoding Complete", f"Encoding finished.\nTime Elapsed: {time.time() - start_time:.2f} seconds")
                                            progress_window.destroy()

                                    progress['finished_ui'] = True
                                    self.root.after(300, finalize)

                            self.root.after(500, resume_to_100)
                            return

                        new_value = min(current_value + 1, target_value)
                        progress_bar['value'] = new_value
                        time_label.config(text=f"Time Elapsed: {elapsed:.2f} seconds | {new_value}%")

                    elif target_value == 100 and current_value == 100 and not progress['finished_ui']:
                        progress['finished_ui'] = True

                    progress_window.update_idletasks()

                    if not progress.get('finished_ui'):
                        self.root.after(100, update_progress_bar)

                def encode_task():
                    try:
                        encoder = ExistingEncoder(model, bitstream) if algorithm == "Existing Algorithm" else EnhancedEncoder(model, bitstream)
                        initial_estimated_steps = max(1, len(bitstream) // 8)
                        estimated_steps = initial_estimated_steps
                        current_step = 0

                        while not encoder.finished:
                            encoder.step()
                            current_step += 1

                            if current_step >= estimated_steps and not encoder.finished:
                                estimated_steps += int(estimated_steps * 0.1)

                            raw_progress = int((current_step / initial_estimated_steps) * 100)
                            progress['value'] = min(raw_progress, 100)

                        # Final update
                        progress['value'] = 100
                        progress['finished'] = True
                        progress['finished_ui'] = False
                        progress['started'] = True

                        encoded_text = encoder.output
                        elapsed = time.time() - start_time

                        save_file_record(file_name, algorithm, "encode", encoded_text)
                        self.file_table.insert("", "end", values=(file_name, algorithm, "encode", time.strftime("%Y-%m-%d %H:%M:%S"), "View/Decode"))

                    except Exception as e:
                        messagebox.showerror("Encoding Error", f"Error during encoding: {str(e)}")
                        logging.error(f"Error during encoding: {str(e)}")
                        progress['finished'] = True
                        if progress_window.winfo_exists():
                            progress_window.destroy()

                self.root.after(500, update_progress_bar)
                threading.Thread(target=encode_task, daemon=True).start()

            except Exception as e:
                messagebox.showerror("Encoding Error", f"Error during encoding: {str(e)}")
                logging.error(f"Error during encoding: {str(e)}")




    def decode_selected(self):
        """Decode the selected file from the table."""
        selected_item = self.file_table.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a file from the table.")
            return

        file_name = self.file_table.item(selected_item, "values")[0]

        try:
            # Retrieve encoded plain text from the database
            records = get_all_files()
            encoded_text = get_encoded_text(file_name, "encode")

            if not encoded_text:
                messagebox.showwarning("Data Not Found", "Encoded text not found in the database.")
                return

            # Ensure encoded text is plain text
            encoded_text = encoded_text.strip()

            start_time = time.time()

            # Select the appropriate decoder based on the algorithm
            decoder = ExistingDecoder(model, encoded_text) if self.algorithm.get() == "Existing Algorithm" else EnhancedDecoder(model, encoded_text)

            # Perform decoding step by step
            while not decoder.finished:
                decoder.step()

            # Get the decoded text (binary bitstream)
            decoded_text = decoder.solve()
            elapsed = time.time() - start_time

            # Display the encoded plain text as it is the steganographic text
            self.show_decoded_text(encoded_text, file_name, elapsed)
            messagebox.showinfo("Decoding Complete", f"Decoding finished.\nTime Elapsed: {elapsed:.2f} seconds")
            logging.info(f"Decoding completed for file: {file_name}")
        except Exception as e:
            messagebox.showerror("Decoding Error", f"Error during decoding: {str(e)}")
            logging.error(f"Error during decoding: {str(e)}")



    def show_decoded_text(self, encoded_text, file_name, elapsed):
        """Show the encoded steganographic text in a new window."""
        result_window = tk.Toplevel(self.root)
        result_window.title("Decoded Steganographic Text")
        result_window.geometry("700x500")
        path_label = tk.Label(result_window, text=f"Decoded from: {file_name}\nTime Elapsed: {elapsed:.2f} seconds")
        path_label.pack(pady=5)
        text_box = tk.Text(result_window, wrap=tk.WORD, height=25, width=80)
        text_box.insert(tk.END, encoded_text)
        text_box.pack(pady=10)
        close_button = tk.Button(result_window, text="Close", command=result_window.destroy)
        close_button.pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = SteganographyApp(root)
    root.mainloop()
