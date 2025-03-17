import re
import curses
from art import text2art

from fretty.pages.page import Page
from fretty.globals import *

class NoteToFret(Page):
    def __init__(self, stdscr, fretboard):
        super().__init__(stdscr)
        self.display = None
        self.fretboard = fretboard
        self.name = "Note -> Fretboard"
        self.state = {}
        self.key = None

    def load(self):
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        top_y = (height - FRETBOARD_CHAR_HEIGHT) // 2
        left_x = (width - (FRETBOARD_CHAR_WIDTH + NOTE_WIDTH + SPACING)) // 2

        # ascii_art = text2art("A#", font="varsity")
        ascii_art = text2art("C", font="tarty1")
        lines = ascii_art.split("\n")

        for i, line in enumerate(lines):
            self.stdscr.addstr(i + top_y - 1, left_x + FRETBOARD_CHAR_WIDTH + 4, line)

        self.stdscr.refresh()
        # self.stdscr.clear()

        strings = list(enumerate([re.sub(r'\d+', '', s) for s in self.fretboard.tuning]))
        if self.fretboard.view == "first_person":
            strings.reverse()

        frets = range(1, NUM_FRETS + 1)
        if self.fretboard.view == "third_person":
            frets.reverse()

        line_y = top_y
        for s, string in strings:
            if s == 2:
                style = curses.A_BOLD | curses.color_pair(4)
            else:
                style = curses.A_NORMAL
            self.stdscr.addstr(line_y, left_x + 0, f" {string} ", style)
            self.stdscr.addstr(line_y, left_x + 3, "║", style)

            for f in frets:
                if f in {3, 5, 7, 9} and string == "G":
                    self.stdscr.addstr(line_y, left_x + 0 + f * 4, " ● ", style)
                elif f == 12 and string in ["D", "B"]:
                    self.stdscr.addstr(line_y, left_x + 0 + f * 4, " ● ", style)
                else:
                    self.stdscr.addstr(line_y, left_x + 0 + f * 4, "   ", style)

                self.stdscr.addstr(line_y, left_x + 0 + f * 4 + 3, "│", style)
            
            line_y += 1

        self.draw()
        self.start()

    def start(self):
        while True:
            self.stdscr.addstr(1, 5, "<-- Backspace / Esc", curses.A_BOLD)
            if self.key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                self.stop()
                break
                
            self.key = self.stdscr.getch()

    def draw(self):
        self.stdscr.refresh()

    def stop(self):
        self.stdscr.clear()