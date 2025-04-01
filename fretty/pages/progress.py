import curses
import re
from fretty.utils import restyle_region

from fretty.pages.page import Page
from fretty.globals import *

class Progress(Page):
    def __init__(self, stdscr, fretboard):
        super().__init__(stdscr)
        self.fretboard = fretboard
        self.height, self.width = self.stdscr.getmaxyx()
        self.top_y = (self.height - FRETBOARD_CHAR_HEIGHT) // 2
        self.left_x = (self.width - FRETBOARD_CHAR_WIDTH) // 2


    def load(self):
        self.stdscr.clear()
        self.stdscr.addstr(1, 5, "<-- Backspace / Esc", curses.A_BOLD)

        strings = list(enumerate([s[:-1] for s in self.fretboard.tuning]))
        if self.fretboard.view == "first_person":
            strings.reverse()

        frets = range(1, NUM_FRETS + 1)
        if self.fretboard.view == "third_person":
            frets.reverse()

        line_y = self.top_y
        for s, string in strings:
            self.stdscr.addstr(line_y, self.left_x + 0, f" {string} ")
            self.stdscr.addstr(line_y, self.left_x + 3, "║")

            for f in frets:
                if f in {3, 5, 7, 9} and string == "G":
                    self.stdscr.addstr(line_y, self.left_x + 0 + f * 4, " ● ")
                elif f == 12 and string in ["D", "B"]:
                    self.stdscr.addstr(line_y, self.left_x + 0 + f * 4, " ● ")
                else:
                    self.stdscr.addstr(line_y, self.left_x + 0 + f * 4, "   ")

                self.stdscr.addstr(line_y, self.left_x + 0 + f * 4 + 3, "│")
            
            line_y += 1

        self.draw_progress()

        self.stdscr.refresh()

        while True:
            key = self.stdscr.getch()
            if key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                self.stdscr.clear()
                break
    
    def draw_progress(self):
        for string in self.fretboard.get_spots():
            for spot in string:
                if spot.status == "new":
                    style = curses.color_pair(3)
                elif spot.status == "learning":
                    style = curses.color_pair(4)
                elif spot.status == "review":
                    style = curses.color_pair(14)
                else:
                    style = curses.A_NORMAL

                screen_x, screen_y = self.get_spot_coords(spot)
                marker = spot.get_pos() in {(3, 3), (3, 5), (3, 7), (3, 9), (2, 12), (4, 12)}
                restyle_region(self.stdscr, screen_x, screen_y, 3, style, marker=marker)

        legend = ["NEW", "LEARNING", "REVIEW"]
        spacing = 5
        legend_len = sum([len(label) for label in legend]) + (spacing * 2) + (2 * 3)
        legend_x = (self.width - legend_len) // 2
        self.stdscr.addstr(self.top_y - 2, legend_x, ' ' + legend[0] + ' ', curses.color_pair(3))
        legend_x += len(legend[0]) + 2 + spacing
        self.stdscr.addstr(self.top_y - 2, legend_x, ' ' + legend[1] + ' ', curses.color_pair(4))
        legend_x += len(legend[1]) + 2 + spacing
        self.stdscr.addstr(self.top_y - 2, legend_x, ' ' + legend[2] + ' ', curses.color_pair(14))

        self.stdscr.refresh()
    
    def get_spot_coords(self, spot):
        string, fret = spot.get_pos()
        screen_x = self.left_x + (4 * fret)
        if self.fretboard.view == "first_person":
            screen_y = self.top_y + (NUM_STRINGS - string) - 1
        else:
            screen_y = self.top_y + string

        return screen_x, screen_y
