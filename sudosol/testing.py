import os
import sys
import glob
import re
import time
import random
import io
import itertools
from contextlib import redirect_stdout

from tqdm import tqdm
from icecream import ic

import sudosol


def application_error(*args):
    print('sudosol error:', *args)
    sys.exit(1)


def testfile(options, filename, techniques, explain):
    grid = sudosol.Grid()
    grid.decorate = options.decorate
    ngrids = 0
    solved = 0
    try:
        with open(filename) as f:
            grids = f.readlines()
    except IOError:
        application_error('unable to read', filename)

    # remove empty lines and full line comments before choosing grids
    grids = [line for line in grids if line.strip() and line[0] not in ';#']

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
                sudosol.solve(grid, options, techniques, explain)
                if grid.compare_string(output):
                    solved += 1
                    if options.trace == 'success':
                        print(input, output, file=f)
                else:
                    if options.trace == 'failure':
                        print(input, output, file=f)
                ngrids += 1
            except (ValueError, sudosol.SudokuError):
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
                testoptions = sudosol.parse_command_line(testargs)

                # propagate batch options
                if options.first:
                    testoptions.first = options.first
                if options.random:
                    testoptions.random = options.random
                if options.explain:
                    testoptions.explain = options.explain
                if options.decorate:
                    testoptions.decorate = options.decorate

                success, timing = sudosol.main_args(testoptions)
                if not success:
                    break
                timing_batch += timing

    print(f'BATCH OK Time: {timing_batch:0.3}' if success else 'TEST FAILURE')
    return success, timing_batch


def compare_output(options):
    """Run the main command (--testfile, --testdir, --testbatch) after redirecting
    stdout to get all traces in a file. Make a reference file or compare with a
    reference file after that.
    """
    # save and remove from options record
    compare = options.compare
    reference = options.reference
    options.compare = None
    options.reference = None
    t0 = time.time()

    with io.StringIO() as buf, redirect_stdout(buf):
        # call again main without --reference or --compare parameters.
        sudosol.main_args(options)
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
        print('COMPARE OK:' if res else 'COMPARE FAILURE:', compare)
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
    diff = []
    res = True
    for i, (x, y) in enumerate(itertools.zip_longest(list1, list2, fillvalue='extra\n')):
        if x != y:
            diff.append('line %s %d: %s' % (tag1, i + 1, x))
            diff.append('line %s %d: %s' % (tag2, i + 1, y))
            res = False
    return res, diff


REGTEST = r'D:\Gilles\Dev\sudosol\tests\reglib-1.3.txt'


def compare_placements(placements: str, cell) -> bool:
    return placements == f'{cell.value}{cell.rownum + 1}{cell.colnum + 1}'


def discarded_to_string(discarded: str) -> bool:
    eliminations = set()
    for cand, cells in discarded.items():
        eliminations |= {f'{cand}{cell.rownum + 1}{cell.colnum + 1}' for cell in cells}
    return ' '.join(sorted(eliminations))


def compare_discarded(eliminations: str, discarded: dict) -> bool:
    # eliminations: <cand1><col><row> <cand2><col><row> ...
    # discarded: {cand1 : cells, cand2: cells, ...}
    eliminations2 = set()
    for cand, cells in discarded.items():
        eliminations2 |= {f'{cand}{cell.rownum + 1}{cell.colnum + 1}' for cell in cells}
    return set(eliminations.split()) == eliminations2


def testone(technique_names, line, counters: dict, not_implemented: dict):
    counters['total'] += 1
    # extra may be omitted
    if line.count(':') == 6:
        line += ':'
    technique, candidates, values, exclusions, eliminations, placements, extra = line[1:].split(':')

    if technique == '0610-x':
        # TODO: à voir, en particulier à cause du assert ligne 2528
        counters['ignored'] += 1
        return

    counters['tested'] += 1
    grid = sudosol.Grid()
    grid.input_hodoku(values + ':' + exclusions)

    tech = technique[:4]
    techname, caption = technique_names[tech]
    list_techniques = sudosol.make_list_techniques(sudosol.STRATEGY_HODOKU_UNFAIR)

    if techname not in list_techniques:
        counters['not_implemented'] += 1
        if tech not in not_implemented:
            not_implemented[tech] = 1
        else:
            not_implemented[tech] += 1
    elif re.match(r'060[0-6]-2', technique):
        # Unique rectangles and hidden rectangles with missing candidates
        counters['not_implemented'] += 1
        if technique not in not_implemented:
            not_implemented[technique] = 1
        else:
            not_implemented[technique] += 1
    else:
        if sudosol.apply_strategy(grid, [techname], explain=False, target=candidates):
            _, move, *rest = grid.history[grid.history_top]
            if eliminations:
                if move == 'discard':
                    discarded, = rest
                    if compare_discarded(eliminations, discarded):
                        counters['solved'] += 1
                    else:
                        counters['partial'] += 1
                        trace(line, tech, techname, caption, 'Partial (1)', eliminations, ' | ', discarded_to_string(discarded))
                else:
                    counters['failed'] += 1
                    trace(line, tech, techname, caption, 'Failed (1)')
            elif placements:
                if move == 'value':
                    cell, value, discarded = rest
                    if compare_placements(placements, cell):
                        counters['solved'] += 1
                    else:
                        counters['partial'] += 1
                        trace(line, tech, techname, caption, 'Partial (2)', placements, set([value]))
                else:
                    counters['failed'] += 1
                    trace(line, tech, techname, caption, 'Failed (2)')
            else:
                assert 0

        else:
            counters['failed'] += 1
            trace(line, tech, techname, caption, 'Failed (3)')


def trace(line, tech, techname, caption, *more):
    print(line)
    print(tech, techname, caption)
    print(*more)
    print()


def get_technique_names():
    """Get conversion data from technique IDs (4 digits) to technique names from
    java source code. IDs equal to xxxx are ignored.
    """
    technique_names = {}
    with open(os.path.join(os.path.dirname(__file__), 'SolutionType.java')) as f:
        for line in f:
            if 'java.util.ResourceBundle.getBundle' in line:
                # getString("Uniqueness_Test_1"), "0600", "u1"),
                _, caption, ID, name = re.findall('"([^"]+)"', line)
                if ID == 'xxxx':
                    pass
                else:
                    technique_names[ID] = (name, caption)
    return technique_names


def regression_testing():
    technique_names = get_technique_names()
    counters = dict(total=0, ignored=0, tested=0, solved=0, partial=0, not_implemented=0, failed=0)
    not_implemented = {}
    t0 = time.time()
    with open(REGTEST) as f:
        for line in f:
            if line.strip() and line[0] != '#':
                testone(technique_names, line.strip(), counters, not_implemented)

    print('Not implemented')
    for tech, count in sorted(not_implemented.items()):
        print(tech, *technique_names[tech[:4]], count)
    print()

    for counter, value in counters.items():
        print(counter, value)
    print('check', counters['solved'] + counters['partial'] + counters['not_implemented'] + counters['failed'])
    t1 = time.time()
    return counters['partial'] == counters['failed'] == 0, t1 - t0


if __name__ == '__main__':
    regression_testing()
