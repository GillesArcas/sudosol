# sudosol

# ![python-3.6|3.7|3.8](https://img.shields.io/badge/python-3.6%20|%203.7%20|%203.8-blue) [![Build Status](https://travis-ci.org/GillesArcas/sudosol.svg?branch=master)](https://travis-ci.org/GillesArcas/sudosol) [![Coverage Status](https://coveralls.io/repos/github/GillesArcas/sudosol/badge.svg?branch=master)](https://coveralls.io/github/GillesArcas/sudosol?branch=master)

sudosol is a sudoku solver using only human techniques. Currently, sudosol implements the techniques from Simple Sudoku program (Simple Sudoku Technique Set, ssts). These techniques are:

- naked and hidden single, pair, triple and quad,
- locked candidate (pointing and claiming),
- X-wing and swordfish,
- XY-wing,
- simple coloring and multi coloring.

More techniques are being implemented, either equivalent to Simple Sudoku techniques, or beyond Simple Sudoku techniques. Currently, they are:

- locked pair and triple, turbot fish, skyscraper, 2-string kite, empty rectangle,
- jellyfish, finned and sashimi X-wing, finned and sashimi swordfish, finned and sashimi jellyfish, XYZ-wing, W-wing, X-chain, XY-chain, BUG+1, uniqueness test 1, 2, 3, 4, 5 and 6, hidden rectangle, avoidable rectangle type 1 and type 2, Sue de Coq.

Tests make sure each technique is handled correctly. 

sudosol requires python >= 3.6.

## Command line

All commands are related to solving or testing.

```
--solve 
```

Solve a grid from the command line argument, the clipboard or a file:

`--solve 00000001270006000 ... 000030800502000000`

`--solve 24,79,2679,349,8,2379,69,1,5,3, ... ,79,9,1,3,2,4,5,7,6,8,,3,9,1,7,6,8,1,39,39,5`

Solve the grid given as argument. See input formats for formats taken into account.

`--solve clipboard`

Solve the grid stored in clipboard.  See input formats for formats taken into account.

`--solve <filename>`

Solve the grid stored in a file.

## Input formats

*All the formats described below may be read from the clipboard or from a file by sudosol.*

#### String formats

###### s81 format

A grid is stored in a 81 character strings.  Unknown digits are stored with a single character not in [1-9]. Usually, the character used for unknow digits is '.' or '0'.

Example:

`00000001270006000 ... 000030800502000000`

###### CSV format

This format stores candidates separated with commas (',').

Example:

`24,79,2679,349,8,2379,69,1,5,3, ... ,79,9,1,3,2,4,5,7,6,8,,3,9,1,7,6,8,1,39,39,5`

###### GVC format (Given, Value, Candidates)

This format enables to store precisely the resolution state of a grid by identifying for each cell its content as a given, prefixed with 'g', a value (not a given), prefixed with 'v', or a list of candidates, prefixed with 'c'.

Example:

`v1c368g9g7c368g5c346c346g2g7c236g5c369c2369g4c369g8v1c234c2368c23468g1 ...`

####  Matrix formats

###### Value matrix

 Values are given in a nine lines matrix. Some horizontal and vertical separators or delimiters may be added. Horizontal separators are lines containing at least a dash ('-'). Vertical separators are the '|' character. Unknown digits follow the same rule as for s81 format.

Examples:

```
6.1|...|.78   4XXX91XX8   *-----------*
...|213|.4.   XXX2X8XXX   |x42|63x|xx5|
...|.6.|.1.   X1XX53X6X   |xx5|27x|xxx|
-----------   XX31X79XX   |xxx|954|x28|
..2|9..|4..   XX1XX97XX   |---+---+---|
8.4|1.6|9.3   XX75X23XX   |19x|862|x5x|
..9|..2|5..   X64X1582X   |xx3|145|2x9|
-----------   1XX9X46XX   |52x|397|xx6|
.1.|.5.|...   5XXX261X4   |---+---+---|
.4.|387|...               |759|416|xx2|
73.|...|8.6               |231|589|467|
                          |4xx|723|591|
                          *-----------*
```

###### Candidate matrix

Candidates in matrix form. Candidates are separated by at least one space character or a vertical separator. Same description of horizontal and vertical separators as for given matrices.

Example:

```
 *--------------------------------------------------------------------*
 | 13678  12478  12346  | 278    5      9      | 4678   1478   4678   |
 | 1378   178    9      | 6      4      378    | 2      1578   578    |
 | 678    5      246    | 278    1      278    | 46789  478    3      |
 |----------------------+----------------------+----------------------|
 | 2      48     45     | 458    7      1      | 3      9      4568   |
 | 1589   6      145    | 458    3      58     | 4578   2      4578   |
 | 58     3      7      | 9      2      568    | 4568   458    1      |
 |----------------------+----------------------+----------------------|
 | 4      127    1235   | 1257   9      257    | 578    6      2578   |
 | 3579   279    8      | 257    6      4      | 1      357    2579   |
 | 15679  1279   1256   | 3      8      257    | 4579   457    24579  |
 *--------------------------------------------------------------------*
```

#### Simple Sudoku formats

###### SS clipboard format

When pasting a grid into the clipboard Simple Sudoku stores:

- a given matrix and a candidate matrix when starting,
- a given matrix, a value matrix and a candidate matrix during game,
- a given matrix, a value matrix and a candidate matrix when solved.

###### SS file format

When saving a file, Simple Sudoku stores:

- a given matrix,
- the history of moves described next.

Example:

```
 *-----------*
 |..9|7.5|..2|
 |7.5|..4|.8.|
 |...|1..|...|
 |---+---+---|
 |6..|...|.5.|
 |.4.|...|.9.|
 |.7.|...|..8|
 |---+---+---|
 |...|..9|...|
 |.1.|2..|5.3|
 |8..|5.6|1..|
 *-----------*

I001
I171
I581
I521
E60002
E45002
E49012
E51022
I265
I555
```

Each move is stored as one or more lines prefixed with 'I' for insertion and 'E' for exclusion.

For insertion lines, the format is `Innd`, where nn is the sequential number (0-80, left to right, top to bottom) of the cell and d is the value to set.

For exclusion lines, the format is `EnnppD`, with nn as before, pp is an index of the cells concerned by the exclusion move, and D is a list of at most eight digits.