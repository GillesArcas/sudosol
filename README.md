# sudosol

# [![Build Status](https://travis-ci.org/GillesArcas/sudosol.svg?branch=master)](https://travis-ci.org/GillesArcas/sudosol)

sudosol is a sudoku solver using only human techniques. Currently, sudosol implements the techniques from Simple Sudoku program (Simple Sudoku Technique Set, ssts). These techniques are:

- naked and hidden singles, pairs, triples and quads,
- locked candidates (pointing and claiming),
- X-wings and swordfishes,
- XY-wings,
- simple coloring and multi coloring.

Tests make sure each technique is handled correctly.

sudosol requires python >= 3.6.
