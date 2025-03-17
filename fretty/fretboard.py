from enum import Enum
import re
import curses
import json

from fretty.notes import note_to_frequency, spot_to_note
from fretty.globals import *

EASY_TIME = 1
GOOD_TIME = 1.5
HARD_TIME = 2.5
FAIL_TIME = 5

NEW_GOOD_ATTEMPTS = 3
LEARNING_GOOD_ATTEMPTS = 3
REVIEW_GOOD_ATTEMPTS = 2

BASE_EASE_FACTOR = 1.6
MIN_EASE_FACTOR = 1
MAX_EASE_FACTOR = 3
EASE_FACTOR_DROP = 0.2
EASE_FACTOR_BUMP = 0.2

UNICODE_COLOURS = {
    "black": "\033[40m",
    "red": "\033[41m",
    "green": "\033[42m",
    "yellow": "\033[43m",
    "blue": "\033[44m",
    "magenta": "\033[45m",
    "cyan": "\033[46m",
    "white": "\033[47m",
    "reset": "\033[0m",
}

STATUS_COLOURS = {
    "unlearnable": "reset",
    "new" : "red",
    "learning" : "yellow",
    "review": "green"
}

def get_unicode_colour(status):
    if status in STATUS_COLOURS:
        return UNICODE_COLOURS[STATUS_COLOURS[status]]
    return UNICODE_COLOURS["reset"]

class Fretboard:
    def __init__(self, tuning=None, state_filepath=None, learn_sharps=False):
        if state_filepath is None:
            self.view = "first_person"
            self.learn_sharps = learn_sharps
            
            if tuning is None:
                self.tuning = ["E2", "A2", "D3", "G3", "B3", "E4"]
            else:
                self.tuning = tuning

            self.init_spots()
        else:
            self.read_state(state_filepath)


    def init_spots(self):
        self.spots = []
        for s in range(NUM_STRINGS):
            string = []
            for f in range(NUM_FRETS + 1):
                note = spot_to_note((s, f), self.tuning)
                learnable = self.learn_sharps or ('#' not in note)
                spot = FretboardSpot(s, f, note, learnable=learnable)
                string.append(spot)
            self.spots.append(string)

    def set_spots(spots_state):
        pass

    def get_spots(self):
        return self.spots
    
    def read_state(self, state_filepath):
        try:
            with open(state_filepath, 'r') as file:
                state = json.load(file)
                self.view = state.get("view", "first_person")
                self.tuning = state.get("tuning", ["E2", "A2", "D3", "G3", "B3", "E4"])
                file_spots = state.get("spots", None)
                
                self.spots = []
                for s in range(NUM_STRINGS):
                    string = []
                    for f in range(NUM_FRETS + 1):
                        note = spot_to_note((s, f), self.tuning)
                        spot = FretboardSpot(s, f, note, spot_state=file_spots[s][f])
                        string.append(spot)
                    self.spots.append(string)

        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading state file: {e}")
            self.init_spots()  # fallback to default initialization

    def write_state(self, state_filepath):
        state = {
            "view": self.view,
            "tuning": self.tuning,
            "spots": [[spot.get_state() for spot in string] for string in self.spots]
        }
        try:
            with open(state_filepath, 'w') as file:
                json.dump(state, file, indent=4)
        except IOError as e:
            print(f"Error writing state file: {e}")

    def get_spot(self, pos):
        string, fret = pos
        return self.spots[string][fret]


    def adjust_tuning(self, adjustments):
        for i in range(len(self.tuning)):
            note = self.tuning[i]
            adjustment = adjustments[i]
            note_list = list(note_to_frequency.keys())
            note_idx = note_list.index(note)
            new_note_idx = max(0, min(len(note_list), note_idx + adjustment))
            self.tuning[i] = note_list[new_note_idx]     

    def display(self, stdscr):
        stdscr.clear()

        STATUS_COLOR_MAPPING = {
            "new": curses.color_pair(1),
            "learning": curses.color_pair(2),
            "review": curses.color_pair(3),
            "unlearnable": curses.A_NORMAL,
        }

        strings = list(enumerate([re.sub(r'\d+', '', s) for s in self.tuning]))
        if self.view == "first_person":
            strings.reverse()

        frets = range(1, NUM_FRETS + 1)
        if self.view == "third_person":
            frets.reverse()

        # Print upper boundary
        # stdscr.addstr(0, 3, "-" * 47)

        line_y = 1
        for s, string in strings:
            open_spot = self.get_spot((s, 0))
            open_status = open_spot.get_status()
            open_color_pair = STATUS_COLOR_MAPPING.get(open_status, curses.color_pair(4))
            stdscr.addstr(line_y, 0, f" {string} ", open_color_pair)
            stdscr.addstr(line_y, 3, "║")

            for f in frets:
                print(print(f"f: {f}"))
                spot = self.get_spot((s, f))
                note = spot.get_note()
                print(print(f"note: {note}"))
                spot_status = spot.get_status()
                
                color_pair = STATUS_COLOR_MAPPING.get(spot_status, curses.color_pair(4))

                if f in {3, 5, 7, 9} and string == "G":
                    stdscr.addstr(line_y, 0 + f * 4, " ● ", color_pair)
                elif f == 12 and string in ["D", "B"]:
                    stdscr.addstr(line_y, 0 + f * 4, " ● ", color_pair)
                else:
                    stdscr.addstr(line_y, 0 + f * 4, "   ", color_pair)

                stdscr.addstr(line_y, 0 + f * 4 + 3, "│")  # Fret divider
            
            line_y += 1

        # Print lower boundary
        # stdscr.addstr(NUM_STRINGS + 1, 3, "-" * 47)
        stdscr.refresh()
        stdscr.getch()
        
class FretboardSpot:
    def __init__(self, string, fret, note, learnable=True, spot_state=None):
        if spot_state is None:
            self.string = string
            self.fret = fret
            self.note = note
            self.learnable = learnable
            if self.learnable:
                self.status = "new"
            else:
                self.status = "unlearnable"
            self.interval = None
            self.history = []
            self.ease_factor = BASE_EASE_FACTOR
            self.good_attempts = 0
        else:
            self.set_state(spot_state)
    
    def __str__(self):
        return str(self.get_state())

    def set_state(self, spot_state):
        self.status = spot_state['status']
        self.interval = spot_state['interval']
        self.history = spot_state['history']
        self.ease_factor = spot_state['ease_factor']
        self.good_attempts = spot_state['good_attempts']
        
    def get_state(self):
        spot_state = {}
        spot_state['status'] = self.status
        spot_state['interval'] = self.interval
        spot_state['history'] = self.history
        spot_state['ease_factor'] = self.ease_factor
        spot_state['good_attempts'] = self.good_attempts

        return spot_state
    
    def get_status(self):
        return self.status
    
    def get_note(self):
        return self.note

    def add_attempt(self, time):
        """
        Records an attempt for this spot and updates
        learning status / revision interval accordingly. 
        """
        if not self.learnable:
            return

        if time is None or time > FAIL_TIME:
            rating = "fail"
        elif time <= EASY_TIME:
            rating = "easy"
        elif time <= GOOD_TIME:
            rating = "good"
        elif time <= HARD_TIME:
            rating = "hard"
        else:
            rating = "fail"

        if self.status == "new":
            if rating == "fail":
                self.good_attempts = 0
            elif rating == "hard":
                pass
            elif rating == "good":
                self.good_attempts += 1
            elif rating == "easy":
                self.good_attempts = NEW_GOOD_ATTEMPTS

            if self.good_attempts >= NEW_GOOD_ATTEMPTS:
                self.status = "learning"
                self.good_attempts = 0

        elif self.status == "learning":
            if rating == "fail":
                self.good_attempts = 0
            elif rating == "hard":
                pass
            elif rating == "good":
                self.good_attempts += 1
            elif rating == "easy":
                self.good_attempts = LEARNING_GOOD_ATTEMPTS

            if self.good_attempts >= LEARNING_GOOD_ATTEMPTS:
                self.status = "review"
                self.good_attempts = 0

        elif self.status == "review":
            if rating == "fail":
                self.status = "review"
                self.good_attempts = LEARNING_GOOD_ATTEMPTS - 1
                self.ease_factor = min(self.ease_factor, BASE_EASE_FACTOR)
                self.interval = max(1, self.interval / self.ease_factor)
            elif rating == "hard":
                self.ease_factor = max(MIN_EASE_FACTOR, self.ease_factor - EASE_FACTOR_DROP)
                self.interval = self.interval * self.ease_factor
            elif rating == "good":
                self.interval = self.interval * self.ease_factor
            elif rating == "easy":
                self.ease_factor = min(MAX_EASE_FACTOR, self.ease_factor + EASE_FACTOR_BUMP)
                self.interval = self.interval * self.ease_factor

        self.history.append((time, rating, self.status))


