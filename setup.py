#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import glob
import codecs
from setuptools import setup, find_packages


def read(*parts):
    here = os.path.abspath(os.path.dirname(__file__))
    # intentionally *not* adding an encoding option to open, See:
    #   https://github.com/pypa/virtualenv/issues/201#issuecomment-3145690
    with codecs.open(os.path.join(here, *parts), 'r') as fp:
        return fp.read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^VERSION = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


if __name__ == "__main__":
    setup(
        name='sudosol',
        version=find_version("sudosol", "sudosol.py"),
        license='MIT',
        url='https://github.com/GillesArcas/sudosol',
        author='Gilles Arcas',
        author_email='gilles.arcas@gmail.com',
        description='Sudoku solver with human techniques\n',
        install_requires=['colorama', 'clipboard'],
        packages=find_packages(),
        entry_points={
            'console_scripts': ['sudosol = sudosol.sudosol:main']
        },
        zip_safe=True,
        include_package_data=True,
        data_files=[
           ('Lib/site-packages/sudosol', ['README.md', 'LICENSE'] + glob.glob('tests/*.*')),
        ]
    )
