import argparse
import os
import sys
import re
import itertools
import glob
import random
import time
import io
import itertools

from collections import defaultdict
from enum import Enum
from contextlib import redirect_stdout
from tqdm import tqdm

import clipboard
import colorama
from colorama import Fore
from icecream import ic

import dlx
try:
    import dlx_sudoku
except:
    from . import dlx_sudoku


VERSION = '0.1'


# Data structures


ALLCAND = {1, 2, 3, 4, 5, 6, 7, 8, 9}
ALLDIGITS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


class Cell:
    def __init__(self, cellnum):
        self.given = False
        self.value = None
        self.candidates = set(range(1, 10))
        self.cellnum = cellnum
        self.rownum = cellnum // 9
        self.colnum = cellnum % 9
        self.boxnum = (self.rownum // 3) * 3 + self.colnum // 3
        self.boxrownum = self.cellnum // 3
        self.boxcolnum = self.colnum * 3 + self.rownum // 3

        # to be completed in grid.__init__
        self.row = set()
        self.col = set()
        self.box = set()
        self.boxrow = set()
        self.boxcol = set()
        self.peers = set()

    def __str__(self):
        """format cell as value or candidates
        """
        if self.value:
            return str(self.value) + '.'
        else:
            return ''.join(str(_) for _ in sorted(list(self.candidates)))

    def strcoord(self):
        """format cell as coordinates
        """
        return f'r{self.rownum + 1}c{self.colnum + 1}'

    def __lt__(self, other):
        return self.rownum < other.rownum or (self.rownum == other.rownum and self.colnum < other.colnum)

    def reset(self):
        self.given = False
        self.value = None
        self.candidates = set(range(1, 10))

    def set_value(self, digit, given=False):
        self.given = given
        self.value = digit
        self.candidates = set()

    def discard(self, digit):
        """remove a candidate from cell
        """
        self.candidates.discard(digit)

    def mrownum(self):
        return self.rownum

    def mcolnum(self):
        return self.colnum

    def mboxrow(self):
        return self.boxrow

    def mboxcol(self):
        return self.boxcol

    def is_pair(self):
        return len(self.candidates) == 2

    def same_digit_in_row(self, digit) -> set:
        """return all cells in self row with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.row if digit in peer.candidates)

    def same_digit_in_col(self, digit) -> set:
        """return all cells in self col with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.col if digit in peer.candidates)

    def same_digit_in_box(self, digit) -> set:
        """return all cells in self box with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.box if digit in peer.candidates)

    def same_digit_peers(self, digit) -> set:
        """return all cells in self peers with digit as candidate (not
        including self)
        """
        return set(peer for peer in self.peers if digit in peer.candidates)

    def alone_in_row(self, digit):
        return next((False for peer in self.row if digit in peer.candidates and peer != self), True)

    def alone_in_col(self, digit):
        return next((False for peer in self.col if digit in peer.candidates and peer != self), True)

    def alone_in_box(self, digit):
        return next((False for peer in self.box if digit in peer.candidates and peer != self), True)

    def conjugates(self, digit):
        rowpeers = self.same_digit_in_row(digit)
        colpeers = self.same_digit_in_col(digit)
        boxpeers = self.same_digit_in_box(digit)
        conj = set()
        conj = conj.union(rowpeers if len(rowpeers) == 2 else set())
        conj = conj.union(colpeers if len(colpeers) == 2 else set())
        conj = conj.union(boxpeers if len(boxpeers) == 2 else set())
        conj.discard(self)
        return conj


class Grid:
    def __init__(self):
        """create a grid without known values
        """
        # make the list of 81 cells
        self.cells = [Cell(cellnum) for cellnum in range(81)]

        # make the list of 9 rows
        self.rows = [self.cells[i:i + 9] for i in range(0, 81, 9)]

        # make the list of 9 cols
        self.cols = [x for x in zip(*self.rows)]

        # make the list of 9 boxes
        self.boxes = []
        for i in (0, 3, 6):
            rows = self.rows[i:i + 3]
            self.boxes.append(rows[0][0:3] + rows[1][0:3] + rows[2][0:3])
            self.boxes.append(rows[0][3:6] + rows[1][3:6] + rows[2][3:6])
            self.boxes.append(rows[0][6:9] + rows[1][6:9] + rows[2][6:9])

        # make the list of horizontal triplets
        self.boxrows = [self.cells[i:i + 3] for i in range(0, 81, 3)]

        # make the list of vertical triplets
        self.boxcols = []
        for col in self.cols:
            self.boxcols.extend([col[i:i + 3] for i in range(0, 9, 3)])

        # make the list of complements of triplets in rows:
        self.rows_less_boxrow = []
        for triplet in self.boxrows:
            row_less_boxrow = [cell for cell in self.rows[triplet[0].rownum] if cell not in triplet]
            self.rows_less_boxrow.append(row_less_boxrow)

        # make the list of complements of triplets in cols:
        self.cols_less_boxcol = []
        for triplet in self.boxcols:
            col_less_boxcol = [cell for cell in self.cols[triplet[0].colnum] if cell not in triplet]
            self.cols_less_boxcol.append(col_less_boxcol)

        # make the list of complements of horizontal triplets in boxes:
        self.boxes_less_boxrow = []
        for triplet in self.boxrows:
            box_less_boxrow = [cell for cell in self.boxes[triplet[0].boxnum] if cell not in triplet]
            self.boxes_less_boxrow.append(box_less_boxrow)

        # make the list of complements of vertical triplets in boxes:
        self.boxes_less_boxcol = []
        for triplet in self.boxcols:
            box_less_boxcol = [cell for cell in self.boxes[triplet[0].boxnum] if cell not in triplet]
            self.boxes_less_boxcol.append(box_less_boxcol)

        # init cell data
        for cell in self.cells:
            cell.row = self.rows[cell.rownum]
            cell.col = self.cols[cell.colnum]
            cell.box = self.boxes[cell.boxnum]
            cell.boxrow = self.boxrows[cell.boxrownum]
            cell.boxcol = self.boxcols[cell.boxcolnum]

        # peers
        # properties: x not in x.peers, x in y.peers equivalent to y in x.peers
        for cell in self.cells:
            cell.peers = sorted(cellunion(cell.row, cellunion(cell.col, cell.box)))
            cell.peers.remove(cell)

        # init history
        self.history = []
        self.history_top = -1

        # cell decoration when tracing ('color' or 'char')
        self.decorate = 'color'

    def reset(self):
        self.history = []
        self.history_top = -1
        for cell in self.cells:
            cell.reset()

    def units(self):
        return itertools.chain(self.rows, self.cols, self.boxes)

    def input(self, string):
        # breakpoint()
        if re.match(r'[\d.]{81}$', string):
            self.input_s81(string)
        elif re.match('([1-9]{1,9},){80}[1-9]{1,9}$', string):
            self.input_csv(string)
        elif re.match(r'([gvc][1-9]{1,9}){81}$', string):
            self.input_gvc(string)
        elif string81 := grid_to_string81(string):
            self.input_s81(string81)
        elif stringcsv := grid_to_csv(string):
            self.input_csv(stringcsv)
        elif given_values_candidates := load_ss_clipboard(self, string):
            self.input_gvc_strings(*given_values_candidates)
        elif given_history := load_ss_grid_and_history(string):
            self.input_grid_and_history(*given_history)
        else:
            raise SudokuError(f'illegal grid format in string: {string}')

    def input_s81(self, str81, autofilter=True, given=True):
        """load a 81 character string of given values
        """
        self.reset()
        for cell, char in zip(self.cells, str81):
            if char in '123456789':
                if autofilter is False:
                    cell.value = int(char)
                    cell.given = given
                    cell.candidates = set()
                else:
                    self.set_value(cell, int(char), given=given)

    def input_csv(self, strcand):
        """load a comma separated list of candidates, a single candidate is
        considered as a given value
        """
        self.reset()
        for index, candidates in enumerate(strcand.split(',')):
            if len(candidates) == 1:
                self.set_value(self.cells[index], int(candidates[0]), given=True)
            else:
                self.cells[index].candidates = set(int(_) for _ in candidates)

    def input_gvc_strings(self, given, values, candidates):
        """
        """
        self.reset()
        for cell, g, v, c in zip(self.cells, given, values, candidates.split(',')):
            if g in '123456789':
                cell.value = int(g)
                cell.given = True
                cell.candidates = set()
            elif v in '123456789':
                cell.value = int(v)
                cell.given = False
                cell.candidates = set()
            else:
                cell.candidates = set([int(_) for _ in c])

    def input_grid_and_history(self, given, history):
        self.reset()
        self.input_s81(given)
        for line in history.splitlines():
            if match := re.match(r'I(\d\d)([1-9])', line):
                cell_index = int(match[1])
                cell = self.cells[cell_index]
                cand = int(match[2])
                discarded = self.set_value(cell, cand)
                self.push(('Insert', 'value', cell, cand, discarded))
            elif match := re.match(r'E(\d\d)(\d\d)([1-9]{1,8})', line):
                # TODO: gather cells within same move
                cell_index = int(match[1])
                cell = self.cells[cell_index]
                cell_num = int(match[2])
                candidates = match[3]
                for cand in candidates:
                    cell.discard(int(cand))
                self.push(('Exclude', 'discard', {int(c): [cell] for c in candidates}))

    def input_gvc(self, str):
        """load a given-value-candidates string ([gvc][1-9]{1,9}){81}
        """
        self.reset()
        for index, s in enumerate(re.findall(r'[gvc][1-9]{1,9}', str)):
            if s[0] == 'g':
                self.set_value(self.cells[index], int(s[1]), given=True)
            elif s[0] == 'v':
                self.set_value(self.cells[index], int(s[1]), given=False)
            else:
                self.cells[index].candidates = set(int(_) for _ in s[1:])

    def output_s81(self):
        """return a 81 character string
        """
        return ''.join(str(cell.value) if cell.value else '.' for cell in self.cells)

    def output_csv(self):
        """return a comma separated list of candidates, a value is considered
         as a single candidate
        """
        return ','.join(str(cell.value) if cell.value else ''.join(str(_) for _ in sorted(cell.candidates)) for cell in self.cells)

    def output_gvc(self):
        """return a given-value-candidates string ([gvc][1-9]{1,9}){81}
        """
        lst = []
        for cell in self.cells:
            if cell.given:
                lst.append(f'g{cell.value}')
            elif cell.value:
                lst.append(f'v{cell.value}')
            else:
                lst.append('c' + ''.join(str(_) for _ in sorted(cell.candidates)))
        return ''.join(lst)

    def compare_string(self, ref):
        if re.match(r'^[\d.]{81}$', ref):
            return self.output_s81() == ref
        elif re.match(r'^([1-9]{1,9},){80}\d{1,9}$', ref):
            return self.output_csv() == ref
        elif re.match(r'^([gvc][1-9]{1,9}){81}$', ref):
            str = self.output_gvc()
            str = re.sub(r'c([1-9]([gvc]|$))', r'v\1', str)
            ref = re.sub(r'c([1-9]([gvc]|$))', r'v\1', ref)
            return str == ref
        else:
            raise ValueError

    def cell_rc(self, irow, icol):
        return self.rows[irow][icol]

    def box_rc(self, irow, icol):
        return self.boxes[(irow // 3) * 3 + icol // 3]

    def set_value(self, cell, digit, given=False):
        discarded = defaultdict(set)
        for candidate in cell.candidates:
            discarded[candidate].add(cell)
        cell.set_value(digit, given=given)

        for peer in cell.peers:
            if digit in peer.candidates:
                peer.discard(digit)
                discarded[digit].add(peer)

        return discarded

    def solved(self):
        return all(cell.value is not None for cell in self.cells)

    def dump_values(self, given:bool):
        lines = []
        lines.append('*-----------*')
        for index, boxrows in enumerate(batched(self.boxrows, 3)):
            s = [''.join(str(cell.value) if cell.value and (cell.given >= given) else '.' for cell in boxrow)
                for boxrow in boxrows]
            lines.append('|' + '|'.join(s) + '|')
            if index in (2, 5):
                lines.append('|---+---+---|')
        lines.append('*-----------*\n')
        return '\n'.join(lines)

    def dumpstr(self, decor=None):
        if self.decorate == 'color':
            colorize_candidates = colorize_candidates_color
        elif self.decorate == 'char':
            colorize_candidates = colorize_candidates_char
        elif self.decorate == 'none':
            colorize_candidates = colorize_candidates_none
        else:
            colorize_candidates = colorize_candidates_color

        lines = []
        hborder = ('+' + ('-' * (3 * 10 - 1))) * 3 + '+'
        for i in range(9):
            if i % 3 == 0:
                lines.append(hborder)
            line = []
            for j, cell in enumerate(self.rows[i]):
                line.append('%s%-9s' % ('|' if j % 3 == 0 else ' ', colorize_candidates(cell, decor)))
            lines.append(''.join(line) + '|')
        lines.append(hborder)
        lines.append('')
        return '\n'.join(lines)

    def dump(self, decor=None):
        print(self.dumpstr(decor))

    def push(self, item):
        """
        Push item on history. Item is a tuple:
        (caption, 'value', Cell, value, {cand: set_of_cells, cand: set_of_cells, ...})
        (caption, 'discard', {cand: set_of_cells, cand: set_of_cells, ...})
        """
        self.history = self.history[:self.history_top + 1]
        self.history.append(item)
        self.history_top = len(self.history) - 1

    def undo(self):
        if not self.history:
            return
        item = self.history[self.history_top]
        self.history_top -= 1

        if item[1] == 'discard':
            _, _, discarded = item
            for digit, cells in discarded.items():
                for cell in cells:
                    # if digit not already eliminated by some value:
                    if all(digit != c.value for c in cell.peers):
                        cell.candidates.add(digit)

        elif item[1] == 'value':
            _, _, cell, value, discarded = item
            cell.value = None
            cell.candidates.add(value)
            for digit, cells in discarded.items():
                for cell in cells:
                    cell.candidates.add(digit)
        else:
            pass

    def redo(self):
        if self.history_top == len(self.history) - 1:
            return
        self.history_top += 1
        item = self.history[self.history_top]

        if item[1] == 'discard':
            _, _, discarded = item
            for digit, cells in discarded.items():
                for cell in cells:
                    cell.candidates.discard(digit)

        elif item[1] == 'value':
            _, _, cell, value, discarded = item
            cell.value = value
            cell.candidates = set()
            for digit, cells in discarded.items():
                for cell in cells:
                    cell.candidates.discard(digit)
        else:
            pass

    def dump_history(self):
        # TODO
        """
        (caption, 'value', Cell, value, {cand: set_of_cells, cand: set_of_cells, ...})
        (caption, 'discard', {cand: set_of_cells, cand: set_of_cells, ...})
        """
        dump = []
        for _, move, spec in self.history:
            pass

    def solution(self):
        grid = Grid()
        grid.input_gvc(self.output_gvc())
        grid.nbbacktrack = 0
        for sol in solutions(grid, 0):
            return sol
        return None


def solutions(grid, i):
    if i == 81:
        yield grid.output_s81()
    elif grid.cells[i].value:
        yield from solutions(grid, i + 1)
    else:
        candidates = grid.cells[i].candidates
        if candidates:
            for candidate in sorted(candidates):
                grid.nbbacktrack += 1
                discarded = grid.set_value(grid.cells[i], candidate)
                grid.push(('Naked single', 'value', grid.cells[i], candidate, discarded))
                yield from solutions(grid, i + 1)
                grid.undo()


class SudokuError (Exception):
    def __init__(self, *args):
        self.message = ' '.join(args)


CellDecor = Enum('CellDecor', 'VALUE GIVEN DEFAULTCAND DEFININGCAND REMOVECAND COLOR1 COLOR2 COLOR3 COLOR4')

CellDecorColor = {
    CellDecor.GIVEN: Fore.BLUE,
    CellDecor.VALUE: Fore.CYAN,
    CellDecor.DEFAULTCAND: Fore.WHITE,
    CellDecor.DEFININGCAND: Fore.GREEN,
    CellDecor.REMOVECAND: Fore.RED,
    CellDecor.COLOR1: Fore.GREEN,
    CellDecor.COLOR2: Fore.CYAN,
    CellDecor.COLOR3: Fore.YELLOW,
    CellDecor.COLOR4: Fore.MAGENTA
}

def colorize_candidates_color(cell, color_spec):
    """
    color_spec ::= [cells, [candidates, color]*]*
    ex:
    (({cell}, [1], CellDecor.COLOR1),
     ((cell1, cell2), ALLCAND, CellDecor.COLOR2, {cand1, cand2}, CellDecor.COLOR1))

    cells and candidates are iterables.
    A cell or a candidate may appear several times. The last color spec is taken into accout.
    """
    if not cell.candidates:
        decor = CellDecor.GIVEN if cell.given else CellDecor.VALUE
        res = CellDecorColor[decor] + str(cell.value) + Fore.RESET
        # manual padding as colorama information fools format padding
        res += ' ' * (9 - 1)
        return res
    else:
        if color_spec is None:
            res = CellDecorColor[CellDecor.DEFAULTCAND] + str(cell) + Fore.RESET
        else:
            candcol = retain_decor(cell, color_spec)
            res = ''
            for cand in sorted(cell.candidates):
                res += CellDecorColor[candcol[cand]] + str(cand) + Fore.RESET

        # manual padding as colorama information fools format padding
        res += ' ' * (9 - len(cell.candidates))
        return res


CellDecorChar = {
    CellDecor.GIVEN: '.',
    CellDecor.VALUE: '+',
    CellDecor.DEFAULTCAND: '',
    CellDecor.DEFININGCAND: '!',
    CellDecor.REMOVECAND: 'x',
    CellDecor.COLOR1: 'a',
    CellDecor.COLOR2: 'b',
    CellDecor.COLOR3: 'c',
    CellDecor.COLOR4: 'd'
}


def colorize_candidates_char(cell, color_spec):
    """
    color_spec ::= [cells, [candidates, color]*]*
    ex:
    (({cell}, [1], CellDecor.COLOR1),
     ((cell1, cell2), ALLCAND, CellDecor.COLOR2, {cand1, cand2}, CellDecor.COLOR1))

    cells and candidates are iterables.
    A cell or a candidate may appear several times. The last color spec is taken into accout.
    """
    if not cell.candidates:
        decor = CellDecor.GIVEN if cell.given else CellDecor.VALUE
        return str(cell.value) + CellDecorChar[decor]

    if color_spec is None:
        res = str(cell)
    else:
        candcol = retain_decor(cell, color_spec)
        res = ''
        for cand in sorted(cell.candidates):
            res += str(cand) + CellDecorChar[candcol[cand]]

    res += ' ' * (9 - len(res))
    return res


def colorize_candidates_none(cell, color_spec):
    if not cell.candidates:
        return str(cell.value)

    res = str(cell)
    res += ' ' * (9 - len(res))
    return res


def retain_decor(cell, color_spec):
    candcol = defaultdict(lambda:CellDecor.DEFAULTCAND)
    for target, *spec_col in color_spec:
        if cell in target:
            for cand in cell.candidates:
                for spec_cand, speccol in zip(spec_col[::2], spec_col[1::2]):
                    if cand in spec_cand:
                        candcol[cand] = speccol
    return candcol


# Loading


def format_ss_clipboard(grid):
    """Handle the three formats from SS clipboard:
    - given + candidates            when starting
    - given + values + candidates   during game
    - given + values                at the end
    """
    s1 = grid.dump_values(given=True)
    if not grid.history:
        s2 = grid.dumpstr()
        lines = [s1, s2]
    elif grid.solved():
        s2 = grid.dump_values(given=False)
        lines = [s1, s2]
    else:
        s2 = grid.dump_values(given=False)
        s3 = grid.dumpstr()
        lines = [s1, s2, s3]
    return '\n\n'.join(lines)


def grid_to_string81(string: str) -> str:
    """Convert a string containing a grid of values into a normalized string made
    of 81 digits or dots. The grid may contain horizontal or vertical separators.
    Horizontal separators are lines containing dashes ('-') which cannot be used
    as an unknown digit. Vertical separators are bar characters ('|'). The
    character denoting unknown digits ('.', '0', ...) must be unique.
    """
    lines = [line.strip() for line in string.splitlines()]
    lines = [line for line in lines if line]
    lines = [line for line in lines if '-' not in line]
    string = ''.join(lines)
    string = string.replace('|', '')
    if len(string) != 81:
        return ''
    else:
        chars = ''.join(sorted(set(string)))
        if '123456789' in chars and len(chars) == 10:
            return string
        else:
            return ''


def grid_to_csv(string: str) -> str:
    """Convert a string containing a grid of candidates into a normalized string
    made of candidates separated by commas. Same as grid_to_string81 for
    separators.
    """
    lines = [line.strip() for line in string.splitlines()]
    lines = [line for line in lines if line]
    lines = [line for line in lines if '-' not in line]
    string = ''.join(lines)
    string = string.replace('|', '')
    if re.match(r'([1-9]{1,9}\s+){80}[1-9]{1,9}$', string) is False:
        return ''
    else:
        xs = re.findall('[1-9]{1,9}', string)
        if len(xs) != 81:
            return ''
        else:
            return ','.join(xs)


def load_ss_clipboard(grid, content, autofilter=True):
    """Handle the three formats from SS clipboard:
    - given + candidates            when starting
    - given + values + candidates   during game
    - given + values                at the end

    When candidates are present, the candidates of the resulting grid are those
    candidates. If candidates are not present, when setting a value, the
    candidates of adjacent cells are filtered or not depending on the parameter
    autofilter.
    """
    content = [_.strip() for _ in content.splitlines()]
    if len(content) not in (28, 43):
        print('bad clipboard (1)')
        return ''

    lines1 = ''.join(content[1:4] + content[5:8] + content[9:12])
    lines2 = ''.join(content[16:19] + content[20:23] + content[24:27])
    if len(content) == 43:
        lines3 = ''.join(content[31:34] + content[35:38] + content[39:42])

    lines_given = lines1
    lines_values = None
    lines_candidates = None
    if len(content[16]) == 13:
        lines_values = lines2
    else:
        lines_candidates = lines2
    if len(content) == 43:
        lines_candidates = lines3

    if not (given := grid_to_string81(lines_given)):
        print('bad clipboard (2)')
        # exit(1)
        return ''

    if lines_values:
        if not (values := grid_to_string81(lines_values)):
            print('bad clipboard (3)')
            # exit(1)
            return ''
    else:
        values = given

    if lines_candidates:
        if not (candidates := grid_to_csv(lines_candidates)):
            print('bad clipboard (4)')
            # exit(1)
            return ''
    else:
        candidates = ','.join(list(values))

    # grid.input_gvc_strings(given, values, candidates)
    return given, values, candidates


def load_ss_grid_and_history(content):
    """whatever format for initial position + history
    """
    content = [_.strip() for _ in content.splitlines()]
    content = '\n'.join(content)
    match = re.match(r'(.*\n)\n+(.*)', content, re.DOTALL)

    if not match:
        print('bad grid and history (1)')
        return ''
    else:
        sgrid, history = match[1], match[2]

    if not (given := grid_to_string81(sgrid)):
        print('bad grid and history')
        # exit(1)
        return ''

    for line in history.splitlines():
        if re.match(r'I\d\d[1-9]', line) or re.match(r'E\d\d\d\d[1-9]{1,8}', line):
            pass
        else:
            print('bad history')
            return ''

    return given, history


def load_ss_file(grid, filename, autofilter=True):
    # TODO: autofilter ?
    with open(filename) as f:
        content = f.read()

    try:
        grid.input(content)
        return
    except SudokuError:
        pass


# Helpers


def cellinter(cells1, cells2):
    return [cell for cell in cells1 if cell in cells2]


def cellunion(cells1, cells2):
    return set.union(set(cells1), set(cells2))


def cellunionx(*list_of_list_cells):
    return set.union(*[set(cells) for cells in list_of_list_cells])


def cellinterx(*list_of_list_cells):
    return set.intersection(*[set(cells) for cells in list_of_list_cells])


def candidate_in_cells(digit, cells):
    for cell in cells:
        if digit in cell.candidates:
            return True
    else:
        return False


def candidate_union(cells):
    """return the union of candidates in cells. cells is a collection supporting
    for loops
    """
    return set().union(*(cell.candidates for cell in cells))


def bivaluedict(grid):
    """return a dictionary with pairs of candidates as keys, and sets of cells
    as values.
    """
    pairs = defaultdict(set)
    for cell in grid.cells:
        if cell.is_pair():
            pairs[frozenset(cell.candidates)].add(cell)
    return pairs


def candidates_cells(candidates, cells):
    """Test which candidates are in a list of cells. Return a dict candidate-cells.
    """
    result = defaultdict(set)
    for cell in cells:
        for candidate in candidates:
            if candidate in cell.candidates:
                result[candidate].add(cell)
    return result


def candidate_cells(dict_candidate_cells):
    for candidate, cells in dict_candidate_cells.items():
        for cell in cells:
            yield candidate, cell


def apply_remove_candidates(grid, caption, remove_dict):
    grid.push((caption, 'discard', remove_dict))
    for candidate, cell in candidate_cells(remove_dict):
        cell.candidates.discard(candidate)
    return sum(len(_) for _ in remove_dict.values())


def packed_coordinates(cells):
    """Make a string of packed coordinates (ex: r4c89,r5c89) from a list of cells.
    """
    row_cells = defaultdict(list)
    col_cells = defaultdict(list)
    for cell in cells:
        row_cells[cell.rownum + 1].append(cell.colnum + 1)
        col_cells[cell.colnum + 1].append(cell.rownum + 1)

    if len(row_cells) <= len(col_cells):
        for rownum, lst in row_cells.items():
            row_cells[rownum] = ''.join(str(_) for _ in sorted(lst))
        lcoord = sorted(f'r{rownum}c{cols}' for rownum, cols in row_cells.items())
    else:
        for colnum, lst in col_cells.items():
            col_cells[colnum] = ''.join(str(_) for _ in sorted(lst))
        lcoord = sorted(f'r{rows}c{colnum}' for colnum, rows in col_cells.items())

    return ','.join(lcoord)


def packed_candidates(candidates):
    return ','.join(str(_) for _ in sorted(candidates))


def discarded_at_last_move(grid):
    """Return candidates discarded at last move (from history).
    """
    _, _, discarded = grid.history[-1]
    return discarded


def discarded_text(cand_cells_dict):
    """Return candidates discarded in text
    explanation format (e.g. 'r45c8<>3, r4c89<>5').
    """
    list_coord = []
    for digit, cells in sorted(cand_cells_dict.items()):
        list_coord.append(f'{packed_coordinates(cells)}<>{digit}')
    return ', '.join(list_coord)


def single_history(grid):
    start = len(grid.history) - 1

    i = start
    while i >= 0 and grid.history[i][0] in ('Full house', 'Naked single', 'Hidden single'):
        i -= 1

    i += 1
    hist = []
    while i <= start:
        tech = grid.history[i][0]
        ldesc = []
        while i <= start and grid.history[i][0] == tech:
            ldesc.append('%s=%d' % (grid.history[i][2].strcoord(), grid.history[i][3]))
            i += 1
        for k in range(0, len(ldesc), 10):
            hist.append('%-13s: ' % tech + ', '.join(ldesc[k:k + 10]))

    return '\n'.join(hist)


def print_single_history(grid):
    singlehistory = single_history(grid)
    if singlehistory:
        print(singlehistory)
        print()


def batched(iterable, n, *, strict=False):
    # TODO: remove when updating python to 3.12 or above
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError('n must be at least one')
    iterator = iter(iterable)
    while batch := tuple(itertools.islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError('batched(): incomplete batch')
        yield batch


# Brute force


def solve_backtrack(grid, explain):
    sol = grid.solution()
    if sol:
        #print(grid.nbbacktrack)
        grid.input(sol)
        return 81
    return 0


def solve_dancing_links(grid, explain):
    s = grid.output_s81()
    s = s.replace('.', '0')
    d = dlx_sudoku.DLXsudoku(s)
    for sol in d.solve():
        grid.input(d.createSolutionString(sol))
        return 81
    return 0


# Singles


def solve_full_house(grid, explain):
    for unit in grid.units():
        unset = [cell for cell in unit if cell.value is None]
        if len(unset) == 1:
            cell = unset[0]
            cand = list(cell.candidates)[0]
            discarded = grid.set_value(cell, cand)
            grid.push(('Full house', 'value', cell, cand, discarded))
            return 10
    return 0


def solve_single_candidate(grid, explain):
    # naked singles
    for cell in grid.cells:
        if len(cell.candidates) == 1:
            value = list(cell.candidates)[0]
            discarded = grid.set_value(cell, value)
            grid.push(('Naked single', 'value', cell, value, discarded))
            return 10
    return 0


# Single digit techniques


def solve_hidden_candidate(grid, explain):
    # hidden singles
    for cell in grid.cells:
        if len(cell.candidates) == 1:
            continue
        for cand in cell.candidates:
            if (cell.alone_in_row(cand) or
                cell.alone_in_col(cand) or
                cell.alone_in_box(cand)):
                discarded = grid.set_value(cell, cand)
                grid.push(('Hidden single', 'value', cell, cand, discarded))
                return 10
    return 0


# Locked pairs and triples


def solve_locked_pairs(grid, explain):

    for trinum, triplet in enumerate(grid.boxrows):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                remove_set = [cell for cell in triplet if cell not in subset] + grid.rows_less_boxrow[trinum] + grid.boxes_less_boxrow[trinum]
                nb_removed = apply_locked_sets(grid, 'Locked pair', explain, subset[0].candidates, subset, remove_set)
                if nb_removed:
                    return nb_removed

    for trinum, triplet in enumerate(grid.boxcols):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                remove_set = [cell for cell in triplet if cell not in subset] + grid.cols_less_boxcol[trinum] + grid.boxes_less_boxcol[trinum]
                nb_removed = apply_locked_sets(grid, 'Locked pair', explain, subset[0].candidates, subset, remove_set)
                if nb_removed:
                    return nb_removed

    return 0


def solve_locked_triples(grid, explain):

    for trinum, triplet in enumerate(grid.boxrows):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = candidate_union(triplet)
            if len(candidates) == 3:
                remove_set = grid.rows_less_boxrow[trinum] + grid.boxes_less_boxrow[trinum]
                nb_removed = apply_locked_sets(grid, 'Locked triple', explain, candidates, triplet, remove_set)
                if nb_removed:
                    return nb_removed

    for trinum, triplet in enumerate(grid.boxcols):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = candidate_union(triplet)
            if len(candidates) == 3:
                remove_set = grid.cols_less_boxcol[trinum] + grid.boxes_less_boxcol[trinum]
                nb_removed = apply_locked_sets(grid, 'Locked triple', explain, candidates, triplet, remove_set)
                if nb_removed:
                    return nb_removed

    return 0


def apply_locked_sets(grid, caption, explain, candidates, define_set, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_locked_sets(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_locked_sets(grid, caption, candidates, define_set, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_locked_set(caption, candidates, define_set, remove_dict))
    grid.dump(((define_set, candidates, CellDecor.DEFININGCAND),
                (remove_set, candidates, CellDecor.REMOVECAND)))


def describe_locked_set(legend, candidates, define_set, remove_dict):
    return '%s: %s in %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(candidates)),
        packed_coordinates(define_set),
        discarded_text(remove_dict))


# Locked candidates


def solve_pointing(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.boxrows):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_boxrow[trinum])):
                nb_removed = apply_locked_candidates(grid, 'Pointing', 'b', explain, [digit], triplet,
                                                 grid.rows_less_boxrow[trinum])
                if nb_removed:
                    return nb_removed

        for trinum, triplet in enumerate(grid.boxcols):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_boxcol[trinum])):
                nb_removed = apply_locked_candidates(grid, 'Pointing', 'b', explain, [digit], triplet,
                                                 grid.cols_less_boxcol[trinum])
                if nb_removed:
                    return nb_removed

    return 0


def solve_claiming(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.boxrows):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.rows_less_boxrow[trinum])):
                nb_removed = apply_locked_candidates(grid, 'Claiming', 'r', explain, [digit], triplet,
                                                 grid.boxes_less_boxrow[trinum])
                if nb_removed:
                    return nb_removed

        for trinum, triplet in enumerate(grid.boxcols):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.cols_less_boxcol[trinum])):
                nb_removed = apply_locked_candidates(grid, 'Claiming', 'c', explain, [digit], triplet,
                                                 grid.boxes_less_boxcol[trinum])
                if nb_removed:
                    return nb_removed

    return 0


def apply_locked_candidates(grid, caption, flavor, explain, candidates, define_set, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_locked_candidates(grid, caption, flavor, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_locked_candidates(grid, caption, flavor, candidates, define_set, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_locked_candidates(caption, flavor, candidates, define_set, remove_dict))
    grid.dump(((define_set, candidates, CellDecor.DEFININGCAND),
               (remove_set, candidates, CellDecor.REMOVECAND)))


def describe_locked_candidates(caption, flavor, candidates, define_set, remove_dict):
    if flavor == 'b':
        defunit = f'b{define_set[0].boxnum + 1}'
    elif flavor == 'r':
        defunit = f'r{define_set[0].rownum + 1}'
    elif flavor == 'c':
        defunit = f'c{define_set[0].colnum + 1}'
    return '%s: %s in %s => %s' % (caption,
        ','.join(f'{_}' for _ in sorted(candidates)),
        defunit,
        discarded_text(remove_dict))


# Locked sets


def solve_nacked_pairs(grid, explain):
    nb_removed = (nacked_sets_n(grid, x, 2, 'Naked pair', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def solve_nacked_triples(grid, explain):
    nb_removed = (nacked_sets_n(grid, x, 3, 'Naked triple', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def solve_nacked_quads(grid, explain):
    nb_removed = (nacked_sets_n(grid, x, 4, 'Naked quadruple', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def nacked_sets_n(grid, unit, size, legend, explain):
    subcells = [cell for cell in unit if len(cell.candidates) > 1]
    for subset in itertools.combinations(subcells, size):
        candidates = candidate_union(subset)
        if len(candidates) == size:
            cells_less_subset = [cell for cell in subcells if cell not in subset]
            nb_removed = apply_naked_set(grid, legend, explain, candidates, subset, cells_less_subset)
            if nb_removed:
                return nb_removed
    return 0


def apply_naked_set(grid, caption, explain, candidates, subset, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_naked_set(grid, caption, candidates, subset, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_naked_set(grid, caption, candidates, subset, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_locked_set(caption, candidates, subset, remove_dict))
    grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
                (remove_set, candidates, CellDecor.REMOVECAND)))


def solve_hidden_pair(grid, explain):
    nb_removed = (solve_hidden_set(grid, x, 2, 'Hidden pair', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def solve_hidden_triple(grid, explain):
    nb_removed = (solve_hidden_set(grid, x, 3, 'Hidden triple', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def solve_hidden_quad(grid, explain):
    nb_removed = (solve_hidden_set(grid, x, 4, 'Hidden quadruple', explain) for x in grid.units())
    return next((x for x in nb_removed if x), 0)


def solve_hidden_set(grid, unit, size, caption, explain):
    cells = [cell for cell in unit if len(cell.candidates) > 1]
    for subset in itertools.combinations(cells, size):
        candidates = candidate_union(subset)
        cellcompl = set(cells) - set(subset)
        candcompl = candidate_union(cellcompl)
        for candset in itertools.combinations(candidates, size):
            if not set(candset).intersection(candcompl):
                if all(set(candset).intersection(cell.candidates) for cell in subset):
                    nb_removed = apply_hidden_set(grid, caption, explain, candidates - set(candset), subset, subset)
                    if nb_removed:
                        return nb_removed
    return 0


def apply_hidden_set(grid, caption, explain, candidates, define_set, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_hidden_set(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_hidden_set(grid, caption, candidates, define_set, remove_set, remove_dict):
    print_single_history(grid)
    allcand = candidate_union(define_set)
    print(describe_locked_set(caption, allcand - candidates, remove_set, remove_dict))
    grid.dump(((remove_set,
                ALLCAND - candidates, CellDecor.DEFININGCAND,
                candidates, CellDecor.REMOVECAND),))


# Basic fishes


def solve_X_wing(grid, explain):
    return solve_basicfish(grid, explain, 2, 'X-wing')


def solve_swordfish(grid, explain):
    return solve_basicfish(grid, explain, 3, 'Swordfish')


def solve_jellyfish(grid, explain):
    return solve_basicfish(grid, explain, 4, 'Jellyfish')


def solve_basicfish(grid, explain, size, name):
    for digit in ALLDIGITS:
        nb_removed = solve_basicfish_rows(grid, explain, size, name, digit, grid.rows, grid.cols, Cell.mrownum, Cell.mcolnum, 'H')
        if nb_removed:
            return nb_removed
        nb_removed = solve_basicfish_rows(grid, explain, size, name, digit, grid.cols, grid.rows, Cell.mcolnum, Cell.mrownum, 'V')
        if nb_removed:
            return nb_removed
    return 0


def solve_basicfish_rows(grid, explain, size, name, digit, rows, cols, mrownum, mcolnum, orientation):
    candrows = []
    for row in rows:
        rowcells = [cell for cell in row if digit in cell.candidates]
        if 1 < len(rowcells) <= size:
            candrows.append(rowcells)

    for defrows in itertools.combinations(candrows, size):
        rowsnum = [mrownum(row[0]) for row in defrows]
        colsnum = {mcolnum(cell) for row in defrows for cell in row}
        if len(colsnum) == size:
            # n rows with candidates in n cols
            remove_set = []
            for colnum in colsnum:
                for cell in cols[colnum]:
                    if mrownum(cell) not in rowsnum:
                        remove_set.append(cell)
            nb_removed = apply_basic_fish(grid, name, explain, [digit], defrows, remove_set, orientation)
            if nb_removed:
                return nb_removed
    return 0


def apply_basic_fish(grid, caption, explain, candidates, defunits, remove_set, orientation):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_basic_fish(grid, caption, candidates, defunits, remove_set, remove_dict, orientation)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_basic_fish(grid, caption, candidates, defunits, remove_set, remove_dict, orientation):
    subset = cellunionx(*defunits)
    print_single_history(grid)
    print(describe_basic_fish(caption, candidates, subset, remove_dict, orientation))
    grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
               (remove_set, candidates, CellDecor.REMOVECAND)))


def describe_basic_fish(legend, candidates, subset, remove_dict, orientation):
    rows = {cell.rownum + 1 for cell in subset}
    cols = {cell.colnum + 1 for cell in subset}
    srows = ''.join(f'{_}' for _ in sorted(list(rows)))
    scols = ''.join(f'{_}' for _ in sorted(list(cols)))
    defcells = f'r{srows} c{scols}' if orientation == 'H' else f'c{scols} r{srows}'
    return '%s: %s %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(candidates)),
        defcells,
        discarded_text(remove_dict))


# Finned and sashimi fishes


def solve_finned_x_wing(grid, explain):
    return solve_finned_x_wing_tech(grid, explain, tech={'Finned'})


def solve_sashimi_x_wing(grid, explain):
    return solve_finned_x_wing_tech(grid, explain, tech={'Sashimi'})


def solve_finned_x_wing_tech(grid, explain, tech):
    for digit in ALLDIGITS:
        nb_removed = solve_finned_x_wing_unit(grid, explain, digit, grid.rows,
            Cell.mrownum, Cell.mcolnum, Cell.mboxrow, Cell.mboxcol, tech=tech)
        if nb_removed:
            return nb_removed
        nb_removed = solve_finned_x_wing_unit(grid, explain, digit, grid.cols,
            Cell.mcolnum, Cell.mrownum, Cell.mboxcol, Cell.mboxrow, tech=tech)
        if nb_removed:
            return nb_removed
    return 0


def solve_finned_x_wing_unit(grid, explain, digit, rows, rownum, colnum, mboxrow, mboxcol, tech):
    for row in rows:
        rowcells = [cell for cell in row if digit in cell.candidates]
        if len(rowcells) == 2:
            cell1, cell2 = rowcells
            for row2 in rows:
                if row2 == row:
                    continue
                cell3 = row2[colnum(cell1)]
                cell4 = row2[colnum(cell2)]
                if digit in cell3.candidates or digit in cell4.candidates:
                    tri3 = mboxrow(cell3)
                    tri4 = mboxrow(cell4)
                    row2num = sum(1 for cell in row2 if digit in cell.candidates)
                    tri3num = sum(1 for cell in tri3 if digit in cell.candidates)
                    tri4num = sum(1 for cell in tri4 if digit in cell.candidates)
                    if row2num == tri3num + tri4num:
                        if ('Finned' in tech and digit in cell3.candidates and tri3num == 1 and
                            digit in cell4.candidates and tri4num > 1):
                            flavor = 'Finned'
                        elif ('Finned' in tech and digit in cell3.candidates and tri3num > 1 and
                            digit in cell4.candidates and tri4num == 1):
                            flavor = 'Finned'
                            cell1, cell2, cell3, cell4, tri3, tri4 = cell2, cell1, cell4, cell3, tri4, tri3
                        elif 'Sashimi' in tech and digit in cell3.candidates and tri3num == 1 and tri4num > 1: # >= 1
                            flavor = 'Sashimi'
                        elif 'Sashimi' in tech and digit in cell4.candidates and tri3num > 1 and tri4num == 1:
                            flavor = 'Sashimi'
                            cell1, cell2, cell3, cell4, tri3, tri4 = cell2, cell1, cell4, cell3, tri4, tri3
                        else:
                            continue
                        remove_set = [cell for cell in mboxcol(cell4) if cell != cell2 and cell != cell4]
                        nb_removed = apply_finned_fish(grid, f'{flavor} X-wing', explain, [digit],
                            [[cell1, cell2], [cell3, cell4], set(tri4) - {cell4}], remove_set)
                        if nb_removed:
                            return nb_removed
    return 0


def apply_finned_fish(grid, caption, explain, candidates, defunits, cells_to_discard):
    remove_dict = candidates_cells(candidates, cells_to_discard)
    if remove_dict:
        if explain:
            explain_finned_fish(grid, caption, candidates, defunits, cells_to_discard, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_finned_fish(grid, caption, candidates, defunits, cells_to_discard, remove_dict):
    orientation = 'H' if defunits[0][0].rownum == defunits[0][1].rownum else 'V'
    subset = cellunionx(*defunits[:-1])
    fin = [cell for cell in defunits[-1] if candidates[0] in cell.candidates]
    print_single_history(grid)
    print(describe_finned_fish(caption, candidates, subset, fin, orientation, remove_dict))
    grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
               (fin, candidates, CellDecor.COLOR3),
               (cells_to_discard, candidates, CellDecor.REMOVECAND)))


def describe_finned_fish(legend, candidates, subset, fin, orientation, remove_dict):
    rows = {cell.rownum + 1 for cell in subset}
    cols = {cell.colnum + 1 for cell in subset}
    srows = ''.join(f'{_}' for _ in sorted(list(rows)))
    scols = ''.join(f'{_}' for _ in sorted(list(cols)))
    defcells = f'r{srows} c{scols}' if orientation == 'H' else f'c{scols} r{srows}'
    return '%s: %s %s f%s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(candidates)),
        defcells,
        packed_coordinates(fin),
        discarded_text(remove_dict))


def solve_finned_swordfish(grid, explain):
    return solve_finned_fish(grid, explain, 3, 'Finned swordfish', tech={'Finned'})


def solve_finned_jellyfish(grid, explain):
    return solve_finned_fish(grid, explain, 4, 'Finned jellyfish', tech={'Finned'})


def solve_sashimi_swordfish(grid, explain):
    return solve_finned_fish(grid, explain, 3, 'Sashimi swordfish', tech={'Sashimi'})


def solve_sashimi_jellyfish(grid, explain):
    return solve_finned_fish(grid, explain, 4, 'Sashimi jellyfish', tech={'Sashimi'})


def solve_finned_fish(grid, explain, size, name, tech):
    for digit in ALLDIGITS:
        nb_removed = solve_finned_fish_rows(grid, explain, size, name, digit, grid.rows, grid.cols, Cell.mrownum, Cell.mcolnum, Cell.mboxrow, tech)
        if nb_removed:
            return nb_removed
        nb_removed = solve_finned_fish_rows(grid, explain, size, name, digit, grid.cols, grid.rows, Cell.mcolnum, Cell.mrownum, Cell.mboxcol, tech)
        if nb_removed:
            return nb_removed
    return 0


def solve_finned_fish_rows(grid, explain, size, name, digit, rows, cols, mrownum, mcolnum, mboxrow, tech):
    candrows = []
    for row in rows:
        rowcells = [cell for cell in row if digit in cell.candidates]
        if len(rowcells) >= 2:
            candrows.append(rowcells)

    for defrows in itertools.combinations(candrows, size):
        colsnum = {mcolnum(cell) for row in defrows for cell in row}

        for covercols in itertools.combinations(sorted(colsnum), size):

            # search for cell in defrows not in coverrows
            complement = set()
            for row in defrows:
                for cell in row:
                    if mcolnum(cell) not in covercols:
                        complement.add(cell)

            # all cells in complement must be in a single box
            box = None
            for cell in complement:
                if box is None:
                    box = cell.box
                elif box == cell.box:
                    pass
                else:
                    # at least two boxes
                    box = False

            if not box:
                continue

            # the box must intersect with a cover col
            intersect = False
            for colnum in covercols:
                if colnum // 3 == mcolnum(box[0]) // 3:
                    intersect = True
                    break

            if not intersect:
                continue

            # test for sashimi
            if 'Sashimi' not in tech and not is_genuine_fish(grid, size, digit, rows, defrows, covercols, mrownum, mcolnum):
                continue

            defcells = []
            for row in defrows:
                defcells.extend(cell for cell in row if mcolnum(cell) in covercols)

            fin_set = []
            remove_set = []
            for cell in box:
                in_base = any(cell in row for row in defrows)
                in_cover = mcolnum(cell) in covercols
                if in_base and not in_cover:
                    fin_set.append(cell)
                elif not in_base and in_cover:
                    remove_set.append(cell)

            nb_removed = apply_finned_fish(grid, name, explain, [digit], [defcells] + [fin_set], remove_set)
            if nb_removed:
                return nb_removed
    return 0


def is_genuine_fish(grid, size, digit, rows, fishrows, colnums, mrownum, mcolnum):
    if len(fishrows) != len(colnums):
        return False
    else:
        for row in fishrows:
            n = sum(1 for cell in row if mcolnum(cell) in colnums)
            if n < 2:
                return False
        for colnum in colnums:
            n = sum(1 for row in fishrows if rows[mrownum(row[0])][colnum] in row)
            if n < 2:
                return False
        return True


# Simple coloring


def solve_coloring_trap(grid, explain):
    """a candidate sees both colors of a cluster. Whatever the color coding, the
    candidate can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        for cluster in clusters:
            cluster_blue, cluster_green = colorize(digit, cluster)

            peers_cluster_blue = multi_peers(digit, cluster_blue) - cluster_blue
            peers_cluster_green = multi_peers(digit, cluster_green) - cluster_green
            remove_set = cellinter(peers_cluster_blue, peers_cluster_green)

            if remove_set:
                return apply_colortrap(grid, 'Simple color trap', explain, digit, cluster_blue, cluster_green, remove_set)

    return 0


def apply_colortrap(grid, caption, explain, digit, cluster_blue, cluster_green, remove_set):
    remove_dict = candidates_cells([digit], remove_set)
    if explain:
        explain_colortrap(grid, caption, digit, cluster_blue, cluster_green, remove_set, remove_dict)
    return apply_remove_candidates(grid, caption, remove_dict)


def explain_colortrap(grid, caption, digit, cluster_blue, cluster_green, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_simple_coloring(caption, digit, cluster_green, cluster_blue, remove_dict))
    grid.dump(((cluster_green, [digit], CellDecor.COLOR1),
                (cluster_blue, [digit], CellDecor.COLOR2),
                (remove_set, [digit], CellDecor.REMOVECAND)))


def describe_simple_coloring(caption, digit, cluster_green, cluster_blue, remove_cells):
    return '%s: %d (%s) / (%s) => %s' % (caption, digit,
        packed_coordinates(cluster_green),
        packed_coordinates(cluster_blue),
        discarded_text(remove_cells))


def solve_coloring_wrap(grid, explain):
    """two candidates in the same unit have the same color. All candidates with
    this color can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        for cluster in clusters:
            cluster_blue, cluster_green = colorize(digit, cluster)

            if color_contradiction(cluster_blue):
                return apply_colorwrap(grid, 'Simple color wrap', explain, digit, cluster_blue, cluster_green, cluster_blue)

            if color_contradiction(cluster_green):
                return apply_colorwrap(grid, 'Simple color wrap', explain, digit, cluster_blue, cluster_green, cluster_green)

    return 0


def apply_colorwrap(grid, caption, explain, digit, cluster_blue, cluster_green, remove_set):
    remove_dict = candidates_cells([digit], remove_set)
    if explain:
        explain_colorwrap(grid, caption, explain, digit, cluster_blue, cluster_green, remove_set, remove_dict)
    return apply_remove_candidates(grid, caption, remove_dict)


def explain_colorwrap(grid, caption, explain, digit, cluster_blue, cluster_green, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_simple_coloring(caption, digit, cluster_blue, cluster_green, remove_dict))
    grid.dump(((cluster_blue, [digit], CellDecor.COLOR1),
                (cluster_green, [digit], CellDecor.COLOR2),
                (remove_set, [digit], CellDecor.REMOVECAND)))


def color_contradiction(same_color):
    """all cells in same_color must have the same status; if two cells of the
    same color are in the same unit, the associated candidate cannot be the
    value.
    """
    rows = [0] * 9
    cols = [0] * 9
    boxs = [0] * 9
    for cell in same_color:
        rows[cell.rownum] += 1
        cols[cell.colnum] += 1
        boxs[cell.boxnum] += 1
    return any(x > 1 for x in rows) or any(x > 1 for x in cols) or any(x > 1 for x in boxs)


# Multi  coloring


def solve_multi_coloring_type_1(grid, explain):
    """Consider two clusters. If a unit contains a color of each cluster, all
    cells seing the opposite colors can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        clusters_data = []
        to_be_removed = None

        for cluster in clusters:
            cluster_blue, cluster_green = colorize(digit, cluster)

            peers_cluster_blue = multi_peers(digit, cluster_blue) #- cluster_blue
            peers_cluster_green = multi_peers(digit, cluster_green) #- cluster_green
            common = cellinter(peers_cluster_blue, peers_cluster_green)

            clusters_data.append((cluster, cluster_blue, cluster_green,
                                  peers_cluster_blue, peers_cluster_green, common))

        for clusters_data1, clusters_data2 in itertools.combinations(clusters_data, 2):
            _, cluster_blue1, cluster_green1, peers_cluster_blue1, peers_cluster_green1, _ = clusters_data1
            _, cluster_blue2, cluster_green2, peers_cluster_blue2, peers_cluster_green2, _ = clusters_data2

            if any(cell in peers_cluster_blue2 for cell in cluster_blue1):
                to_be_removed = cellinter(peers_cluster_green1, peers_cluster_green2)
                if to_be_removed:
                    break

            if any(cell in peers_cluster_green2 for cell in cluster_blue1):
                to_be_removed = cellinter(peers_cluster_green1, peers_cluster_blue2)
                if to_be_removed:
                    break

            if any(cell in peers_cluster_blue2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_green2)
                if to_be_removed:
                    break

            if any(cell in peers_cluster_green2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_blue2)
                if to_be_removed:
                    break

        if to_be_removed:
            return apply_multicolor(grid, 'Multi color type 1', explain, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            to_be_removed)

    return 0


def solve_multi_coloring_type_2(grid, explain):
    """Consider two clusters. If a color of one cluster sees both colors of the
    second cluster, all candidates from first color can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        clusters_data = []
        to_be_removed = None
        for cluster in clusters:
            cluster_blue, cluster_green = colorize(digit, cluster)

            peers_cluster_blue = multi_peers(digit, cluster_blue) #- cluster_blue
            peers_cluster_green = multi_peers(digit, cluster_green) #- cluster_green
            common = cellinter(peers_cluster_blue, peers_cluster_green)

            clusters_data.append((cluster, cluster_blue, cluster_green,
                                  peers_cluster_blue, peers_cluster_green, common))

        for clusters_data1, clusters_data2 in itertools.combinations(clusters_data, 2):
            _, cluster_blue1, cluster_green1, peers_cluster_blue1, peers_cluster_green1, _ = clusters_data1
            _, cluster_blue2, cluster_green2, peers_cluster_blue2, peers_cluster_green2, _ = clusters_data2

            if (any(cell in peers_cluster_blue2 for cell in cluster_blue1) and
                any(cell in peers_cluster_green2 for cell in cluster_blue1)):
                to_be_removed = cluster_blue1
                break

            if (any(cell in peers_cluster_blue2 for cell in cluster_green1) and
                any(cell in peers_cluster_green2 for cell in cluster_green1)):
                to_be_removed = cluster_green1
                break

            if (any(cell in peers_cluster_blue1 for cell in cluster_blue2) and
                any(cell in peers_cluster_green1 for cell in cluster_blue2)):
                to_be_removed = cluster_blue2
                break

            if (any(cell in peers_cluster_blue1 for cell in cluster_green2) and
                any(cell in peers_cluster_green1 for cell in cluster_green2)):
                to_be_removed = cluster_green2
                break

        if to_be_removed:
            return apply_multicolor(grid, 'Multi color type 2', explain, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            to_be_removed)

    return 0


def apply_multicolor(grid, caption, explain, digit,
                     cluster_blue1, cluster_green1,
                     cluster_blue2, cluster_green2,
                     cells_to_discard):
    remove_dict = candidates_cells([digit], cells_to_discard)
    if explain:
        explain_multicolor(grid, caption, digit,
                        cluster_blue1, cluster_green1,
                        cluster_blue2, cluster_green2,
                        cells_to_discard, remove_dict)
    return apply_remove_candidates(grid, caption, remove_dict)


def explain_multicolor(grid, caption, digit,
                     cluster_blue1, cluster_green1,
                     cluster_blue2, cluster_green2,
                     cells_to_discard, remove_dict):
    print_single_history(grid)
    print(describe_multi_coloring(caption, digit,
                cluster_blue1, cluster_green1,
                cluster_blue2, cluster_green2, remove_dict))
    grid.dump(((cluster_blue1, [digit], CellDecor.COLOR1),
               (cluster_green1, [digit], CellDecor.COLOR2),
               (cluster_blue2, [digit], CellDecor.COLOR3),
               (cluster_green2, [digit], CellDecor.COLOR4),
               (cells_to_discard, [digit], CellDecor.REMOVECAND)))


def describe_multi_coloring(caption, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            remove_dict):
    """multi coloring is limited to two clusters.
    """
    return '%s: %d (%s) / (%s), (%s) / (%s) => %s' % (caption, digit,
        packed_coordinates(cluster_blue1),
        packed_coordinates(cluster_green1),
        packed_coordinates(cluster_blue2),
        packed_coordinates(cluster_green2),
        discarded_text(remove_dict))


# Clusters


def make_clusters(grid, digit):
    clusters = []
    for cell in grid.cells:
        check_cluster(grid, clusters, cell, digit)
    return clusters


def check_cluster(grid, clusters, cell, digit):
    if digit not in cell.candidates:
        pass
    elif is_cell_in_clusters(cell, clusters):
        pass
    else:
        new_cluster = set()
        new_cluster.add(cell)
        clusters.append(new_cluster)
        conjs = cell.conjugates(digit)
        for conj in conjs:
            check_cluster_conj(grid, new_cluster, conj, digit)


def is_cell_in_clusters(cell, clusters):
    return clusters and any(cell in cluster for cluster in clusters)


def check_cluster_conj(grid, cluster, conj, digit):
    if conj in cluster:
        pass
    else:
        cluster.add(conj)
        conjs = conj.conjugates(digit)
        for conj in conjs:
            check_cluster_conj(grid, cluster, conj, digit)


def colorize(digit, cluster):

    def colorize_cell(cell, colorset, conjcolorset):
        if cell not in colorset and cell not in conjcolorset:
            colorset.add(cell)
            for conj in cell.conjugates(digit):
                colorize_cell(conj, conjcolorset, colorset)

    cluster_blue, cluster_green = set(), set()
    first_cell = list(cluster)[0]
    colorize_cell(first_cell, cluster_blue, cluster_green)

    if not cluster_blue or not cluster_green:
        return cluster_blue, cluster_green
    elif min(cluster_blue) < min(cluster_green):
        return cluster_blue, cluster_green
    else:
        return cluster_green, cluster_blue


def multi_peers(digit, cluster):
    digit_peers = set()
    for cell in cluster:
        digit_peers = cellunion(digit_peers, set(c for c in cell.peers if digit in c.candidates))
    return digit_peers


# x-chains


def solve_X_chain(grid, explain, technique='x'):
    for digit in ALLDIGITS:

        cells, weak_links, strong_links = x_links(grid, digit)
        if len(strong_links) < 2:
            continue

        # initialize adjacency matrix
        adjacency = [None] * len(cells)
        for i in range(len(cells)):
            adjacency[i] = [[] for _ in cells]
        for link in weak_links:
            cell1, cell2 = link
            adjacency[cells.index(cell1)][cells.index(cell2)].append(link)

        # transitive closure
        for k in range(len(cells)):
            for i in range(len(cells)):
                for j in range(len(cells)):
                    if i == j or (i, k) == (k, j):
                        continue
                    for chain1 in adjacency[i][k]:
                        for chain2 in adjacency[k][j]:
                            cells_to_discard = test_new_xchain(grid, digit,
                                                               adjacency[i][j], chain1, chain2,
                                                               strong_links, technique)
                            if cells_to_discard:
                                return apply_x_chain(grid, digit, technique, explain,
                                              adjacency[i][j][-1], cells_to_discard)
    return 0


def x_links(grid, digit):
    """make list of cells and list of weak and strong links
    """
    cells = [cell for cell in grid.cells if digit in cell.candidates]
    cells = sorted(cells)
    weak_links = []
    strong_links = []

    for cell1 in cells:
        for cell2 in cells:
            if cell1 == cell2:
                pass
            elif cell1 not in cell2.peers:
                pass
            else:
                weak_links.append([cell1, cell2])
                peers1 = [cell for cell in cell1.peers if digit in cell.candidates]
                peers2 = [cell for cell in cell2.peers if digit in cell.candidates]
                peers = cellinter(peers1, peers2)
                if len(peers) == 0:
                    strong_links.append((cell1, cell2))

    return cells, weak_links, strong_links


def test_new_xchain(grid, digit, adjacency, chain1, chain2, strong_links, technique):
    if any(x in chain2[1:] for x in chain1):
        # concatenation would make a loop
        return None
    if tuple(chain1[-2:]) not in strong_links and tuple(chain2[:2]) not in strong_links:
        # a weak link must be followed by a strong link
        return None

    if len(chain1) + len(chain2) - 1 > 5 and technique in ('tf', 'sk', '2sk'):
        return None

    chain = chain1 + chain2[1:]
    adjacency.append(chain)

    if len(chain) < 4 or len(chain) % 2 == 1:
        return None

    if any(link not in strong_links for link in zip(chain[::2], chain[1::2])):
        # even links (0-based) must be strong links
        return None

    if technique == 'sk' and not test_skyscraper(chain):
        return None

    if technique == '2sk' and not test_2_string_kite(chain):
        return None

    if technique == 'tf' and not test_turbot_fish(chain):
        return None

    return test_x_remove(grid, digit, chain)


def test_x_remove(grid, digit, chain):
    to_be_removed = cellinter(chain[0].peers, chain[-1].peers)
    to_be_removed = [cell for cell in to_be_removed if digit in cell.candidates]
    #to_be_removed = [cell for cell in to_be_removed if cell not in chain]
    return to_be_removed


def apply_x_chain(grid, digit, technique, explain, chain, cells_to_discard):
    caption = {'x': 'X-chain', 'sk': 'Skyscraper', '2sk': '2 string kite', 'tf': 'Turbotfish'}
    remove_dict = candidates_cells([digit], cells_to_discard)
    if explain:
        explain_x_chain(grid, caption, digit, technique, chain, cells_to_discard, remove_dict)
    return apply_remove_candidates(grid, caption[technique], remove_dict)


def explain_x_chain(grid, caption, digit, technique, chain, cells_to_discard, remove_dict):
    print_single_history(grid)
    print(describe_x_chain(caption[technique], digit, chain, remove_dict))
    L = []
    for cell1, cell2 in zip(chain[::2], chain[1::2]):
        L.extend((([cell1], [digit], CellDecor.COLOR1),
                    ([cell2], [digit], CellDecor.COLOR2)))
    L.append((cells_to_discard, [digit], CellDecor.REMOVECAND))
    grid.dump(L)


def describe_x_chain(caption, digit, chain, remove_cells):
    l = []
    for index, cell in enumerate(chain[:-1]):
        l.append(cell.strcoord())
        l.append(('=%d=' if index % 2 == 0 else '-%d-') % digit)
    l.append(chain[-1].strcoord())

    return '%s: %d %s => %s' % (caption, digit, ' '.join(l), discarded_text(remove_cells))


def solve_skyscraper(grid, explain):
    return solve_X_chain(grid, explain, technique='sk')


def test_skyscraper(chain):
    link1 = chain[0:2]
    link2 = chain[2:4]
    if (link1[0].rownum == link1[1].rownum and link2[0].rownum == link2[1].rownum or
        link1[0].colnum == link1[1].colnum and link2[0].colnum == link2[1].colnum):
        return True
    else:
        return False


def solve_2_string_kite(grid, explain):
    return solve_X_chain(grid, explain, technique='2sk')


def test_2_string_kite(chain):
    link1 = chain[0:2]
    link2 = chain[2:4]
    if (link1[0].rownum == link1[1].rownum and link2[0].colnum == link2[1].colnum or
        link1[0].colnum == link1[1].colnum and link2[0].rownum == link2[1].rownum):
        return True
    else:
        return False


def solve_turbot_fish(grid, explain):
    return solve_X_chain(grid, explain, technique='tf')


def test_turbot_fish(chain):
    return len(chain) == 4


def solve_empty_rectangle(grid, explain):
    for digit in ALLDIGITS:
        nb_removed = solve_empty_rectangle_rows(grid, explain, digit, grid.rows, Cell.mrownum, Cell.mcolnum)
        if nb_removed:
            return nb_removed
        nb_removed = solve_empty_rectangle_rows(grid, explain, digit, grid.cols, Cell.mcolnum, Cell.mrownum)
        if nb_removed:
            return nb_removed
    return 0


def solve_empty_rectangle_rows(grid, explain, digit, rows, mrownum, mcolnum):
    strong_links = []
    for row in rows:
        cells = [cell for cell in row if digit in cell.candidates]
        if len(cells) == 2 and cells[0].boxnum != cells[1].boxnum:
            strong_links.append(cells)

    for strong_link in strong_links:
        floornum = mrownum(strong_link[0]) // 3
        colnum1 = mcolnum(strong_link[0])
        colnum2 = mcolnum(strong_link[1])
        for row in rows:
            if mrownum(row[0]) // 3 != floornum:
                nb_removed = test_empty_rectangle(grid, explain, digit, strong_link, row, colnum1, colnum2)
                if nb_removed:
                    return nb_removed
                nb_removed = test_empty_rectangle(grid, explain, digit, strong_link, row, colnum2, colnum1)
                if nb_removed:
                    return nb_removed
    return 0


def test_empty_rectangle(grid, explain, digit, strong_link, line, num1, num2):
    if digit in line[num1].candidates:
        pivot = line[num2]
        if is_empty_rectangle(grid, digit, pivot):
            return apply_empty_rectangle(grid, digit, 'Empty rectangle', explain,
                strong_link, grid.boxes[pivot.boxnum], line[num1])
    return 0


def is_empty_rectangle(grid, digit, pivot):
    rownum = pivot.rownum
    colnum = pivot.colnum
    boxnum = pivot.boxnum
    cells = [cell for cell in grid.boxes[boxnum] if digit in cell.candidates]
    if cells:
        for cell in cells:
            if cell.rownum != rownum and cell.colnum != colnum:
                return False
        else:
            return True
    return False


def apply_empty_rectangle(grid, digit, caption, explain, link, box, cell_to_discard):
    remove_dict = candidates_cells([digit], [cell_to_discard])
    if explain:
        explain_empty_rectangle(grid, digit, caption, link, box, cell_to_discard, remove_dict)
    return apply_remove_candidates(grid, caption, remove_dict)


def explain_empty_rectangle(grid, digit, caption, link, box, cell_to_discard, remove_dict):
    print_single_history(grid)
    print(describe_empty_rectangle(caption, digit, link, box, remove_dict))
    colors = [(link, [digit], CellDecor.COLOR1),
                (box, [digit], CellDecor.COLOR2),
                ([cell_to_discard], [digit], CellDecor.REMOVECAND)]
    grid.dump(colors)


def describe_empty_rectangle(caption, digit, link, box, remove_dict):
    return '%s: %d in b%d (%s) => %s' % (
        caption, digit, box[0].boxnum + 1, packed_coordinates(link), discarded_text(remove_dict))


# xy-wings


def solve_XY_wing(grid, explain):
    for cell in grid.cells:
        if cell.is_pair():
            pairpeers = (peer for peer in cell.peers if peer.is_pair())
            for wing1, wing2 in itertools.combinations(pairpeers, 2):
                if wing1 in wing2.peers:
                    # cell, wing1, wing2 in the same house: not a xy-wing
                    continue
                wings_inter = wing1.candidates.intersection(wing2.candidates)
                if len(wings_inter) != 1 or min(wings_inter) in cell.candidates:
                    continue
                cand1, cand2 = sorted(cell.candidates)
                if (cand1 in wing1.candidates and cand2 in wing2.candidates or
                    cand1 in wing2.candidates and cand2 in wing1.candidates):
                    digit = min(wings_inter)
                    remove_set = cellinter(wing1.peers, wing2.peers)
                    nb_removed = apply_xy_wing(grid, 'XY-wing', explain, [cand1, cand2, digit], [cell, wing1, wing2], remove_set)
                    if nb_removed:
                        return nb_removed
    return 0


def apply_xy_wing(grid, caption, explain, candidates, define_set, remove_set):
    cand1, cand2, digit = candidates
    remove_dict = candidates_cells([digit], remove_set)
    if remove_dict:
        if explain:
            explain_xy_wing(grid, caption, candidates, define_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_xy_wing(grid, caption, candidates, define_set, remove_dict):
    cand1, cand2, digit = candidates
    cell, wing1, wing2 = define_set
    print_single_history(grid)
    print(describe_xy_wing(caption, candidates, define_set, remove_dict))
    grid.dump(((define_set, cell.candidates, CellDecor.COLOR1),
               ((wing1, wing2), ALLCAND - cell.candidates, CellDecor.COLOR2),
               (remove_dict[digit], [digit], CellDecor.REMOVECAND)))


def describe_xy_wing(caption, digits, cells, remove_dict):
    return '%s: %s in %s => %s' % (caption,
        '/'.join(str(_) for _ in digits),
        packed_coordinates(cells),
        discarded_text(remove_dict))


# xyz-wings


def solve_XYZ_wing(grid, explain):
    for cell in grid.cells:
        if len(cell.candidates) == 3:
            pairpeers = (peer for peer in cell.peers if peer.is_pair())
            for wing1, wing2 in itertools.combinations(pairpeers, 2):
                wings_inter = wing1.candidates.intersection(wing2.candidates)
                wings_union = wing1.candidates.union(wing2.candidates)
                if len(wings_inter) == 1 and wings_union == cell.candidates:
                    digit = min(wings_inter)
                    remove_set = cellinterx(wing1.peers, wing2.peers, cell.peers)
                    nb_removed = apply_xyz_wing(grid, 'XYZ-wing', explain, digit, [cell, wing1, wing2], remove_set)
                    if nb_removed:
                        return nb_removed
    return 0


def apply_xyz_wing(grid, caption, explain, digit, define_set, remove_set):
    remove_dict = candidates_cells([digit], remove_set)
    if remove_dict:
        if explain:
            explain_xyz_wing(grid, caption, digit, define_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_xyz_wing(grid, caption, digit, define_set, remove_dict):
    cell, _, _ = define_set
    print_single_history(grid)
    print(describe_xy_wing(caption, [digit], define_set, remove_dict))
    grid.dump(((define_set, cell.candidates, CellDecor.COLOR1),
               (define_set, [digit], CellDecor.COLOR2),
               (remove_dict[digit], [digit], CellDecor.REMOVECAND)))


# xy-chains


def solve_XY_chain(grid, explain, remote_pair=False):
    all_solutions = False
    pairs, links = xy_links(grid, remote_pair)

    caption = 'Remote pair' if remote_pair else 'XY-chain'

    # initialize adjacency matrix
    adjacency = [None] * len(pairs)
    for i in range(len(pairs)):
        adjacency[i] = [[] for _ in pairs]
    for link in links:
        (pair1, pair2), _ = link
        adjacency[pairs.index(pair1)][pairs.index(pair2)].append(link)

    # transitive closure
    for k in range(len(pairs)):
        for i in range(len(pairs)):
            for j in range(len(pairs)):
                for adjacency1 in adjacency[i][k]:
                    for adjacency2 in adjacency[k][j]:
                        cells_to_discard = test_new_chain(grid, adjacency[i][j],
                                                          adjacency1, adjacency2, all_solutions, remote_pair)
                        if cells_to_discard:
                            return apply_xy_chain(grid, caption, explain, adjacency[i][j][-1], cells_to_discard, remote_pair)

    if all_solutions:  # not used
        for i in range(len(pairs)):
            for j in range(len(pairs)):
                for chain in adjacency[i][j]:
                    cells_to_discard = test_xy_remove(grid, *chain)
                    if cells_to_discard:
                        return apply_xy_chain(grid, caption, explain, chain, cells_to_discard, remote_pair)

    return 0


def solve_remote_pair(grid, explain):
    return solve_XY_chain(grid, explain, remote_pair=True)


def apply_xy_chain(grid, caption, explain, link, cells_to_discard, remote_pair):
    cellchain, candchain = link
    candset = candchain[:2] if remote_pair else candchain[:1]
    remove_dict = candidates_cells(candset, cells_to_discard)
    if explain:
        explain_xy_chain(grid, caption, link, cells_to_discard, remote_pair, remove_dict)
    return apply_remove_candidates(grid, caption, remove_dict)


def xy_links(grid, remote_pair):
    """make list of pairs and list of links; each link is made of the list
    of pairs and the list of candidates
    """
    pairs = [cell for cell in grid.cells if cell.is_pair()]
    pairs = sorted(pairs)
    links = []

    for pair1 in pairs:
        for pair2 in pairs:
            if pair1 == pair2:
                pass
            elif pair1 not in pair2.peers:
                pass
            elif pair1.candidates == pair2.candidates:
                # remote pair
                cand1, cand2 = list(pair1.candidates)
                links.append([[pair1, pair2], [cand1, cand2, cand1]])
                links.append([[pair1, pair2], [cand2, cand1, cand2]])
            elif remote_pair:
                pass
            else:
                inter = pair1.candidates.intersection(pair2.candidates)
                if len(inter) == 0:
                    pass
                elif len(inter) == 1:
                    candlink = list(pair1.candidates - inter) + list(inter) + list(pair2.candidates - inter)
                    links.append([[pair1, pair2], candlink])
                else:
                    pass
    return pairs, links


def test_new_chain(grid, adjacency, adjacency1, adjacency2, all_solutions, remote_pair):
    cellchain1, candchain1 = adjacency1
    cellchain2, candchain2 = adjacency2
    if candchain1[-2:] != candchain2[:2]:
        # chains of candidates cannot be concatenated
        return False
    if any(x in cellchain2[1:] for x in cellchain1):
        # concatenation would make a loop
        return False
    if any((x[0] == candchain1[0] and x[-1] == candchain2[-1]) for _, x in adjacency):
        # already a chain of candidates with same start and end
        return False

    cellchain = cellchain1 + cellchain2[1:]
    candchain = candchain1 + candchain2[2:]

    # number of links: number of cells + number of links between cells
    # TODO: check
    # numlinks = len(cellchain) + (len(cellchain) - 1)
    # if numlinks > 20:
    #     return False

    adjacency.append([cellchain, candchain])

    # TODO: why never 4 paths from one cell to another
    # if len(adjacency) == 4:
    #     for index, x in enumerate(adjacency):
    #         print(index, x)

    if all_solutions:
        return False
    elif remote_pair:
        return test_remote_pair_remove(grid, cellchain)
    else:
        return test_xy_remove(grid, cellchain, candchain)


def test_xy_remove(grid, cellchain, candchain):
    if candchain[0] == candchain[-1]:
        digit = candchain[0]
        to_be_removed = cellinter(cellchain[0].peers, cellchain[-1].peers)
        to_be_removed = [cell for cell in to_be_removed if digit in cell.candidates]
        to_be_removed = [cell for cell in to_be_removed if cell not in cellchain]
        return to_be_removed
    return False


def test_remote_pair_remove(grid, cellchain):
    if len(cellchain) % 2 == 0:
        digits = cellchain[0].candidates
        to_be_removed = cellinter(cellchain[0].peers, cellchain[-1].peers)
        to_be_removed = [cell for cell in to_be_removed if digits.intersection(cell.candidates)]
        to_be_removed = [cell for cell in to_be_removed if cell not in cellchain]
        return to_be_removed
    return False


def explain_xy_chain(grid, caption, link, cells_to_discard, remote_pair, remove_dict):
    cellchain, candchain = link
    candset = candchain[:2] if remote_pair else candchain[:1]
    print_single_history(grid)
    print(describe_xy_chain(caption, candset, cellchain, candchain, remove_dict))
    L = []
    for cell, cand1, cand2 in zip(cellchain, candchain[:-1], candchain[1:]):
        L.append(([cell], [cand1], CellDecor.COLOR1, [cand2], CellDecor.COLOR2))
    L.append((cells_to_discard, candset, CellDecor.REMOVECAND))
    grid.dump(L)


def describe_xy_chain(caption, candset, cellchain, candchain, remove_cells):
    l = []
    l.append('%d-' % candchain[0])
    for index, cell in enumerate(cellchain[:-1]):
        l.append(cell.strcoord())
        l.append('-%d-' % candchain[index + 1])
    l.append(cellchain[-1].strcoord())
    l.append('-%d' % candchain[-1])
    candidates = '/'.join(str(_) for _ in sorted(candset))
    return '%s: %s %s => %s' % (
                caption, candidates, ' '.join(l), discarded_text(remove_cells))


# W-wing


def solve_w_wing(grid, explain):
    pairs = bivaluedict(grid)

    for candidates, cells in pairs.items():
        for wing1, wing2 in itertools.combinations(sorted(cells), 2):
            if wing1.rownum == wing2.rownum or wing1.colnum == wing2.colnum:
                continue
            for candidate in sorted(candidates):
                peers1 = wing1.same_digit_peers(candidate)
                peers2 = wing2.same_digit_peers(candidate)
                for peer in sorted(peers1):
                    inter = sorted(cellinter(peer.conjugates(candidate), peers2))
                    if inter:
                        nb_removed = apply_w_wing(grid, 'W-wing',
                            explain, candidates - {candidate}, [wing1, wing2, peer, inter[0]],
                            cellinter(wing1.peers, wing2.peers))
                        if nb_removed:
                            return nb_removed
    return 0


def apply_w_wing(grid, caption, explain, candidates, define_set, remove_set):
    remove_cells = candidates_cells(candidates, remove_set)
    if remove_cells:
        if explain:
            explain_w_wing(grid, caption, candidates, define_set, remove_set, remove_cells)
        return apply_remove_candidates(grid, caption, remove_cells)
    return 0


def explain_w_wing(grid, caption, candidates, define_set, remove_set, remove_cells):
    print_single_history(grid)
    print(describe_w_wing(caption, candidates, define_set, remove_cells))
    wing1, wing2, _, _ = define_set
    grid.dump(((define_set, wing1.candidates - candidates, CellDecor.COLOR2),
               ({wing1, wing2}, candidates, CellDecor.COLOR1),
               (remove_set, candidates, CellDecor.REMOVECAND),))


def describe_w_wing(caption, defcands, defset, remset):
    # W-Wing: 7/9 in r6c5,r9c9 connected by 9 in r68c8 => r9c5<>7
    wing1 = defset[0]
    return '%s: %s in %s connected by %d in %s => %s' % (
        caption,
        '/'.join(str(_) for _ in list(defcands) + list(wing1.candidates - defcands)),
        packed_coordinates(defset[:2]),
        list(wing1.candidates - defcands)[0],
        packed_coordinates(defset[2:]),
        discarded_text(remset))


# BUG+1


def solve_bug1(grid, explain):
    digits = defaultdict(set)
    more_than_2 = None
    for cell in grid.cells:
        if len(cell.candidates) == 0:
            # no candidates, not concerned
            pass
        elif len(cell.candidates) == 1:
            # should be handled with singles
            return 0
        elif len(cell.candidates) == 2:
            pass
        elif len(cell.candidates) == 3:
            if more_than_2:
                return 0
            more_than_2 = cell
        else:
            # more than three candidates
            return 0

        for candidate in cell.candidates:
            digits['row', cell.rownum, candidate].add(cell)
            digits['col', cell.colnum, candidate].add(cell)
            digits['box', cell.boxnum, candidate].add(cell)

    # no cell with more than two candidates (grid already solved for instance)
    if more_than_2 is None:
        return 0

    # search the extra candidates
    extra = None
    for candidate in more_than_2.candidates:
        if (len(digits['row', more_than_2.rownum, candidate]) != 2 or
            len(digits['col', more_than_2.colnum, candidate]) != 2 or
            len(digits['box', more_than_2.boxnum, candidate]) != 2):
            extra = candidate
            break
    assert extra

    # remove cells with extra candidate
    digits['row', more_than_2.rownum, candidate].discard(more_than_2)
    digits['col', more_than_2.colnum, candidate].discard(more_than_2)
    digits['box', more_than_2.boxnum, candidate].discard(more_than_2)

    # check all candidates in all rows, cols and boxes
    if any(len(cells) != 2 for cells in digits.values()):
        return 0

    return apply_bug1(grid, 'Bivalue Universal Grave + 1', explain,
                      more_than_2.candidates - {extra}, {}, {more_than_2})


def apply_bug1(grid, caption, explain, candidates, define_set, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_bug1(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_bug1(grid, caption, candidates, define_set, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_bug1(caption, candidates, define_set, remove_dict))
    grid.dump(((remove_set, candidates, CellDecor.REMOVECAND),))


def describe_bug1(caption, candidates, define_set, remove_dict):
    return '%s => %s' % (caption, discarded_text(remove_dict))


# Unique rectangle


def solve_uniqueness_test_1(grid, explain):
    pairs = bivaluedict(grid)

    for candidates, cells in pairs.items():
        for cell1, cell2 in itertools.combinations(sorted(cells), 2):
            if cell1.rownum == cell2.rownum:
                for row in grid.rows:
                    if row[0].rownum != cell1.rownum:
                        cell3 = row[cell1.colnum]
                        cell4 = row[cell2.colnum]
                        if cell3 in cells:
                            if candidates < cell4.candidates and len(cell4.candidates) > 2:
                                if in_two_boxes(cell1, cell2, cell3):
                                    return apply_uniqueness_test_1(grid, 'Uniqueness test 1', explain,
                                        candidates, [cell1, cell2, cell3, cell4], [cell4])
                        if cell4 in cells:
                            if candidates < cell3.candidates and len(cell3.candidates) > 2:
                                if in_two_boxes(cell1, cell2, cell3):
                                    return apply_uniqueness_test_1(grid, 'Uniqueness test 1', explain,
                                        candidates, [cell1, cell2, cell3, cell4], [cell3])
    return False


def apply_uniqueness_test_1(grid, caption, explain, candidates, define_set, remove_set):
    remove_dict = candidates_cells(candidates, remove_set)
    if remove_dict:
        if explain:
            explain_uniqueness_test_1(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_uniqueness_test_1(grid, caption, candidates, define_set, remove_set, remove_dict):
    print_single_history(grid)
    print(describe_xy_wing(caption, sorted(candidates), define_set, remove_dict))
    grid.dump(((define_set, candidates, CellDecor.DEFININGCAND),
               (remove_set, candidates, CellDecor.REMOVECAND),))


def solve_uniqueness_test_2(grid, explain):
    pairs = bivaluedict(grid)

    for candidates, cells in pairs.items():
        for cell1, cell2 in itertools.combinations(sorted(cells), 2):
            nb_removed = solve_uniqueness_test_2_on_unit(
                grid, explain, candidates, cell1, cell2, grid.rows, Cell.mrownum, Cell.mcolnum
            )
            if nb_removed:
                return nb_removed
            nb_removed = solve_uniqueness_test_2_on_unit(
                grid, explain, candidates, cell1, cell2, grid.cols, Cell.mcolnum, Cell.mrownum
            )
            if nb_removed:
                return nb_removed
    return 0


def solve_uniqueness_test_2_on_unit(grid, explain, candidates, cell1, cell2, rows, rownum, colnum):
    if rownum(cell1) == rownum(cell2):
        for row in rows:
            if rownum(row[0]) != rownum(cell1):
                cell3 = row[colnum(cell1)]
                cell4 = row[colnum(cell2)]
                if in_two_boxes(cell1, cell2, cell3):
                    if candidates < cell3.candidates and len(cell3.candidates) == 3 and cell3.candidates == cell4.candidates:
                        extra = min(cell3.candidates - candidates)
                        remove_set = cellinter(cell3.same_digit_peers(extra),
                                               cell4.same_digit_peers(extra))
                        nb_removed = apply_uniqueness_test_2(grid, 'Uniqueness test 2', explain,
                            [candidates, [extra]], [cell1, cell2, cell3, cell4], remove_set)
                        if nb_removed:
                            return nb_removed
    return 0


def apply_uniqueness_test_2(grid, caption, explain, candidates, define_set, remove_set):
    defcand, extra = candidates
    remove_dict = candidates_cells(extra, remove_set)
    if remove_dict:
        if explain:
            explain_uniqueness_test_2(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_uniqueness_test_2(grid, caption, candidates, define_set, remove_set, remove_dict):
    defcand, extra = candidates
    print_single_history(grid)
    print(describe_xy_wing(caption, sorted(defcand), define_set, remove_dict))
    grid.dump(((define_set, defcand, CellDecor.DEFININGCAND),
               (remove_set, extra, CellDecor.REMOVECAND),))


def solve_uniqueness_test_3(grid, explain):
    pairs = bivaluedict(grid)
    for candidates, cells in pairs.items():
        for cell1, cell2 in itertools.combinations(sorted(cells), 2):
            nb_removed = solve_uniqueness_test_3_on_unit(grid, explain, candidates, cell1, cell2, grid.rows, Cell.mrownum, Cell.mcolnum)
            if nb_removed:
                return nb_removed
            nb_removed = solve_uniqueness_test_3_on_unit(grid, explain, candidates, cell1, cell2, grid.cols, Cell.mcolnum, Cell.mrownum)
            if nb_removed:
                return nb_removed
    return 0


def solve_uniqueness_test_3_on_unit(grid, explain, candidates, cell1, cell2, rows, rownum, colnum):
    if rownum(cell1) == rownum(cell2):
        for row in rows:
            if rownum(row[0]) != rownum(cell1):
                cell3 = row[colnum(cell1)]
                cell4 = row[colnum(cell2)]
                if in_two_boxes(cell1, cell2, cell3):
                    if candidates < cell3.candidates and candidates < cell4.candidates:
                        nb_removed = solve_uniqueness_test_3_on_unit_target(grid, explain, candidates, cell1, cell2, cell3, cell4, rows, row)
                        if nb_removed:
                            return nb_removed
                        if cell3.boxnum == cell4.boxnum:
                            nb_removed = solve_uniqueness_test_3_on_unit_target(grid, explain, candidates, cell1, cell2, cell3, cell4, rows, grid.boxes[cell3.boxnum])
                            if nb_removed:
                                return nb_removed
    return 0


def solve_uniqueness_test_3_on_unit_target(grid, explain, candidates, cell1, cell2, cell3, cell4, rows, target):
    # will search for subset in target
    subcells = {cell for cell in target if len(cell.candidates) > 1}
    subcells.discard(cell3)
    subcells.discard(cell4)
    # the additional candidates in rectangle
    extra = cellunion(cell3.candidates, cell4.candidates) - candidates
    for length in range(2, 7):
        if length >= len(extra):
            for subset in itertools.combinations(subcells, length - 1):
                setcandidates = candidate_union(subset)
                setcandidates = setcandidates.union(extra)
                if len(setcandidates) == length:
                    # found a subset, completed with the extra candidates, it forms a naked subset of length length
                    cells_less_subset = [cell for cell in subcells if cell not in subset]
                    nb_removed = apply_naked_set_u3(
                        grid, 'Uniqueness test 3', explain, [candidates, setcandidates],
                        [cell1, cell2, cell3, cell4], subset, cells_less_subset
                    )
                    if nb_removed:
                        return nb_removed
    return 0


def apply_naked_set_u3(grid, caption, explain, candidates, define_set, subset, remove_set):
    defcand, extra = candidates
    remove_dict = candidates_cells(extra, remove_set)
    if remove_dict:
        if explain:
            explain_uniqueness_test_3(grid, caption, candidates, define_set, subset, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_uniqueness_test_3(grid, caption, candidates, define_set, subset, remove_set, remove_dict):
    defcand, extra = candidates
    print_single_history(grid)
    print(describe_xy_wing(caption, sorted(defcand), define_set, remove_dict))
    grid.dump(((define_set, defcand, CellDecor.DEFININGCAND),
               (define_set + list(subset), extra, CellDecor.COLOR3),
               (remove_set, extra, CellDecor.REMOVECAND),))


def solve_uniqueness_test_4(grid, explain):
    pairs = bivaluedict(grid)
    for candidates, cells in pairs.items():
        for cell1, cell2 in itertools.combinations(sorted(cells), 2):
            nb_removed = solve_uniqueness_test_4_on_unit(grid, explain, candidates, cell1, cell2, grid.rows, Cell.mrownum, Cell.mcolnum)
            if nb_removed:
                return nb_removed
            nb_removed = solve_uniqueness_test_4_on_unit(grid, explain, candidates, cell1, cell2, grid.cols, Cell.mcolnum, Cell.mrownum)
            if nb_removed:
                return nb_removed
    return 0


def solve_uniqueness_test_4_on_unit(grid, explain, candidates, cell1, cell2, rows, rownum, colnum):
    if rownum(cell1) == rownum(cell2):
        for row in rows:
            if rownum(row[0]) != rownum(cell1):
                cell3 = row[colnum(cell1)]
                cell4 = row[colnum(cell2)]
                if in_two_boxes(cell1, cell2, cell3):
                    if candidates < cell3.candidates and candidates < cell4.candidates:
                        for candidate in list(candidates):
                            peers = cellinter(cell3.same_digit_peers(candidate),
                                              cell4.same_digit_peers(candidate))
                            if not peers:
                                extra = list(candidates - {candidate})[0]
                                nb_removed = apply_uniqueness_test_2(grid, 'Uniqueness test 4', explain,
                                            [candidates, [extra]], [cell1, cell2, cell3, cell4], [cell3, cell4])
                                if nb_removed:
                                    return nb_removed
    return 0


def solve_uniqueness_test_5(grid, explain):
    pairs = bivaluedict(grid)
    for candidates, cells in pairs.items():
        for cell1 in sorted(cells):
            cell2s = [cell for cell in cell1.row
                if candidates < cell.candidates and len(cell.candidates) == 3]
            cell3s = [cell for cell in cell1.col
                if candidates < cell.candidates and len(cell.candidates) == 3]
            for cell2, cell3 in itertools.product(cell2s, cell3s):
                if cell2.candidates == cell3.candidates:
                    cell4 = cell3.row[cell2.colnum]
                    if in_two_boxes(cell1, cell2, cell3):
                        if cell4.candidates == candidates or cell4.candidates == cell2.candidates:
                            extracand = list(cell2.candidates - candidates)[0]
                            remove_set = cellinterx(cell2.same_digit_peers(extracand),
                                                    cell3.same_digit_peers(extracand),
                                                    cell4.same_digit_peers(extracand))
                            nb_removed = apply_uniqueness_test_2(grid, 'Uniqueness test 5', explain,
                                        [candidates, [extracand]], [cell1, cell2, cell3, cell4], remove_set)
                            if nb_removed:
                                return nb_removed
    return 0


def solve_uniqueness_test_6(grid, explain):
    pairs = bivaluedict(grid)
    for candidates, cells in pairs.items():
        for cell1, cell2 in itertools.combinations(sorted(cells), 2):
            if cell1.rownum != cell2.rownum and cell1.colnum != cell2.colnum:
                cell3 = cell1.row[cell2.colnum]
                cell4 = cell2.row[cell1.colnum]
                if in_two_boxes(cell1, cell2, cell3):
                    if cell3.candidates > candidates and cell4.candidates > candidates:
                        for candidate in list(candidates):
                            if (len(cell1.same_digit_in_row(candidate)) == 2 and
                                len(cell2.same_digit_in_row(candidate)) == 2 and
                                len(cell1.same_digit_in_col(candidate)) == 2 and
                                len(cell2.same_digit_in_col(candidate)) == 2):
                                nb_removed = apply_uniqueness_test_2(grid, 'Uniqueness test 6', explain,
                                            [candidates, [candidate]], [cell1, cell2, cell3, cell4], [cell3, cell4])
                                if nb_removed:
                                    return nb_removed
    return 0


def solve_hidden_rectangle(grid, explain):
    pairs = bivaluedict(grid)
    for candidates, cells in pairs.items():
        for cell1 in sorted(cells):
            cell2s = [cell for cell in cell1.row if candidates < cell.candidates]
            cell3s = [cell for cell in cell1.col if candidates < cell.candidates]
            for cell2, cell3 in itertools.product(cell2s, cell3s):
                if in_two_boxes(cell1, cell2, cell3):
                    cell4 = cell3.row[cell2.colnum]
                    if cell4.candidates >= candidates:
                        for candidate in list(candidates):
                            if (len(cell4.same_digit_in_row(candidate)) == 2 and
                                len(cell4.same_digit_in_col(candidate)) == 2):
                                extracand = list(cell1.candidates - {candidate})[0]
                                nb_removed = apply_uniqueness_test_2(grid, 'Hidden rectangle', explain,
                                            [candidates, [extracand]], [cell1, cell2, cell3, cell4], [cell4])
                                if nb_removed:
                                    return nb_removed
    return 0


def in_two_boxes(*cells):
    boxnum = set()
    for cell in cells:
        boxnum.add(cell.boxnum)
    return len(boxnum) == 2


def solve_avoidable_rectangle_1(grid, explain):
    for cell1 in grid.cells:
        if cell1.value and not cell1.given:
            cell2s = [cell for cell in cell1.row if cell != cell1 and cell.value and not cell.given]
            cell3s = [cell for cell in cell1.col if cell != cell1 and cell.value and not cell.given]
            for cell2, cell3 in itertools.product(cell2s, cell3s):
                if cell2.value == cell3.value:
                    if in_two_boxes(cell1, cell2, cell3):
                        cell4 = cell3.row[cell2.colnum]
                        if cell1.value in cell4.candidates:
                            return apply_uniqueness_test_2(grid, 'Avoidable rectangle type 1', explain,
                                            [[cell1.value, cell2.value], [cell1.value]], [cell1, cell2, cell3, cell4], [cell4])
    return 0


def solve_avoidable_rectangle_2(grid, explain):
    for cell1 in grid.cells:
        if cell1.value and not cell1.given:
            cell2s = [cell for cell in cell1.row if cell != cell1]  # TODO: start after cell?
            cell3s = [cell for cell in cell1.col if cell != cell1]
            for cell2, cell3 in itertools.product(cell2s, cell3s):
                if (cell2.value and not cell2.given and len(cell3.candidates) == 2 and cell2.value in cell3.candidates or
                    cell3.value and not cell3.given and len(cell2.candidates) == 2 and cell3.value in cell2.candidates):
                    if in_two_boxes(cell1, cell2, cell3):
                        cell4 = cell3.row[cell2.colnum]
                        if len(cell4.candidates) == 2 and cell1.value in cell4.candidates:
                            extracand = list(cell4.candidates - {cell1.value})[0]
                            if (cell2.candidates and extracand in cell2.candidates) or extracand in cell3.candidates:
                                if cell2.candidates:
                                    remove_set = cellinter(cell4.same_digit_peers(extracand), cell2.same_digit_peers(extracand))
                                    defcand = [cell1.value, cell3.value]
                                else:
                                    remove_set = cellinter(cell4.same_digit_peers(extracand), cell3.same_digit_peers(extracand))
                                    defcand = [cell1.value, cell2.value]
                                nb_removed = apply_avoidable_rectangle_2(grid, 'Avoidable rectangle type 2', explain,
                                                [defcand, [extracand]], [cell1, cell2, cell3, cell4], remove_set)
                                if nb_removed:
                                    return nb_removed
    return 0


def apply_avoidable_rectangle_2(grid, caption, explain, candidates, define_set, remove_set):
    defcand, extra = candidates
    remove_dict = candidates_cells(extra, remove_set)
    if remove_dict:
        if explain:
            explain_avoidable_rectangle_2(grid, caption, candidates, define_set, remove_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_avoidable_rectangle_2(grid, caption, candidates, define_set, remove_set, remove_dict):
    defcand, extracand = candidates
    print_single_history(grid)
    print(describe_xy_wing(caption, sorted(defcand), define_set, remove_dict))
    grid.dump(((define_set, defcand, CellDecor.DEFININGCAND),
               (define_set, extracand, CellDecor.COLOR4),
               (remove_set, extracand, CellDecor.REMOVECAND),))


# Sue de Coq


def subsets(cells, delta):
    candcells = [cell for cell in cells if cell.candidates]
    for size in range(1, len(candcells) + 1):
        for subset in itertools.combinations(sorted(candcells), size):
            candidates = candidate_union(subset)
            if len(candidates) - len(subset) == delta:
                yield subset, candidates


def solve_sue_de_coq(grid, explain):
    for pattern in sue_de_coq_patterns(grid, explain):
        cells, cells_row, cells_box, candidates, cand_row, cand_box, extra, row_less_cells, box_less_cells = pattern
        remove_dict = remove_cells_sue_de_coq(pattern)
        nb_removed = sum(len(cells) for cand, cells in remove_dict.items())
        if nb_removed > 0:
            apply_sue_de_coq(grid, 'Sue de Coq', explain,
                [candidates, cand_row, cand_box, extra],
                [cells, cells_row, cells_box], remove_dict)
            return nb_removed
    return 0


def solve_sue_de_coq_best(grid, explain):
    max_removed = 0
    max_pattern = None
    for pattern in sue_de_coq_patterns(grid, explain):
        remove_dict = remove_cells_sue_de_coq(pattern)
        nb_removed = sum(len(cells) for cand, cells in remove_dict.items())
        if nb_removed > max_removed:
            max_removed = nb_removed
            max_remove_dict = remove_dict
            max_pattern = pattern

    if max_removed > 0:
        cells, cells_row, cells_box, candidates, cand_row, cand_box, extra, row_less_cells, box_less_cells = max_pattern
        apply_sue_de_coq(grid, 'Sue de Coq', explain,
            [candidates, cand_row, cand_box, extra],
            [cells, cells_row, cells_box], max_remove_dict)
        return max_removed
    return 0


def sue_de_coq_patterns(grid, explain):
    for _ in sue_de_coq_row_patterns(grid, explain, grid.boxrows, grid.rows, grid.boxes, Cell.mrownum):
        yield _
    for _ in sue_de_coq_row_patterns(grid, explain, grid.boxcols, grid.cols, grid.boxes, Cell.mcolnum):
        yield _


def sue_de_coq_row_patterns(grid, explain, boxrows, row, box, mrownum):
    for boxrow in boxrows:
        candcells = [cell for cell in boxrow if cell.candidates]
        if len(candcells) < 2:
            continue

        for cells in itertools.combinations(candcells, 2):
            candidates = candidate_union(cells)
            if len(candidates) >= 4:
                row_less_cells = [cell for cell in row[mrownum(cells[0])] if cell.candidates and cell not in cells]
                box_less_cells = [cell for cell in box[cells[0].boxnum] if cell.candidates and cell not in cells]
                for (cells_row, cand_row), (cells_box, cand_box) in itertools.product(
                    subsets(row_less_cells, delta=1),
                    subsets(box_less_cells, delta=1)):
                    if candidates <= set().union(cand_row, cand_box) and not cellinterx(cells, cells_row, cells_box):
                        yield (cells, cells_row, cells_box, candidates, cand_row, cand_box, None,
                            row_less_cells, box_less_cells)

        if len(candcells) == 3:
            cells = candcells
            candidates = candidate_union(cells)
            if len(candidates) >= 5:
                row_less_cells = [cell for cell in row[mrownum(cells[0])] if cell.candidates and cell not in cells]
                box_less_cells = [cell for cell in box[cells[0].boxnum] if cell.candidates and cell not in cells]
                for (cells_row, cand_row), (cells_box, cand_box) in itertools.product(
                    subsets(row_less_cells, delta=1),
                    subsets(box_less_cells, delta=1)):
                    extra = candidates - set().union(cand_row, cand_box)
                    if len(extra) == 1 and not cellinterx(cells, cells_row, cells_box):
                        yield (cells, cells_row, cells_box, candidates, cand_row, cand_box, extra,
                            row_less_cells, box_less_cells)

                for (cells_row, cand_row), (cells_box, cand_box) in itertools.product(
                    subsets(row_less_cells, delta=1),
                    subsets(box_less_cells, delta=2)):
                    if (candidates <= set().union(cand_row, cand_box) and
                        not cellinterx(cells, cells_row, cells_box)):
                        yield (cells, cells_row, cells_box, candidates, cand_row, cand_box, None,
                            row_less_cells, box_less_cells)

                for (cells_row, cand_row), (cells_box, cand_box) in itertools.product(
                    subsets(row_less_cells, delta=2),
                    subsets(box_less_cells, delta=1)):
                    if (candidates <= set().union(cand_row, cand_box) and
                        not cellinterx(cells, cells_row, cells_box)):
                        yield (cells, cells_row, cells_box, candidates, cand_row, cand_box, None,
                            row_less_cells, box_less_cells)


def remove_cells_sue_de_coq(pattern):
    cells, cells_row, cells_box, candidates, cand_row, cand_box, extra, row_less_cells, box_less_cells = pattern
    remove_dict = dict()

    for cand in cand_row:
        remcells = [cell for cell in row_less_cells
            if cell not in cells_row and cand in cell.candidates]
        if remcells:
            remove_dict[cand] = remcells

    for cand in cand_box:
        remcells = [cell for cell in box_less_cells
            if cell not in cells_box and cand in cell.candidates]
        if remcells:
            remove_dict[cand] = remcells

    if extra:
        extracand = list(extra)[0]
        remcells1 = [cell for cell in row_less_cells
            if cell not in cells_row and extracand in cell.candidates]
        remcells2 = [cell for cell in box_less_cells
            if cell not in cells_box and extracand in cell.candidates]
        remcells = cellunion(remcells1, remcells2)
        if remcells:
            remove_dict[extracand] = remcells

    return remove_dict


def apply_sue_de_coq(grid, caption, explain, candidates, define_set, remove_dict):
    if remove_dict:
        if explain:
            explain_sue_de_coq(grid, caption, candidates, define_set, remove_dict)
        return apply_remove_candidates(grid, caption, remove_dict)
    return 0


def explain_sue_de_coq(grid, caption, candidates, define_set, remove_dict):
    cells, cells_row, cells_box = define_set
    print_single_history(grid)
    print(describe_sue_de_coq(caption, candidates, define_set, remove_dict))
    grid.dump([(cells, candidate_union(cells_row), CellDecor.COLOR1),
               (cells, candidate_union(cells_box), CellDecor.COLOR3),
               (cells_row, candidate_union(cells_row), CellDecor.COLOR1),
               (cells_box, candidate_union(cells_box), CellDecor.COLOR3),
                ] + [(cells, {cand}, CellDecor.REMOVECAND) for cand, cells in remove_dict.items()])


def describe_sue_de_coq(caption, digits, define_set, remove_dict):
    # Sue de Coq: r23c6 - {2579} (r456c6 - {1245}, r1c456 - {1789}) => r19c6<>1, r79c6<>5
    cells, cells_row, cells_box = define_set
    candidates, cand_row, cand_box, extra = digits
    return '%s: %s - {%s} (%s - {%s}, %s - {%s}) => %s' % (caption,
        packed_coordinates(cells),
        packed_candidates(candidates),
        packed_coordinates(cells_row),
        packed_candidates(cand_row),
        packed_coordinates(cells_box),
        packed_candidates(cand_box),
        discarded_text(remove_dict))


# Solving engine


# Simple Sudoku
# source: http://sudopedia.enjoysudoku.com/SSTS.html
STRATEGY_SSTS = 'n1,h1,n2,lc1,lc2,n3,n4,h2,bf2,bf3,sc1,sc2,mc2,mc1,h3,xy,h4'

# Hodoku
# upper case techniques are not yet implemented
STRATEGY_HODOKU_EASY = 'fh,n1,h1'
STRATEGY_HODOKU_MEDIUM = 'fh,n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3'
STRATEGY_HODOKU_HARD = 'fh,n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3,n4,h4,bf2,bf3,bf4,rp,bug1,sk,2sk,tf,er,w,xy,xyz,u1,u2,u3,u4,u5,u6,hr,ar1,ar2,fbf2,sbf2,sc1,sc2,mc1,mc2'
STRATEGY_HODOKU_UNFAIR = STRATEGY_HODOKU_HARD + ',BF5,BF6,BF7,fbf3,sbf3,fbf4,sbf4,FBF5,SBF5,FBF6,SBF6,FBF7,SBF7,sdc,x,xyc'


def make_list_techniques(strategy):
    ALL = ','.join(SOLVER.keys())
    ALL = STRATEGY_SSTS + ','  + ','.join(sorted(set(SOLVER.keys()) - set(STRATEGY_SSTS.split(','))))

    strategy = re.sub(r'\bssts\b', STRATEGY_SSTS, strategy)
    strategy = re.sub(r'\bhodoku_easy\b', STRATEGY_HODOKU_EASY, strategy)
    strategy = re.sub(r'\bhodoku_medium\b', STRATEGY_HODOKU_MEDIUM, strategy)
    strategy = re.sub(r'\bhodoku_hard\b', STRATEGY_HODOKU_HARD , strategy)
    strategy = re.sub(r'\bhodoku_unfair\b', STRATEGY_HODOKU_UNFAIR , strategy)
    strategy = re.sub(r'\ball\b', ALL, strategy)

    if '-' not in strategy:
        r = strategy.split(',')
    else:
        x, y = strategy.split('-')
        x = x.split(',')
        y = y.split(',')
        r = [z for z in x if z not in y]

    return r


SOLVER = {
    'fh': solve_full_house,
    'n1': solve_single_candidate,
    'n2': solve_nacked_pairs,
    'n3': solve_nacked_triples,
    'n4': solve_nacked_quads,
    'h1': solve_hidden_candidate,
    'h2': solve_hidden_pair,
    'h3': solve_hidden_triple,
    'h4': solve_hidden_quad,
    'lc1': solve_pointing,
    'lc2': solve_claiming,
    'l2': solve_locked_pairs,
    'l3': solve_locked_triples,
    'bf2': solve_X_wing,
    'bf3': solve_swordfish,
    'bf4': solve_jellyfish,
    'fbf2': solve_finned_x_wing,
    'sbf2': solve_sashimi_x_wing,
    'fbf3': solve_finned_swordfish,
    'sbf3': solve_sashimi_swordfish,
    'fbf4': solve_finned_jellyfish,
    'sbf4': solve_sashimi_jellyfish,
    'sc1': solve_coloring_trap,
    'sc2': solve_coloring_wrap,
    'mc1': solve_multi_coloring_type_1,
    'mc2': solve_multi_coloring_type_2,
    'sk': solve_skyscraper,
    '2sk': solve_2_string_kite,
    'tf': solve_turbot_fish,
    'er': solve_empty_rectangle,
    'xy': solve_XY_wing,
    'xyz': solve_XYZ_wing,
    'x': solve_X_chain,
    'rp': solve_remote_pair,
    'xyc': solve_XY_chain,
    'bug1': solve_bug1,
    'u1': solve_uniqueness_test_1,
    'u2': solve_uniqueness_test_2,
    'u3': solve_uniqueness_test_3,
    'u4': solve_uniqueness_test_4,
    'u5': solve_uniqueness_test_5,
    'u6': solve_uniqueness_test_6,
    'hr': solve_hidden_rectangle,
    'ar1': solve_avoidable_rectangle_1,
    'ar2': solve_avoidable_rectangle_2,
    'w': solve_w_wing,
    'sdc': solve_sue_de_coq,
    'sdc*': solve_sue_de_coq_best,
    'bt': solve_backtrack,
    'dlx': solve_dancing_links,
}


def apply_strategy(grid, list_techniques, explain):
    for technique in list_techniques:
        if technique.isupper():
            continue
        if SOLVER[technique](grid, explain):
            return True
    else:
        return False


def solve(grid, options, techniques, explain, step=False):
    list_techniques = make_list_techniques(techniques)
    if explain:
        print(grid.output_s81())
        grid.dump()
    while not grid.solved() and apply_strategy(grid, list_techniques, explain) and not options.step:
        if step:
            break
        else:
            pass
    if explain and not options.step:
        print_single_history(grid)
        grid.dump()


# Commands


def solvegrid(options, techniques, explain):
    """
    Solve a single grid given on the command line, in the clipboard or
    a file.
    """
    t0 = time.time()
    grid = Grid()
    grid.decorate = options.decorate

    if re.match(r'[\d.]{81}', options.solve):
        sgrid = options.solve
    elif re.match(r'(\d{1,9},){80}\d{1,9}', options.solve):
        sgrid = options.solve
    elif options.solve == 'clipboard':
        sgrid = clipboard.paste()
    elif os.path.isfile(options.solve):
        with open(options.solve) as f:
            sgrid = f.read()
    else:
        return False, None

    if options.format is None:
        grid.input(sgrid)
    elif options.format == 'ss':
        # TODO: remove
        grid.input(sgrid)
    else:
        print('Unknown format', options.format)
        return False, None

    if options.output == 'clipboard':
        solve(grid, options, techniques, explain)
        clipboard.copy(grid.dumpstr())
    else:
        if not explain:
            print(grid.output_s81())
            grid.dump()
        solve(grid, options, techniques, explain)
        if not explain:
            grid.dump()

    return True, time.time() - t0


def testfile(options, filename, techniques, explain):
    grid = Grid()
    grid.decorate = options.decorate
    ngrids = 0
    solved = 0
    try:
        with open(filename) as f:
            grids = f.readlines()
    except IOError:
        application_error('unable to read', filename)

    # remove empty lines and full line comments before choosing grids
    grids = [line for line in grids if line.strip() and line[0] != '#']

    # choose grids
    if options.first:
        if options.first < len(grids):
            grids = grids[:options.first]
    elif options.random:
        if options.random < len(grids):
            grids = random.sample(grids, options.random)
    else:
        pass

    t0 = time.time()

    try:
        f = open(options.output, 'wt') if options.output else sys.stdout
        for line in tqdm(grids, disable=not options.progressbar):
            if '#' in line:
                line = re.sub('#.*', '', line)
            try:
                input, output = line.strip().split(None, 1)
                grid.input(input)
                solve(grid, options, techniques, explain)
                if grid.compare_string(output):
                    solved += 1
                    if options.trace == 'success':
                        print(input, output, file=f)
                else:
                    # if True and re.match(r'([gcv]\d+){81}', output):
                    #     grid2 = Grid()
                    #     grid2.input(input)
                    #     sol1 = grid2.solution()
                    #     print(sol1)
                    #     grid2.input(output)
                    #     sol2 = grid2.solution()
                    #     if sol1 == sol2:
                    #         solved += 1
                    #         if options.trace == 'success':
                    #             print(input, output, file=f)
                    if options.trace == 'failure':
                        print(input, output, file=f)
                ngrids += 1
            except (ValueError, SudokuError):
                print(f'Test file: {filename:20} Result: False Solved: {solved}/{ngrids} Error: Incorrect line format')
                return False, 0
    finally:
        if options.output:
            f.close()

    timing = time.time() - t0
    success = solved == ngrids
    print(f'Test file: {filename:20} Result: {success} Solved: {solved}/{ngrids} Time: {timing:0.3}')
    return success, timing


def testdir(options, dirname, techniques, explain):
    tested = 0
    solved = 0
    t0 = time.time()
    for filename in sorted(glob.glob(f'{dirname}/*.txt')):
        filename = filename.replace('\\', '/')
        if not filename.startswith('.'):
            tested += 1
            success, timing = testfile(options, filename, techniques, explain)
            if success:
                solved += 1

    success = solved == tested
    timing_dir = time.time() - t0
    print(f'Test dir : {dirname:20} Result: {success} Solved: {solved}/{tested} Time: {timing_dir:0.3}')
    return success, timing_dir


def testbatch(options):
    success = True
    timing_batch = 0

    with open(options.batch) as batch:
        for line in batch:
            if line.strip() and line[0] not in ';#':
                testargs = line.strip()
                testoptions = parse_command_line(testargs)

                # propagate batch options
                if options.first:
                    testoptions.first = options.first
                if options.random:
                    testoptions.random = options.random
                if options.explain:
                    testoptions.explain = options.explain
                if options.decorate:
                    testoptions.decorate = options.decorate

                success, timing = main_args(testoptions)
                if not success:
                    break
                timing_batch += timing

    print(f'BATCH OK Time: {timing_batch:0.3}' if success else 'TEST FAILURE')
    return success, timing_batch


def compare_output(options):
    compare = options.compare
    reference = options.reference
    options.compare = None
    options.reference = None
    t0 = time.time()

    with io.StringIO() as buf, redirect_stdout(buf):
        main_args(options)
        output = buf.getvalue()

    if reference:
        with open(reference, 'wt') as f:
            print(output, end='', file=f)
        res = True

    if compare:
        output = output.splitlines(True)

        with open(compare) as f:
            reference = f.readlines()

        # remove lines with timing
        reference = remove_timing(reference)
        output = remove_timing(output)

        res, diff = list_compare('ref', 'res', reference, output)
        print(f'COMPARE OK:' if res else 'COMPARE FAILURE:', compare)
        if not res:
            for _ in diff[0:20]:
                print(_, end='')
            with open('tmp.txt', 'wt') as f:
                for line in output:
                    print(line, file=f, end='')

    return res, time.time() - t0


def remove_timing(lines):
    result = []
    for line in lines:
        if 'Time' not in line:
            result.append(line)
        else:
            result.append(re.sub('Time: [^ \n]+', '', line))
    return result


def list_compare(tag1, tag2, list1, list2):

    # make sure both lists have same length
    maxlen = max(len(list1), len(list2))
    list1.extend(['extra\n'] * (maxlen - len(list1)))
    list2.extend(['extra\n'] * (maxlen - len(list2)))

    diff = list()
    res = True
    for i, (x, y) in enumerate(zip(list1, list2)):
        if x != y:
            diff.append('line %s %d: %s' % (tag1, i + 1, x))
            diff.append('line %s %d: %s' % (tag2, i + 1, y))
            res = False
    return res, diff


def list_compare(tag1, tag2, list1, list2):
    diff = list()
    res = True
    for i, (x, y) in enumerate(itertools.zip_longest(list1, list2, fillvalue='extra\n')):
        if x != y:
            diff.append('line %s %d: %s' % (tag1, i + 1, x))
            diff.append('line %s %d: %s' % (tag2, i + 1, y))
            res = False
    return res, diff


def application_error(*args):
    print('sudosol error:', *args)
    exit(1)


def parse_command_line(argstring=None):
    usage = "usage: sudosol ..."
    parser = argparse.ArgumentParser(description=usage, usage=argparse.SUPPRESS)
    parser.add_argument('-s', '--solve', help='solve grid in command line argument, clipboard or file',
                        action='store', default=None)
    parser.add_argument('-f', '--format', help='format',
                        action='store', default=None)
    parser.add_argument('-t', '--testfile', help='test file',
                        action='store', default=None)
    parser.add_argument('-T', '--testdir', help='test directory',
                        action='store', default=None)
    parser.add_argument('-b', '--batch', help='test batch',
                        action='store', default=None)
    parser.add_argument('--reference', help='make file reference for comparison',
                        action='store', default=None)
    parser.add_argument('--compare', help='compare test output with file argument',
                        action='store', default=None)
    parser.add_argument('--random', help='test N random grids from file',
                        type=int,
                        action='store', default=None)
    parser.add_argument('--first', help='test N first grids from file',
                        type=int,
                        action='store', default=None)
    parser.add_argument('--techniques', help='techniques',
                        action='store', default='ssts')
    parser.add_argument('--step', help='apply a single step from the given technique set',
                        action='store_true', default=False)
    parser.add_argument('--explain', help='explain techniques',
                        action='store_true', default=False)
    parser.add_argument('--decorate', help='candidate decor when tracing grid',
                        choices=['none', 'color', 'char'],
                        action='store', default=None)
    parser.add_argument('--trace', help='additional traces',
                        choices=['success', 'failure'],
                        action='store', default=None)
    parser.add_argument('--output', help='file to trace on',
                        action='store', default=None)
    parser.add_argument('--progressbar', help='display progress bar when solving file',
                        action='store_true', default=False)

    if argstring is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argstring.split())
    return args


def main(argstring=None):
    options = parse_command_line(argstring)
    return main_args(options)


def main_args(options):
    if options.compare or options.reference:
        return compare_output(options)

    elif options.solve:
        return solvegrid(options, options.techniques, options.explain)

    elif options.testfile:
        return testfile(options, options.testfile, options.techniques, options.explain)

    elif options.testdir:
        return testdir(options, options.testdir, options.techniques, options.explain)

    elif options.batch:
        return testbatch(options)

    else:
        return False, None


if __name__ == '__main__':
    colorama.init()
    success, timing = main()
    if success:
        exit(0)
    else:
        exit(1)
