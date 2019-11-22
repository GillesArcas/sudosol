"""
Generate or solve sudoku grids using hodoku.
"""

import sys
import os
import time
import subprocess
import re


def tailf(fname):
    f = open(fname)
    while True:
        line = f.readline().strip()

        if not line:
            time.sleep(0.1)
            continue

        yield line


NAME_GENERATED = 'generated.txt'
NAME_TOBESOLVED = 'tobesolved.txt'
NAME_SOLVED = 'solved.txt'
HODOKU_JAR = 'hodoku.jar'


def main():
    tech = sys.argv[1]
    name_out = sys.argv[2]
    numwanted = int(sys.argv[3])
    enable_ssts = len(sys.argv) == 5 and sys.argv[4] == 'ssts'
    enable_x = len(sys.argv) == 5 and sys.argv[4] == 'x'

    name_generated = f'{tech}-{NAME_GENERATED}'

    # calculate number of existing solutions if any
    try:
        with open(name_out) as f:
            num_existing = len(f.readlines())
    except IOError:
        num_existing = 0

    # check if number wanted is reached
    if num_existing == numwanted:
        exit(0)

    # check hodoku presence
    if not os.path.isfile(HODOKU_JAR):
        print('Error: hodoku.jar not found')
        exit(1)

    # start hodoku in generate mode
    mode = 0 if enable_x else 1 if enable_ssts else 3
    comm = f'java -jar {HODOKU_JAR} /s /sc {tech}:{mode} /o {name_generated}'
    p = subprocess.Popen(comm.split())
    time.sleep(1)

    try:
        numobtained = num_existing
        for line in tailf(name_generated):
            if enable_ssts or 'ssts' not in line:
                # even with tech:3 some grids are generated requiring ssts techniques
                # these lines have to be filtered
                numobtained += 1
                print(numobtained)
                if numobtained >= numwanted:
                    p.terminate()
                    break

    except KeyboardInterrupt:
        p.terminate()
        print("Program stopped by user !")

    except Exception as e:
        p.terminate()
        print("Unknown error during execution !")
        print(e)
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
            if enable_ssts or 'ssts' not in line1:
                line = line1[0:81] + '  ' + line2[0:81] + line1[81:]
                print(line, end='', file=g)
                numobtained += 1
                if numobtained == numwanted:
                    break

    # clean
    os.remove(name_generated)
    os.remove(NAME_TOBESOLVED)
    os.remove(NAME_SOLVED)


def main2():
    assert sys.argv[1] == 'solve'
    name_in = sys.argv[2]
    name_out = sys.argv[3]

    # check hodoku presence
    if not os.path.isfile(HODOKU_JAR):
        print('Error: hodoku.jar not found')
        exit(1)

    # start hodoku in solving mode (hodoku must be in path)
    comm = f'java -jar {HODOKU_JAR} /bs {name_in} /vs /o {NAME_SOLVED}'
    subprocess.check_output(comm)

    # merge
    with open(name_in) as f1, open(NAME_SOLVED) as f2, open(name_out, 'wt') as g:
        numobtained = 0
        for line1, line2 in zip(f1, f2):
            line = line1[0:81] + '  ' + line2[0:81] + '  #\n'
            print(line, end='', file=g)
            numobtained += 1

    # clean
    os.remove(NAME_SOLVED)


def main3():
    """Take a file generated for some technique and generate the file focus on
    the positions before and after apllication of the technique. Before and after
    positions are represented as the lists of candidates. Requires the full
    captions associated with the technique as an argument.
    """
    assert sys.argv[1] == 'step'
    name_in = sys.argv[2]
    name_out = sys.argv[3]
    caption = sys.argv[4]

    TMP1 = 'tmp1.txt'
    TMP2 = 'tmp2.txt'

    # check hodoku presence
    if not os.path.isfile(HODOKU_JAR):
        print('Error: hodoku.jar not found')
        exit(1)

    # make sure there is only one value string in line
    with open(name_in) as f, open(TMP1, 'wt') as g:
        for line in f:
            x = line.split()
            print(x[0], file=g)

    # solve grids with full solution and pencilmarks for all techniques (some
    # are rejected by hodoku). List of techniques generated from java -jar hodoku.jar -lt
    listtech = '2sk,aic,ach,axy,axz,ar1,ar2,bug1,bf,cnl,db,dnl,d2sk,der,er,fff4,fff7,fff5,fff3,fff6,fff2,fbf4,fbf7,fmf4,fmf7,fmf5,fmf3,fmf6,fmf2,fbf5,fbf3,fbf6,fbf2,fc,fcc,fcv,fn,fnc,fnv,ff4,ff7,ff5,ff3,ff6,ff2,fh,gu,gaic,gcnl,gdnl,gnl,h2,h4,hr,h1,h3,in,bf4,kf,kf1,kf2,bf7,lc,lc1,lc2,l2,l3,mc,mc1,mc2,mf4,mf7,mf5,mf3,mf6,mf2,n2,n4,n1,n3,nl,rp,sbf4,sbf7,sbf5,sbf3,sbf6,sbf2,sc,sc1,sc2,sk,bf5,sdc,bf3,td,ts,tf,u1,u2,u3,u4,u5,u6,w,bf6,x,bf2,xyc,xy,xyz'
    comm = f'java -jar {HODOKU_JAR} /bs {TMP1} /vp /vg c:{listtech} /o {TMP2}'
    subprocess.check_output(comm)

    with open(name_out, 'wt') as file_out:
        for rec in getrecord(TMP2):
            rec = pack_pencilmarks(rec)
            res = before_after_tech(caption, rec)
            if res:
                print(res[0], res[1], '#', rec[0], file=file_out)

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


if __name__ == '__main__':
    if sys.argv[1] == 'solve':
        main2()
    elif sys.argv[1] == 'step':
        main3()
    else:
        main()
