"""
Generate or solve sudoku grids using hodoku.
"""

import argparse
import sys
import os
import time
import subprocess
import re


NAME_GENERATED = 'generated.txt'
NAME_TOBESOLVED = 'tobesolved.txt'
NAME_SOLVED = 'solved.txt'
HODOKU_JAR = 'hodoku.jar'


USAGE = """
generate.py test tech name_out num_wanted s|ssts|x
    technique   hodoku ID's
    s|ssts|x    technique occurs after and is followrd by only singles, ssts
                techniques or any technique (default to s)
    generate list of grids with solution for given techniques

generate.py solve name_in name_out
    add final grid to list of grids

generate.py step name_in name_out caption
    caption     hodoku caption of the technique
    input a list of grids with a given technique, output pencil marks just
    before application of the technique
"""


def parse_command_line():
    parser = argparse.ArgumentParser(
        description=USAGE,
        usage=argparse.SUPPRESS,
        formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers()

    _ = subparsers.add_parser('test')
    _.add_argument('technique')
    _.add_argument('name_out')
    _.add_argument('numwanted', type=int)
    _.add_argument('context', nargs='?', choices=['s', 'ssts', 'x'], default='s')
    _.add_argument('--timeout', action='store', type=int, default=3600)
    _.set_defaults(func=main_testdeck)

    _ = subparsers.add_parser('solve')
    _.add_argument('name_in')
    _.add_argument('name_out')
    _.set_defaults(func=main_solve)

    _ = subparsers.add_parser('step')
    _.add_argument('name_in')
    _.add_argument('name_out')
    _.add_argument('caption')
    _.set_defaults(func=main_step)

    return parser.parse_args()


def main_testdeck(args):
    """Generate a testdeck for sudosol. Starting grid and solution grid on
    the same line.
    """
    tech = args.technique
    name_out = args.name_out
    numwanted = args.numwanted
    name_generated = f'{tech}-{NAME_GENERATED}'

    # calculate number of existing solutions if any
    try:
        with open(name_out) as f:
            num_existing = len(f.readlines())
    except IOError:
        num_existing = 0

    # check if number wanted is reached
    if num_existing >= numwanted:
        exit(0)

    # start hodoku in generate mode
    mode = {'x': 0, 'ssts': 1, 's': 3}[args.context]
    comm = f'java -jar {HODOKU_JAR} /s /sc {tech}:{mode} /o {name_generated}'
    print(comm)
    numobtained = num_existing
    t0 = time.time()

    try:
        cont = True
        while cont:
            # errors and warnings on stderr
            p = subprocess.Popen(comm.split(), stderr=subprocess.STDOUT, stdout=subprocess.PIPE)
            time.sleep(2)
            print('STARTED')

            while True:
                output = p.stdout.readline()
                output = output.decode("ascii", errors="ignore")
                if output == '' and p.poll() is not None:
                    cont = False
                    break
                if output:
                    print(output.strip())
                    runtime = time.time() - t0
                    if numobtained == 0 and runtime > args.timeout:
                        p.terminate()
                        cont = False
                        print(f'Time out: no solution generated in {int(runtime)} seconds')
                        break
                    if 'Exception' in output:
                        p.terminate()
                        print('Exception detected')
                        break
                    if re.match(r'[1-9.]{81}', output):
                        # even with tech:3 some grids are generated requiring ssts techniques
                        # these lines have to be filtered
                        if args.context == 's' and 'ssts' in output:
                            continue
                        else:
                            numobtained += 1
                            print(f'{numobtained}/{numwanted}')
                            if numobtained >= numwanted:
                                p.terminate()
                                cont = False
                                break

    except KeyboardInterrupt:
        p.terminate()
        print("Program stopped by user !")

    except Exception as e:
        p.terminate()
        print("Error during execution:", e)
        sys.exit(1)

    # make file of grids to be solved
    with open(name_generated) as f, open(NAME_TOBESOLVED, 'wt') as g:
        for line in f:
            grid = line.split(None, 1)[0]
            print(grid, file=g)

    # start hodoku in solving mode (hodoku must be in path)
    comm = f'java -jar {HODOKU_JAR} /bs {NAME_TOBESOLVED} /vs /o {NAME_SOLVED}'
    subprocess.check_output(comm)

    # merge
    with open(name_generated) as f1, open(NAME_SOLVED) as f2, open(name_out, 'at') as g:
        numobtained = 0
        for line1, line2 in zip(f1, f2):
            if args.context == 's' and 'ssts' in line1:
                continue
            else:
                line = line1[:81] + '  ' + line2[:81] + line1[81:]
                print(line, end='', file=g)
                numobtained += 1
                if numobtained == numwanted:
                    break

    # clean
    os.remove(name_generated)
    os.remove(NAME_TOBESOLVED)
    os.remove(NAME_SOLVED)


def main_solve(args):
    """Take a file with starting grids only and add solution grids.
    """
    # start hodoku in solving mode (hodoku must be in path)
    comm = f'java -jar {HODOKU_JAR} /bs {args.name_in} /vs /o {NAME_SOLVED}'
    subprocess.check_output(comm)

    # merge
    with open(args.name_in) as f1, open(NAME_SOLVED) as f2, open(args.name_out, 'wt') as g:
        numobtained = 0
        for line1, line2 in zip(f1, f2):
            line = line1[0:81] + '  ' + line2[0:81] + '  #\n'
            print(line, end='', file=g)
            numobtained += 1

    # clean
    os.remove(NAME_SOLVED)


def main_step(args):
    """Take a file generated for some technique and generate the file focus on
    the positions before and after apllication of the technique. Before and after
    positions are represented as the lists of candidates. Requires the full
    captions associated with the technique as an argument.
    """
    TMP1 = 'tmp1.txt'
    TMP2 = 'tmp2.txt'

    # make sure there is only one value string in line
    with open(args.name_in) as f, open(TMP1, 'wt') as g:
        for line in f:
            x = line.split()
            print(x[0], file=g)

    # solve grids with full solution and pencilmarks for all techniques (some
    # are rejected by hodoku). List of techniques generated from java -jar hodoku.jar -lt
    listtech = '2sk,aic,ach,axy,axz,ar1,ar2,bug1,bf,cnl,db,dnl,d2sk,der,er,fff4,fff7,fff5,fff3,fff6,fff2,fbf4,fbf7,fmf4,fmf7,fmf5,fmf3,fmf6,fmf2,fbf5,fbf3,fbf6,fbf2,fc,fcc,fcv,fn,fnc,fnv,ff4,ff7,ff5,ff3,ff6,ff2,fh,gu,gaic,gcnl,gdnl,gnl,h2,h4,hr,h1,h3,in,bf4,kf,kf1,kf2,bf7,lc,lc1,lc2,l2,l3,mc,mc1,mc2,mf4,mf7,mf5,mf3,mf6,mf2,n2,n4,n1,n3,nl,rp,sbf4,sbf7,sbf5,sbf3,sbf6,sbf2,sc,sc1,sc2,sk,bf5,sdc,bf3,td,ts,tf,u1,u2,u3,u4,u5,u6,w,bf6,x,bf2,xyc,xy,xyz'
    comm = f'java -jar {HODOKU_JAR} /bs {TMP1} /vp /vg c:{listtech} /o {TMP2}'
    subprocess.check_output(comm)

    with open(args.name_out, 'wt') as file_out:
        for rec in getrecord(TMP2):
            rec = pack_pencilmarks(rec)
            giv = rec[0]
            res = before_after_tech(args.caption, rec)
            if res:
                print(format_gvc(giv, res[0]), format_gvc(giv, res[1]), '#', rec[0], file=file_out)

    # clean
    os.remove(TMP1)
    os.remove(TMP2)


def getrecord(filename):
    rec = []
    with open(filename) as f:
        for line in f:
            m = re.match(r'([.0-9]{81})', line)
            if m:
                if rec:
                    yield rec
                rec = []
            rec.append(line)
        if rec:
            yield rec


def pack_pencilmarks(rec):
    def repl_pencilmarks(matchobj):
        return','.join(re.findall('[0-9]+', matchobj.group(0)))
    return re.sub(r"(   \.---[^A-Z]+---')", repl_pencilmarks, ''.join(rec), flags=re.DOTALL).splitlines()


def before_after_tech(tech, rec):
    m = re.search(r'((?:[1-9]+,){80}[1-9]+)\s*%s[^\n]*\s*((?:[1-9]+,){80}[1-9]+)' % tech, '\n'.join(rec), flags=re.DOTALL)
    if m:
        return m.group(1), m.group(2)
    else:
        return None


def format_gvc(given, candidates):
    lst = []
    for g, c in zip(given, candidates.split(',')):
        if g in '123456789':
            lst.append(f'g{g}')
        elif len(c) == 1:
            lst.append(f'v{c}')
        else:
            lst.append(f'c{c}')
    return ''.join(lst)


def main():
    # check hodoku presence
    if not os.path.isfile(HODOKU_JAR):
        print('Error: hodoku.jar not found')
        exit(1)

    args = parse_command_line()
    args.func(args)


if __name__ == '__main__':
    main()
