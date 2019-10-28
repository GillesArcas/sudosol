# sudosol

# ![python-3.6|3.7|3.8](https://img.shields.io/badge/python-3.6%20|%203.7%20|%203.8-blue) [![Build Status](https://travis-ci.org/GillesArcas/sudosol.svg?branch=master)](https://travis-ci.org/GillesArcas/sudosol) [![Coverage Status](https://coveralls.io/repos/github/GillesArcas/sudosol/badge.svg?branch=master)](https://coveralls.io/github/GillesArcas/sudosol?branch=master)

sudosol is a sudoku solver using only human techniques. Currently, sudosol implements the techniques from Simple Sudoku program (Simple Sudoku Technique Set, ssts). These techniques are:

- naked and hidden singles, pairs, triples and quads,
- locked candidates (pointing and claiming),
- X-wings and swordfishes,
- XY-wings,
- simple coloring and multi coloring.

More techniques are being implemented, either equivalent to Simple Sudoku techniques, or beyond Simple Sudoku techniques. Currently, they are:

- locked pairs and triples, turbot fish, skyscraper, 2-string kite, empty rectangle,
- jellyfish, X-chains, XY-chains.

Tests make sure each technique is handled correctly.

sudosol requires python >= 3.6.
