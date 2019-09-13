import sys
import os
import time
import subprocess


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

    name_generated = f'{tech}-{NAME_GENERATED}'

    # check hodoku presence
    if not os.path.isfile(HODOKU_JAR):
        print('Error: hodoku.jar not found')
        exit(1)

    # calculate number of existing solutions if any
    try:
        with open(name_out) as f:
            num_existing = len(f.readlines())
    except IOError:
        num_existing = 0

    # start hodoku in generate mode
    comm = f'java -jar {HODOKU_JAR} /s /sc {tech}:3 /o {name_generated}'
    p = subprocess.Popen(comm.split())
    time.sleep(1)

    try:
        numobtained = num_existing
        for line in tailf(name_generated):
            if 'ssts' not in line:
                # even with tech:3 some grids are generated requiring ssts techniques
                # these lines have to be filtered
                numobtained += 1
                print(numobtained)
                if numobtained >= numwanted:
                    p.terminate()
                    break

    except KeyboardInterrupt as e:
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
            if 'ssts' not in line1:
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


if __name__ == '__main__':
    if sys.argv[1] == 'solve':
        main2()
    else:
        main()
