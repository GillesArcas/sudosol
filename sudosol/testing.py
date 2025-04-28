import os
import re
import time
import sudosol
from icecream import ic

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
    tech, candidates, values, exclusions, eliminations, placements, extra = line[1:].split(':')

    if tech == '0610-x':
        # TODO: à voir, en particulier à cause du assert ligne2528
        counters['ignored'] += 1
        return

    counters['tested'] += 1
    grid = sudosol.Grid()
    grid.input_hodoku(values + ':' + exclusions)
    # print(grid.dumpstr())
    tech = tech[:4]
    # print(terminology[tech])
    techname, caption = technique_names[tech]
    list_techniques = sudosol.make_list_techniques(sudosol.STRATEGY_HODOKU_UNFAIR)

    if techname not in list_techniques:
        counters['not_implemented'] += 1
        if tech not in not_implemented:
            not_implemented[tech] = 0
        else:
            not_implemented[tech] += 1
    else:
        if sudosol.apply_strategy(grid, [techname], explain=False, target=candidates):
            caption2, move, *rest = grid.history[grid.history_top]
            if eliminations:
                if move == 'discard':
                    discarded, = rest
                    if compare_discarded(eliminations, discarded):
                        counters['solved'] += 1
                    else:
                        counters['partial'] += 1
                        print(line)
                        print(tech, techname, caption)
                        print('Partial (1)', eliminations, ' | ', discarded_to_string(discarded))
                        print()
                else:
                    counters['failed'] += 1
                    print(line)
                    print(tech, techname, caption)
                    print('Failed (1)')
                    print()
            elif placements:
                if move == 'value':
                    cell, value, discarded = rest
                    if compare_placements(placements, cell):
                        counters['solved'] += 1
                    else:
                        counters['partial'] += 1
                        print(line)
                        print(tech, techname, caption)
                        print('Partial (2)', placements, set([value]))
                        print()
                else:
                    counters['failed'] += 1
                    print(line)
                    print(tech, techname, caption)
                    print('Failed (2)')
                    print()
            else:
                assert 0

        else:
            counters['failed'] += 1
            print(line)
            print(tech, techname, caption)
            print('Failed (3)')
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
        print(tech, *technique_names[tech], count)
    print()

    for counter, value in counters.items():
        print(counter, value)
    print('check', counters['solved'] + counters['partial'] + counters['not_implemented'] + counters['failed'])
    t1 = time.time()
    return counters['partial'] == counters['failed'] == 0, t1 - t0


if __name__ == '__main__':
    regression_testing()
