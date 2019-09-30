import argparse
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
        return f'r{self.rownum}c{self.colnum}'

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
    # ((cell, '*', Fore.GREEN), ((wing1, wing2), {cand1, cand2}, Fore.GREEN, ALLCAND, Fore.RED))
    # if not cell.candidates:
    #     return Fore.BLUE + str(cell.value) + Fore.RESET + ' ' * 8

    # if spec_color is None or not cell.candidates:
    #     return str(cell)

    if not cell.candidates:
        return str(cell.value)

    if spec_color is None:
        res = Fore.CYAN + str(cell) + Fore.RESET
        res += ' ' * (9 - len(cell.candidates))
        return res

    for target, *spec_col in spec_color:
        #print('--', target)
        if isinstance(target, Cell):
            target = (target,)
        for targ in target:
            if targ == cell:
                res = ''
                for cand in sorted(targ.candidates):
                    for spec_cand, speccol in zip(spec_col[::2], spec_col[1::2]):
                        if cand == spec_cand or cand in spec_cand:
                            res += speccol + str(cand) + Fore.RESET
                            break
                    else:
                        # res += str(cand)
                        res += Fore.CYAN + str(cand) + Fore.RESET
                # manual padding as colorama information fools format padding
                res += ' ' * (9 - len(targ.candidates))
                return res
    else:
        # return str(cell)
        res = Fore.CYAN + str(cell) + Fore.RESET
        res += ' ' * (9 - len(cell.candidates))
        return res


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


# helpers


def discard_candidates(grid, candidates, cells, caption):
    """Discard candidates in cells
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


# Singles


def solve_single_candidate(grid, explain):
    # naked singles
    for cell in grid.cells:
        if len(cell.candidates) == 1:
            value = list(cell.candidates)[0]
            #  TODO: use grid.set_value return value to enable undo
            grid.set_value_rc(cell.rownum, cell.colnum, value)
            grid.history.append(('naked single', cell, 'value', value))
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
                # TODO: should store remining candidates
                grid.history.append(('hidden single', cell, 'value', cand))
                # avoid to loop on candidates from initial cell state
                break
    return grid_modified


# Locked pairs and triplets


def explain_move(grid, colorspec):
    i = len(grid.history) - 2
    while i >= 0 and grid.history[i][0] in ('naked single', 'hidden single'):
        i -= 1
    i += 1
    hist = ''
    while i < len(grid.history) - 1:
        tech = grid.history[i][0]
        desc = grid.history[i][0] + ' '
        while grid.history[i][0] == tech:
            desc += '%s=%d ' % (grid.history[i][1].strcoord(), grid.history[i][3])
            i += 1
        hist += desc
    print(hist)
    tech, _, discarded = grid.history[-1]
    for digit, cells in discarded.items():
        for cell in cells:
            cell.candidates.add(digit)
    print(tech)
    grid.dump(colorspec)
    for digit, cells in discarded.items():
        for cell in cells:
            cell.candidates.discard(digit)


def solve_locked_pairs(grid, explain):

    for trinum, triplet in enumerate(grid.horizontal_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.rows_less_triplet[trinum] + grid.boxes_less_hortriplet[trinum]
                if discard_candidates(grid, subset[0].candidates, cells_to_discard, 'locked pair'):
                    if explain:
                        explain_move(grid, ((subset, subset[0].candidates, Fore.GREEN),
                                (cells_to_discard, subset[0].candidates, Fore.RED)))
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        for subset in itertools.combinations(triplet, 2):
            if len(subset[0].candidates) == 2 and subset[0].candidates == subset[1].candidates:
                cells_to_discard = [cell for cell in triplet if cell not in subset] + grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                if discard_candidates(grid, subset[0].candidates, cells_to_discard, 'locked pair'):
                    if explain:
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
                if discard_candidates(grid, candidates, cells_to_discard, 'locked triple'):
                    return True

    for trinum, triplet in enumerate(grid.vertical_triplets):
        if all(len(cell.candidates) > 0 for cell in triplet):
            candidates = set().union(*(cell.candidates for cell in triplet))
            if len(candidates) == 3:
                cells_to_discard = grid.cols_less_triplet[trinum] + grid.boxes_less_vertriplet[trinum]
                if discard_candidates(grid, candidates, cells_to_discard, 'locked triple'):
                    return True

    return False


# Pointing


def solve_pointing(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_hortriplet[trinum])):
                if discard_candidates(grid, [digit], grid.rows_less_triplet[trinum], 'pointing h'):
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.boxes_less_vertriplet[trinum])):
                if discard_candidates(grid, [digit], grid.cols_less_triplet[trinum], 'pointing h'):
                    return True

    return False


def solve_claiming(grid, explain):

    for digit in ALLDIGITS:

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.rows_less_triplet[trinum])):
                if discard_candidates(grid, [digit], grid.boxes_less_hortriplet[trinum], 'claiming h'):
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if (candidate_in_cells(digit, triplet) and
                not candidate_in_cells(digit, grid.cols_less_triplet[trinum])):
                if discard_candidates(grid, [digit], grid.boxes_less_vertriplet[trinum], 'claiming v'):
                    return True

    return False


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
                    explain_move(grid, ((subset, candidates, Fore.GREEN),
                            (cells_less_subset, candidates, Fore.RED)))
                return True
    return False


def solve_nacked_pairs(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 2, 'Naked pair in row', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 2, 'Naked pair in col', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 2, 'Naked pair in box', explain) for box in grid.boxes)
    )


def solve_nacked_triples(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 3, 'Naked triple in row', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 3, 'Naked triple in col', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 3, 'Naked triple in box', explain) for box in grid.boxes)
    )


def solve_nacked_quads(grid, explain):
    return (
        any(nacked_sets_n(grid, row, None, 4, 'Naked quad in row', explain) for row in grid.rows) or
        any(nacked_sets_n(grid, col, None, 4, 'Naked quad in col', explain) for col in grid.cols) or
        any(nacked_sets_n(grid, box, None, 4, 'Naked quad in box', explain) for box in grid.boxes)
    )


def solve_hidden_set(grid, cells, length, legend, explain):
    subcells = [cell for cell in cells if len(cell.candidates) > 1]
    for len_naked_set in range(5, 10 - length):
        len_hidden_set = len(subcells) - len_naked_set
        if len_hidden_set == length:
            if nacked_sets_n(grid, cells, subcells, len_naked_set, legend, explain=False):
                return True
    return False


def solve_hidden_pair(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 2, 'Hidden pair in row', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 2, 'Hidden pair in col', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 2, 'Hidden pair in box', explain) for box in grid.boxes)
    )


def solve_hidden_triple(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 3, 'Hidden triple in row', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 3, 'Hidden triple in col', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 3, 'Hidden triple in box', explain) for box in grid.boxes)
    )


def solve_hidden_quad(grid, explain):
    return (
        any(solve_hidden_set(grid, row, 4, 'Hidden quad in row', explain) for row in grid.rows) or
        any(solve_hidden_set(grid, col, 4, 'Hidden quad in col', explain) for col in grid.cols) or
        any(solve_hidden_set(grid, box, 4, 'Hidden quad in box', explain) for box in grid.boxes)
    )


# Fishes


def solve_X_wing(grid, explain):

    for digit in ALLDIGITS:

        for index, house in enumerate(grid.rows):
            dig_house = [cell for cell in house if digit in cell.candidates]
            if len(dig_house) == 2:
                for index2, house2 in enumerate(grid.rows[index + 1:], index + 1):
                    dig_house2 = [cell for cell in house2 if digit in cell.candidates]
                    if len(dig_house2) == 2:
                        if dig_house[0].colnum == dig_house2[0].colnum and dig_house[1].colnum == dig_house2[1].colnum:
                            cells_to_discard = []
                            for cell in grid.cols[dig_house[0].colnum] + grid.cols[dig_house[1].colnum]:
                                if cell.rownum not in (index, index2):
                                    cells_to_discard.append(cell)
                            if discard_candidates(grid, [digit], cells_to_discard, 'X-wing'):
                                return True

        for index, house in enumerate(grid.cols):
            dig_house = [cell for cell in house if digit in cell.candidates]
            if len(dig_house) == 2:
                for index2, house2 in enumerate(grid.cols[index + 1:], index + 1):
                    dig_house2 = [cell for cell in house2 if digit in cell.candidates]
                    if len(dig_house2) == 2:
                        if dig_house[0].rownum == dig_house2[0].rownum and dig_house[1].rownum == dig_house2[1].rownum:
                            cells_to_discard = []
                            for cell in grid.rows[dig_house[0].rownum] + grid.rows[dig_house[1].rownum]:
                                if cell.colnum not in (index, index2):
                                    cells_to_discard.append(cell)
                            if discard_candidates(grid, [digit], cells_to_discard, 'X-wing'):
                                return True
    return False


def solve_swordfish(grid, explain):

    for digit in ALLDIGITS:

        rows = []
        for row in grid.rows:
            rowcells = [cell for cell in row if digit in cell.candidates]
            if 0 < len(rowcells) <= 3:
                rows.append(rowcells)
        for rowtriple in itertools.combinations(rows, 3):
            rowsnum = [row[0].rownum for row in rowtriple]
            colsnum = set()
            for row in rowtriple:
                for cell in row:
                    colsnum.add(cell.colnum)
            if len(colsnum) == 3:
                # 3 rows with candidates in 3 cols
                cells_to_discard = []
                for colnum in colsnum:
                    for cell in grid.cols[colnum]:
                        if cell.rownum not in rowsnum:
                            cells_to_discard.append(cell)
                if discard_candidates(grid, [digit], cells_to_discard, 'swordfish'):
                    if explain:
                        subset = cellunion(rowtriple[0], cellunion(rowtriple[1], rowtriple[2]))
                        explain_move(grid, ((subset, [digit], Fore.YELLOW),
                                (cells_to_discard, [digit], Fore.RED)))
                    return True

        cols = []
        for col in grid.cols:
            colcells = [cell for cell in col if digit in cell.candidates]
            if 0 < len(colcells) <= 3:
                cols.append(colcells)
        for coltriple in itertools.combinations(cols, 3):
            colsnum = [col[0].colnum for col in coltriple]
            rowsnum = set()
            for col in coltriple:
                for cell in col:
                    rowsnum.add(cell.rownum)
            if len(rowsnum) == 3:
                cells_to_discard = []
                for rownum in rowsnum:
                    for cell in grid.rows[rownum]:
                        if cell.colnum not in colsnum:
                            cells_to_discard.append(cell)
                if discard_candidates(grid, [digit], cells_to_discard, 'swordfish'):
                    return True
    return False


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
                return True

            if color_contradiction(cluster_green):
                discard_candidates(grid, [digit], cluster_green, 'color wrap')
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


def solve_multi_coloring_type_1(grid, explain):
    """Consider two clusters. If a unit contains a color of each cluster, all
    cells seing the opposite colors can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        clusters_data = []
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
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    return True

            if any(cell in peers_cluster_green2 for cell in cluster_blue1):
                to_be_removed = cellinter(peers_cluster_green1, peers_cluster_blue2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    return True

            if any(cell in peers_cluster_blue2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_green2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    return True

            if any(cell in peers_cluster_green2 for cell in cluster_green1):
                to_be_removed = cellinter(peers_cluster_blue1, peers_cluster_blue2)
                if to_be_removed:
                    discard_candidates(grid, [digit], to_be_removed, 'multi color type 1')
                    return True


def solve_multi_coloring_type_2(grid, explain):
    """Consider two clusters. If a color of one cluster sees both colors of the
    second cluster, all candidates from first color can be eliminated.
    """
    for digit in ALLDIGITS:
        clusters = make_clusters(grid, digit)
        clusters_data = []
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
                discard_candidates(grid, [digit], cluster_blue1, 'multi color type 2')
                return True

            if (any(cell in peers_cluster_blue2 for cell in cluster_green1) and
                any(cell in peers_cluster_green2 for cell in cluster_green1)):
                discard_candidates(grid, [digit], cluster_green1, 'multi color type 2')
                return True

            if (any(cell in peers_cluster_blue1 for cell in cluster_blue2) and
                any(cell in peers_cluster_green1 for cell in cluster_blue2)):
                discard_candidates(grid, [digit], cluster_blue2, 'multi color type 2')
                return True

            if (any(cell in peers_cluster_blue1 for cell in cluster_green2) and
                any(cell in peers_cluster_green1 for cell in cluster_green2)):
                discard_candidates(grid, [digit], cluster_green2, 'multi color type 2')
                return True

    return False


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
                    discarded = [_ for _ in cellinter(wing1.peers, wing2.peers)
                                         if digit in _.candidates]
                    grid_modified = len(discarded) > 0
                    if False and grid_modified:
                        grid.dump(((cell, ALLCAND, Fore.GREEN),
                                ((wing1, wing2), {cand1, cand2}, Fore.GREEN, ALLCAND, Fore.RED),
                                (discarded, {digit}, Fore.RED)))
                    for cell2 in discarded:
                        cell2.discard(digit)
                    if grid_modified:
                        grid.history.append(('XY-wing', discarded, 'discard', digit))
                        return True
    else:
        return False


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
    # TOTO: check
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
STRATEGY_HODOKU_UNFAIR = STRATEGY_SSTS + ',xyc' #+ '-xy'


def list_techniques(strategy):
    if '-' not in strategy:
        r = strategy.split(',')
    else:
        x, y = strategy.split('-')
        x = x.split(',')
        y = y.split(',')
        r = [z for z in x if z not in y]

    r2 = []
    for s in r:
        if s == 'ssts':
            r2.extend(STRATEGY_SSTS.split(','))
        else:
            r2.append(s)

    return r2


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
    while not grid.solved() and apply_strategy(grid, techniques, explain):
        pass


#


def testfile(filename, randnum, techniques, explain):
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

    time_solve = time.time() - t0
    print(f'Test file: {filename:20} Result: {success} Solved: {solved}/{ngrids} Time: {time_solve}')
    return success


def testdir(dirname, randnum, techniques, explain):
    tested = 0
    succeeded = 0
    for filename in sorted(glob.glob(f'{dirname}/*.txt')):
        if not filename.startswith('.'):
            tested += 1
            if testfile(filename, randnum, techniques, explain):
                succeeded += 1

    success = succeeded == tested
    print(f'Test dir : {dirname:20} Result: {success} Succeeded: {succeeded}/{tested}')
    return success


def testbatch(args):
    status = True
    with open(args.batch) as batch:
        for line in batch:
            if line.strip() and line[0] != ';':
                testargs = line.strip()

                status = main(testargs)
                if not status:
                    break
    print('BATCH OK' if status else 'ONE TEST FAILURE in ' + line.strip())
    return status


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
        grid = Grid()
        grid.input(options.solve)
        grid.dump()
        solve(grid, options.techniques, options.explain)
        grid.dump()
        return True

    elif options.testfile:
        return testfile(options.testfile, options.random, options.techniques, options.explain)

    elif options.testdir:
        return testdir(options.testdir, options.random, options.techniques, options.explain)

    elif options.batch:
        return testbatch(options)

    elif options.clipboard:
        if options.format == 'ss':
            grid = Grid()
            content = clipboard.paste()
            load_ss_clipboard(grid, content)
            grid.dump()
            solve(grid, options.explain, options.history)
            grid.dump()
        return True

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
        return True
        # grid.discard_rc(5, 8, 4)
        # grid.discard_rc(5, 8, 6)
        # grid.set_value_rc(5, 2, 1)
        # grid.set_value_rc(0, 8, 9)


if __name__ == '__main__':
    colorama.init()
    if main():
        exit(0)
    else:
        exit(1)
