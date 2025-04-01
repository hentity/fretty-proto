import curses
import os
import textwrap
from datetime import date
import sounddevice as sd

from fretty.fretboard import Fretboard, FretboardSpot
from fretty.pages.page import Page
from fretty.pages.note_to_fret import NoteToFret
from fretty.pages.progress import Progress

# Define screens
NAVIGATION = {
    "Main": ["Learn", "Progress", "Settings", "Exit"],
    "Exit": ["Exit", "Cancel"],
    "Learn": ["Note -> Fretboard", "Fretboard -> Note"],
    "Progress": [],
    "Settings": ["Tuning", "Fretboard View"],
    "Fretboard -> Note": [],
    "Note -> Fretboard": [],
    "Tuning": [],
    "Fretboard View": [],
}

PAGES = {
    "Note -> Fretboard": None,
    "Fretboard -> Note": None,
    "Progress": None,
    "Tuning": None,
    "Fretboard View": None,
}

def init_colors():
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED) 
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW) 
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_CYAN) 
    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
    curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(7, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(9, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(10, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(11, 208, curses.COLOR_BLACK) # orange
    curses.init_pair(12, curses.COLOR_BLACK, 208) # orange
    curses.init_pair(13, 165, curses.COLOR_BLACK) # purple
    curses.init_pair(14, curses.COLOR_BLACK, 165) # purple
    curses.init_pair(15, 248, curses.COLOR_BLACK) # grey
    curses.init_pair(16, curses.COLOR_BLACK, 248) # grey


def display_popup(stdscr, message):
    # Get the size of the screen
    height, width = stdscr.getmaxyx()

    # Wrap message to fit within the popup width
    max_msg_width = 40
    lines = textwrap.wrap(message, max_msg_width)
    box_width = max(len(line) for line in lines) + 4
    box_height = len(lines) + 4

    # Calculate position to center the popup
    start_y = (height - box_height) // 2
    start_x = (width - box_width) // 2

    # Save the underlying content
    backup = []
    for y in range(start_y, start_y + box_height):
        row = []
        for x in range(start_x, start_x + box_width):
            try:
                row.append((stdscr.inch(y, x)))
            except curses.error:
                row.append(ord(' '))  # Fallback in case we go out of bounds
        backup.append(row)

    # Draw popup box
    stdscr.attron(curses.A_REVERSE)
    for y in range(start_y, start_y + box_height):
        for x in range(start_x, start_x + box_width):
            stdscr.addch(y, x, ' ')
    stdscr.attroff(curses.A_REVERSE)

    # Write message
    for idx, line in enumerate(lines):
        stdscr.addstr(start_y + 1 + idx, start_x + 2, line, curses.A_REVERSE)

    # Write OK button
    ok_msg = "[ OK ]"
    ok_x = start_x + (box_width - len(ok_msg)) // 2
    stdscr.attron(curses.A_STANDOUT)
    stdscr.addstr(start_y + box_height - 2, ok_x, ok_msg, curses.A_NORMAL)
    stdscr.attroff(curses.A_STANDOUT)

    stdscr.refresh()
    stdscr.getch()

    # Restore underlying content
    for dy, row in enumerate(backup):
        for dx, ch in enumerate(row):
            stdscr.addch(start_y + dy, start_x + dx, ch)

    stdscr.refresh()

def draw_menu(stdscr, current_screen):
    curses.curs_set(0)  # Hide cursor
    stdscr.clear()
    stdscr.refresh()
    
    options = NAVIGATION[current_screen]
    selected = 0
    
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        if current_screen != "Main":
            stdscr.addstr(1, 5, "<-- Backspace / Esc", curses.A_BOLD)

        if current_screen not in PAGES:
            for i, option in enumerate(options):
                x = width // 2 - len(option) // 2
                y = height // 2 - len(options) // 2 + i
                
                if i == selected:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, x, f"{i+1}. {option}")
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, x, f"{i+1}. {option}")
        
            key = stdscr.getch()
            
            if key == curses.KEY_UP and selected > 0:
                selected -= 1
            elif key == curses.KEY_DOWN and selected < len(options) - 1:
                selected += 1
            elif key in [10, 13]:  # enter key
                return options[selected]
            elif key in [ord(str(i + 1)) for i in range(len(options))]:
                return options[int(chr(key)) - 1]
            elif current_screen != "Main" and key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                return "Back"
        else:
            key = stdscr.getch()
            if current_screen != "Main" and key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                return "Back"
        
        

def main(stdscr):
    curses.start_color()  # Initialize curses color mode
    init_colors()

    current_screen = "Main"
    screen_stack = []

    if os.path.exists("state.json"):
        fretboard = Fretboard(state_filepath="state.json")
        # fretboard.curr_date = date(2025, 3, 31)
    else:
        fretboard = Fretboard()
    
    while True:
        selected_option = draw_menu(stdscr, current_screen)
        
        if selected_option == "Back":
            if screen_stack:
                current_screen = screen_stack.pop()
            else:
                break  # exit program when going back from main
        elif selected_option == "Exit":
            break  # exit program
        elif selected_option == "Note -> Fretboard":
            if fretboard.done_for_day():
                display_popup(stdscr, "You have finished your practice for today.")
            else:
                page = NoteToFret(stdscr, fretboard)
                page.load()
        elif selected_option == "Progress":
            page = Progress(stdscr, fretboard)
            page.load()
        elif selected_option in NAVIGATION:
            screen_stack.append(current_screen)
            current_screen = selected_option
        else:
            stdscr.clear()
            stdscr.addstr(5, 5, f"(Placeholder) {selected_option} Screen. Press any key to go back.")
            stdscr.getch()

def run_cli():
    curses.wrapper(main)

if __name__ == "__main__":
    run_cli()