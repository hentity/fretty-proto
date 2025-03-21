import re
import curses
from art import text2art
import time
import threading
import time
import queue

from fretty.pages.page import Page
from fretty.globals import *
from fretty.fretboard import EASY_TIME, GOOD_TIME, FAIL_TIME, MAX_DAILY_REVIEWS
from fretty.audio import listen

LISTEN_INTERVAL = 0.1   # How often to start a new thread
SEGMENT_DURATION = 0.3

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
        self.left_x = (self.width - (FRETBOARD_CHAR_WIDTH + NOTE_WIDTH + SPACING)) // 2
        self.timer = None
        self.lesson = []
        self.time_limit = time_limit
        

    def load(self):
        self.stdscr.clear()
        self.stdscr.addstr(1, 5, "<-- Backspace / Esc", curses.A_BOLD)

        # ascii_art = text2art("A#", font="varsity")
        ascii_art = text2art("C", font="tarty1")
        lines = ascii_art.split("\n")

        for i, line in enumerate(lines):
            self.stdscr.addstr(i + self.top_y - 1, self.left_x + FRETBOARD_CHAR_WIDTH + 4, line)

        self.stdscr.refresh()
        # self.stdscr.clear()

        strings = list(enumerate([re.sub(r'\d+', '', s) for s in self.fretboard.tuning]))
        if self.fretboard.view == "first_person":
            strings.reverse()

        frets = range(1, NUM_FRETS + 1)
        if self.fretboard.view == "third_person":
            frets.reverse()

        line_y = self.top_y
        for s, string in strings:
            if s == 2:
                style = curses.A_BOLD | curses.color_pair(8)
            else:
                style = curses.A_NORMAL
            self.stdscr.addstr(line_y, self.left_x + 0, f" {string} ", style)
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
        reviews = self.fretboard.get_reviews_today()
        self.lesson += reviews

        num_reviews = len(reviews)
        learning_space = MAX_DAILY_REVIEWS - num_reviews
        new_spots = self.fretboard.get_spots(status="new")[:learning_space]
        self.lesson += new_spots

    def end_lesson(self):
        for spot in self.lesson:
            spot.reset()
        # end of lesson UI
    
    def start(self):
        self.create_lesson()
        start = time.time()
        now = time.time()
        while self.lesson:
            if (self.time_limit is not None) and ((now - start) >= self.time_limit):
                break
            curr_spot = self.lesson.pop(0)
            curr_note = curr_spot.get_note()
            self.stdscr.addstr(0, self.width - 15, f"target note: {curr_note}")
            attempt_time = self.listen_for_note(curr_note)
            curr_spot.add_attempt(attempt_time)
            self.stdscr.addstr(3, self.width - 15, f"{curr_spot.get_pos()}: {curr_spot.get_status()}")

            if curr_spot.get_status() != "review":
                self.lesson.append(curr_spot)

            self.stdscr.refresh()
            
            self.key = self.stdscr.getch()
            if self.key in [27, 127, curses.KEY_BACKSPACE, curses.KEY_DC]:
                self.stop()
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
                
            self.stdscr.refresh()

    def stop(self):
        self.stdscr.clear()

    def listen_for_note(self, target_note):
        start = time.monotonic()
        result_queue = queue.Queue()
        active_threads = []
        line = 2
        last_thread_start = start - LISTEN_INTERVAL

        while True:
            now = time.monotonic()
            self.timer = now - start
            if self.timer > FAIL_TIME:
                break

            # Start a new thread every interval
            if now - last_thread_start >= LISTEN_INTERVAL:
                t = threading.Thread(
                    target=self.threaded_listen,
                    args=(SEGMENT_DURATION, result_queue, start + FAIL_TIME),
                    daemon=True
                )
                t.start()
                active_threads.append(t)
                last_thread_start = now

            # Process any new notes
            while not result_queue.empty():
                ts, heard_note = result_queue.get()
                self.stdscr.addstr(line, self.width - 30, f"{ts - start:.2f}s: {heard_note}   ")
                # line += 1
                if (heard_note is not None) and (heard_note[:-1] == target_note[:-1]):
                    return self.timer

            self.draw_timer()
            self.stdscr.refresh()

            time.sleep(0.03)

        # cleanup
        for t in active_threads:
            t.join(timeout=0.1)  # wait for thread to wrap up
        return None
    
    def threaded_listen(self, segment_duration, result_queue, deadline):
        """Runs in thread. Stops after `segment_duration` or if past deadline."""
        start_time = time.monotonic()
        while time.monotonic() - start_time < segment_duration:
            if time.monotonic() > deadline:
                return
            heard_note = listen(segment_duration)
            result_queue.put((time.monotonic(), heard_note))
            return  # Stop after first result
    
    # def threaded_listen(self, segment_duration, result_queue):
    #     while (self.timer is not None) and (self.timer < FAIL_TIME):
    #         heard_note = listen(segment_duration)
    #         result_queue.put(heard_note)

    
    def _get_pos_coord(self, pos):
        s, f = pos
        x = self.top_y + s
        y = self.left_x + (f * 4)
        return x, y