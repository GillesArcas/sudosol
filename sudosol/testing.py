"""
Testing module for sudosol.
"""


import os
import sys
import glob
import re
import time
import random
import io
import itertools
from contextlib import redirect_stdout
from collections import defaultdict

from tabulate import tabulate
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


def not_implemented_variant(technique):
    if re.match(r'060[0-6]-2', technique):
        # Unique rectangles and hidden rectangles with missing candidates
        return True
    if re.match(r'03..1', technique):
        # Siamese fishes
        return True
    return False


def testone(technique_names, line, counters: dict, implemented: dict, not_implemented: dict):
    counters['total'] += 1
    # extra may be omitted
    if line.count(':') == 6:
        line += ':'
    technique, candidates, values, exclusions, eliminations, placements, extra = line[1:].split(':')

    counters['tested'] += 1
    grid = sudosol.Grid()
    grid.input_hodoku(values + ':' + exclusions)

    tech = technique[:4]
    techname, caption = technique_names[tech]
    list_techniques = sudosol.make_list_techniques(sudosol.STRATEGY_HODOKU_UNFAIR)

    if techname not in list_techniques:
        counters['not_implemented'] += 1
        not_implemented[tech] += 1
    elif not_implemented_variant(technique):
        counters['not_implemented'] += 1
        not_implemented[technique] += 1
    else:
        implemented[technique] += 1
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

        elif technique in ('0606-x', '0610-x'):
            counters['failed_ok'] += 1
        else:
            counters['failed'] += 1
            trace(line, tech, techname, caption, 'Failed (3)')


def trace(line, tech, techname, caption, *more):
    print(line)
    print(tech, techname, caption)
    print(*more)
    print()


TECHNIQUES = {
    '0000': ('fh', 'Full_House'),
    '0002': ('h1', 'Hidden_Single'),
    '0003': ('n1', 'Naked_Single'),
    '0100': ('lc1', 'Locked_Candidates_Type_1_(Pointing)'),
    '0101': ('lc2', 'Locked_Candidates_Type_2_(Claiming)'),
    '0110': ('l2', 'Locked_Pair'),
    '0111': ('l3', 'Locked_Triple'),
    '0200': ('n2', 'Naked_Pair'),
    '0201': ('n3', 'Naked_Triple'),
    '0202': ('n4', 'Naked_Quadruple'),
    '0210': ('h2', 'Hidden_Pair'),
    '0211': ('h3', 'Hidden_Triple'),
    '0212': ('h4', 'Hidden_Quadruple'),
    '0300': ('bf2', 'X-Wing'),
    '0301': ('bf3', 'Swordfish'),
    '0302': ('bf4', 'Jellyfish'),
    '0303': ('bf5', 'Squirmbag'),
    '0304': ('bf6', 'Whale'),
    '0305': ('bf7', 'Leviathan'),
    '0310': ('fbf2', 'Finned_X-Wing'),
    '0311': ('fbf3', 'Finned_Swordfish'),
    '0312': ('fbf4', 'Finned_Jellyfish'),
    '0313': ('fbf5', 'Finned_Squirmbag'),
    '0314': ('fbf6', 'Finned_Whale'),
    '0315': ('fbf7', 'Finned_Leviathan'),
    '0320': ('sbf2', 'Sashimi_X-Wing'),
    '0321': ('sbf3', 'Sashimi_Swordfish'),
    '0322': ('sbf4', 'Sashimi_Jellyfish'),
    '0323': ('sbf5', 'Sashimi_Squirmbag'),
    '0324': ('sbf6', 'Sashimi_Whale'),
    '0325': ('sbf7', 'Sashimi_Leviathan'),
    '0330': ('ff2', 'Franken_X-Wing'),
    '0331': ('ff3', 'Franken_Swordfish'),
    '0332': ('ff4', 'Franken_Jellyfish'),
    '0333': ('ff5', 'Franken_Squirmbag'),
    '0334': ('ff6', 'Franken_Whale'),
    '0335': ('ff7', 'Franken_Leviathan'),
    '0340': ('fff2', 'Finned_Franken_X-Wing'),
    '0341': ('fff3', 'Finned_Franken_Swordfish'),
    '0342': ('fff4', 'Finned_Franken_Jellyfish'),
    '0343': ('fff5', 'Finned_Franken_Squirmbag'),
    '0344': ('fff6', 'Finned_Franken_Whale'),
    '0345': ('fff7', 'Finned_Franken_Leviathan'),
    '0350': ('mf2', 'Mutant_X-Wing'),
    '0351': ('mf3', 'Mutant_Swordfish'),
    '0352': ('mf4', 'Mutant_Jellyfish'),
    '0353': ('mf5', 'Mutant_Squirmbag'),
    '0354': ('mf6', 'Mutant_Whale'),
    '0355': ('mf7', 'Mutant_Leviathan'),
    '0360': ('fmf2', 'Finned_Mutant_X-Wing'),
    '0361': ('fmf3', 'Finned_Mutant_Swordfish'),
    '0362': ('fmf4', 'Finned_Mutant_Jellyfish'),
    '0363': ('fmf5', 'Finned_Mutant_Squirmbag'),
    '0364': ('fmf6', 'Finned_Mutant_Whale'),
    '0365': ('fmf7', 'Finned_Mutant_Leviathan'),
    '0371': ('kf1', 'Kraken_Fish_Type_1'),
    '0372': ('kf2', 'Kraken_Fish_Type_2'),
    '0400': ('sk', 'Skyscraper'),
    '0401': ('2sk', '2-String_Kite'),
    '0402': ('er', 'Empty_Rectangle'),
    '0403': ('tf', 'Turbot_Fish'),
    '0404': ('d2sk', 'Dual_2-String_Kite'),
    '0405': ('der', 'Dual_Empty_Rectangle'),
    '0500': ('sc1', 'Simple_Colors_Trap'),
    '0501': ('sc2', 'Simple_Colors_Wrap'),
    '0502': ('mc1', 'Multi_Colors_1'),
    '0503': ('mc2', 'Multi_Colors_2'),
    '0600': ('u1', 'Uniqueness_Test_1'),
    '0601': ('u2', 'Uniqueness_Test_2'),
    '0602': ('u3', 'Uniqueness_Test_3'),
    '0603': ('u4', 'Uniqueness_Test_4'),
    '0604': ('u5', 'Uniqueness_Test_5'),
    '0605': ('u6', 'Uniqueness_Test_6'),
    '0606': ('hr', 'Hidden_Rectangle'),
    '0607': ('ar1', 'Avoidable_Rectangle_Type_1'),
    '0608': ('ar2', 'Avoidable_Rectangle_Type_2'),
    '0610': ('bug1', 'Bivalue_Universal_Grave_+_1'),
    '0701': ('x', 'X-Chain'),
    '0702': ('xyc', 'XY-Chain'),
    '0703': ('rp', 'Remote_Pair'),
    '0706': ('cnl', 'Continuous_Nice_Loop'),
    '0707': ('dnl', 'Discontinuous_Nice_Loop'),
    '0708': ('aic', 'AIC'),
    '0709': ('gcnl', 'Grouped_Continuous_Nice_Loop'),
    '0710': ('gdnl', 'Grouped_Discontinuous_Nice_Loop'),
    '0711': ('gaic', 'Grouped_AIC'),
    '0800': ('xy', 'XY-Wing'),
    '0801': ('xyz', 'XYZ-Wing'),
    '0803': ('w', 'W-Wing'),
    '0901': ('axz', 'Almost_Locked_Set_XZ-Rule'),
    '0902': ('axy', 'Almost_Locked_Set_XY-Wing'),
    '0903': ('ach', 'Almost_Locked_Set_XY-Chain'),
    '0904': ('db', 'Death_Blossom'),
    '1101': ('sdc', 'Sue_de_Coq'),
    '1201': ('ts', 'Template_Set'),
    '1202': ('td', 'Template_Delete'),
    '1301': ('fcc', 'Forcing_Chain_Contradiction'),
    '1302': ('fcv', 'Forcing_Chain_Verity'),
    '1303': ('fnc', 'Forcing_Net_Contradiction'),
    '1304': ('fnv', 'Forcing_Net_Verity')
}


def get_technique_names():
    """Get conversion data from technique IDs (4 digits) to technique names from
    Hodoku java source code (file SolutionType.java). IDs equal to xxxx are ignored.
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


def get_technique_names():
    return TECHNIQUES


def regression_testing(regtestfile):
    technique_names = get_technique_names()
    counters = dict(total=0, tested=0, solved=0, partial=0, not_implemented=0, failed=0, failed_ok=0)
    implemented = defaultdict(int)
    not_implemented = defaultdict(int)
    t0 = time.time()
    with open(regtestfile) as f:
        for line in f:
            if line.strip() and line[0] != '#':
                testone(technique_names, line.strip(), counters, implemented, not_implemented)

    print('Implemented techniques')
    tabulate_data = []
    for tech, count in sorted(implemented.items()):
        tabulate_data.append([tech, *technique_names[tech[:4]], count])
    print(tabulate(tabulate_data))
    print()

    print('Techniques or variants not implemented')
    tabulate_data = []
    for tech, count in sorted(not_implemented.items()):
        tabulate_data.append([tech, *technique_names[tech[:4]], count])
    print(tabulate(tabulate_data))
    print()

    print('Statistics')
    tabulate_data = []
    for counter, value in counters.items():
        tabulate_data.append([counter, value])
    tabulate_data.append(['check', sum(counters[_] for _ in counters if _ not in ('total', 'tested'))])
    print(tabulate(tabulate_data))
    print()
    t1 = time.time()
    return counters['partial'] == counters['failed'] == 0, t1 - t0
