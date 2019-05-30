

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

    def reset(self):
        for cell in self.cells:
            cell.reset()

    # def __str__(self):
    #     pass

    def input(self, str81):
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


# Singles


def solve_single_candidate(grid):
    # naked singles
    grid_modified = False
    for cell in grid.cells:
        if len(cell.candidates) == 1:
            grid.set_value_rc(cell.rownum, cell.colnum, list(cell.candidates)[0])
            grid_modified = True
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
                # avoid to loop on candidates from initial cell state
                break
    return grid_modified


# solving engine


def solve(grid):
    grid_modified = True
    while grid_modified:
        grid_modified = (
            solve_single_candidate(grid) or
            solve_hidden_candidate(grid) or
            False
        )


def solve_pointing(grid):
    for digit in range(1, 9 + 1):
        solve_pointing_digit(grid, digit)


def solve_pointing_digit(grid, digit):

    # row triplets
    solve_row_pointing_digit(grid, digit)

    # col triplets
    transpose(grid)
    solve_row_pointing_digit(grid, digit)
    transpose(grid)


def solve_row_pointing_digit(grid, digit):
    for triplet in range(1, 27 + 1):
        if is_locked_in_row(grid, digit, triplet):
            for shared_triplet in shared_box_horizontal_triplets(triplet):
                remove_cand_in_horizontal_triplet(grid, digit, shared_triplet)


def solve_row_claiming_digit(grid, digit):
    for triplet in range(1, 27 + 1):
        if is_locked_in_box(grid, digit, triplet):
            for shared_triplet in shared_row_horizontal_triplets(triplet):
                remove_cand_row(grid, digit, shared_triplet)



def test():
    fname = r"D:\Gilles\Sudoku\.Applications\HoDoKu\singles.txt"
    grid = Grid()
    with open(fname) as f:
        for line in f:
            input, output = line.strip().split()
            grid.input(input)
            solve(grid)
            print(output == grid.output(), output, grid.output())


# grid = Grid()
# grid.input('.7..6..45.96..........4.1...13..97.46..7.......43...5.5.....82184................')
# grid.dump()
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
test()
