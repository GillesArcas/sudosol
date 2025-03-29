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
        for cand in cell.candidates:    # TODO : randomize
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


LEVELS = (
    sudosol.STRATEGY_SSTS_EASY,
    sudosol.STRATEGY_SSTS_STANDARD,
    sudosol.STRATEGY_SSTS_HARD,
    sudosol.STRATEGY_SSTS_EXPERT,
    sudosol.STRATEGY_SSTS_EXTREME
)


def random_sudoku_batch():
    grid = random_full_sudoku()

    cells = grid.cells[:]
    random.shuffle(cells)
    stack = []
    while cells:
        cell = cells.pop()
        stack.append((cell, cell.value))
        grid.rem_value(cell)
        s = grid.output_s81(unknown='0')
        d = dlx_sudoku.DLXsudoku(s)
        if len(list(d.solve())) > 1:
            cell, digit = stack.pop()
            grid.set_value(cell, digit)
            if sum(c.value is not None for c in grid.cells) > 35:
                cell, digit = stack.pop()
                grid.set_value(cell, digit)
                if not cells:
                    break

    s81 = grid.output_s81()
    for techniques, level in zip(SSTS, SSTS_LEVEL):
        sudosol.solve(grid, Options(), techniques=techniques, explain=False, step=False)
        if grid.solved():
            print(s81, '#', level)
            break
    else:
        print(s81, '#', 'UNSOLVED')


def random_sudoku(level_1:None|str, level_2:str) -> str:
    """Return a puzzle solved by level_2 but not by level_1. May required
    time-out.
    """
    while True:
        grid = random_full_sudoku()

        cells = grid.cells[:]
        random.shuffle(cells)
        stack = []
        while cells:
            cell = cells.pop()
            stack.append((cell, cell.value))
            grid.rem_value(cell)
            s = grid.output_s81(unknown='0')
            d = dlx_sudoku.DLXsudoku(s)
            if len(list(d.solve())) > 1:
                cell, digit = stack.pop()
                grid.set_value(cell, digit)
                if sum(c.value is not None for c in grid.cells) > 35:
                    cell, digit = stack.pop()
                    grid.set_value(cell, digit)
                    if not cells:
                        break

        s81 = grid.output_s81()
        if level_1:
            sudosol.solve(grid, Options(), techniques=level_1, explain=False, step=False)
            if grid.solved():
                continue
        sudosol.solve(grid, Options(), techniques=level_2, explain=False, step=False)
        if grid.solved():
            return s81


def main():
    t0 = time.time()
    for _ in range(1000):
        random_sudoku()
    ic(time.time() - t0)


if __name__ == 'main':
    # cProfile.run('main()')
    main()