import argparse
import os
import sys
import re
import itertools
import glob
import random
import time
import io

from collections import defaultdict
from enum import Enum
from contextlib import redirect_stdout
from tqdm import tqdm

import clipboard
import colorama
from colorama import Fore


VERSION = '0.1'


# Data structures


ALLCAND = {1, 2, 3, 4, 5, 6, 7, 8, 9}
ALLDIGITS = (1, 2, 3, 4, 5, 6, 7, 8, 9)


class Cell:
    def __init__(self, cellnum):
        self.value = None
        self.candidates = set(range(1, 10))
        self.cellnum = cellnum
        self.rownum = cellnum // 9
        self.colnum = cellnum % 9
        self.boxnum = (self.rownum // 3) * 3 + self.colnum // 3

        # to be completed in grid.__init__
        self.row = set()
        self.col = set()
        self.box = set()
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
        self.value = None
        self.candidates = set(range(1, 10))

    def set_value(self, digit):
        self.value = digit
        self.candidates = set()

    def discard(self, digit):
        """remove a candidate from cell
        """
        self.candidates.discard(digit)

    def is_pair(self):
        return len(self.candidates) == 2

    def same_digit_in_row(self, digit):
        """return all cells in self row with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.row if digit in peer.candidates)

    def same_digit_in_col(self, digit):
        """return all cells in self col with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.col if digit in peer.candidates)

    def same_digit_in_box(self, digit):
        """return all cells in self box with digit as candidate (possibly
        including self)
        """
        return set(peer for peer in self.box if digit in peer.candidates)

    def same_digit_peers(self, digit):
        """return all cells in self peers with digit as candidate (not
        including self)
        """
        return set(peer for peer in self.peers if digit in peer.candidates)

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
        self.horizontal_triplets = [self.cells[i:i + 3] for i in range(0, 81, 3)]

        # make the list of vertical triplets
        self.vertical_triplets = []
        for col in self.cols:
            self.vertical_triplets.extend([col[i:i + 3] for i in range(0, 9, 3)])

        # make the list of complements of triplets in rows:
        self.rows_less_triplet = []
        for triplet in self.horizontal_triplets:
            row_less_triplet = [cell for cell in self.rows[triplet[0].rownum] if cell not in triplet]
            self.rows_less_triplet.append(row_less_triplet)

        # make the list of complements of triplets in cols:
        self.cols_less_triplet = []
        for triplet in self.vertical_triplets:
            col_less_triplet = [cell for cell in self.cols[triplet[0].colnum] if cell not in triplet]
            self.cols_less_triplet.append(col_less_triplet)

        # make the list of complements of horizontal triplets in boxes:
        self.boxes_less_hortriplet = []
        for triplet in self.horizontal_triplets:
            box_less_triplet = [cell for cell in self.boxes[triplet[0].boxnum] if cell not in triplet]
            self.boxes_less_hortriplet.append(box_less_triplet)

        # make the list of complements of vertical triplets in boxes:
        self.boxes_less_vertriplet = []
        for triplet in self.vertical_triplets:
            box_less_triplet = [cell for cell in self.boxes[triplet[0].boxnum] if cell not in triplet]
            self.boxes_less_vertriplet.append(box_less_triplet)

        # init cell data
        for cell in self.cells:
            cell.row = self.rows[cell.rownum]
            cell.col = self.cols[cell.colnum]
            cell.box = self.boxes[cell.boxnum]

        # peers
        # properties: x not in x.peers, x in y.peers equivalent to y in x.peers
        for cell in self.cells:
            cell.peers = sorted(cellunion(cell.row, cellunion(cell.col, cell.box)))
            cell.peers.remove(cell)

        # init history
        self.history = []

        # cell decoration when tracing ('color' or 'char')
        self.decorate = 'color'

    def reset(self):
        for cell in self.cells:
            cell.reset()

    def input(self, str81):
        """load a 81 character string
        """
        self.reset()
        for index, char in enumerate(str81):
            if char not in '.0':
                self.set_value(self.cells[index], int(char))

    def output(self):
        """return a 81 character string
        """
        return ''.join(str(cell.value) if cell.value else '.' for cell in self.cells)

    def cell_rc(self, irow, icol):
        return self.rows[irow][icol]

    def box_rc(self, irow, icol):
        return self.boxes[(irow // 3) * 3 + icol // 3]

    def set_value(self, cell, digit):

        discarded = defaultdict(set)
        for candidate in cell.candidates:
            discarded[candidate].add(cell)
        cell.set_value(digit)

        for peer in cell.peers:
            if digit in peer.candidates:
                peer.discard(digit)
                discarded[digit].add(peer)

        return discarded

    def solved(self):
        return all(cell.value is not None for cell in self.cells)

    def dump(self, decor=None):
        if self.decorate == 'color':
            colorize_candidates = colorize_candidates_color
        elif self.decorate == 'char':
            colorize_candidates = colorize_candidates_char
        else:
            colorize_candidates = colorize_candidates_color

        hborder = ('+' + ('-' * (3 * 10 - 1))) * 3 + '+'
        for i in range(9):
            if i % 3 == 0:
                print(hborder)
            line = []
            for j, cell in enumerate(self.rows[i]):
                line.append('%s%-9s' % ('|' if j % 3 == 0  else ' ', colorize_candidates(cell, decor)))
            print(''.join(line) + '|')
        print(hborder)
        print()

    def push(self, item):
        self.history.append(item)


CellDecor = Enum('CellDecor', 'VALUE DEFAULTCAND DEFININGCAND REMOVECAND COLOR1 COLOR2 COLOR3 COLOR4')

CellDecorColor = {
    CellDecor.VALUE: Fore.BLUE,
    CellDecor.DEFAULTCAND: Fore.WHITE,
    CellDecor.DEFININGCAND: Fore.GREEN,
    CellDecor.REMOVECAND: Fore.RED,
    CellDecor.COLOR1: Fore.GREEN,
    CellDecor.COLOR2: Fore.CYAN,
    CellDecor.COLOR3: Fore.YELLOW,
    CellDecor.COLOR4: Fore.MAGENTA
}

def colorize_candidates_color(cell, spec_color):
    """
    col_spec ::= [cells, [candidates, color]*]*
    ex:
    (({cell}, [1], CellDecor.COLOR1),
     ((cell1, cell2), ALLCAND, CellDecor.COLOR2, {cand1, cand2}, CellDecor.COLOR1))

    cells and candidates are iterables.
    A cell or a candidate may appear several times. The last color spec is taken into accout.
    """
    if not cell.candidates:
        res = CellDecorColor[CellDecor.VALUE] + str(cell.value)  + Fore.RESET
        # manual padding as colorama information fools format padding
        res += ' ' * (9 - 1)
        return res
    else:
        if spec_color is None:
            res = CellDecorColor[CellDecor.DEFAULTCAND] + str(cell) + Fore.RESET
        else:
            candcol = retain_decor(cell, spec_color)
            res = ''
            for cand in sorted(cell.candidates):
                res += CellDecorColor[candcol[cand]] + str(cand) + Fore.RESET

        # manual padding as colorama information fools format padding
        res += ' ' * (9 - len(cell.candidates))
        return res


CellDecorChar = {
    CellDecor.VALUE: '.',
    CellDecor.DEFAULTCAND: '',
    CellDecor.DEFININGCAND: '!',
    CellDecor.REMOVECAND: 'x',
    CellDecor.COLOR1: 'a',
    CellDecor.COLOR2: 'b',
    CellDecor.COLOR3: 'c',
    CellDecor.COLOR4: 'd'
}


def colorize_candidates_char(cell, spec_color):
    """
    col_spec ::= [cells, [candidates, color]*]*
    ex:
    (({cell}, [1], CellDecor.COLOR1),
     ((cell1, cell2), ALLCAND, CellDecor.COLOR2, {cand1, cand2}, CellDecor.COLOR1))

    cells and candidates are iterables.
    A cell or a candidate may appear several times. The last color spec is taken into accout.
    """
    if not cell.candidates:
        return str(cell.value) + CellDecorChar[CellDecor.VALUE]

    if spec_color is None:
        res = str(cell)
    else:
        candcol = retain_decor(cell, spec_color)
        res = ''
        for cand in sorted(cell.candidates):
            res += str(cand) + CellDecorChar[candcol[cand]]

    res += ' ' * (9 - len(res))
    return res


def retain_decor(cell, spec_color):
    candcol = defaultdict(lambda:CellDecor.DEFAULTCAND)
    for target, *spec_col in spec_color:
        if cell in target:
            for cand in cell.candidates:
                for spec_cand, speccol in zip(spec_col[::2], spec_col[1::2]):
                    if cand in spec_cand:
                        candcol[cand] = speccol
    return candcol


def candidate_in_cells(digit, cells):
    for cell in cells:
        if digit in cell.candidates:
            return True
    else:
        return False


def cellinter(cells1, cells2):
    return [cell for cell in cells1 if cell in cells2]


def cellunion(cells1, cells2):
    return set.union(set(cells1), set(cells2))


def cellunionx(*list_of_list_cells):
    return set.union(*[set(cells) for cells in list_of_list_cells])


# Loading


def load_ss_clipboard(grid, content):
    grid.reset()
    content = content.splitlines()

    if len(content) == 28:      # when starting
        lines = ''.join(content[1:4] + content[5:8] + content[9:12])
        values = lines.replace('|', '')
        values = values.replace(' ', '')
        grid.input(values)

    elif len(content) == 43:    # after first move
        # TODO: should set candidates
        # values
        lines = ''.join(content[16:19] + content[20:23] + content[24:27])
        values = lines.replace('|', '')
        values = values.replace(' ', '')
        grid.input(values)
        # candidates
        lines = content[31:34] + content[35:38] + content[39:42]
        lines = [re.findall(r'\b\d+\b', line) for line in lines]
        if any([len(x) != 9 for x in lines]):
            print('bad clipboard (2)')
            exit(1)
        cells = sum(lines, [])
        for cell, cand in zip(grid.cells, cells):
            cell.candidates = set(int(_) for _ in cand)

    else:
        print(content)
        print('bad clipboard (1)')
        exit(1)

    return lines


# Helpers


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


def apply_remove_candidates(grid, caption, remove_cells):
    grid.push((caption, 'discard', remove_cells))
    for candidate, cell in candidate_cells(remove_cells):
        cell.candidates.discard(candidate)


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
    for digit, cells in cand_cells_dict.items():
        list_coord.append(f'{packed_coordinates(cells)}<>{digit}')
    return ', '.join(list_coord)


def single_history(grid):
    start = len(grid.history) - 1

    i = start
    while i >= 0 and grid.history[i][0] in ('Naked single', 'Hidden single'):
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

# Singles


def solve_single_candidate(grid, explain):
    # naked singles
    for cell in grid.cells:
        if len(cell.candidates) == 1:
            value = list(cell.candidates)[0]
            discarded = grid.set_value(cell, value)
            grid.push(('Naked single', 'value', cell, value, discarded))
            return True
    return False


# Single digit techniques


def solve_hidden_candidate(grid, explain):
    # hidden singles
    grid_modified = False
    for cell in grid.cells:
        cands = cell.candidates
        for cand in cands:
            rowcells = cell.same_digit_in_row(cand)
            colcells = cell.same_digit_in_col(cand)
            boxcells = cell.same_digit_in_box(cand)
            if len(rowcells) == 1 or len(colcells) == 1 or len(boxcells) == 1:
                grid_modified = True
                discarded = grid.set_value(cell, cand)
                grid.push(('Hidden single', 'value', cell, cand, discarded))
                # avoid to loop on candidates from initial cell state
                break
    return grid_modified


# Locked sets


def solve_locked_pairs(grid, explain):

    for trinum, triplet in enumerate(grid.horizontal_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.rows_less_triplet[trinum] + grid.boxes_less_hortriplet[trinum]
                result = apply_locked_sets(grid, 'Locked pair', explain, subset[0].candidates, subset, cells_to_discard)
                if result:
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                result = apply_locked_sets(grid, 'Locked pair', explain, subset[0].candidates, subset, cells_to_discard)
                if result:
                    return True

    return False


def solve_locked_triples(grid, explain):

    for trinum, triplet in enumerate(grid.horizontal_triplets):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = set().union(*(cell.candidates for cell in triplet))
            if len(candidates) == 3:
                cells_to_discard = grid.rows_less_triplet[trinum] + grid.boxes_less_hortriplet[trinum]
                result = apply_locked_sets(grid, 'Locked triple', explain, candidates, triplet, cells_to_discard)
                if result:
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = set().union(*(cell.candidates for cell in triplet))
            if len(candidates) == 3:
                cells_to_discard = grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                result = apply_locked_sets(grid, 'Locked triple', explain, candidates, triplet, cells_to_discard)
                if result:
                    return True

    return False


def apply_locked_sets(grid, caption, explain, candidates, define_set, remove_set):
    remove_cells = candidates_cells(candidates, remove_set)
    if remove_cells:
        if explain:
            remove_set2 = set().union(*(cells for cand, cells in remove_cells.items()))
            print_single_history(grid)
            print(describe_locked_set(caption, candidates, define_set, remove_cells))
            grid.dump(((define_set, candidates, CellDecor.DEFININGCAND),
                       (remove_set2, candidates, CellDecor.REMOVECAND)))
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def describe_locked_set(legend, defcands, defset, remset):
    return '%s: %s in %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(defcands)),
        packed_coordinates(defset),
        discarded_text(remset))


# Locked candidates


def solve_pointing(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_hortriplet[trinum])):
                result = apply_locked_candidates(grid, 'Pointing', 'b', explain, [digit], triplet,
                                                 grid.rows_less_triplet[trinum])
                if result:
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_vertriplet[trinum])):
                result = apply_locked_candidates(grid, 'Pointing', 'b', explain, [digit], triplet,
                                                 grid.cols_less_triplet[trinum])
                if result:
                    return True

    return False


def solve_claiming(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.rows_less_triplet[trinum])):
                result = apply_locked_candidates(grid, 'Claiming', 'r', explain, [digit], triplet,
                                                 grid.boxes_less_hortriplet[trinum])
                if result:
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.cols_less_triplet[trinum])):
                result = apply_locked_candidates(grid, 'Claiming', 'c', explain, [digit], triplet,
                                                 grid.boxes_less_vertriplet[trinum])
                if result:
                    return True

    return False


def apply_locked_candidates(grid, caption, flavor, explain, candidates, subset, cells_to_discard):
    remove_cells = candidates_cells(candidates, cells_to_discard)
    if remove_cells:
        if explain:
            print_single_history(grid)
            print(describe_locked_candidates(caption, flavor, candidates, subset, remove_cells))
            grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
                        (cells_to_discard, candidates, CellDecor.REMOVECAND)))
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def describe_locked_candidates(caption, flavor, defcands, defset, remset):
    if flavor == 'b':
        defunit = f'b{defset[0].boxnum + 1}'
    elif flavor == 'r':
        defunit = f'r{defset[0].rownum + 1}'
    elif flavor == 'c':
        defunit = f'c{defset[0].colnum + 1}'
    return '%s: %s in %s => %s' % (caption,
        ','.join(f'{_}' for _ in sorted(defcands)),
        defunit,
        discarded_text(remset))


# Locked sets


def apply_naked_set(grid, caption, explain, candidates, subset, cells_to_discard, subcells):
    remove_cells = candidates_cells(candidates, cells_to_discard)
    if remove_cells:
        if explain:
            print_single_history(grid)
            if caption.startswith('Naked'):
                print(describe_locked_set(caption, candidates, subset, remove_cells))
                grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
                           (cells_to_discard, candidates, CellDecor.REMOVECAND)))
            if caption.startswith('Hidden'):
                allcand = set().union(*(cell.candidates for cell in subcells))
                print(describe_locked_set(caption, allcand - candidates, cells_to_discard, remove_cells))
                grid.dump(((cells_to_discard,
                            ALLCAND - candidates, CellDecor.DEFININGCAND,
                            candidates, CellDecor.REMOVECAND),))
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def nacked_sets_n(grid, cells, subcells, length, legend, explain):
    if subcells is None:
        subcells = [cell for cell in cells if len(cell.candidates) > 1]
    for subset in itertools.combinations(subcells, length):
        candidates = set().union(*(cell.candidates for cell in subset))
        if len(candidates) == length:
            cells_less_subset = [cell for cell in subcells if cell not in subset]
            result = apply_naked_set(grid, legend, explain, candidates, subset, cells_less_subset, subcells)
            if result:
                return True
    return False


def solve_nacked_pairs(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 2, 'Naked pair', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 2, 'Naked pair', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 2, 'Naked pair', explain) for box in grid.boxes)
    )


def solve_nacked_triples(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 3, 'Naked triple', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 3, 'Naked triple', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 3, 'Naked triple', explain) for box in grid.boxes)
    )


def solve_nacked_quads(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 4, 'Naked quadruple', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 4, 'Naked quadruple', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 4, 'Naked quadruple', explain) for box in grid.boxes)
    )


def solve_hidden_set(grid, cells, length, legend, explain):
    subcells = [cell for cell in cells if len(cell.candidates) > 1]
    for len_naked_set in range(5, 10 - length):
        len_hidden_set = len(subcells) - len_naked_set
        if len_hidden_set == length:
            if nacked_sets_n(grid, cells, subcells, len_naked_set, legend, explain):
                return True
    return False


def solve_hidden_pair(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 2, 'Hidden pair', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 2, 'Hidden pair', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 2, 'Hidden pair', explain) for box in grid.boxes)
    )


def solve_hidden_triple(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 3, 'Hidden triple', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 3, 'Hidden triple', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 3, 'Hidden triple', explain) for box in grid.boxes)
    )


def solve_hidden_quad(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 4, 'Hidden quadruple', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 4, 'Hidden quadruple', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 4, 'Hidden quadruple', explain) for box in grid.boxes)
    )


# Basic fishes


def solve_X_wing(grid, explain):
     return solve_basicfish(grid, explain, 2, 'X-wing')


def solve_swordfish(grid, explain):
    return solve_basicfish(grid, explain, 3, 'Swordfish')


def solve_jellyfish(grid, explain):
    return solve_basicfish(grid, explain, 4, 'Jellyfish')


def solve_basicfish(grid, explain, order, name):

    for digit in ALLDIGITS:

        rows = []
        for row in grid.rows:
            rowcells = [cell for cell in row if digit in cell.candidates]
            if 1 < len(rowcells) <= order:
                rows.append(rowcells)

        for defrows in itertools.combinations(rows, order):
            rowsnum = [row[0].rownum for row in defrows]
            colsnum = {cell.colnum for row in defrows for cell in row}
            if len(colsnum) == order:
                # n rows with candidates in n cols
                cells_to_discard = []
                for colnum in colsnum:
                    for cell in grid.cols[colnum]:
                        if cell.rownum not in rowsnum:
                            cells_to_discard.append(cell)
                if apply_basicfish(grid, name, explain, [digit], defrows, cells_to_discard, 'H'):
                    return True

        cols = []
        for col in grid.cols:
            colcells = [cell for cell in col if digit in cell.candidates]
            if 1 < len(colcells) <= order:
                cols.append(colcells)

        for defcols in itertools.combinations(cols, order):
            colsnum = [col[0].colnum for col in defcols]
            rowsnum = {cell.rownum for col in defcols for cell in col}
            if len(rowsnum) == order:
                cells_to_discard = []
                for rownum in rowsnum:
                    for cell in grid.rows[rownum]:
                        if cell.colnum not in colsnum:
                            cells_to_discard.append(cell)
                if apply_basicfish(grid, name, explain, [digit], defcols, cells_to_discard, 'V'):
                    return True
    return False


def apply_basicfish(grid, caption, explain, candidates, defunits, cells_to_discard, flavor):
    remove_cells = candidates_cells(candidates, cells_to_discard)
    if remove_cells:
        if explain:
            subset = cellunionx(*defunits)
            print_single_history(grid)
            print(describe_basic_fish(caption, candidates, subset, flavor, remove_cells))
            grid.dump(((subset, candidates, CellDecor.DEFININGCAND),
                       (cells_to_discard, candidates, CellDecor.REMOVECAND)))
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def describe_basic_fish(legend, defcands, subset, dir, remove_cells):
    rows = {cell.rownum + 1 for cell in subset}
    cols = {cell.colnum + 1 for cell in subset}
    srows = ''.join(f'{_}' for _ in sorted(list(rows)))
    scols = ''.join(f'{_}' for _ in sorted(list(cols)))
    defcells = f'r{srows} c{scols}' if dir == 'H' else f'c{scols} r{srows}'
    return '%s: %s %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(defcands)),
        defcells,
        discarded_text(remove_cells))


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
            cells_to_discard = cellinter(peers_cluster_blue, peers_cluster_green)

            if cells_to_discard:
                apply_colortrap(grid, 'Simple color trap', explain, digit, cluster_blue, cluster_green, cells_to_discard)
                return True

    return False


def apply_colortrap(grid, caption, explain, digit, cluster_blue, cluster_green, cells_to_discard):
    remove_cells = candidates_cells([digit], cells_to_discard)
    if explain:
        print_single_history(grid)
        print(describe_simple_coloring(caption, digit, cluster_green, cluster_blue, remove_cells))
        grid.dump(((cluster_green, [digit], CellDecor.COLOR1),
                    (cluster_blue, [digit], CellDecor.COLOR2),
                    (cells_to_discard, [digit], CellDecor.REMOVECAND)))
    apply_remove_candidates(grid, caption, remove_cells)
    return True


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
                apply_colorwrap(grid, 'Simple color wrap', explain, digit, cluster_blue, cluster_green, cluster_blue)
                return True

            if color_contradiction(cluster_green):
                apply_colorwrap(grid, 'Simple color wrap', explain, digit, cluster_blue, cluster_green, cluster_green)
                return True

    return False


def apply_colorwrap(grid, caption, explain, digit, cluster_blue, cluster_green, cells_to_discard):
    remove_cells = candidates_cells([digit], cells_to_discard)
    if explain:
        print_single_history(grid)
        print(describe_simple_coloring(caption, digit, cluster_blue, cluster_green, remove_cells))
        grid.dump(((cluster_blue, [digit], CellDecor.COLOR1),
                    (cluster_green, [digit], CellDecor.COLOR2),
                    (cells_to_discard, [digit], CellDecor.REMOVECAND)))
    apply_remove_candidates(grid, caption, remove_cells)
    return True


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
            apply_multicolor(grid, 'Multi color type 1', explain, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            to_be_removed)
            return True

    return False


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
            apply_multicolor(grid, 'Multi color type 2', explain, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            to_be_removed)
            return True

    return False


def apply_multicolor(grid, caption, explain, digit,
                     cluster_blue1, cluster_green1,
                     cluster_blue2, cluster_green2,
                     cells_to_discard):
    remove_cells = candidates_cells([digit], cells_to_discard)
    if explain:
        print_single_history(grid)
        print(describe_multi_coloring(caption, digit,
                    cluster_blue1, cluster_green1,
                    cluster_blue2, cluster_green2, remove_cells))
        grid.dump(((cluster_blue1, [digit], CellDecor.COLOR1),
                   (cluster_green1, [digit], CellDecor.COLOR2),
                   (cluster_blue2, [digit], CellDecor.COLOR3),
                   (cluster_green2, [digit], CellDecor.COLOR4),
                   (cells_to_discard, [digit], CellDecor.REMOVECAND)))
    apply_remove_candidates(grid, caption, remove_cells)
    return True


def describe_multi_coloring(caption, digit,
                            cluster_blue1, cluster_green1,
                            cluster_blue2, cluster_green2,
                            remove_cells):
    """multi coloring is limited to two clusters.
    """
    return '%s: %d (%s) / (%s), (%s) / (%s) => %s' % (caption, digit,
        packed_coordinates(cluster_blue1),
        packed_coordinates(cluster_green1),
        packed_coordinates(cluster_blue2),
        packed_coordinates(cluster_green2),
        discarded_text(remove_cells))


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
                                apply_x_chain(grid, digit, technique, explain,
                                              adjacency[i][j][-1], cells_to_discard)
                                return adjacency[i][j][-1]
    return False


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
    if  tuple(chain1[-2:]) not in strong_links and tuple(chain2[:2]) not in strong_links:
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
    remove_cells = candidates_cells([digit], cells_to_discard)
    if explain:
        print_single_history(grid)
        print(describe_x_chain(caption[technique], digit, chain, remove_cells))
        L = []
        for cell1, cell2 in zip(chain[::2], chain[1::2]):
            L.extend((([cell1], [digit], CellDecor.COLOR1),
                      ([cell2], [digit], CellDecor.COLOR2)))
        L.append((cells_to_discard, [digit], CellDecor.REMOVECAND))
        grid.dump(L)
    apply_remove_candidates(grid, caption[technique], remove_cells)


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

        strong_links = []
        for row in grid.rows:
            cells = [cell for cell in row if digit in cell.candidates]
            if len(cells) == 2 and cells[0].boxnum != cells[1].boxnum:
                strong_links.append(cells)

        for strong_link in strong_links:
            floornum = strong_link[0].rownum // 3
            colnum1 = strong_link[0].colnum
            colnum2 = strong_link[1].colnum
            for row in grid.rows:
                if row[0].rownum // 3 != floornum:
                    if test_empty_rectangle(grid, explain, digit, strong_link, row, colnum1, colnum2):
                        return True
                    if test_empty_rectangle(grid, explain, digit, strong_link, row, colnum2, colnum1):
                        return True

        strong_links = []
        for col in grid.cols:
            cells = [cell for cell in col if digit in cell.candidates]
            if len(cells) == 2 and cells[0].boxnum != cells[1].boxnum:
                strong_links.append(cells)

        for strong_link in strong_links:
            towernum = strong_link[0].colnum // 3
            rownum1 = strong_link[0].rownum
            rownum2 = strong_link[1].rownum
            for col in grid.cols:
                if col[0].colnum // 3 != towernum:
                    if test_empty_rectangle(grid, explain, digit, strong_link, col, rownum1, rownum2):
                        return True
                    if test_empty_rectangle(grid, explain, digit, strong_link, col, rownum2, rownum1):
                        return True

    return False


def test_empty_rectangle(grid, explain, digit, strong_link, line, num1, num2):
    if digit in line[num1].candidates:
        pivot = line[num2]
        if is_empty_rectangle(grid, digit, pivot):
            apply_empty_rectangle(grid, digit, 'Empty rectangle', explain,
                strong_link, grid.boxes[pivot.boxnum], line[num1])
            return True
    return False


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
    remove_cells = candidates_cells([digit], [cell_to_discard])
    if explain:
        print_single_history(grid)
        print(describe_empty_rectangle(caption, digit, link, box, remove_cells))
        colors = [(link, [digit], CellDecor.COLOR1),
                  (box, [digit], CellDecor.COLOR2),
                  ([cell_to_discard], [digit], CellDecor.REMOVECAND)]
        grid.dump(colors)
    apply_remove_candidates(grid, caption, remove_cells)


def describe_empty_rectangle(caption, digit, link, box, remove_cells):
    return '%s: %d in b%d (%s) => %s' % (
        caption, digit, box[0].boxnum + 1, packed_coordinates(link), discarded_text(remove_cells))


# xy-wings


def solve_XY_wing(grid, explain):
    for cell in grid.cells:
        if cell.is_pair():
            cand1, cand2 = sorted(cell.candidates)
            pairpeers = (peer for peer in cell.peers if peer.is_pair())
            for wing1, wing2 in itertools.combinations(pairpeers, 2):
                if wing1 in wing2.peers:
                    # cell, wing1, wing2 in the same house: not a xy-wing
                    continue
                wings_inter = wing1.candidates.intersection(wing2.candidates)
                if len(wings_inter) != 1 or min(wings_inter) in cell.candidates:
                    continue
                if (cand1 in wing1.candidates and cand2 in wing2.candidates or
                    cand1 in wing2.candidates and cand2 in wing1.candidates):
                    digit = min(wings_inter)
                    cells_to_discard = cellinter(wing1.peers, wing2.peers)
                    if apply_xy_wing(grid, 'XY-wing', explain, [cand1, cand2, digit], [cell, wing1, wing2], cells_to_discard):
                        return True
    else:
        return False


def apply_xy_wing(grid, caption, explain, candidates, defcells, cells_to_discard):
    cand1, cand2, digit = candidates
    remove_cells = candidates_cells([digit], cells_to_discard)
    if remove_cells:
        if explain:
            cell, wing1, wing2 = defcells
            print_single_history(grid)
            print(describe_xy_wing(caption, candidates, defcells, remove_cells))
            grid.dump(((defcells, cell.candidates, CellDecor.COLOR1),
                    ((wing1, wing2), ALLCAND - cell.candidates, CellDecor.COLOR2),
                    (cells_to_discard, [digit], CellDecor.REMOVECAND)))
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def describe_xy_wing(caption, digits, cells, remove_cells):
    return '%s: %s in %s => %s' % (caption,
        '/'.join(f'{_}' for _ in digits),
        packed_coordinates(cells),
        discarded_text(remove_cells))


# xy-chains


def solve_XY_chain(grid, explain, remote_pair=False):
    all_solutions = False
    pairs, links = xy_links(grid, remote_pair)

    caption = 'Remote pair' if remote_pair else  'XY-chain'

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
                            apply_xy_chain(grid, caption, explain, adjacency[i][j][-1], cells_to_discard, remote_pair)
                            return True

    if all_solutions:
        for i in range(len(pairs)):
            for j in range(len(pairs)):
                for chain in adjacency[i][j]:
                    cells_to_discard = test_xy_remove(grid, *chain)
                    if cells_to_discard:
                        apply_xy_chain(grid, caption, explain, chain, cells_to_discard, remote_pair)
                        return True

    return False


def solve_remote_pair(grid, explain):
    return solve_XY_chain(grid, explain, remote_pair=True)


def apply_xy_chain(grid, caption, explain, link, cells_to_discard, remote_pair):
    cellchain, candchain = link
    candset = candchain[:2] if remote_pair else candchain[:1]
    remove_cells = candidates_cells(candset, cells_to_discard)
    if explain:
        print_single_history(grid)
        print(describe_xy_chain(caption, candset, cellchain, candchain, remove_cells))
        L = []
        for cell, cand1, cand2 in zip(cellchain, candchain[:-1], candchain[1:]):
            L.append(([cell], [cand1], CellDecor.COLOR1, [cand2], CellDecor.COLOR2))
        L.append((cells_to_discard, candset, CellDecor.REMOVECAND))
        grid.dump(L)
    apply_remove_candidates(grid, caption, remove_cells)


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
            return False
        elif len(cell.candidates) == 2:
            pass
        elif len(cell.candidates) == 3:
            if more_than_2:
                return False
            more_than_2 = cell
        else:
            # more than three candidates
            return False

        for candidate in cell.candidates:
            digits['row', cell.rownum, candidate].add(cell)
            digits['col', cell.colnum, candidate].add(cell)
            digits['box', cell.boxnum, candidate].add(cell)

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
        return False

    apply_bug1(grid, 'Bivalue Universal Grave + 1', explain, more_than_2.candidates - {extra}, {}, {more_than_2})
    return True


def apply_bug1(grid, caption, explain, candidates, define_set, remove_set):
    remove_cells = candidates_cells(candidates, remove_set)
    if remove_cells:
        if explain:
            explain_bug1(grid, caption, candidates, define_set, remove_set, remove_cells)
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


def explain_bug1(grid, caption, candidates, define_set, remove_set, remove_cells):
    print_single_history(grid)
    print(describe_bug1(caption, candidates, define_set, remove_cells))
    grid.dump(((remove_set, candidates, CellDecor.REMOVECAND),))


def describe_bug1(caption, defcands, defset, remset):
    return '%s => %s' % (caption, discarded_text(remset))


# W-wing


def solve_w_wing(grid, explain):
    pairs = defaultdict(set)
    for cell in grid.cells:
        if len(cell.candidates) == 2:
            pairs[frozenset(cell.candidates)].add(cell)

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
                        if apply_w_wing(grid, 'W-wing',
                            explain, candidates - {candidate}, [wing1, wing2, peer, inter[0]],
                            cellinter(wing1.peers, wing2.peers)):
                            return True
    return False


def apply_w_wing(grid, caption, explain, candidates, define_set, remove_set):
    remove_cells = candidates_cells(candidates, remove_set)
    if remove_cells:
        if explain:
            explain_w_wing(grid, caption, candidates, define_set, remove_set, remove_cells)
        apply_remove_candidates(grid, caption, remove_cells)
        return True
    return False


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


# Solving engine


# Simple Sudoku
# source: http://sudopedia.enjoysudoku.com/SSTS.html
STRATEGY_SSTS = 'n1,h1,n2,lc1,lc2,n3,n4,h2,bf2,bf3,sc1,sc2,mc2,mc1,h3,xy,h4'

# Hodoku
# upper case techniques are not yet implemented
STRATEGY_HODOKU_EASY = 'n1,h1'
STRATEGY_HODOKU_MEDIUM = 'n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3'
STRATEGY_HODOKU_HARD = 'n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3,n4,h4,bf2,bf3,bf4,rp,bug1,sk,2sk,tf,er,w,xy,XYZ,U1,U2,U3,U4,U5,U6,HR,AR1,AR2,FBF2,SBF2,sc1,sc2,mc1,mc2'
STRATEGY_HODOKU_UNFAIR = STRATEGY_HODOKU_HARD + 'x,BF5,BF6,BF7,FBF3,SBF3,FBF4,SBF4,FBF5,SBF5,FBF6,SBF6,FBF7,SBF7,SDC,xyc'


def list_techniques(strategy):
    ALL = ','.join(SOLVER.keys())

    strategy = re.sub(r'\bssts\b', STRATEGY_SSTS, strategy)
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
    'sc1': solve_coloring_trap,
    'sc2': solve_coloring_wrap,
    'mc1': solve_multi_coloring_type_1,
    'mc2': solve_multi_coloring_type_2,
    'sk': solve_skyscraper,
    '2sk': solve_2_string_kite,
    'tf': solve_turbot_fish,
    'er': solve_empty_rectangle,
    'xy': solve_XY_wing,
    'x': solve_X_chain,
    'rp': solve_remote_pair,
    'xyc': solve_XY_chain,
    'bug1': solve_bug1,
    'w': solve_w_wing,
}


def apply_strategy(grid, strategy, explain):
    for solver in list_techniques(strategy):
        if SOLVER[solver](grid, explain):
            return True
    else:
        return False


def solve(grid, techniques, explain):
    if explain:
        print(grid.output())
        grid.dump()
    while not grid.solved() and apply_strategy(grid, techniques, explain):
        pass
    if explain:
        print_single_history(grid)
        grid.dump()


# Commands


def solvegrid(options, techniques, explain):
    """
    Solve a single grid given on a the command line, in the clipboard or
    a file.
    """
    t0 = time.time()
    grid = Grid()
    grid.decorate = options.decorate

    if re.match(r'[\d.]{81}', options.solve):
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
        load_ss_clipboard(grid, sgrid)
    else:
        print('Unknown format', options.format)
        return False, None

    if not explain:
        print(grid.output())
        grid.dump()
    solve(grid, techniques, explain)
    if not explain:
        grid.dump()
    return True, time.time() - t0


def testfile(options, filename, techniques, explain):
    grid = Grid()
    grid.decorate = options.decorate
    ngrids = 0
    solved = 0
    with open(filename) as f:
        grids = f.readlines()

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
        for line in tqdm(grids, disable=True):
            if '#' in line:
                line = re.sub('#.*', '', line)
            try:
                input, output = line.strip().split(None, 1)
                if len(input) != 81 or len(output) != 81:
                    raise ValueError
            except ValueError:
                print(f'Test file: {filename:20} Result: False Solved: {solved}/{ngrids} Error: Incorrect line format')
                return False, 0
            ngrids += 1
            grid.input(input)
            solve(grid, techniques, explain)
            if output == grid.output():
                solved += 1
                if options.trace == 'success':
                    print(input, output, file=f)
            else:
                if options.trace == 'failure':
                    print(input, output, file=f)
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
        print(f'COMPARE OK' if res else 'COMPARE FAILURE')
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
            result.append(re.sub('Time: [^ ]+', '', line))
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


def parse_command_line(argstring=None):
    usage = "usage: sudosol ..."
    parser = argparse.ArgumentParser(description=usage, usage=argparse.SUPPRESS)
    parser.add_argument('-s', '--solve', help='solve file or str81 argument',
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
    parser.add_argument('--explain', help='explain techniques',
                        action='store_true', default=False)
    parser.add_argument('--decorate', help='candidate decor when tracing grid',
                        choices=['color', 'char'],
                        action='store', default=None)
    parser.add_argument('--trace', help='additional traces',
                        choices=['success', 'failure'],
                        action='store', default=None)
    parser.add_argument('--output', help='file to trace on',
                        action='store', default=None)

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
