import random
import time
import sudosol

try:
    import dlx_sudoku
except:
    from . import dlx_sudoku


def candleft(grid):
    """Check if all cells without a value have some candidates left.
    """
    return all(cell.candidates for cell in [cell for cell in grid.cells if not cell.value])


def chose_cell(grid):
    """Chose the first cell which value has not yet been set.
    """
    for cell in grid.cells:
        if not cell.value:
            return cell


def chose_cell_(grid):
    """Chose a random cell without value. Much slower than returning the first one.
    """
    # not used
    return random.choice([cell for cell in grid.cells if not cell.value])


def genrec(grid):
    if grid.is_solved():
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
    random.shuffle(digits)
    for cell, digit in zip(grid.boxes[4], digits):
        grid.set_value(cell, digit)
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


def remove_given(grid, tempo=False):
    """Make one attempt to remove as many as possible given from a full grid.
    tempo used during background generation.
    """
    cells = grid.cells[:]
    random.shuffle(cells)
    for cell in cells:
        value = cell.value
        grid.rem_value(cell)
        if not unicity(grid):
            grid.set_value(cell, value)
        if tempo and cell.cellnum % 10 == 0:
            time.sleep(0.01)


def remove_given_sym(grid, tempo=False):
    """Make one attempt to remove as many as possible given from a full grid while
    preserving central symmetry.
    tempo used during background generation.
    """
    cells = grid.cells[:41]
    random.shuffle(cells)
    for cell in cells:
        value = cell.value
        grid.rem_value(cell)
        if cell.cellnum != 40:
            cell2 = grid.cells[9 * (8 - cell.rownum) + (8 - cell.colnum)]
            value2 = cell2.value
            grid.rem_value(cell2)
        if not unicity(grid):
            grid.set_value(cell, value)
            grid.set_value(cell2, value2)
        if tempo and cell.cellnum % 10 == 0:
            time.sleep(0.01)


def test_level(grid, level_1:None|str, level_2:str) -> None|str:
    """Test if puzzle solved by level_2 but not by level_1.
    """
    s81 = grid.output_s81()
    if level_1:
        sudosol.solve(grid, Options(), techniques=level_1, explain=False, step=False)
        if grid.is_solved():
            return None
    sudosol.solve(grid, Options(), techniques=level_2, explain=False, step=False)
    if grid.is_solved():
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


def attempt_sudoku_any(symmetric=True, tempo=False): # -> None|(int,str)
    """Make one attempt to generate a puzzle solved by any sudogui level.
    Return the grid if success, None otherwise.
    """
    grid = random_full_sudoku()
    if symmetric:
        remove_given_sym(grid, tempo=tempo)
    else:
        remove_given(grid, tempo=tempo)
    s81 = grid.output_s81()
    for level in range(6):
        grid.input(s81)
        level_1 = None if level == 0 else f'sudosol-level-{level}'
        level_2 = f'sudosol-level-{level + 1}'
        if test_level(grid, level_1, level_2):
            return level + 1, s81
    return None


def random_sudoku(level_1:None|str, level_2:str) -> str:
    """Return a puzzle solved by level_2 but not by level_1.
    """
    while True:
        grid = attempt_sudoku(level_1, level_2)
        if grid is not None:
            return grid


def main():
    T0 = time.time()
    for _ in range (1000):
        grid = attempt_sudoku_any()
    T1 = time.time()
    print(int((T1 - T0) * 1000))


if __name__ == '__main__':
    main()
