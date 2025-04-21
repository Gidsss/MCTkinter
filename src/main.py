import sys
import os
import time
import logging
import threading
import tkinter as tk
import pickle
from tkinter import filedialog, messagebox, ttk, scrolledtext
from tqdm import tqdm
import sqlite3

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
        self.file_table = ttk.Treeview(root, columns=("Name", "Algorithm", "Filesize", "Timestamp"), show="headings")
        self.file_table.heading("Name", text="File Name")
        self.file_table.heading("Algorithm", text="Algorithm")
        self.file_table.heading("Filesize", text="Filesize (KB)")
        self.file_table.heading("Timestamp", text="Timestamp")
        self.file_table.pack(pady=10, fill=tk.BOTH, expand=True)

        # View/Decode Button
        self.decode_button = tk.Button(root, text="View", command=self.decode_selected)
        self.decode_button.pack(pady=5)

        # Delete Button
        self.delete_button = tk.Button(root, text="Delete Selected", command=self.delete_selected)
        self.delete_button.pack(pady=5)

        # Populate file table on startup
        self.load_file_table()

        # For temp storage of original bit streams
        self.bit_memory = {}

        if os.path.exists("bit_memory.pkl"):
            with open("bit_memory.pkl", "rb") as f:
                self.bit_memory = pickle.load(f)
        else:
            with open("bit_memory.pkl", "wb") as f:
                pickle.dump(self.bit_memory, f)

    def load_file_table(self):
        """Load file records into the table."""
        self.file_table.delete(*self.file_table.get_children())
        for record in get_all_files():
            file_name, algorithm, timestamp, encoded_text = record[1], record[2], record[4], record[5]
            size_kb = len(encoded_text.encode('utf-8')) / 1024
            self.file_table.insert("", "end", values=(file_name, algorithm, timestamp, f"{size_kb:.2f}"))

    def delete_selected(self):
        """Delete selected record from database and table."""
        selected_item = self.file_table.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a record to delete.")
            return

        file_name, algorithm = self.file_table.item(selected_item, "values")[0:2]

        confirm = messagebox.askyesno("Confirm Deletion", f"Are you sure you want to delete '{file_name}' using {algorithm}?")
        if not confirm:
            return

        # Delete from database and memory
        try:
            # Optional: also delete from bit_memory
            if file_name + algorithm in self.bit_memory:
                del self.bit_memory[file_name + algorithm]
                with open("bit_memory.pkl", "wb") as f:
                    pickle.dump(self.bit_memory, f)

            # Delete from DB
            conn = sqlite3.connect("steganography.db")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_history WHERE file_name = ? AND algorithm = ?", (file_name, algorithm))
            conn.commit()
            conn.close()

            self.file_table.delete(selected_item)
            messagebox.showinfo("Deleted", "Record successfully deleted.")
        except Exception as e:
            messagebox.showerror("Deletion Error", f"Could not delete record: {e}")

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
                progress = {'value': 0}

                def update_progress_bar():
                    elapsed_time = time.time() - start_time

                    # Once finished, destroy window and quit loop
                    if progress['value'] == 100:
                        messagebox.showinfo("Encoding Complete", f"Encoding finished.\nTime Elapsed: {elapsed_time:.2f} seconds")
                        progress_window.destroy()
                        return

                    # Update time and percent labels
                    time_label.config(text=f"Time Elapsed: {elapsed_time:.2f} seconds | {progress['value']:.2f}%")

                    # Update progress bar
                    progress_bar['value'] = progress['value']
                    progress_window.update_idletasks()
                    self.root.after(100, update_progress_bar)

                def encode_task():
                    try:
                        encoder = ExistingEncoder(model, bitstream) if algorithm == "Existing Algorithm" else EnhancedEncoder(model, bitstream)
                        while not encoder.finished:
                            progress['value'] = encoder.step() * 100

                        encoded_text = encoder.output
                        save_file_record(file_name, algorithm, "Encode", encoded_text, self.file_path)
                        self.bit_memory[file_name+algorithm] = bitstream
                        with open("bit_memory.pkl", "wb") as f:
                            pickle.dump(self.bit_memory, f)
                        filesize_kb = os.path.getsize(self.file_path) // 1024
                        self.file_table.insert("", "end", values=(file_name, algorithm, f"{filesize_kb} KB", time.strftime("%Y-%m-%d %H:%M:%S")))

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
        """Open a window to view encoded steganographic text and provide a Decode button."""
        selected_item = self.file_table.selection()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a file from the table.")
            return

        file_name, algorithm = self.file_table.item(selected_item, "values")[:2]

        try:
            encoded_text = get_encoded_text(file_name, algorithm)
            if not encoded_text:
                messagebox.showwarning("Data Not Found", "Encoded text not found in the database.")
                return

            # Show the encoded text and a Decode button
            self.show_encoded_viewer_paginated(encoded_text.strip(), file_name)

        except Exception as e:
            messagebox.showerror("View Error", f"Error retrieving encoded text: {str(e)}")
            logging.error(f"Error retrieving encoded text: {str(e)}")

    def show_encoded_viewer_paginated(self, encoded_text, file_name):
        """Paginated display of long encoded text with navigation buttons."""
        words = encoded_text.split()
        page_size = 5000
        pages = [" ".join(words[i:i+page_size]) for i in range(0, len(words), page_size)]
        total_pages = len(pages)
        current_page = tk.IntVar(value=0)

        window = tk.Toplevel(self.root)
        window.title(f"Encoded Text: {file_name}")
        window.geometry("800x600")

        label = tk.Label(window, text=f"Encoded from: {file_name}", font=("Arial", 10))
        label.pack(pady=5)

        # Text Display
        text_box = scrolledtext.ScrolledText(window, wrap=tk.WORD, width=100, height=25)
        text_box.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        def update_text():
            index = current_page.get()
            text_box.config(state=tk.NORMAL)
            text_box.delete("1.0", tk.END)
            text_box.insert(tk.END, pages[index])
            text_box.config(state=tk.DISABLED)
            page_label.config(text=f"Page {index + 1} of {total_pages}")

        # Navigation Controls
        nav_frame = tk.Frame(window)
        nav_frame.pack(pady=10)

        def prev_page():
            if current_page.get() > 0:
                current_page.set(current_page.get() - 1)
                update_text()

        def next_page():
            if current_page.get() < total_pages - 1:
                current_page.set(current_page.get() + 1)
                update_text()

        tk.Button(nav_frame, text="Previous", command=prev_page).pack(side=tk.LEFT, padx=10)
        page_label = tk.Label(nav_frame, text="")
        page_label.pack(side=tk.LEFT)
        tk.Button(nav_frame, text="Next", command=next_page).pack(side=tk.LEFT, padx=10)

        # Decode + Close buttons
        button_frame = tk.Frame(window)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Decode", command=lambda: [window.destroy(), self.start_decoding_with_progress(encoded_text, file_name)]).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Close", command=window.destroy).pack(side=tk.LEFT)

        update_text()

    def start_decoding_with_progress(self, encoded_text, file_name):
        """Decode with progress bar and display result file + metrics."""
        selected_item = self.file_table.selection()
        algorithm = self.file_table.item(selected_item, "values")[1]

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Decoding Progress")
        progress_window.geometry("400x150")

        progress_label = tk.Label(progress_window, text="Decoding in progress...")
        progress_label.pack(pady=5)

        time_label = tk.Label(progress_window, text="Time Elapsed: 0.00 seconds | 0%")
        time_label.pack(pady=5)

        progress_bar = ttk.Progressbar(progress_window, length=300, mode="determinate")
        progress_bar.pack(pady=10)

        progress = {'value': 0}
        start_time = time.time()

        def update_progress_bar():
            elapsed_time = time.time() - start_time

            if progress['value'] == 100:
                progress_window.destroy()
                return
            
            # Update time and percent labels
            time_label.config(text=f"Time Elapsed: {elapsed_time:.2f} seconds | {progress['value']:.2f}%")

            # Update progress bar
            progress_bar['value'] = progress['value']
            self.root.update_idletasks()
            self.root.after(100, update_progress_bar)

        def decode_task():
            try:
                selected_item = self.file_table.selection()
                file_name = self.file_table.item(selected_item, "values")[0]

                decoder = ExistingDecoder(model, encoded_text) if algorithm == "Existing Algorithm" else EnhancedDecoder(model, encoded_text)
                while not decoder.finished:
                    progress['value'] = decoder.step() * 100

                decoded_bits = decoder.output
                output_path = os.path.join(OUTPUT_DIR, f"decoded_{algorithm.split(" ")[0].lower()}_{file_name}")
                bitstream_to_file(decoded_bits, output_path)

                elapsed = time.time() - start_time
                encoded_size = len(encoded_text) * 8
                original_bits = self.bit_memory[file_name+algorithm]
                self.show_decoded_file(output_path, elapsed, encoded_size, original_bits, decoded_bits)

            except Exception as e:
                progress_window.destroy()
                messagebox.showerror("Decoding Error", f"Error during decoding: {str(e)}")
                logging.error(f"Error during decoding: {str(e)}")

        self.root.after(100, update_progress_bar)
        threading.Thread(target=decode_task, daemon=True).start()

    def show_decoded_file(self, filepath, elapsed, encoded_size, original_bits, decoded_bits):
        """Display decoded file metrics and success info."""
        window = tk.Toplevel(self.root)
        window.title("Decoded File and Metrics")
        window.geometry("600x300")

        label = tk.Label(window, text=f"Decoded File: {filepath}\nTime Elapsed: {elapsed:.2f} seconds", font=("Arial", 10))
        label.pack(pady=10)

        metrics_frame = tk.Frame(window)
        metrics_frame.pack(pady=5)

        original_size = os.path.getsize(filepath)
        embedding_rate = original_size / encoded_size * 100
        tk.Label(metrics_frame, text="Embedding Rate:", anchor="w", width=25).grid(row=1, column=0, sticky="w")
        tk.Label(metrics_frame, text=f"{embedding_rate:0.2f}%").grid(row=1, column=1, sticky="w")

        validity = validate_bitstreams(original_bits, decoded_bits)
        validity_string = "Valid" if len(validity) == 0 else "Invalid"
        tk.Label(metrics_frame, text="Validity Check:", anchor="w", width=25).grid(row=2, column=0, sticky="w")
        tk.Label(metrics_frame, text=validity_string).grid(row=2, column=1, sticky="w")

        # Create two text widgets displaying the two bit streams
        # Pad spaces to shorter bit stream
        if len(original_bits) < len(decoded_bits):
            original_bits += " " * (len(decoded_bits) - len(original_bits))
        else:
            decoded_bits += " " * (len(original_bits) - len(decoded_bits))
        # Truncate the bitstreams to a max of 10000 bits, getting the second portion
        original_bits = original_bits[-10000:]
        decoded_bits = decoded_bits[-10000:]

        text_area1 = tk.Text(window, width=10, height=1, wrap="none", pady=0)
        text_area2 = tk.Text(window, width=10, height=1, wrap="none", pady=0)
        text_area1.insert("1.0", original_bits)
        text_area2.insert("1.0", decoded_bits)
        text_area1.config(state="disabled")
        text_area2.config(state="disabled")
        tk.Label(window, text="Original Bits:").pack()
        text_area1.pack(side="top", fill="both", expand=True)
        tk.Label(window, text="Decoded Bits:").pack()
        text_area2.pack(side="top", fill="both", expand=True)

        # Initialize tag
        text_area1.tag_config("match", background="palegreen")
        text_area1.tag_config("mismatch", background="tomato")
        text_area2.tag_config("match", background="palegreen")
        text_area2.tag_config("mismatch", background="tomato")

        # Color matching and mismatching bits
        text_area1.tag_add("match", "1.0", tk.END)
        text_area2.tag_add("match", "1.0", tk.END)

        for index in validity:
            text_area1.tag_add("mismatch", f"1.{index}", f"1.{index+1}")
            text_area2.tag_add("mismatch", f"1.{index}", f"1.{index+1}")

        # Create a horizontal scrollbar
        scrollbar = tk.Scrollbar(window, orient="horizontal")
        scrollbar.pack(fill="x")
        # Configure the scrollbar to control both text areas
        scrollbar.config(command=lambda *args: [text_area1.xview(*args), text_area2.xview(*args)])

        open_btn = tk.Button(window, text="Open File", command=lambda: os.startfile(filepath))
        open_btn.pack(pady=10)

        close_btn = tk.Button(window, text="Close", command=window.destroy)
        close_btn.pack(pady=5)

if __name__ == "__main__":
    root = tk.Tk()
    app = SteganographyApp(root)
    root.mainloop()
