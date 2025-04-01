from enum import Enum
import re
import curses
import json
import ast
from datetime import date, timedelta

from fretty.notes import note_to_frequency, spot_to_note
from fretty.globals import *

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
            
            self.spots = None
            self.init_spots()

            self.review_date_to_spots = {}
            self.spot_to_review_date = {}

            self.last_review_date = None

            self.new = True
        else:
            self.read_state(state_filepath)
        
        self.curr_date = date.today()


    def init_spots(self):
        self.spots = []
        for s in range(NUM_STRINGS):
            string = []
            for f in range(1, NUM_FRETS + 1):
                note = spot_to_note((s, f), self.tuning)
                learnable = self.learn_sharps or ('#' not in note)
                spot = FretboardSpot(self, s, f, note, learnable=learnable)
                string.append(spot)
            self.spots.append(string)

    def get_spot(self, pos):
        s, f = pos
        return self.spots[s][f-1]
    
    def set_spots(self, spots_state):
        pass

    def get_curr_date(self):
        return self.curr_date
    
    def get_last_review_date(self):
        return self.last_review_date
    
    def get_reviews_today(self):
        if self.curr_date in self.review_date_to_spots:
            return self.review_date_to_spots[self.curr_date]
        else:
            return []
        
    def push_back_reviews(self):
        if not self.review_date_to_spots:
            return
        
        earliest_review = min(
            date for date, spots in self.review_date_to_spots.items() if spots
        )
        shift = (self.curr_date - earliest_review).days
        
        if shift > 0:
            new_review_date_to_spots = {}
            for old_date, spots in self.review_date_to_spots.items():
                new_date = old_date + timedelta(days=shift)
                new_review_date_to_spots[new_date] = spots
                for spot in spots:
                    self.spot_to_review_date[spot] = new_date
            self.review_date_to_spots = new_review_date_to_spots
            
    
    def add_review(self, spot, days):
        review_date = self.curr_date + timedelta(days=days)
        while True:
            if review_date in self.review_date_to_spots:
                if len(self.review_date_to_spots[review_date]) < MAX_DAILY_REVIEWS:
                    self.review_date_to_spots[review_date].append(spot)
                    self.spot_to_review_date[spot] = review_date
                    break
                else:
                    review_date += timedelta(days=1)
            else:
                self.review_date_to_spots[review_date] = [spot]
                self.spot_to_review_date[spot] = review_date
                break
    
    def remove_review(self, spot):
        review_date = None
        if spot in self.spot_to_review_date:
            review_date = self.spot_to_review_date[spot]
            self.review_date_to_spots[review_date].remove(spot)
            del self.spot_to_review_date[spot]
            if len(self.review_date_to_spots[review_date]) == 0:
                del self.review_date_to_spots[review_date]

    def get_spots(self, status=None):
        if status is None:
            return self.spots
        else:
            spots = []
            for s in range(NUM_STRINGS):
                state_spots = [spot for spot in self.spots[s] if spot.get_status() == status]
                spots += state_spots
            return spots
            
    def read_state(self, state_filepath):
        try:
            with open(state_filepath, 'r') as file:
                state = json.load(file)
                self.new = state.get("new", False)
                self.view = state.get("view", "first_person")
                self.tuning = state.get("tuning", ["E2", "A2", "D3", "G3", "B3", "E4"])
                last_review_date_str = state.get("last_review_date", None)
                if last_review_date_str is not None:
                    self.last_review_date = date.fromisoformat(state["last_review_date"])
                else:
                    self.last_review_date = None

                file_spots = state.get("spots", None)
                
                self.spots = []
                for s in range(NUM_STRINGS):
                    string = []
                    for f in range(1, NUM_FRETS + 1):
                        note = spot_to_note((s, f), self.tuning)
                        spot = FretboardSpot(self, s, f, note, spot_state=file_spots[s][f-1])
                        spot.good_attempts = 0
                        string.append(spot)
                    self.spots.append(string)

                self.review_date_to_spots = {
                    date.fromisoformat(k): [self.get_spot(ast.literal_eval(pos)) for pos in v] for k, v in state.get("review_date_to_spots", {}).items()
                }
                self.spot_to_review_date = {
                    self.get_spot(ast.literal_eval(k)): date.fromisoformat(v) for k, v in state.get("spot_to_review_date", {}).items()
                }



        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading state file: {e}")
            self.init_spots()  # fallback to default initialization

    def write_state(self, state_filepath):
        review_date_to_spots_serialized = {
            d.isoformat(): [str(spot.get_pos()) for spot in v] for d, v in self.review_date_to_spots.items()
        }

        spot_to_review_date_serialized = {
            str(k.get_pos()): v.isoformat() for k, v in self.spot_to_review_date.items()
        }
        
        state = {
            "new": self.new,
            "view": self.view,
            "tuning": self.tuning,
            "last_review_date": self.curr_date.isoformat(),
            "review_date_to_spots": review_date_to_spots_serialized,
            "spot_to_review_date": spot_to_review_date_serialized,
            "spots": [[spot.get_state() for spot in string] for string in self.spots]
        }
        try:
            with open(state_filepath, 'w') as file:
                json.dump(state, file, indent=4)
        except IOError as e:
            print(f"Error writing state file: {e}")

    def done_for_day(self):
        if self.new:
            return False

        if len(self.get_reviews_today()) > 0 or self.last_review_date != self.curr_date:
            return False
        
        for string in self.spots:
            for spot in string:
                if spot.status in {"new", "learning"}:
                    return False

        return True
    
    def get_spot(self, pos):
        string, fret = pos
        return self.spots[string][fret-1]


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
            "new": curses.color_pair(9),
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

        stdscr.refresh()
        stdscr.getch()
        
class FretboardSpot:
    def __init__(self, fretboard, string, fret, note, learnable=True, spot_state=None):
        self.fretboard = fretboard
        self.string = string
        self.fret = fret
        self.note = note
        self.learnable = learnable
        
        if spot_state is None:
            if self.learnable:
                self.status = "unseen"
            else:
                self.status = "unlearnable"
            self.interval = 1
            self.history = []
            self.ease_factor = BASE_EASE_FACTOR
            self.good_attempts = 0
        else:
            self.set_state(spot_state)
    
    def __str__(self):
        return str(self.get_state())
    
    def __hash__(self):
        return hash((self.string, self.fret))
    
    def __eq__(self, other):
        return (self.string, self.fret) == (other.string, other.fret)

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
    
    def get_pos(self):
        return self.string, self.fret

    def reset(self):
        self.interval = 1
        self.ease_factor = BASE_EASE_FACTOR
        self.good_attempts = 0
        self.status = "unseen"
    
    def add_attempt(self, time):
        """
        Records an attempt for this spot and updates
        learning status / revision interval accordingly. 
        """
        if not self.learnable:
            return None

        if time is None or time > FAIL_TIME:
            rating = "fail"
        elif time <= EASY_TIME:
            rating = "easy"
        elif time <= GOOD_TIME:
            rating = "good"
        elif time < FAIL_TIME:
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
                self.fretboard.add_review(self, self.interval)
                self.good_attempts = 0

        elif self.status == "review":
            self.fretboard.remove_review(self)
            if rating == "fail":
                self.status = "learning"
                self.good_attempts = LEARNING_GOOD_ATTEMPTS - 1
                self.ease_factor = min(self.ease_factor, BASE_EASE_FACTOR)
                self.interval = max(1, self.interval / self.ease_factor)
            elif rating == "hard":
                self.ease_factor = max(MIN_EASE_FACTOR, self.ease_factor - EASE_FACTOR_DROP)
                self.interval = self.interval * self.ease_factor
                self.fretboard.add_review(self, self.interval)
            elif rating == "good":
                self.interval = self.interval * self.ease_factor
                self.fretboard.add_review(self, self.interval)
            elif rating == "easy":
                self.ease_factor = min(MAX_EASE_FACTOR, self.ease_factor + EASE_FACTOR_BUMP)
                self.interval = self.interval * self.ease_factor
                self.fretboard.add_review(self, self.interval)

        self.history.append((time, rating, self.status))


