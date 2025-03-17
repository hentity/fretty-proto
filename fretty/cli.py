import curses

from fretty.fretboard import Fretboard, FretboardSpot
from fretty.pages.page import Page
from fretty.pages.note_to_fret import NoteToFret

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
    "Fretboard Vi": [],
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
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_RED)      # "new" → red background
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)   # "learning" → yellow background
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_GREEN)    # "review" → green background
    curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLUE)    # "review" → green background

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
            fretboard = Fretboard()
            page = NoteToFret(stdscr, fretboard)
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
    fretboard = Fretboard()
    run_cli()