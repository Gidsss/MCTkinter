import os
import random
from math import ceil, log2
import numpy as np
cimport numpy as np  # Cython import for NumPy
import markovify
import random
import huffman
import re

# -- Utility Functions ---

# Function to build the Markov model
def build_model(json_file: str):
    """ Takes in a json markov model and builds it. Returns the constructed Markov Model. """
    with open(json_file, "r") as f:
        return markovify.Text.from_json(f.read())

# Function to validate two bitstreams
def validate_bitstreams(bitstream1, bitstream2):
    """
    Validate two bit streams and returns a list of mismatched indices.

    Parameters:
    bitstream1 (numpy.ndarray or list): First bitstream to validate.
    bitstream2 (numpy.ndarray or list): Second bitstream to validate.

    Returns:
    bool: True if the bitstreams are valid, False otherwise.
    """
    # Convert input to NumPy arrays if they are not already
    arr1 = np.array(list(bitstream1), dtype=int)
    arr2 = np.array(list(bitstream2), dtype=int)
    len1 = len(arr1)
    len2 = len(arr2)
    min_len = min(len1, len2)
    max_len = max(len1, len2)

    mismatched_indices = np.where(arr1[:min_len] != arr2[:min_len])[0]
    extra_indices = np.arange(min_len, max_len)

    return np.concatenate((mismatched_indices, extra_indices))

# NumPy-based efficient bitstream conversion functions
def file_to_bitstream(file_path: str) -> str:
    """Convert file to binary bitstream using NumPy."""
    with open(file_path, 'rb') as file:
        file_data = np.frombuffer(file.read(), dtype=np.uint8)

    # Use NumPy's unpackbits for fast conversion
    bitstream = np.unpackbits(file_data)
    return ''.join(map(str, bitstream))

def bitstream_to_file(bitstream: str, output_file: str):
    """Convert a binary bitstream back into a binary file."""
    byte_data = [bitstream[i:i+8] for i in range(0, len(bitstream), 8)]
    byte_array = bytearray(int(byte, 2) for byte in byte_data)
    with open(output_file, 'wb') as file:
        file.write(byte_array)

# -- Enhanced Algorithms --
cdef class EnhancedEncoder:
    """
    Encodes a bitstream using a Markov Model with the enhanced algorithm.
    For basic usage, run `self.generate()` and get the generated output from `self.output`.
    """
    cdef object model  # Markov model object
    cdef str bitstream  # Bitstream string
    cdef int bitstream_length  # Length of the bitstream
    cdef list entrypoints  # List of entry points for the Markov model
    cdef object current_gram  # Current n-gram in Markov model processing
    cdef list output_tokens  # Output tokens list
    cdef bint exhausted  # Flag to check if exhausted
    cdef bint finished  # Flag to check if finished
    cdef int end_key  # End key for the encoded message

    def __init__(self, object model, str bitstream):
        self.model = model
        self.bitstream = bitstream
        self.bitstream_length = len(bitstream)
        self.entrypoints = self._get_entrypoints()

        self.current_gram = None
        self.output_tokens = []
        self.exhausted = True
        self.finished = False
        self.end_key = 0

    def _get_entrypoints(self):
        """Get valid entry points from the Markov model."""
        if self.model.state_size == 1:
            return [key for key in self.model.chain.model.get(("___BEGIN__",)).keys()]
        else:
            return [key[-1] for key in self.model.chain.model.keys() if key.count("___BEGIN__") == self.model.state_size - 1][1:]

    @property
    def output(self):
        """Returns the current state of the output string."""
        return " ".join(self.output_tokens)

    @property
    def finished(self):
        return self.finished

    def step(self):
        """Generates a new word for the output and appends it to the output string.

        Returns:
            float: The progress of the encoding process.
        """

        if self.finished:
            return 1

        if self.exhausted:
            self._choose_entrypoint()
        else:
            self._choose_next_token()

        return (self.bitstream_length - len(self.bitstream)) / self.bitstream_length

    def _choose_entrypoint(self):
        """Choose a new starting point (entrypoint) for the Markov chain."""
        self.exhausted = False
        next_token, removed, bit_length, encoded_index = self._consume_from_list(self.entrypoints)
        self.current_gram = (next_token,) if self.model.state_size == 1 else (*["___BEGIN__"] * (self.model.state_size - 1), next_token)

        if type(next_token) == tuple:
            self.output_tokens.extend(next_token)
        else:
            self.output_tokens.append(next_token)

        if not self.bitstream:
            self._inject_end_key(removed)

    def _choose_next_token(self):
        """Choose the next token in the Markov chain."""
        transitions = self._get_transitions(self.current_gram)
        if "___END__" in transitions:
            self.exhausted = True
            return
        next_token, removed, bit_length, encoded_index = self._consume_from_list(transitions)

        # Construct next gram
        next_gram = list(self.current_gram)
        next_gram.append(next_token)
        self.current_gram = tuple(next_gram[1:])

        if type(next_token) == tuple:
            self.output_tokens.extend(next_token)
        else:
            self.output_tokens.append(next_token)

        if not self.bitstream:
            self._inject_end_key(removed)

    def _inject_end_key(self, removed):
        """Inject the end key to mark the end of encoding."""
        self.end_key = len(removed)
        i = random.randint(0, len(self.output_tokens) - 1)
        self.output_tokens[i] += chr(self.end_key + 97)
        self.finished = True

    def generate(self):
        """Consumes the entire bitstream and generates the output for it."""
        while not self.finished:
            self.step()

        return self.output

    def _consume_from_list(self, lst):
        """Consume bits from the bitstream and choose an item from the list based on the bits."""
        list_length = len(lst)
        bit_length = ceil(log2(list_length))
        if list_length < 2 ** bit_length:
            bit_length -= 1

        encoded_index = 0 if bit_length == 0 else int(self.bitstream[:bit_length], 2)
        next_token = lst[encoded_index]
        removed = self.bitstream[:bit_length]
        self.bitstream = self.bitstream[bit_length:]

        return next_token, removed, bit_length, encoded_index

    def _get_transitions(self, gram):
        """Get possible transitions for the current gram in the Markov chain."""
        trans_matrix = self.model.chain.model[gram]
        trans_matrix = sorted(trans_matrix.items(), key=lambda kv: (kv[1]), reverse=True)
        transitions = [i[0] for i in trans_matrix]
        return transitions

cdef class EnhancedDecoder:
    """
    Decodes a steganographic text using a Markov Model with the enhanced algorithm.
    For basic usage, run `self.solve()` and get the generated output from `self.output`.
    """
    cdef object model  # Markov model object
    cdef list stega_text  # Steganographic text to decode
    cdef list entrypoints  # List of entry points for the Markov model
    cdef str output  # Decoded output
    cdef int endkey  # End key

    cdef object current_gram  # Current gram in the Markov model
    cdef bint exhausted  # Flag to check if exhausted
    cdef bint finished  # Flag to check if finished
    cdef int index  # Index for processing the stega_text

    def __init__(self, object model, str stega_text):
        self.model = model
        self.stega_text = stega_text.split(" ")
        self.entrypoints = self._get_entrypoints()
        self.current_gram = None
        self.exhausted = True
        self.finished = False
        self.index = 0
        self.output = ""
        self.endkey = 0

    @property
    def output(self):
        return self.output

    @property
    def finished(self):
        return self.finished

    def _get_entrypoints(self):
        """Get valid entry points from the Markov model."""
        if self.model.state_size == 1:
            return [key for key in self.model.chain.model.get(("___BEGIN__",)).keys()]
        else:
            return [key[-1] for key in self.model.chain.model.keys() if key.count("___BEGIN__") == self.model.state_size - 1][1:]

    def step(self):
        """Consumes a word from the steganographic text and appends the appropriate bits to the output.

        Returns:
            float: The progress of the decoding process.
        """

        # Finish if index is at the end of the stega text
        if self.index >= len(self.stega_text) - 1 and not self.exhausted:
            self.finished = True
            return 1

        if self.exhausted:
            self._choose_entrypoint()
        else:
            self._choose_next_token()

        return self.index / len(self.stega_text)


    def _choose_entrypoint(self):
        """Choose a new starting point (entrypoint) for the Markov chain."""
        self.exhausted = False
        token = self.stega_text[self.index]

        # Check for end key
        if token not in self.entrypoints:
            self.endkey = ord(token[-1]) - 97
            token = token[:-1]

        embedded_index = self.entrypoints.index(token)
        bit_length = ceil(log2(len(self.entrypoints)))
        if len(self.entrypoints) < 2 ** bit_length:
            bit_length -= 1
        bit_length = self.endkey if self.index == len(self.stega_text) - 1 else bit_length
        bit_string = bin(embedded_index)[2:].zfill(bit_length)

        self.current_gram = (token,) if self.model.state_size == 1 else (*["___BEGIN__"] * (self.model.state_size - 1), token)

        # Add bit string to output
        self.output += bit_string

    def _choose_next_token(self):
        """Choose the next token in the Markov chain."""
        transitions = self._get_transitions(self.current_gram)
        at_end = self.index == len(self.stega_text) - 1

        next_token = self.stega_text[self.index + 1] if self.index < len(self.stega_text) - 1 else ""

        # Get max possible bit length based on length of list
        list_length = len(transitions)
        bit_length = ceil(log2(list_length))
        if list_length < 2 ** bit_length:
            bit_length -= 1
            bit_length = 0 if list_length == 1 else bit_length

        if "___END__" in transitions:
            self.exhausted = True
            self.current_gram = None
            self.index += 1
            return
        else:
            next_token = "" if at_end else self.stega_text[self.index + 1]

        # Check for end key
        if next_token not in transitions and not at_end:
            self.endkey = ord(next_token[-1]) - 97
            next_token = next_token[:-1]
        bit_length = self.endkey if self.index == len(self.stega_text) - 2 else bit_length

        if bit_length != 0:
            embedded_index = "N/A" if at_end else transitions.index(next_token)
            bit_string = "" if at_end else bin(embedded_index)[2:].zfill(bit_length)
        else:
            embedded_index = "N/A"
            bit_string = ""

        # Construct gram
        next_gram = list(self.current_gram)
        next_gram.append(next_token)
        self.current_gram = tuple(next_gram[1:])

        # Add bit string to output
        self.output += bit_string

        self.index += 1


    def solve(self):
        """Consumes the entire steganographic text and generates an output bitstream."""
        while not self.finished:
            self.step()

        return self.output

    def _get_transitions(self, gram):
        """Get possible transitions for the current gram in the Markov chain."""
        trans_matrix = self.model.chain.model[gram]
        trans_matrix = sorted(trans_matrix.items(), key=lambda kv: (kv[1]), reverse=True)
        transitions = [i[0] for i in trans_matrix]
        return transitions

# -- Existing Algorithms --
cdef class ExistingEncoder:
    """
    Encodes a bitstream using a Markov Model with the existing algorithm.
    For basic usage, run `self.generate()` and get the generated output from `self.output`.
    """
    cdef object model
    cdef str bitstream
    cdef int bitstream_length
    cdef list entrypoints
    cdef tuple current_gram
    cdef list output_tokens
    cdef bint exhausted, finished
    cdef int c

    def __init__(self, model, str bitstream):
        self.model = model
        self.bitstream = bitstream
        self.bitstream_length = len(bitstream)
        self.entrypoints = [key for key in model.chain.model.keys() if "___BEGIN__" in key][1:]
        self.current_gram = None
        self.output_tokens = []
        self.exhausted = True
        self.finished = False
        self.c = 1

    @property
    def output(self):
        """Returns the current state of the output string."""
        return " ".join(self.output_tokens)

    @property
    def finished(self):
        return self.finished

    def step(self):
        """Generates a new word for the output and appends it to the output string.

        Returns:
            float: The progress of the encoding process.
        """
        if self.finished:
            return

        cdef int char_limit = 20
        cdef int matrix_limit = 10
        cdef int i, count
        cdef int tree_depth
        cdef str bits, next_token, removed
        cdef dict trans_matrix, huffman_code
        cdef list next_gram

        if self.exhausted:
            self.exhausted = False
            self.current_gram = random.choice(self.entrypoints)
            self.output_tokens.append(self.current_gram[1])
        else:
            trans_matrix = self.get_transition_matrix(self.current_gram)
            if len(trans_matrix) > 1:
                self.c += 1
                huffman_code = huffman.codebook([(k, v) for k, v in trans_matrix.items()])
                huffman_code = {v: k for k, v in huffman_code.items()}
                tree_depth = max([len(n) for n in huffman_code.keys()])

                count = 0
                for i in range(tree_depth, 0, -1):
                    if i >= len(self.bitstream):
                        continue
                    bits = self.bitstream[:i]
                    if bits in huffman_code:
                        next_token = huffman_code[bits]
                        count = i
                        break
                else:
                    # next_token = f"<{self.bitstream}>"
                    next_token = "<" + str(self.bitstream) + ">"
                    count = len(self.bitstream)

                removed = self.bitstream[:count]
                self.bitstream = self.bitstream[count:]
            else:
                next_token = list(trans_matrix.keys())[0]

            next_gram = list(self.current_gram)
            next_gram.append(next_token)
            self.current_gram = tuple(next_gram[1:])

            if next_token != "___END__":
                self.output_tokens.append(next_token)
            else:
                self.exhausted = True
                self.current_gram = None

        if not self.bitstream:
            self.finished = True

        return (self.bitstream_length - len(self.bitstream))/self.bitstream_length

    def get_transition_matrix(self, gram):
        return self.model.chain.model[gram]

    def generate(self):
        """Consumes the entire bitstream and generates the output for it."""
        while not self.finished:
            self.step()
        return self.output

cdef class ExistingDecoder:
    cdef object model
    cdef list stega_text
    cdef list entrypoints
    cdef int endkey
    cdef object current_gram
    cdef int index
    cdef bint exhausted
    cdef bint finished
    cdef str output

    def __init__(self, model, str stega_text):
        self.model = model
        self.stega_text = stega_text.split(" ")
        self.entrypoints = [key[1] for key in model.chain.model.keys() if "___BEGIN__" in key][1:]
        self.endkey = 0
        self.current_gram = None
        self.index = 0
        self.exhausted = True
        self.finished = False
        self.output = ""

    @property
    def output(self):
        return self.output

    @property
    def finished(self):
        return self.finished

    def step(self):
        """Consumes a word from the steganographic text and appends the appropriate bits to the output.

        Returns:
            float: The progress of the decoding process.
        """
        cdef int matrix_limit = 10
        cdef int char_limit = 20
        cdef dict trans_matrix
        cdef str previous, token, next_token, bit_string
        cdef list next_gram
        cdef int tree_depth
        cdef object huffman_code
        cdef bint at_end

        if self.index >= len(self.stega_text) - 1 and not self.exhausted:
            self.finished = True
            return

        previous = self.output if len(self.output) <= char_limit else "...{self.output[-char_limit:]}"
        if self.exhausted:
            token = self.stega_text[self.index]
            self.current_gram = ("___BEGIN__", token)
            self.exhausted = False
        else:
            trans_matrix = self.get_transition_matrix(self.current_gram)
            at_end = self.index == len(self.stega_text) - 1
            next_token = "" if at_end else self.stega_text[self.index + 1]

            if len(trans_matrix) > 1:
                huffman_code = huffman.codebook([(k, v) for k, v in trans_matrix.items()])
                tree_depth = max(map(lambda n: len(n), huffman_code.keys()))

                if self.current_gram[1][-1] in ".?!" and "___END__" in trans_matrix:
                    if next_token not in trans_matrix:
                        next_token = "___END__"
                        self.exhausted = True

                if re.match(r"<[01]+>", next_token):
                    bit_string = ""
                    next_token = "INVALID TOKEN {next_token}"
                else:
                    bit_string = "" if at_end else huffman_code[next_token]
            else:
                tree_depth = 0
                bit_string = ""

                if self.current_gram[1][-1] in ".?!" and "___END__" in trans_matrix:
                    next_token = "___END__"
                    self.exhausted = True


            next_gram = list(self.current_gram)
            next_gram.append(next_token)
            self.current_gram = tuple(next_gram[1:])

            self.index += 1
            self.output += bit_string

        return self.index / len(self.stega_text)

    def solve(self):
        """Consumes the entire steganographic text and generates an output bitstream."""
        while not self.finished:
            self.step()

        return self.output

    def get_transition_matrix(self, gram):
        return self.model.chain.model[gram]
