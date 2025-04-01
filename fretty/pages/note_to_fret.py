import re
import curses
from art import text2art
import time
import threading
import time
import queue
import random

from fretty.pages.page import Page
from fretty.globals import *
from fretty.fretboard import EASY_TIME, GOOD_TIME, FAIL_TIME, MAX_DAILY_REVIEWS
from fretty.audio import listen
from fretty.utils import restyle_region

LISTEN_INTERVAL = 0.1   # How often to start a new thread
SEGMENT_DURATION = 0.5

RANDOM_POP_LEN = 2

STRING_MESSAGES = ["1ST STRING", "2ND STRING", "3RD STRING", "4TH STRING", "5TH STRING", "6TH STRING"]

class NoteToFret(Page):
    def __init__(self, stdscr, fretboard, time_limit=None):
        super().__init__(stdscr)
        self.display = None
        self.fretboard = fretboard
        self.name = "Note -> Fretboard"
        self.state = {}
        self.key = None
        self.height, self.width = self.stdscr.getmaxyx()
        self.top_y = (self.height - FRETBOARD_CHAR_HEIGHT) // 2
        self.left_x = (self.width - FRETBOARD_CHAR_WIDTH) // 2
        self.timer = None
        self.lesson = []
        self.time_limit = time_limit
        

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

        self.stdscr.refresh()
        self.start()

    def create_lesson(self):
        self.fretboard.push_back_reviews()
        reviews = self.fretboard.get_reviews_today()
        self.lesson += reviews

        learning_space = MAX_DAILY_REVIEWS - len(self.lesson)
        learning_spots = self.fretboard.get_spots(status="learning")[:learning_space]
        self.lesson += learning_spots
        
        learning_space = MAX_DAILY_REVIEWS - len(self.lesson)
        new_spots = self.fretboard.get_spots(status="new")[:learning_space]
        self.lesson += new_spots

        learning_space = MAX_DAILY_REVIEWS - len(self.lesson)
        unseen_spots = self.fretboard.get_spots(status="unseen")[:learning_space]
        self.lesson += unseen_spots

        if unseen_spots:
            for unseen_spot in unseen_spots:
                unseen_spot.status = "new"

    def end_lesson(self):
        self.fretboard.write_state("state.json")

        # save progress


        # end of lesson UI
        # self.fretboard.display(self.stdscr)

        self.stdscr.clear()
    
    def show_progress(self):
        pass
    
    def draw_time_msg(self, attempt_time, spot):
        if attempt_time is None:
            msg = "FAIL"
            style = curses.color_pair(1)
        elif attempt_time <= EASY_TIME:
            msg = "EASY!"
            style = curses.color_pair(4)
        elif attempt_time <= GOOD_TIME:
            msg = "GOOD"
            style = curses.color_pair(3)
        else:
            msg = "HARD"
            style = curses.color_pair(2)

        screen_x, screen_y = self.get_spot_coords(spot)

        msg = ' ' + msg + ' '
        msg_x = (self.width - len(msg)) // 2
        self.stdscr.addstr(self.top_y + 8, msg_x, msg, style)
        restyle_region(self.stdscr, screen_x, screen_y, 3, style)
        self.stdscr.refresh()
        time.sleep(0.4)
        restyle_region(self.stdscr, screen_x, screen_y, 3, curses.color_pair(9))
        self.stdscr.refresh()
        time.sleep(0.3)
        restyle_region(self.stdscr, screen_x, screen_y, 3, style)
        self.stdscr.refresh()
        time.sleep(0.4)
        self.stdscr.addstr(self.top_y + 8, 0, " " * self.width)
        restyle_region(self.stdscr, screen_x, screen_y, 3, curses.color_pair(9))
        self.stdscr.refresh()
    
    def draw_spot_practice(self, spot):
        note = spot.get_note()[:-1]
        note_art = text2art(note, font="tarty1")
        lines = note_art.split("\n")
        note_art_width = max([len(line) for line in lines])
        self.stdscr.addstr(self.top_y + 8, 0, " " * self.width)


        note_x = self.left_x - (note_art_width + 7)
        for i, line in enumerate(lines):
            self.stdscr.addstr(i + self.top_y - 1, note_x, line)
        
        _, string_y = self.get_spot_coords(spot)
        for y in range(self.top_y, self.top_y + NUM_STRINGS + 1):
            if y == string_y:
                self.stdscr.addstr(y, self.left_x - 4, "-->", curses.A_BOLD)
                self.stdscr.addstr(y, self.left_x + FRETBOARD_CHAR_WIDTH + 1, "<--", curses.A_BOLD)
            else:
                self.stdscr.addstr(y, self.left_x - 4, "   ")
                self.stdscr.addstr(y, self.left_x + FRETBOARD_CHAR_WIDTH + 1, "   ")

        string_message = ' ' + STRING_MESSAGES[spot.string] + ' '
        string_message_x = note_x + (note_art_width // 2) - (len(string_message) // 2)
        self.stdscr.addstr(self.top_y - 2, string_message_x, string_message, curses.A_BOLD)

        self.stdscr.refresh()

    def draw_spot_progress(self, spot, after_practice=False):
        self.stdscr.addstr(self.top_y - 4, 0, " "*self.width)
        if spot.status == 'review':
            if after_practice:
                review_date = spot.fretboard.spot_to_review_date[spot]
                curr_date = spot.fretboard.get_curr_date()
                review_days = (review_date - curr_date).days
                if review_days == 1:
                    review_msg = f"NEXT REVIEW: TOMORROW"
                else:
                    review_msg = f"NEXT REVIEW IN {review_days} DAYS"
            else:
                review_msg = ""
            review_msg_x = (self.width - len(review_msg)) // 2
            self.stdscr.addstr(self.top_y - 4, review_msg_x, review_msg, curses.color_pair(9))
            self.stdscr.refresh()
        
        bar_size = 12
        labels = [" NEW ", " LEARNING ", " REVIEW "]
        total_size = (sum([len(label) for label in labels]) + (bar_size + 2) * 2) + 4
        bar_left_x = (self.width - total_size) // 2
        prog_symbol = "■" # █ ■
        not_prog_symbol = "-"
        
        status_style = curses.color_pair(16)
        if spot.status == "new":
            status_style = curses.color_pair(3)
        self.stdscr.addstr(self.top_y - 2, bar_left_x, f"{labels[0]}", status_style)
        self.stdscr.addstr(self.top_y - 2, bar_left_x + len(labels[0]), f" ")

        bar_left_x += len(labels[0]) + 1
        if spot.status == 'new':
            new_frac = spot.good_attempts / NEW_GOOD_ATTEMPTS
            style = curses.color_pair(9)
            self.stdscr.addstr(self.top_y - 2, bar_left_x, "|", style)
            for i in range(bar_size):
                bar_frac = (i + 1) / bar_size
                if bar_frac <= new_frac:
                    symbol = prog_symbol
                else:
                    symbol = not_prog_symbol
                self.stdscr.addstr(self.top_y - 2, bar_left_x + i + 1, symbol, style)
            self.stdscr.addstr(self.top_y - 2, bar_left_x + bar_size + 1, "|", style)
        else:
            style = curses.color_pair(9)
            self.stdscr.addstr(self.top_y - 2, bar_left_x, "|", style)
            for i in range(bar_size):
                symbol = prog_symbol
                self.stdscr.addstr(self.top_y - 2, bar_left_x + i + 1, symbol, style)
            self.stdscr.addstr(self.top_y - 2, bar_left_x + bar_size + 1, "|", style)
        
        bar_left_x += bar_size + 2
        status_style = curses.color_pair(16)
        if spot.status == "learning":
            status_style = curses.color_pair(4)
        self.stdscr.addstr(self.top_y - 2, bar_left_x, f" ")
        self.stdscr.addstr(self.top_y - 2, bar_left_x + 1, f"{labels[1]}", status_style)
        self.stdscr.addstr(self.top_y - 2, bar_left_x + len(labels[1]) + 1, f" ")
        
        bar_left_x += len(labels[1]) + 2
        if spot.status == 'learning':
            learning_frac = spot.good_attempts / LEARNING_GOOD_ATTEMPTS
            style = curses.color_pair(9)
            self.stdscr.addstr(self.top_y - 2, bar_left_x, "|", style)
            for i in range(bar_size):
                bar_frac = (i + 1) / bar_size
                if bar_frac <= learning_frac:
                    symbol = prog_symbol
                else:
                    symbol = not_prog_symbol
                self.stdscr.addstr(self.top_y - 2, bar_left_x + i + 1, symbol, style)
            self.stdscr.addstr(self.top_y - 2, bar_left_x + bar_size + 1, "|", style)
        elif spot.status == 'review':
            style = curses.color_pair(9)
            self.stdscr.addstr(self.top_y - 2, bar_left_x, "|", style)
            for i in range(bar_size):
                symbol = prog_symbol
                self.stdscr.addstr(self.top_y - 2, bar_left_x + i + 1, symbol, style)
            self.stdscr.addstr(self.top_y - 2, bar_left_x + bar_size + 1, "|", style)
        else:
            style = curses.color_pair(9)
            self.stdscr.addstr(self.top_y - 2, bar_left_x, "|", style)
            for i in range(bar_size):
                symbol = not_prog_symbol
                self.stdscr.addstr(self.top_y - 2, bar_left_x + i + 1, symbol, style)
            self.stdscr.addstr(self.top_y - 2, bar_left_x + bar_size + 1, "|", style)
        
        bar_left_x += bar_size + 2
        status_style = curses.color_pair(16)
        if spot.status == "review":
            status_style = curses.color_pair(14)
        self.stdscr.addstr(self.top_y - 2, bar_left_x, f" ")
        self.stdscr.addstr(self.top_y - 2, bar_left_x + 1, f"{labels[2]}", status_style)

        self.stdscr.refresh()
    
    def start(self):
        self.fretboard.new = False
        self.create_lesson()
        start = time.time()
        now = time.time()
        while self.lesson:
            if (self.time_limit is not None) and ((now - start) >= self.time_limit):
                break
            pop_i = random.randint(0, min(RANDOM_POP_LEN - 1, len(self.lesson) - 1))
            curr_spot = self.lesson.pop(pop_i)
            curr_note = curr_spot.get_note()
            self.draw_spot_practice(curr_spot)
            self.draw_spot_progress(curr_spot)
            attempt_time = self.listen_for_note(curr_note)
            curr_spot.add_attempt(attempt_time)
            self.draw_time_msg(attempt_time, curr_spot)
            self.draw_spot_progress(curr_spot, after_practice=True)

            if curr_spot.get_status() != "review":
                self.lesson.append(curr_spot)

            self.stdscr.refresh()
            
            self.key = self.stdscr.getch()
            if self.key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                break

            now = time.time()
        
        self.end_lesson()

    def draw_timer(self):
        if self.timer is not None:
            easy_frac = EASY_TIME / FAIL_TIME
            good_frac =  GOOD_TIME / FAIL_TIME
            timer_frac = self.timer / FAIL_TIME
            for i in range(FRETBOARD_CHAR_WIDTH):
                frac = (i + 1) / FRETBOARD_CHAR_WIDTH
                if frac <= easy_frac:
                    colour = curses.color_pair(5)
                elif frac <= good_frac:
                    colour = curses.color_pair(6)
                else: 
                    colour = curses.color_pair(7)
                
                if frac <= timer_frac:
                    symbol = "▰"
                else:
                    symbol = "▱"
                
                self.stdscr.addstr(self.top_y + FRETBOARD_CHAR_HEIGHT, self.left_x + i, symbol, colour)
        else:
            for i in range(FRETBOARD_CHAR_WIDTH):
                self.stdscr.addstr(self.top_y + FRETBOARD_CHAR_HEIGHT, self.left_x + i, "▰", curses.color_pair(10))
        
        self.stdscr.refresh()
    
    def get_spot_coords(self, spot):
        string, fret = spot.get_pos()
        screen_x = self.left_x + (4 * fret)
        if self.fretboard.view == "first_person":
            screen_y = self.top_y + (NUM_STRINGS - string) - 1
        else:
            screen_y = self.top_y + string

        return screen_x, screen_y

    def listen_for_note(self, target_note):
        start = time.monotonic()
        result_queue = queue.Queue()
        active_threads = []
        stop_event = threading.Event()
        line = 2
        last_thread_start = start - LISTEN_INTERVAL

        self.stdscr.nodelay(True)

        while True:
            now = time.monotonic()
            self.timer = now - start
            if self.timer > FAIL_TIME:
                break

            # Start a new thread every interval
            if now - last_thread_start >= LISTEN_INTERVAL:
                t = threading.Thread(
                    target=self.threaded_listen,
                    args=(SEGMENT_DURATION, result_queue),
                    daemon=True
                )
                t.start()
                active_threads.append(t)
                last_thread_start = now

            key = self.stdscr.getch()
            if key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                break
            elif key != -1:
                heard_note = chr(key)
                if heard_note == target_note[:-1]:
                    for t in active_threads:
                        t.join()
                    self.stdscr.nodelay(False)
                    return self.timer
            
            # Process any new notes
            while not result_queue.empty():
                ts, heard_note = result_queue.get()
                self.stdscr.addstr(line, self.width - 30, f"{ts - start:.2f}s: {heard_note}   ")
                # line += 1
                if (heard_note is not None) and (heard_note[:-1] == target_note[:-1]):
                    for t in active_threads:
                        t.join()
                    self.stdscr.nodelay(False)
                    return self.timer

            self.draw_timer()
            self.stdscr.refresh()

            time.sleep(0.03)

        self.timer = None
        self.draw_timer()
        
        # cleanup
        for t in active_threads:
            t.join()

        self.stdscr.nodelay(False)

        return None
    
    def threaded_listen(self, segment_duration, result_queue):
        """Runs in thread. Stops after `segment_duration` or if past deadline."""
        heard_note = listen(segment_duration)
        result_queue.put((time.monotonic(), heard_note))
        return  # Stop after first result

    
    def _get_pos_coord(self, pos):
        s, f = pos
        x = self.top_y + s
        y = self.left_x + (f * 4)
        return x, y