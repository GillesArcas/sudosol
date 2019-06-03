import argparse
import re
import itertools

import clipboard


# Data structures


class Cell:
    def __init__(self, cellnum):
        self.value = None
        self.candidates = set(range(1, 10))
        self.cellnum = cellnum
        self.rownum = cellnum // 9
        self.colnum = cellnum % 9
        self.boxnum = (self.rownum // 3) * 3 + self.colnum // 3
        # possible ajouter row (liste des cells), col, box et liste des voisins

    def doset(self, value):
        self.value = value
        self.candidates = set()

    def reset(self):
        self.value = None
        self.candidates = set(range(1, 10))

    def __str__(self):
        if self.value:
            return str(self.value) + '.'
        else:
            return ''.join(str(_) for _ in sorted(list(self.candidates)))

    def __repr__(self):
        return self.__str__()

    def set_value(self, digit):
        self.value = digit
        self.candidates = set()

    def discard(self, digit):
        self.candidates.discard(digit)


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
        return ''.join(str(cell.value) if cell.value else '.' for cell in self.cells)

    def cell_rc(self, irow, icol):
        return self.rows[irow][icol]

    def box_rc(self, irow, icol):
        return self.boxes[(irow // 3) * 3 + icol // 3]

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

    def dump(self):
        for i in range(9):
            print(' '.join('%-9s' % _ for _ in self.rows[i]))
        print()


def candidate_in_cells(digit, cells):
    for cell in cells:
        if digit in cell.candidates:
            return True
    else:
        return False


# Loading


def load_ss_clipboard(grid, content):
    grid.reset()
    content = content.splitlines()

    if len(content) == 28:      # when starting
        assert False
        lines = content[16:19] + content[20:23] + content[24:27]

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



# Singles


def solve_single_candidate(grid):
    # naked singles
    grid_modified = True
    while True:
        grid_modified = False
        for cell in grid.cells:
            if len(cell.candidates) == 1:
                value = list(cell.candidates)[0]
                grid.set_value_rc(cell.rownum, cell.colnum, value)
                grid_modified = True
                grid.history.append(('naked single', cell.rownum, cell.colnum, 'value', value))
                break
        break
    return grid_modified


# Single digit techniques


def solve_hidden_candidate(grid):
    # hidden singles
    grid_modified = False
    for cell in grid.cells:
        cands = cell.candidates
        for cand in cands:
            rowcells = [c for c in grid.rows[cell.rownum] if cand in c.candidates]
            colcells = [c for c in grid.cols[cell.colnum] if cand in c.candidates]
            boxcells = [c for c in grid.boxes[cell.boxnum] if cand in c.candidates]
            if len(rowcells) == 1 or len(colcells) == 1 or len(boxcells) == 1:
                grid.set_value_rc(cell.rownum, cell.colnum, cand)
                grid_modified = True
                grid.history.append(('hidden single', cell.rownum, cell.colnum, 'value', cand))
                # avoid to loop on candidates from initial cell state
                break
    return grid_modified


# Pointing


def solve_pointing(grid):

    grid_modified = False
    for digit in range(1, 10):

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if not candidate_in_cells(digit, triplet):
                continue
            if not candidate_in_cells(digit, grid.boxes_less_hortriplet[trinum]):
                for cell in grid.rows_less_triplet[trinum]:
                    if digit in cell.candidates:
                        cell.discard(digit)
                        grid_modified = True
                if grid_modified:
                    grid.history.append(('pointing h', triplet[0].rownum, triplet[0].boxnum, 'discard', digit))
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if not candidate_in_cells(digit, triplet):
                continue
            if not candidate_in_cells(digit, grid.boxes_less_vertriplet[trinum]):
                for cell in grid.cols_less_triplet[trinum]:
                    if digit in cell.candidates:
                        cell.discard(digit)
                        grid_modified = True
                if grid_modified:
                    grid.history.append(('pointing v', triplet[0].colnum, triplet[0].boxnum, 'discard', digit))
                    return True

    return grid_modified


def solve_claiming(grid):

    grid_modified = False
    for digit in range(1, 10):

        for trinum, triplet in enumerate(grid.horizontal_triplets):
            if not candidate_in_cells(digit, triplet):
                continue
            if not candidate_in_cells(digit, grid.rows_less_triplet[trinum]):
                for cell in grid.boxes_less_hortriplet[trinum]:
                    if digit in cell.candidates:
                        cell.discard(digit)
                        grid_modified = True
                if grid_modified:
                    grid.history.append(('claiming h', triplet[0].rownum, triplet[0].boxnum, 'discard', digit))
                    return True

        for trinum, triplet in enumerate(grid.vertical_triplets):
            if not candidate_in_cells(digit, triplet):
                continue
            if not candidate_in_cells(digit, grid.cols_less_triplet[trinum]):
                for cell in grid.boxes_less_vertriplet[trinum]:
                    if digit in cell.candidates:
                        cell.discard(digit)
                        grid_modified = True
                if grid_modified:
                    grid.history.append(('claiming v', triplet[0].colnum, triplet[0].boxnum, 'discard', digit))
                    return True

    return grid_modified


# Locked sets


def locked_sets_n(grid, cells, length, legend):
    grid_modified = False
    for subset in itertools.combinations(cells, length):
        u = set().union(*(cell.candidates for cell in subset))
        if length == len(u):
            cells_less_subset = (cell for cell in cells if cell not in subset)
            discarded = []
            for cell in cells_less_subset:
                for c in u:
                    if c in sorted(cell.candidates):
                        cell.discard(c)
                        grid_modified = True
                        if c not in discarded:
                            discarded.append(c)
        if grid_modified:
            grid.history.append(('subset', legend, cells, subset, 'discard', discarded))
            return True
    return False


def locked_pair(grid, cells, legend):
    cells = [cell for cell in cells if len(cell.candidates) > 1]
    return locked_sets_n(grid, cells, 2, legend)


def solve_nacked_pairs(grid):
    for row in grid.rows:
        if locked_pair(grid, row, 'row'):
            return True
    for col in grid.cols:
        if locked_pair(grid, col, 'col'):
            return True
    for box in grid.boxes:
        if locked_pair(grid, box, 'box'):
            return True
    return False


def necked_triple(grid, cells, legend):
    cells = [cell for cell in cells if len(cell.candidates) > 1]
    return locked_sets_n(grid, cells, 3, legend)


def solve_nacked_triples(grid):
    return (
        any(necked_triple(grid, row, 'row') for row in grid.rows) or
        any(necked_triple(grid, col, 'col') for col in grid.cols) or
        any(necked_triple(grid, box, 'box') for box in grid.boxes)
    )


def locked_sets(cells):
    cells = [cell for cell in cells if len(cell.candidates) > 1]
    result = list()
    for length in range(2, len(cells)):
        for x in itertools.combinations(cells, length):
            u = set().union(*x)
            if length == len(u):
                result.append((x, u, length, len(u)))

    # if sum(lenset for _, _, _, lenset in result) == len(cells):
    #     result = list()

    return result



# solving engine


def solve(grid, trace_history=False):
    grid_modified = True
    while grid_modified:
        grid_modified = (
            solve_single_candidate(grid) or
            solve_hidden_candidate(grid) or
            solve_pointing(grid) or
            solve_claiming(grid) or
            solve_nacked_pairs(grid) or
            solve_nacked_triples(grid) or
            False
        )
    if trace_history:
        for _ in grid.history:
            print(_)


#


def test(fname):
    grid = Grid()
    success = True
    ngrids = 0
    solved = 0
    with open(fname) as f:
        for line in f:
            input, output, _ = line.strip().split(None, 2)
            ngrids += 1
            grid.input(input)
            solve(grid)
            # print('>', output)
            # print('<', grid.output())
            if output != grid.output():
                print(output, grid.output())
                success = False
            else:
                solved += 1
    print(f'success: {success} solved {solved}/{ngrids}')


def parse_command_line(argstring=None):
    usage = "usage: sudosol ..."
    parser = argparse.ArgumentParser(description=usage, usage=argparse.SUPPRESS)
    parser.add_argument('-s', '--solve', help='solve str81 argument',
                        action='store', default=None)
    parser.add_argument('-c', '--clipboard', help='init grid from clipboard',
                        action='store_true', default=False)
    parser.add_argument('-f', '--format', help='format',
                        action='store', default='ss')
    parser.add_argument('-t', '--test', help='test file',
                        action='store', default=None)
    parser.add_argument('-H', '--history', help='trace history',
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
        solve(grid, options.history)
        grid.dump()

    elif options.test:
        test(options.test)

    elif options.clipboard:
        if options.format == 'ss':
            grid = Grid()
            content = clipboard.paste()
            load_ss_clipboard(grid, content)
            grid.dump()
            # test
            history = []
            solve_pointing(grid, history)
            grid.dump()

    else:
        grid = Grid()
        grid.input('........2..6....39..9.7..463....672..5..........4.1.....235....9.1.8...5.3...9...')
        print(grid.horizontal_triplets)
        print(grid.vertical_triplets)
        grid.dump()
        solve(grid)
        grid.dump()
        print(grid.output())
        print()
        exit
        # grid.discard_rc(5, 8, 4)
        # grid.discard_rc(5, 8, 6)
        # grid.set_value_rc(5, 2, 1)
        # grid.set_value_rc(0, 8, 9)

        #solve_single_candidate(grid)
        #solve_hidden_candidate(grid)
        # solve(grid)
        # grid.dump()
        # print(grid.output())
        # print()
        #test()


if __name__ == '__main__':
    main()
