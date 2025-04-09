# setup.py
from setuptools import setup
from Cython.Build import cythonize
import numpy

setup(
    # Specify the Cython extension module to build
    ext_modules=cythonize("thesis_toolkit.pyx"),

    # Tell setuptools *not* to automatically look for or include
    # any top-level pure Python (.py) modules.
    py_modules=[],

    # Include necessary directories for C compilation (like numpy headers)
    include_dirs=[numpy.get_include()]
)
