import curses

def restyle_region(stdscr, x, y, width, style, marker=False):
    if marker:
        stdscr.addstr(y, x, " ● ", style)
    else:
        for i in range(width):
            ch = stdscr.inch(y, x + i)
            char = chr(ch & curses.A_CHARTEXT)
            stdscr.addch(y, x + i, char, style)

