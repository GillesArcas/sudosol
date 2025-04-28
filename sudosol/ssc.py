"""
SSC, Simple Sudoku Companion
"""


import sys
import os
import tkinter as tk
import time
import configparser
from itertools import combinations
from collections import defaultdict

import clipboard
import customtkinter
from pywinauto.application import Application
from pywinauto.timings import Timings
from pywinauto.keyboard import send_keys
from pywinauto import mouse

import sudosol


class Options:
    def __init__(self):
        self.step = False


# -- Sudoku logic ------------------------------------------------------------


def set_singles(cells, sscells):
    for row, col, value in cells:
        row -= 1
        col -= 1
        sscells[row][col].set_focus()
        send_keys('{VK_NUMPAD%d}' % value)


def set_colors(cells, sscells):
    t0 = time.time()
    for row, col, color in cells:
        row -= 1
        col -= 1
        sscells[row][col].set_focus()
        send_keys(color)
    print(time.time() - t0)


def get_values(grid):
    values = set()
    for i in range(9):
        for j, cell in enumerate(grid.rows[i]):
            if cell.value:
                values.add((i+1, j+1, cell.value))
    return values


def solve_singles(sscells):
    grid = sudosol.Grid()
    grid.decorate = 'none'
    options = Options()

    send_keys('^c')
    sgrid = clipboard.paste()
    sudosol.load_ss_clipboard(grid, sgrid)
    hidden_singles = set()
    naked_singles = set()
    naked_singles_found = False

    while True:
        values_before = get_values(grid)
        sudosol.solve(grid, options, techniques='n1', explain=False)
        values_after = get_values(grid)
        modified1 = (values_after != values_before)
        if modified1:
            naked_singles_found = True
            naked_singles |= values_after - values_before

        values_before = get_values(grid)
        sudosol.solve(grid, options, techniques='h1', explain=False)
        values_after = get_values(grid)
        modified2 = (values_after != values_before)
        if modified2:
            hidden_singles |= values_after - values_before

        if not (modified1 or modified2):
            break

    set_singles(hidden_singles, sscells)
    if naked_singles_found:
        send_keys('{F12}')


def make_groups(strong_links):
    strong_links = {tuple(sorted(link)) for link in strong_links}

    # make groups
    groups = []
    for link in strong_links:
        start, end = link
        for group in groups:
            for link2 in group:
                if start in link2 or end in link2:
                    group.add(link)
                    break
            else:
                continue
            break
        else:
            groups.append({link})

    fusion = True
    while fusion:
        fusion = False
        for group1, group2 in combinations(groups, 2):
            cells1 = set().union(*[set(link) for link in group1])
            cells2 = set().union(*[set(link) for link in group2])
            if cells1 & cells2:
                fusion = group1, group2
                break
        if fusion:
            groups.append(group1 | group2)
            groups.remove(group1)
            groups.remove(group2)

    # divide each group into two color cells
    color_cells = []
    for group in groups:
        group2 = group.copy()
        color1 = set()
        color2 = set()
        while group2:
            group3 = set()
            for link in group2:
                start, end = link
                if not color1:
                    color1.add(start)
                    color2.add(end)
                elif start in color1:
                    color2.add(end)
                elif start in color2:
                    color1.add(end)
                elif end in color1:
                    color2.add(start)
                elif end in color2:
                    color1.add(start)
                else:
                    group3.add(link)
            group2 = group3
        color_cells.append((sorted(group), color1, color2))

    return sorted(color_cells)


def show_groups(digit, num_pair, sscells):
    grid = sudosol.Grid()
    grid.decorate = 'none'
    options = Options()

    send_keys('^c')
    sgrid = clipboard.paste()
    sudosol.load_ss_clipboard(grid, sgrid)
    _, _, strong_links = sudosol.x_links(grid, digit)

    groups = make_groups(strong_links)
    if not groups:
        send_keys('^Q')
        return 0
    else:
        cells = []
        if len(groups) == 1:
            print('#coloring = 1')
            group = list(groups)[0]
            _, color1, color2 = group
            for cell in color1:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^B'))
            for cell in color2:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^G'))
            result = 1
        else:
            pairs_of_groups = list(combinations(groups, 2))
            print('#coloring =', len(pairs_of_groups))
            num_pair = min(num_pair, len(pairs_of_groups) - 1)
            group1, group2 = pairs_of_groups[num_pair]
            _, color1, color2 = group1
            for cell in color1:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^B'))
            for cell in color2:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^G'))
            _, color1, color2 = group2
            for cell in color1:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^K'))
            for cell in color2:
                cells.append((cell.rownum + 1, cell.colnum + 1, '^M'))
            result = len(pairs_of_groups)

        send_keys('^Q')
        set_colors(cells, sscells)
        return result


# -- Commands ----------------------------------------------------------------


def get_grid_signature():
    grid = sudosol.Grid()
    grid.decorate = 'none'
    options = Options()
    send_keys('^c')
    sgrid = clipboard.paste()
    sudosol.load_ss_clipboard(grid, sgrid)
    return grid.output_s81()


def new_command(tkapp, appauto, win, sscells, radio_var):
    mode = radio_var.get()
    if mode == 1:
        new_simple_command(tkapp, win, sscells)
    elif mode == 2:
        new_hodoku_command(tkapp, win, sscells)
    elif mode == 3:
        new_collection_command(tkapp, win, sscells)
    elif mode == 4:
        filename = tk.filedialog.askopenfilename()
        print(filename)
        set_ini_collection(filename)
        new_collection_command(tkapp, win, sscells)
    else:
        assert 0


def new_simple_command(tkapp, win, sscells):
    s = get_grid_signature()
    win.set_focus()
    send_keys('^n')
    static = win['Are you sure you want to quit this puzzle?']
    static.wait_not('visible', timeout=1_000_000)
    if get_grid_signature() != s:
        solve_singles(sscells)
        tkapp.set_digit_button('1')
        win.set_focus()
        send_keys('^{VK_NUMPAD0}')
        send_keys('^{VK_NUMPAD1}')
        tkapp.wheel_mode = 'wheel_digit'


def new_collection_command(tkapp, win, sscells):
    win.set_focus()
    s = get_grid_signature()
    data = get_grid_from_collection(increment=True)
    if data is None:
        return
    grid, collection_name, index, num_grids = data
    clipboard.copy(grid)
    send_keys('^V')
    time.sleep(1)
    static = win['Are you sure you want to quit this puzzle?']
    static.wait_not('visible', timeout=1_000_000)
    s2 = get_grid_signature()
    if s2 != s:
        tkapp.update_collection_label(collection_name, index, num_grids)
        solve_singles(sscells)
        tkapp.set_digit_button('1')
        win.set_focus()
        send_keys('^{VK_NUMPAD0}')
        send_keys('^{VK_NUMPAD1}')
        tkapp.wheel_mode = 'wheel_digit'


def new_hodoku_command(tkapp, win, sscells):
    win.set_focus()
    s = get_grid_signature()
    app = Application(backend="uia").start(r'G:\Sudoku\.Applications\HoDoKu\hodoku.exe')
    time.sleep(3)
    # hodoku = app.window(title_re='.*HoDoKu.*')
    appcon = app.connect(title_re='HoDoKu.*', found_index=0)
    winh = appcon.window(title_re='.*HoDoKu.*')
    # winh.print_control_identifiers()
    # hodoku = winh.child_window(title_re=".*HoDoKu.*", top_level_only=True)
    winh.set_focus()
    time.sleep(1)
    send_keys('^N')     # new
    send_keys('^G')     # copy givens
    send_keys('%X')     # close
    win.set_focus()
    send_keys('^V')
    time.sleep(1)
    static = win['Are you sure you want to quit this puzzle?']
    static.wait_not('visible', timeout=1_000_000)
    s2 = get_grid_signature()
    if s2 != s:
        solve_singles(sscells)
        win.set_focus()
        tkapp.set_digit_button('1')
        send_keys('^{VK_NUMPAD0}')
        send_keys('^{VK_NUMPAD1}')
        tkapp.wheel_mode = 'wheel_digit'


def solve_singles_command(tkapp, win, sscells):
    win.set_focus()
    solve_singles(sscells)
    send_keys('^Q')
    send_keys('^{VK_NUMPAD0}')
    send_keys('^{VK_NUMPAD%d}' % tkapp.current_digit)


def digit_mode_settings(tkapp):
    if tkapp.wheel_mode == 'wheel_digit':
        tkapp.current_digit = (tkapp.current_digit + 1) % 10
    else:
        pass
    tkapp.wheel_mode = 'wheel_digit'
    tkapp.current_color = 0
    tkapp.set_coloring_label(hide=True)


def color_mode_settings(tkapp):
    tkapp.wheel_mode = 'wheel_group'
    tkapp.current_color = 0


def digit_mode_command(tkapp, win):
    digit_mode_settings(tkapp)
    tkapp.on_select_digit(str(tkapp.current_digit))
    #win.set_focus()
    #send_keys('^Q')
    #send_keys('^{VK_NUMPAD0}')
    #send_keys('^{VK_NUMPAD%d}' % tkapp.current_digit)


def coloring_mode_command(tkapp, win, sscells):
    if tkapp.wheel_mode != 'wheel_group':
        color_mode_settings(tkapp)
        win.set_focus()
        tkapp.num_groups = show_groups(tkapp.current_digit, 0, sscells)
        tkapp.set_coloring_label()
    else:
        tkapp.current_color = (tkapp.current_color + 1) % tkapp.num_groups
        win.set_focus()
        show_groups(tkapp.current_digit, tkapp.current_color, sscells)
        tkapp.set_coloring_label()


def hodoku_hint_command(win):
    win.set_focus()
    send_keys('^c')     # copy Simple Sudoku grid into clipboard
    app = Application(backend="uia").start(r'G:\Sudoku\.Applications\HoDoKu\hodoku.exe')
    time.sleep(3)
    # appcon = app.connect(title_re='HoDoKu.*', found_index=0)
    winh = app.window(title_re='.*HoDoKu.*')
    winh.set_focus()
    time.sleep(1)
    send_keys('^v')     # paste grid into HoDoKu
    send_keys('%{F12}')


def quit_command(tkapp, win):
    try:
        win.set_focus()
        send_keys('%{F4}')
    except:
        # in case simple sudoku window has been closed from itself
        pass
    save_window_position(tkapp)
    exit(0)


# -- Automation --------------------------------------------------------------


def start_simple():
    Timings.fast()
    Timings.window_find_timeout = 1

    # backend = uia|win32
    t0 = time.time()
    app = Application(backend="uia").start(r"c:\Program Files (x86)\Simple Sudoku\simplesudoku.exe")
    win = app.window(title_re='.*Simple Sudoku.*')
    print(time.time() - t0)

    sscells = get_ss_cells(win)

    solve_singles(sscells)
    win.set_focus()
    send_keys('^{VK_NUMPAD1}')
    return app, win, sscells


def get_ss_cells(win):
    """
    Return array 9x9 of digit cells in Simple Sudoku.
    """
    t0 = time.time()
    cells = []
    for child in win.children():
        if child.class_name() == 'TCell':
            rect = child.rectangle()
            cells.append((rect.top, rect.left, child))

    sscells = [[None for j in range(9)] for i in range(9)]
    for n, (_, _, cell) in enumerate(sorted(cells)):
        sscells[n // 9][n % 9] = cell
    print(time.time() - t0)
    return sscells


# -- Configuration file ------------------------------------------------------


def load_config():
    """
    Ensure config file exists and has required sections.
    Return configparser.
    """
    config_filename = 'ssc.ini'
    config = configparser.ConfigParser(delimiters='=')

    if not os.path.exists(config_filename):
        with open(config_filename, 'wt') as configfile:
            config.write(configfile)

    config.read(config_filename)
    if not config.has_section('Window'):
        config.add_section('Window')
    if not config.has_section('Collections'):
        config.add_section('Collections')

    return config


def save_config(config):
    config_filename = 'ssc.ini'
    with open(config_filename, 'wt') as configfile:
        config.write(configfile)


def save_window_position(app):
    config = load_config()
    config.set('Window', 'Position', f'{app.winfo_x()},{app.winfo_y()}')
    save_config(config)


def load_window_position(app):
    config = load_config()

    position = config.get('Window', 'Position', fallback=None)
    if position is None:
        return
    else:
        x, y = [int(_) for _ in position.split(',')]
        app.geometry(f"200x380+{x}+{y}")


def get_grid_from_collection(increment):
    config = load_config()
    if config.get('Collections', 'Current', fallback=None) is None:
        return None

    current_collection = config.get('Collections', 'Current')
    index = config.getint('Collections', current_collection)

    with open(current_collection) as f:
        grids = f.readlines()
        grid = grids[index].strip().split('#')[0]
        if increment:
            index = (index + 1) % len(grids)

    config.set('Collections', current_collection, str(index))
    save_config(config)

    return grid, current_collection, index, len(grids)


def set_ini_collection(filename):
    config = load_config()
    config.set('Collections', 'Current', filename)

    if config.get('Collections', filename, fallback=None) is None:
        config.set('Collections', filename, '0')

    save_config(config)


# -- GUI root ----------------------------------------------------------------


DX = 20


class App(customtkinter.CTk):
    def __init__(self, parent=None):
        customtkinter.CTk.__init__(self, parent)
        self.wheel_mode = 'wheel_digit'
        self.current_digit = 1
        self.current_color = 0

    def initialize(self, appauto, win, sscells):
        self.appauto = appauto
        self.win = win
        load_window_position(self)
        self.resizable(False, False)
        self.iconbitmap("ss.ico")
        self.title('SSC')

        button = customtkinter.CTkButton(master=self, text="New",
            command=lambda: new_command(self, appauto, win, sscells, self.radio_var))
        button.place(x=DX, y=10)

        self.radio_var = tk.IntVar(value=1)

        button = customtkinter.CTkRadioButton(master=self, text="Simple Sudoku",
           variable= self.radio_var, value=1, width=150)
        button.place(x=DX, y=40)

        button = customtkinter.CTkRadioButton(master=self, text="HoDoKu",
           variable= self.radio_var, value=2, width=150)
        button.place(x=DX, y=65)

        button = customtkinter.CTkRadioButton(master=self, text="Current collection",
           variable= self.radio_var, value=3, width=150)
        button.place(x=DX, y=90)

        self.text_var = tk.StringVar(value='None')
        label = customtkinter.CTkLabel(master=self, textvariable=self.text_var,
                                              width=150, height=8)
        label.place(x=DX - 5, y=110)

        button = customtkinter.CTkRadioButton(master=self, text="New collection",
           variable= self.radio_var, value=4, width=150)
        button.place(x=DX, y=130)

        button = customtkinter.CTkButton(master=self, text="Solve singles",
            command=lambda: solve_singles_command(self, win, sscells))
        button.place(x=DX, y=160)

        button = customtkinter.CTkButton(master=self, text="Digits",
            command=lambda: digit_mode_command(self, win))
        button.place(x=DX, y=190)

        self.segmented_button1 = customtkinter.CTkSegmentedButton(master=self,
                                                         width=140,
                                                         font=('Arial', 15),
                                                         dynamic_resizing=False,
                                                         values=list('01234:'),
                                                         command=self.on_select_digit)
        self.segmented_button1.place(x=DX, y=220)
        self.segmented_button1.set('1')

        self.segmented_button2 = customtkinter.CTkSegmentedButton(master=self,
                                                         width=140,
                                                         font=('Arial', 15),
                                                         dynamic_resizing=False,
                                                         values=list('56789>'),
                                                         command=self.on_select_digit)
        self.segmented_button2.place(x=DX, y=250)

        self.bt_coloring = customtkinter.CTkButton(master=self, text="Colors",
            command=lambda: coloring_mode_command(self, win, sscells))
        self.bt_coloring.place(x=DX, y=280)

        button = customtkinter.CTkButton(master=self, text="HoDoKu hint",
            command=lambda: hodoku_hint_command(win))
        button.place(x=DX, y=310)

        button = customtkinter.CTkButton(master=self, text="Quit",
            command=lambda: quit_command(self, win))
        button.place(x=DX, y=340)

        self.bind("<MouseWheel>", lambda event: self.on_wheel_event(event, win, appauto, sscells))
        self.bind("<Unmap>", self.on_unmap)
        self.bind("<Map>", self.on_map)
        self.protocol("WM_DELETE_WINDOW", lambda: quit_command(self, win))

        data = get_grid_from_collection(increment=False)
        if data:
            _, name, index, size = data
            self.update_collection_label(name, index, size)

    def on_unmap(self, event):
        return
        self.win.minimize()

    def on_map(self, event):
        return
        self.win.maximize()

    def update_collection_label(self, name, index, size):
        self.text_var.set(f'{os.path.basename(name)} {index}/{size}')

    def set_digit_button(self, value: str):
        if value in list('01234:'):
            self.segmented_button1.set(value)
            self.segmented_button2.set('')
        if value in list('56789>'):
            self.segmented_button1.set('')
            self.segmented_button2.set(value)
        if value in list('0123456789'):
            self.current_digit = int(value)

    def on_select_digit(self, value):
        print('CTkSegmentedButton', value, 'current', self.current_digit)
        digit_mode_settings(self)
        self.set_digit_button(value)
        self.win.set_focus()
        send_keys('^Q')
        if value in list('0123456789'):
            send_keys('^{VK_NUMPAD0}')
            send_keys('^{VK_NUMPAD%d}' % int(value))
        elif value == ':':
            send_keys('^Y')
        elif value == '>':
            self.current_digit = (self.current_digit + 1) % 10
            print('new current_digit', self.current_digit)
            self.on_select_digit(str(self.current_digit))
        else:
            assert 0, value

    def on_wheel_digits_event(self, event):
        print('wheel delta', event.delta)
        if event.delta > 0:
            self.current_digit = (self.current_digit - 1) % 10
        else:
            self.current_digit = (self.current_digit + 1) % 10
        self.on_select_digit(str(self.current_digit))

    def on_wheel_colors_event(self, event, win, app, sscells):
        if event.delta > 0:
            self.current_color = (self.current_color - 1) % self.num_groups
        else:
            self.current_color = (self.current_color + 1) % self.num_groups
        win.set_focus()
        show_groups(self.current_digit, self.current_color, sscells)
        self.set_coloring_label()

    def on_wheel_event(self, event, win, app, sscells):
        if self.wheel_mode == 'wheel_digit':
            self.on_wheel_digits_event(event)
        else:
            self.on_wheel_colors_event(event, win, app, sscells)

    def set_coloring_label(self, hide: bool = False):
        if hide:
            self.bt_coloring.configure(text='Colors')
        else:
            self.bt_coloring.configure(text=f'Colors ({self.current_color + 1} / {self.num_groups})')


# -- Main --------------------------------------------------------------------


def mainw():
    customtkinter.set_appearance_mode("System")  # Modes: system (default), light, dark
    customtkinter.set_default_color_theme("blue")  # Themes: blue (default), dark-blue, green

    app = App()
    appauto, win, sscells = start_simple()
    app.initialize(appauto, win, sscells)
    app.mainloop()


def main(win, app, sscells):
    # appconnect = app.connect(title_re='.*Simple Sudoku.*')
    # app_dlg = appconnect.top_window_()
    # app.SimpleSudokuUntitled.print_control_identifiers()
    # app.SimpleSudokuUntitled.Pane1.click()
    # app.Dialog.Pane1.click()
    # app.SimpleSudokuUntitled.Pane1.click()
    # app.SimpleSudokuUntitled.Pane81.set_focus()  --> ok pour 1ere case mais long
    # app.SimpleSudokuUntitled.Pane81.set_focus()

    while True:
        x = input('? ')
        x = short_to_full(x)

        if x == 'singles':
            win.set_focus()
            solve_singles(sscells)
        elif x == 'new':
            win.set_focus()
            send_keys('^n')
            solve_singles(sscells)
        elif x == 'quit':
            win.set_focus()
            send_keys('%{F4}')
            break


def short_to_full(short):
    for x in ('singles', 'new', 'quit'):
        if x.startswith(short):
            return x


if __name__ == '__main__':
    # mainw(None, None, None)
    # exit(1)
    if len(sys.argv) == 1:
        sys.argv.append('win')

    # Timings.fast()
    # Timings.window_find_timeout = 1
    #
    # # backend = uia|win32
    # t0 = time.time()
    # app = Application(backend="uia").start(r"c:\Program Files (x86)\Simple Sudoku\simplesudoku.exe")
    # win = app.window(title_re='.*Simple Sudoku.*')
    # print(time.time() - t0)
    #
    # sscells = get_ss_cells(win)
    #
    # solve_singles(sscells)
    # win.set_focus()
    # send_keys('^{VK_NUMPAD1}')

    if sys.argv[1] == 'win':
        mainw()
    elif sys.argv[1] == 'cli':
        main(win, app, sscells)
    else:
        pass
