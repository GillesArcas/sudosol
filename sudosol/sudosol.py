import argparse
import sys
import re
import itertools
import glob
import random
import time
from collections import defaultdict

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

    def __repr__(self):
        return self.__str__()

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
            cell.peers = cellunion(cell.row, cellunion(cell.col, cell.box))
            cell.peers.remove(cell)

        # init history
        self.history = []

    def reset(self):
        for cell in self.cells:
            cell.reset()

    # def __str__(self):
    #     pass

    def input(self, str81):
        """load a 81 character string
        """
        self.reset()
        for index, char in enumerate(str81):
            if char not in '.0':
                self.set_value_rc(index // 9, index % 9, int(char))

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


    def set_value_rc(self, irow, icol, digit):
        cell = self.cell_rc(irow, icol)
        cell.set_value(digit)
        for cell in self.rows[irow]:
            cell.discard(digit)
        for cell in self.cols[icol]:
            cell.discard(digit)
        for cell in self.box_rc(irow, icol):
            cell.discard(digit)

    def discard_rc(self, irow, icol, digit):
        self.cell_rc(irow, icol).discard(digit)

    def solved(self):
        return all(cell.value is not None for cell in self.cells)

    def conjugates(self, cell, digit):
        rowpeers = cell.same_digit_in_row(digit)
        colpeers = cell.same_digit_in_col(digit)
        boxpeers = cell.same_digit_in_box(digit)
        conj = set()
        conj = conj.union(rowpeers if len(rowpeers) == 2 else set())
        conj = conj.union(colpeers if len(colpeers) == 2 else set())
        conj = conj.union(boxpeers if len(boxpeers) == 2 else set())
        conj.discard(cell)
        #print('conj', cell, digit, conj)
        return conj

    def dump(self, decor=None):
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


def colorize_candidates(cell, spec_color):
    """
    col_spec ::= [cells, [candidates, color]*]*
    ex:
    (({cell}, [1], Fore.GREEN), ((cell1, cell2), ALLCAND, Fore.RED, {cand1, cand2}, Fore.GREEN))

    cells and candidates are iterables.
    A cell or a candidate may appear several times. The last color spec is taken into accout.
    """
    if not cell.candidates:
        return str(cell.value)

    if spec_color is None:
        res = Fore.CYAN + str(cell) + Fore.RESET
    else:
        candcol = retain_decor(cell, spec_color)
        res = ''
        for cand in sorted(cell.candidates):
            res += candcol[cand] + str(cand) + Fore.RESET

    # manual padding as colorama information fools format padding
    res += ' ' * (9 - len(cell.candidates))
    return res


def retain_decor(cell, spec_color):
    candcol = defaultdict(lambda:Fore.CYAN)
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
        # values
        lines = ''.join(content[16:19] + content[20:23] + content[24:27])
        print(lines)
        values = lines.replace('|', '')
        values = values.replace(' ', '')
        print(values)
        grid.input(values)
        # candidates
        lines = content[31:34] + content[35:38] + content[39:42]
        lines = [re.findall(r'\b\d+\b', line) for line in lines]
        if any([len(x) != 9 for x in lines]):
            print('bad clipboard (2)')
            exit(1)
        cells = sum(lines, [])
        print(cells)
        for cell, cand in zip(grid.cells, cells):
            cell.candidates = set(int(_) for _ in cand)

    else:
        print(content)
        print('bad clipboard (1)')
        exit(1)

    return lines


# Helpers


def discard_candidates(grid, candidates, cells, caption):
    """Discard candidates in a list of cells. Update grid history.
    """
    discarded = defaultdict(set)
    for cell in cells:
        for candidate in candidates:
            if candidate in cell.candidates:
                cell.discard(candidate)
                discarded[candidate].add(cell)
    if discarded:
        grid.history.append((caption, 'discard', discarded))
        return True
    else:
        return False


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


def discarded_at_last_move_text(grid):
    """Return candidates discarded at last move (from history) in text
    explanation format (e.g. 'r45c8<>3, r4c89<>5').
    """
    discarded = discarded_at_last_move(grid)
    list_coord = []
    for digit, cells in discarded.items():
        list_coord.append(f'{packed_coordinates(cells)}<>{digit}')
    return ', '.join(list_coord)


def single_history(grid):
    i = len(grid.history) - 2
    while i >= 0 and grid.history[i][0] in ('Naked single', 'Hidden single'):
        i -= 1
    i += 1
    hist = []
    while i < len(grid.history) - 1:
        tech = grid.history[i][0]
        ldesc = []
        while i < len(grid.history) - 1 and grid.history[i][0] == tech:
            ldesc.append('%s=%d' % (grid.history[i][1].strcoord(), grid.history[i][3]))
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
            #  TODO: use grid.set_value return value to enable undo
            grid.set_value_rc(cell.rownum, cell.colnum, value)
            grid.history.append(('Naked single', cell, 'value', value))
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
                grid.set_value_rc(cell.rownum, cell.colnum, cand)
                grid_modified = True
                # TODO: should store remaining candidates
                grid.history.append(('Hidden single', cell, 'value', cand))
                # avoid to loop on candidates from initial cell state
                break
    return grid_modified


# Locked pairs and triplets


def explain_move(grid, colorspec):
    _, _, discarded = grid.history[-1]

    for digit, cells in discarded.items():
        for cell in cells:
            cell.candidates.add(digit)

    grid.dump(colorspec)

    for digit, cells in discarded.items():
        for cell in cells:
            cell.candidates.discard(digit)


def solve_locked_pairs(grid, explain):

    for trinum, triplet in enumerate(grid.horizontal_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.rows_less_triplet[trinum] + grid.boxes_less_hortriplet[trinum]
                if discard_candidates(grid, subset[0].candidates, cells_to_discard, 'Locked pair'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_set(grid, 'Locked pair', subset[0].candidates, subset))
                        explain_move(grid, ((subset, subset[0].candidates, Fore.GREEN),
                                (cells_to_discard, subset[0].candidates, Fore.RED)))
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                if discard_candidates(grid, subset[0].candidates, cells_to_discard, 'Locked pair'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_set(grid, 'Locked pair', subset[0].candidates, subset))
                        explain_move(grid, ((subset, subset[0].candidates, Fore.GREEN),
                                (cells_to_discard, subset[0].candidates, Fore.RED)))
                    return True

    return False


def solve_locked_triples(grid, explain):

    for trinum, triplet in enumerate(grid.horizontal_triplets):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = set().union(*(cell.candidates for cell in triplet))
            if len(candidates) == 3:
                cells_to_discard = grid.rows_less_triplet[trinum] + grid.boxes_less_hortriplet[trinum]
                if discard_candidates(grid, candidates, cells_to_discard, 'Locked triple'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_set(grid, 'Locked triple', candidates, triplet))
                        explain_move(grid, ((triplet, candidates, Fore.GREEN),
                                (cells_to_discard, candidates, Fore.RED)))
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = set().union(*(cell.candidates for cell in triplet))
            if len(candidates) == 3:
                cells_to_discard = grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                if discard_candidates(grid, candidates, cells_to_discard, 'Locked triple'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_set(grid, 'Locked triple', candidates, triplet))
                        explain_move(grid, ((triplet, candidates, Fore.GREEN),
                                (cells_to_discard, candidates, Fore.RED)))
                    return True

    return False


# Pointing


def solve_pointing(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_hortriplet[trinum])):
                if discard_candidates(grid, [digit], grid.rows_less_triplet[trinum], 'Pointing'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_candidates(grid, 'Pointing', [digit], f'b{triplet[0].boxnum + 1}'))
                        explain_move(grid, ((triplet, [digit], Fore.GREEN),
                                (grid.rows_less_triplet[trinum], [digit], Fore.RED)))
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_vertriplet[trinum])):
                if discard_candidates(grid, [digit], grid.cols_less_triplet[trinum], 'Pointing'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_candidates(grid, 'Pointing', [digit], f'b{triplet[0].boxnum + 1}'))
                        explain_move(grid, ((triplet, [digit], Fore.GREEN),
                                (grid.cols_less_triplet[trinum], [digit], Fore.RED)))
                    return True

    return False


def solve_claiming(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.rows_less_triplet[trinum])):
                if discard_candidates(grid, [digit], grid.boxes_less_hortriplet[trinum], 'Claiming'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_candidates(grid, 'Claiming', [digit], f'r{triplet[0].rownum + 1}'))
                        explain_move(grid, ((triplet, [digit], Fore.GREEN),
                                (grid.boxes_less_hortriplet[trinum], [digit], Fore.RED)))
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.cols_less_triplet[trinum])):
                if discard_candidates(grid, [digit], grid.boxes_less_vertriplet[trinum], 'Claiming'):
                    if explain:
                        print_single_history(grid)
                        print(legend_locked_candidates(grid, 'Claiming', [digit], f'c{triplet[0].colnum + 1}'))
                        explain_move(grid, ((triplet, [digit], Fore.GREEN),
                                (grid.boxes_less_vertriplet[trinum], [digit], Fore.RED)))
                    return True

    return False


def legend_locked_candidates(grid, legend, defcands, defunit):
    discarded = discarded_at_last_move_text(grid)

    return '%s: %s in %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(defcands)),
        defunit,
        discarded)


# Locked sets


def nacked_sets_n(grid, cells, subcells, length, legend, explain):
    if subcells is None:
        subcells = [cell for cell in cells if len(cell.candidates) > 1]
    for subset in itertools.combinations(subcells, length):
        candidates = set().union(*(cell.candidates for cell in subset))
        if len(candidates) == length:
            cells_less_subset = [cell for cell in subcells if cell not in subset]
            if discard_candidates(grid, candidates, cells_less_subset, legend):
                if explain:
                    print_single_history(grid)
                    if legend.startswith('Naked'):
                        print(legend_locked_set(grid, legend, candidates, subset))
                        explain_move(grid, ((subset, candidates, Fore.GREEN), (cells_less_subset, candidates, Fore.RED)))
                    if legend.startswith('Hidden'):
                        allcand = set().union(*(cell.candidates for cell in subcells))
                        print(legend_locked_set(grid, legend, allcand - candidates, cells_less_subset))
                        explain_move(grid, ((cells_less_subset, ALLCAND - candidates, Fore.GREEN, candidates, Fore.RED),))
                return True
    return False


def legend_locked_set(grid, legend, defcands, defset):
    discarded = discarded_at_last_move_text(grid)

    return '%s: %s in %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(defcands)),
        packed_coordinates(defset),
        discarded)


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
                #print(grid.history[-1])
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
                if discard_candidates(grid, [digit], cells_to_discard, name):
                    if explain:
                        subset = cellunionx(*defrows)
                        print_single_history(grid)
                        print(legend_basic_fish(grid, name, [digit], subset, 'H'))
                        explain_move(grid, ((subset, [digit], Fore.GREEN),
                                (cells_to_discard, [digit], Fore.RED)))
                    return True

        cols = []
        for col in grid.cols:
            colcells = [cell for cell in col if digit in cell.candidates]
            if 1 < len(colcells) <= order:
                cols.append(colcells)

        for defrows in itertools.combinations(cols, order):
            colsnum = [col[0].colnum for col in defrows]
            rowsnum = {cell.rownum for col in defrows for cell in col}
            if len(rowsnum) == order:
                cells_to_discard = []
                for rownum in rowsnum:
                    for cell in grid.rows[rownum]:
                        if cell.colnum not in colsnum:
                            cells_to_discard.append(cell)
                if discard_candidates(grid, [digit], cells_to_discard, name):
                    if explain:
                        subset = cellunionx(*defrows)
                        print_single_history(grid)
                        print(legend_basic_fish(grid, name, [digit], subset, 'V'))
                        explain_move(grid, ((subset, [digit], Fore.GREEN),
                                (cells_to_discard, [digit], Fore.RED)))
                    return True
    return False


def legend_basic_fish(grid, legend, defcands, subset, dir):
    discarded = discarded_at_last_move_text(grid)

    rows = {cell.rownum + 1 for cell in subset}
    cols = {cell.colnum + 1 for cell in subset}
    srows = ''.join(f'{_}' for _ in sorted(list(rows)))
    scols = ''.join(f'{_}' for _ in sorted(list(cols)))
    defcells = f'r{srows} c{scols}' if dir == 'H' else f'c{scols} r{srows}'
    return '%s: %s %s => %s' % (legend,
        ','.join(f'{_}' for _ in sorted(defcands)),
        defcells,
        discarded)


# coloring


def solve_coloring_trap(grid, explain):
    """a candidate sees both colors of a cluster. Whatever the color coding, the
    candidate can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        for cluster in clusters:
            cluster_blue, cluster_green = colorize(grid, digit, cluster)

            peers_cluster_blue = multi_peers(grid, digit, cluster_blue) - cluster_blue
            peers_cluster_green = multi_peers(grid, digit, cluster_green) - cluster_green
            common = cellinter(peers_cluster_blue, peers_cluster_green)

            if common:
                discard_candidates(grid, [digit], common, 'color trap')
                if explain:
                    print_single_history(grid)
                    print(legend_simple_coloring(grid, 'Simple color trap', digit, cluster_green, cluster_blue))
                    explain_move(grid, ((cluster_green, [digit], Fore.GREEN),
                                        (cluster_blue, [digit], Fore.YELLOW),
                                        (common, [digit], Fore.RED)))
                return True

    return False


def solve_coloring_wrap(grid, explain):
    """two candidates in the same unit have the same color. All candidates with
    this color can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        for cluster in clusters:
            cluster_blue, cluster_green = colorize(grid, digit, cluster)

            if color_contradiction(cluster_blue):
                discard_candidates(grid, [digit], cluster_blue, 'color wrap')
                if explain:
                    print_single_history(grid)
                    print(legend_simple_coloring(grid, 'Simple color wrap', digit, cluster_green, cluster_blue))
                    explain_move(grid, ((cluster_green, [digit], Fore.GREEN),
                                        (cluster_blue, [digit], Fore.RED)))
                return True

            if color_contradiction(cluster_green):
                discard_candidates(grid, [digit], cluster_green, 'color wrap')
                if explain:
                    print_single_history(grid)
                    print(legend_simple_coloring(grid, 'Simple color wrap', digit, cluster_green, cluster_blue))
                    explain_move(grid, ((cluster_blue, [digit], Fore.GREEN),
                                        (cluster_green, [digit], Fore.RED)))
                return True

    return False


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


def legend_simple_coloring(grid, legend, digit, cluster_green, cluster_blue):
    discarded = discarded_at_last_move_text(grid)

    return '%s: %d (%s) / (%s) => %s' % (legend, digit,
        packed_coordinates(cluster_green),
        packed_coordinates(cluster_blue),
        discarded)


def solve_multi_coloring_type_1(grid, explain):
    """Consider two clusters. If a unit contains a color of each cluster, all
    cells seing the opposite colors can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        clusters_data = []
        to_be_removed = None

        for cluster in clusters:
            cluster_blue, cluster_green = colorize(grid, digit, cluster)

            peers_cluster_blue = multi_peers(grid, digit, cluster_blue) #- cluster_blue
            peers_cluster_green = multi_peers(grid, digit, cluster_green) #- cluster_green
            common = cellinter(peers_cluster_blue, peers_cluster_green)

            clusters_data.append((cluster, cluster_blue, cluster_green,
                                  peers_cluster_blue, peers_cluster_green, common))

            if common:
                print(cluster)

        for clusters_data1, clusters_data2 in itertools.combinations(clusters_data, 2):
            _, cluster_blue1, cluster_green1, peers_cluster_blue1, peers_cluster_green1, _ = clusters_data1
            _, cluster_blue2, cluster_green2, peers_cluster_blue2, peers_cluster_green2, _ = clusters_data2

            if any(cell in peers_cluster_blue2 for cell in cluster_blue1):
                to_be_removed = cellinter(peers_cluster_green1, peers_cluster_green2)
                if to_be_removed:
                    # TODO: move outside loop
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    break

            if any(cell in peers_cluster_green2 for cell in cluster_blue1):
                to_be_removed = cellinter(peers_cluster_green1, peers_cluster_blue2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    break

            if any(cell in peers_cluster_blue2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_green2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    break

            if any(cell in peers_cluster_green2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_blue2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    break

        if to_be_removed:
            if explain:
                print_single_history(grid)
                print(legend_multi_coloring(grid, 'Multi color type 1', digit,
                          cluster_green1, cluster_blue1,
                          cluster_green2, cluster_blue2))
                explain_move(grid, ((cluster_blue1, [digit], Fore.GREEN),
                                    (cluster_green1, [digit], Fore.BLUE),
                                    (cluster_blue2, [digit], Fore.YELLOW),
                                    (cluster_green2, [digit], Fore.MAGENTA),
                                    (to_be_removed, [digit], Fore.RED)))
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
            cluster_blue, cluster_green = colorize(grid, digit, cluster)

            peers_cluster_blue = multi_peers(grid, digit, cluster_blue) #- cluster_blue
            peers_cluster_green = multi_peers(grid, digit, cluster_green) #- cluster_green
            common = cellinter(peers_cluster_blue, peers_cluster_green)

            clusters_data.append((cluster, cluster_blue, cluster_green,
                                  peers_cluster_blue, peers_cluster_green, common))

            if common:
                # TODO: check why always empty
                print(cluster)

        for clusters_data1, clusters_data2 in itertools.combinations(clusters_data, 2):
            _, cluster_blue1, cluster_green1, peers_cluster_blue1, peers_cluster_green1, common1 = clusters_data1
            _, cluster_blue2, cluster_green2, peers_cluster_blue2, peers_cluster_green2, common2 = clusters_data2

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
            discard_candidates(grid, [digit], to_be_removed, 'multi color type 2')
            if explain:
                print_single_history(grid)
                print(legend_multi_coloring(grid, 'Multi color type 2', digit,
                          cluster_green1, cluster_blue1,
                          cluster_green2, cluster_blue2))
                # TODO: remove 4 lines and test
                if cluster_blue1 == to_be_removed: cluster_blue1 = {}
                if cluster_green1 == to_be_removed: cluster_green1 = {}
                if cluster_blue2 == to_be_removed: cluster_blue2 = {}
                if cluster_green2 == to_be_removed: cluster_green2 = {}

                explain_move(grid, ((cluster_blue1, [digit], Fore.GREEN),
                                    (cluster_green1, [digit], Fore.BLUE),
                                    (cluster_blue2, [digit], Fore.YELLOW),
                                    (cluster_green2, [digit], Fore.MAGENTA),
                                    (to_be_removed, [digit], Fore.RED)))
            return True

    return False


def legend_multi_coloring(grid, legend, digit,
                          cluster_green1, cluster_blue1,
                          cluster_green2, cluster_blue2):
    """multi coloring is limited to two clusters.
    """
    discarded = discarded_at_last_move_text(grid)

    return '%s: %d (%s) / (%s), (%s) / (%s) => %s' % (legend, digit,
        packed_coordinates(cluster_green1),
        packed_coordinates(cluster_blue1),
        packed_coordinates(cluster_green2),
        packed_coordinates(cluster_blue2),
        discarded)


# clusters


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
        conjs = grid.conjugates(cell, digit)
        #print(1, cell, conjs)
        for conj in conjs:
            check_cluster_conj(grid, new_cluster, conj, digit)


def is_cell_in_clusters(cell, clusters):
    return clusters and any(cell in cluster for cluster in clusters)


def check_cluster_conj(grid, cluster, conj, digit):
    if conj in cluster:
        pass
    else:
        cluster.add(conj)
        conjs = grid.conjugates(conj, digit)
        #print(2, conj, conjs)
        for conj in conjs:
            check_cluster_conj(grid, cluster, conj, digit)


def colorize(grid, digit, cluster):

    def colorize_cell(cell, colorset, conjcolorset):
        if cell not in colorset and cell not in conjcolorset:
            colorset.add(cell)
            for conj in grid.conjugates(cell, digit):
                colorize_cell(conj, conjcolorset, colorset)

    cluster_blue, cluster_green = set(), set()
    first_cell = list(cluster)[0]
    colorize_cell(first_cell, cluster_blue, cluster_green)

    return cluster_blue, cluster_green


def multi_peers(grid, digit, cluster):
    digit_peers = set()
    for cell in cluster:
        digit_peers = cellunion(digit_peers, set(c for c in cell.peers if digit in c.candidates))
    return digit_peers


# xy-wings


def solve_XY_wing(grid, explain):
    for cell in grid.cells:
        if cell.is_pair():
            cand1, cand2 = list(cell.candidates)
            pairpeers = (peer for peer in cell.peers if peer.is_pair())
            for wing1, wing2 in itertools.combinations(pairpeers, 2):
                if wing1 in wing2.peers:
                    # cell, wing1, wing2 in the same house: not a xy-wing
                    continue
                wings_inter = wing1.candidates.intersection(wing2.candidates)
                if len(wings_inter) != 1 or list(wings_inter)[0] in cell.candidates:
                    continue
                if (cand1 in wing1.candidates and cand2 in wing2.candidates or
                    cand1 in wing2.candidates and cand2 in wing1.candidates):
                    digit = list(wings_inter)[0]

                    if discard_candidates(grid, [digit], cellinter(wing1.peers, wing2.peers), 'XY-wing'):
                        if explain:
                            print_single_history(grid)
                            print(legend_xy_wing(grid, 'XY-wing', [cand1, cand2, digit], [cell, wing1, wing2]))
                            explain_move(grid, (([cell, wing1, wing2], cell.candidates, Fore.GREEN),
                                    ((wing1, wing2), ALLCAND - cell.candidates, Fore.BLUE),
                                    (cellinter(wing1.peers, wing2.peers), [digit], Fore.RED)))
                        return True
    else:
        return False


def legend_xy_wing(grid, legend, digits, cells):
    discarded = discarded_at_last_move_text(grid)

    return '%s: %s in %s => %s' % (legend,
        '/'.join(f'{_}' for _ in digits),
        packed_coordinates(cells),
        discarded)


# xy-chains


def solve_XY_chain_v1(grid, explain):
    all_solutions = False
    pairs, links = xy_links(grid)

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
                        if test_new_chain(grid, adjacency[i][j], adjacency1, adjacency2, all_solutions):
                            if explain:
                                link = adjacency[i][j][-1]
                                cellchain, candchain = link
                                digit = candchain[0]
                                print_single_history(grid)
                                print(legend_xy_chain(grid, 'XY-chain', digit, cellchain, candchain))
                                L = []
                                for cell, cand1, cand2 in zip(cellchain, candchain[:-1], candchain[1:]):
                                    L.append(([cell], [cand1], Fore.BLUE, [cand2], Fore.GREEN))
                                L.append((discarded_at_last_move(grid)[digit], [digit], Fore.RED))
                                explain_move(grid, L)
                            return True

    if all_solutions:
        for i in range(len(pairs)):
            for j in range(len(pairs)):
                for chain in adjacency[i][j]:
                    if test_xy_remove(grid, *chain):
                        return True

    return False


def xy_links(grid):
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


def test_new_chain(grid, adjacency, adjacency1, adjacency2, all_solutions):
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

    if len(adjacency) == 4:
        for index, x in enumerate(adjacency):
            print(index, x)

    if all_solutions:
        return False
    else:
        return test_xy_remove(grid, cellchain, candchain)


def test_xy_remove(grid, cellchain, candchain):
    if candchain[0] == candchain[-1]:
        digit = candchain[0]
        to_be_removed = cellinter(cellchain[0].peers, cellchain[-1].peers)
        to_be_removed = [cell for cell in to_be_removed if digit in cell.candidates]
        to_be_removed = [cell for cell in to_be_removed if cell not in cellchain]
        if to_be_removed:
            discard_candidates(grid, [digit], to_be_removed, 'XY-chain')
            return True
    return False


def legend_xy_chain(grid, legend, digit, cellchain, candchain):
    l = []
    l.append('%d-' % candchain[0])
    for index, cell in enumerate(cellchain[:-1]):
        l.append(cell.strcoord())
        l.append('-%d-' % candchain[index + 1])
    l.append(cellchain[-1].strcoord())
    l.append('-%d' % candchain[-1])
    return '%s: %d %s => %s' % (
                legend, digit, ' '.join(l), discarded_at_last_move_text(grid))


def solve_XY_chain_v2(grid, explain):
    all_solutions = False
    _, links = xy_links(grid)

    starting_links = defaultdict(list)
    for link in links:
        (cell1, _), _ = link
        starting_links[cell1.cellnum].append(link)

    # init paths of length 1
    paths = [None, links]

    modified = True
    numpath = defaultdict(set)
    while modified:
        modified = False
        length = len(paths) - 1
        paths.append([])
        for path in paths[length]:
            cellchain = path[0]
            candchain = path[1]
            lastcell = cellchain[-1]
            for link in starting_links[lastcell.cellnum]:
                celllink, candlink = link
                if celllink[1] in cellchain:
                    pass
                elif candchain[-2:] == candlink[:2]:
                    newpath = [cellchain + celllink[1:], candchain + candlink[2:]]

                    cellchain2 = newpath[0]
                    candchain2 = newpath[1]
                    cellextr = cellchain2[0].cellnum, cellchain2[-1].cellnum
                    candextr = candchain2[0], candchain2[-1]

                    if candextr not in numpath[cellextr]:
                        numpath[cellextr].add(candextr)
                        if len(numpath[cellextr]) == 4:
                            print(cellextr, numpath[cellextr])

                        paths[length + 1].append(newpath)
                        modified = True

                        if not all_solutions:
                            if test_xy_remove(grid, cellchain, candchain):
                                return True

    if all_solutions:
        for length in range(2, len(paths)):
            for cellchain, candchain in paths[length]:
                if test_xy_remove(grid, cellchain, candchain):
                    return True

    return False


# solving engine


# source: http://sudopedia.enjoysudoku.com/SSTS.html
STRATEGY_SSTS = 'n1,h1,n2,lc1,lc2,n3,n4,h2,bf2,bf3,sc1,sc2,mc1,mc2,h3,xy,h4'

STRATEGY_HODOKU_EASY = 'n1,h1'
STRATEGY_HODOKU_MEDIUM = 'n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3'
STRATEGY_HODOKU_HARD = 'n1,h1,l2,l3,lc1,lc2,n2,n3,h2,h3,n4,h4,bf2,bf3,bf4,RP,BUG1,SK,2SK,TF,ER,W,xy,XYZ,U1,U2,U3,U4,U5,U6,HR,AR1,AR2,FBF2,SBF2,sc1,sc2,mc1,mc2'
STRATEGY_HODOKU_UNFAIR = STRATEGY_SSTS + ',xyc' #+ '-xy'


def list_techniques(strategy):
    strategy = re.sub(r'\bssts\b', STRATEGY_SSTS, strategy)

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
    'mc1' : solve_multi_coloring_type_1,
    'mc2' : solve_multi_coloring_type_2,
    'xy' : solve_XY_wing,
    'xyc' : solve_XY_chain_v1,
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


#


def solvegrid(sgrid, techniques, explain):
    grid = Grid()
    grid.input(sgrid)
    if not explain:
        print(grid.output())
        grid.dump()
    solve(grid, techniques, explain)
    if not explain:
        grid.dump()
    return True, None


def solveclipboard(clipformat, techniques, explain):
    if clipformat == 'ss':
        grid = Grid()
        content = clipboard.paste()
        load_ss_clipboard(grid, content)
        grid.dump()
        solve(grid, techniques, explain)
        grid.dump()
    return True, None


def testfile(filename, randnum, techniques, explain, logfile=None):
    verbose = False
    grid = Grid()
    success = True
    ngrids = 0
    solved = 0
    with open(filename) as f:
        grids = f.readlines()

    if randnum and randnum < len(grids):
        grids = random.sample(grids, randnum)

    t0 = time.time()

    try:
        if logfile:
            stdout = sys.stdout
            sys.stdout = open(logfile, 'wt')
        for line in grids:
            input, output, _ = line.strip().split(None, 2)
            ngrids += 1
            grid.input(input)
            solve(grid, techniques, explain)
            if output != grid.output():
                if verbose:
                    print('-' * 20)
                    print('\n'.join((input, output, grid.output())))
                success = False
            else:
                solved += 1
    finally:
        if logfile:
            sys.stdout = stdout

    timing = time.time() - t0
    print(f'Test file: {filename:20} Result: {success} Solved: {solved}/{ngrids} Time: {timing:0.3}')
    return success, timing


def testdir(dirname, randnum, techniques, explain):
    tested = 0
    succeeded = 0
    timing_dir = 0
    for filename in sorted(glob.glob(f'{dirname}/*.txt')):
        if not filename.startswith('.'):
            tested += 1
            success, timing = testfile(filename, randnum, techniques, explain)
            if success:
                succeeded += 1
            timing_dir += timing

    success = succeeded == tested
    print(f'Test dir : {dirname:20} Result: {success} Succeeded: {succeeded}/{tested} Time: {timing_dir:0.3}')
    return success, timing_dir


def testbatch(args):
    status = True
    timing_batch = 0
    with open(args.batch) as batch:
        for line in batch:
            if line.strip() and line[0] != ';':
                testargs = line.strip()

                success, timing = main(testargs)
                if not success:
                    break
                timing_batch += timing
    print(f'BATCH OK Time: {timing_batch:0.3}' if status else 'ONE TEST FAILURE in ' + line.strip())
    return success, timing_batch


def parse_command_line(argstring=None):
    usage = "usage: sudosol ..."
    parser = argparse.ArgumentParser(description=usage, usage=argparse.SUPPRESS)
    parser.add_argument('-s', '--solve', help='solve str81 argument',
                        action='store', default=None)
    parser.add_argument('-c', '--clipboard', help='init grid from clipboard',
                        action='store_true', default=False)
    parser.add_argument('-f', '--format', help='format',
                        action='store', default='ss')
    parser.add_argument('-t', '--testfile', help='test file',
                        action='store', default=None)
    parser.add_argument('-T', '--testdir', help='test directory',
                        action='store', default=None)
    parser.add_argument('-b', '--batch', help='test batch',
                        action='store', default=None)
    parser.add_argument('-r', '--random', help='test N random grids from file',
                        type=int,
                        action='store', default=None)
    parser.add_argument('--techniques', help='techniques',
                        action='store', default='ssts')
    parser.add_argument('-e', '--explain', help='explain techniques',
                        action='store_true', default=False)

    if argstring is None:
        args = parser.parse_args()
    else:
        args = parser.parse_args(argstring.split())
    return args


def main(argstring=None):
    options = parse_command_line(argstring)

    if options.solve:
        return solvegrid(options.solve, options.techniques, options.explain)

    elif options.testfile:
        return testfile(options.testfile, options.random, options.techniques, options.explain)

    elif options.testdir:
        return testdir(options.testdir, options.random, options.techniques, options.explain)

    elif options.batch:
        return testbatch(options)

    elif options.clipboard:
        return solveclipboard(options.format, options.techniques, options.explain)

    else:
        grid = Grid()
        grid.input('........2..6....39..9.7..463....672..5..........4.1.....235....9.1.8...5.3...9...')
        print(grid.horizontal_triplets)
        print(grid.vertical_triplets)
        grid.dump()
        solve(grid, options.techniques, options.explain)
        grid.dump()
        print(grid.output())
        print()
        return True, None
        # grid.discard_rc(5, 8, 4)
        # grid.discard_rc(5, 8, 6)
        # grid.set_value_rc(5, 2, 1)
        # grid.set_value_rc(0, 8, 9)


if __name__ == '__main__':
    colorama.init()
    success, timing = main()
    if success:
        exit(0)
    else:
        exit(1)
