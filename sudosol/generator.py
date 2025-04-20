import random
import time
import cProfile
import sudosol
from icecream import ic

import dlx
try:
    import dlx_sudoku
except:
    from . import dlx_sudoku


def candleft(grid):
    return all(cell.candidates for cell in [cell for cell in grid.cells if not cell.value])


def chose_cell(grid):
    for cell in grid.cells:
        if not cell.value:
            return cell


def genrec(grid):
    if grid.solved():
        return grid
    elif not candleft(grid):
        return None
    else:
        cell = chose_cell(grid)
        candidates = list(cell.candidates)
        random.shuffle(candidates)
        for cand in candidates:
            discarded = grid.set_value(cell, cand)
            grid.push(('random', 'value', cell, cand, discarded))
            r = genrec(grid)
            if r:
                return grid
            else:
                grid.undo()
        return None


def random_full_sudoku():
    grid = sudosol.Grid()
    digits = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    random.shuffle(digits)
    for cell, digit in zip(grid.boxes[0], digits):
        grid.set_value(cell, digit)
    digits = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    random.shuffle(digits)
    for cell, digit in zip(grid.boxes[4], digits):
        grid.set_value(cell, digit)
    digits = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    random.shuffle(digits)
    for cell, digit in zip(grid.boxes[8], digits):
        grid.set_value(cell, digit)

    grid = genrec(grid)
    return grid


class Options:
    """minimal options for sudosol grid
    """
    def __init__(self):
        self.step = False


def unicity(grid:sudosol.Grid) -> bool:
    s = grid.output_s81(unknown='0')
    d = dlx_sudoku.DLXsudoku(s)
    for index, sol in enumerate(d.solve(), 1):
        if index >= 2:
            return False
    return True


def number_of_given(grid):
    return sum(c.value is not None for c in grid.cells)


def remove_given(grid):
    cells = grid.cells[:]
    random.shuffle(cells)
    stack = []
    while cells:
        cell = cells.pop()
        stack.append((cell, cell.value))
        grid.rem_value(cell)
        if not unicity(grid):
            cell, digit = stack.pop()
            grid.set_value(cell, digit)


def remove_given_sym(grid):
    cells = grid.cells[:5 * 9]
    random.shuffle(cells)
    stack = []
    while cells:
        cell = cells.pop()
        stack.append((cell, cell.value))
        grid.rem_value(cell)
        if cell.cellnum != 4 * 9 + 4:
            cell = grid.cells[9 * (8 - cell.rownum) + (8 - cell.colnum)]
            stack.append((cell, cell.value))
            grid.rem_value(cell)
        if not unicity(grid):
            cell, digit = stack.pop()
            grid.set_value(cell, digit)
            cell, digit = stack.pop()
            grid.set_value(cell, digit)


def test_level(grid, level_1:None|str, level_2:str) -> None|str:
    """    """
    s81 = grid.output_s81()
    if level_1:
        sudosol.solve(grid, Options(), techniques=level_1, explain=False, step=False)
        if grid.solved():
            return None
    sudosol.solve(grid, Options(), techniques=level_2, explain=False, step=False)
    if grid.solved():
        return s81
    else:
        return None


def attempt_sudoku(level_1:None|str, level_2:str, symmetric=True) -> None|str:
    """Make one attempt to generate a puzzle solved by level_2 but not by level_1.
    Return the grid if success, None otherwise.
    """
    grid = random_full_sudoku()
    if symmetric:
        remove_given_sym(grid)
    else:
        remove_given(grid)
    return test_level(grid, level_1, level_2)


def random_sudoku(level_1:None|str, level_2:str) -> str:
    """Return a puzzle solved by level_2 but not by level_1.
    """
    while True:
        grid = attempt_sudoku(level_1, level_2)
        if grid is not None:
            return grid


def main():
    T0 = time.time()
    for _ in range (10):
        t0 = time.time()
        n = 0
        while 1:
            grid = attempt_sudoku('sudosol-level-4', 'sudosol-level-5')
            n += 1
            if grid:
                break
        t1 = time.time()
        print('OK', int((t1 - t0) * 1000), n, sum(x != '.' for x in grid))
    T1 = time.time()
    print(int((T1 - T0) * 1000))


if __name__ == '__main__':
    main()
