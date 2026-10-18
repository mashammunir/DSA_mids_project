import sys
import csv
import time
import threading
import requests
from urllib.parse import urlparse, parse_qs
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout,
                             QHBoxLayout, QGridLayout, QFormLayout,
                             QGroupBox, QLabel, QComboBox,
                             QTableWidget, QTableWidgetItem,
                             QPushButton, QDialog, QLineEdit,
                             QProgressBar, QAbstractItemView)
from sorting import ALGORITHMS, merge_sort

NUMBER_COLUMNS = ["year", "pages", "rating", "editions"]

# 1. Read the books
with open("books.csv", encoding="utf-8") as f:
    reader = csv.reader(f)
    headers = next(reader)
    all_rows = list(reader)      # every book (the full dataset)

rows = list(all_rows)            # the books shown in the table
state = {"last": None, "max": 15000, "msg": ""}


def fill_table():
    table.setUpdatesEnabled(False)
    table.clearContents()
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            table.setItem(r, c, QTableWidgetItem(value))
    table.setUpdatesEnabled(True)
    table.scrollToTop()


def make_value(column, text):
    if headers[column] in NUMBER_COLUMNS:
        return float(text)
    return text.lower()


def get_target():
    if scope_box.currentText() == "Full dataset":
        return all_rows
    return rows


def update_info():
    name = algo_box.currentText()
    function, big_o, stable = ALGORITHMS[name]
    info_label.setText("Time: %s\n%s" % (big_o, stable))


# ---------- THE SCRAPER (runs in the background) ----------
URL = "https://openlibrary.org/search.json"
WEB_HEADERS = {"User-Agent": "CS200BookProject (student project)"}
TARGET = 15000
SCRAPED_FILE = "books_scraped.csv"
SUBJECTS = [
    "fiction", "history", "science", "romance", "fantasy",
    "mystery", "biography", "children", "poetry", "philosophy",
    "art", "religion", "cooking", "travel", "computers",
    "business", "health", "mathematics", "music", "war",
]
FIELDS = ("key,title,author_name,first_publish_year,"
          "number_of_pages_median,publisher,language,"
          "ratings_average,edition_count")


def first(value, default="Unknown"):
    if isinstance(value, list) and value:
        return str(value[0])
    return default


class ScraperThread(QThread):
    progress = pyqtSignal(int)           # how many books so far
    status = pyqtSignal(str)             # message for the label
    finished_rows = pyqtSignal(object)   # the list of scraped rows

    def __init__(self, query=None, target=TARGET):
        super().__init__()
        self.query = query               # None = scrape the subjects list
        self.target = target
        self._can_run = threading.Event()
        self._can_run.set()              # set = allowed to run
        self._stop_flag = False

    def pause(self):
        self._can_run.clear()

    def resume(self):
        self._can_run.set()

    def stop(self):
        self._stop_flag = True
        self._can_run.set()              # wake up if paused

    def make_jobs(self):
        jobs = []                        # (search text, page, category)
        if self.query:
            for page in range(1, 51):
                jobs.append((self.query, page, "web"))
        else:
            for subject in SUBJECTS:
                for page in range(1, 13):
                    jobs.append(("subject:" + subject, page, subject))
        return jobs

    def run(self):
        books = {}
        failures = 0                     # pages that failed in a row
        for text, page, category in self.make_jobs():
            if self._stop_flag or len(books) >= self.target:
                break
            self._can_run.wait()             # waits here while paused
            if self._stop_flag:
                break

            params = {"q": text, "fields": FIELDS,
                      "limit": 100, "page": page}

            docs = None
            last_error = ""
            for attempt in range(2):         # try each page twice
                try:
                    response = requests.get(URL, params=params,
                                            headers=WEB_HEADERS, timeout=30)
                    if response.status_code != 200:
                        raise Exception("server replied %d"
                                        % response.status_code)
                    docs = response.json().get("docs", [])
                    break
                except Exception as error:
                    last_error = str(error)[:80]
                    self.status.emit("Problem on %s page %d: %s"
                                     % (category, page, last_error))
                    time.sleep(2)

            if docs is None:                 # both tries failed
                failures += 1
                if failures >= 5:
                    self.status.emit("Stopped: Open Library is not "
                                     "answering (%s)" % last_error)
                    break
                continue
            failures = 0

            if self.query and not docs:
                break                        # no more results for this link

            for doc in docs:
                key = doc.get("key")
                if not key or key in books:
                    continue
                books[key] = [
                    str(doc.get("title", "Unknown")),
                    first(doc.get("author_name")),
                    str(doc.get("first_publish_year") or 0),
                    str(doc.get("number_of_pages_median") or 0),
                    first(doc.get("publisher")),
                    first(doc.get("language")),
                    str(round(doc.get("ratings_average") or 0, 2)),
                    str(doc.get("edition_count") or 0),
                    category,
                ]

            self.progress.emit(len(books))
            self.status.emit("Scraping %s, page %d" % (category, page))
            time.sleep(1)

        result = list(books.values())
        if result:
            with open(SCRAPED_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(result)
        self.finished_rows.emit(result)


scraper = {"thread": None}


def set_scrape_buttons(start, pause, resume, stop):
    start_btn.setEnabled(start)
    url_btn.setEnabled(start)
    pause_btn.setEnabled(pause)
    resume_btn.setEnabled(resume)
    stop_btn.setEnabled(stop)


def on_scrape_status(text):
    state["msg"] = text
    scrape_label.setText(text)


def launch_scraper(thread, maximum):
    state["max"] = maximum
    progress_bar.setMaximum(maximum)
    progress_bar.setValue(0)
    count_label.setText("0 / %d books" % maximum)
    thread.progress.connect(on_scrape_progress)
    thread.status.connect(on_scrape_status)
    thread.finished_rows.connect(on_scrape_done)
    scraper["thread"] = thread
    thread.start()
    set_scrape_buttons(False, True, False, True)


def start_scraping():
    launch_scraper(ScraperThread(None, TARGET), TARGET)


def start_url_scraping():
    link = url_text.text().strip()
    parsed = urlparse(link)
    if "openlibrary.org" not in parsed.netloc:
        scrape_label.setText("Only Open Library search links work, e.g. "
                             "https://openlibrary.org/search?q=harry+potter")
        return
    query = parse_qs(parsed.query).get("q", [""])[0]
    if query == "":
        scrape_label.setText("That link has no search text (q=...). "
                             "Try https://openlibrary.org/search?q=dragons")
        return
    launch_scraper(ScraperThread(query, 5000), 5000)


def pause_scraping():
    scraper["thread"].pause()
    scrape_label.setText("Paused (after the current request finishes)")
    set_scrape_buttons(False, False, True, True)


def resume_scraping():
    scraper["thread"].resume()
    set_scrape_buttons(False, True, False, True)


def stop_scraping():
    scrape_label.setText("Stopping and saving...")
    scraper["thread"].stop()
    set_scrape_buttons(False, False, False, False)


def on_scrape_progress(count):
    progress_bar.setValue(min(count, state["max"]))
    count_label.setText("%d / %d books" % (count, state["max"]))


def on_scrape_done(result):
    if result:
        all_rows[:] = result
        state["last"] = None
        rows[:] = all_rows
        fill_table()
        scrape_label.setText("Finished. %d books saved to %s."
                             % (len(result), SCRAPED_FILE))
    else:
        scrape_label.setText("0 books collected, nothing was changed.\n"
                             "Last message: " + state["msg"])
    set_scrape_buttons(True, False, False, False)


# ---------- SEARCH ALGORITHMS ----------
def linear_search(values, target, stats):
    found = []
    for i in range(len(values)):
        stats["comparisons"] += 1
        if values[i] == target:
            found.append(i)
    return found


def binary_search(pairs, target, stats):
    low = 0
    high = len(pairs) - 1
    first_pos = -1
    while low <= high:
        mid = (low + high) // 2
        stats["comparisons"] += 1
        if pairs[mid][0] < target:
            low = mid + 1
        elif pairs[mid][0] > target:
            high = mid - 1
        else:
            first_pos = mid
            high = mid - 1
    if first_pos == -1:
        return []
    found = []
    k = first_pos
    while k < len(pairs) and pairs[k][0] == target:
        found.append(pairs[k][1])
        k += 1
    return found


def run_search():
    column = search_column_box.currentIndex()
    algo = search_algo_box.currentText()
    text = search_text.text().strip()

    if headers[column] in NUMBER_COLUMNS:
        try:
            target = float(text)
        except ValueError:
            result_label.setText("Please type a number for column '%s'."
                                 % headers[column])
            return
    else:
        target = text.lower()

    values = [make_value(column, row[column]) for row in all_rows]
    stats = {"comparisons": 0}

    if algo == "Linear Search":
        start = time.perf_counter()
        found = linear_search(values, target, stats)
        ms = (time.perf_counter() - start) * 1000
    else:
        pairs = [(values[i], i) for i in range(len(values))]
        pairs = merge_sort(pairs, {"comparisons": 0, "swaps": 0})
        start = time.perf_counter()
        found = binary_search(pairs, target, stats)
        ms = (time.perf_counter() - start) * 1000

    state["last"] = run_search
    rows[:] = [all_rows[i] for i in found]
    fill_table()
    result_label.setText(
        "%s found %d books | %.3f ms | %d comparisons"
        % (algo, len(rows), ms, stats["comparisons"]))


# ---------- FILTER (AND / OR / NOT) ----------
def matches(row, column, mode, text):
    value = row[column].lower()
    text = text.lower()

    if mode == "contains":
        return text in value
    if mode == "starts with":
        return value.startswith(text)
    if mode == "ends with":
        return value.endswith(text)
    if mode == "equals":
        return value == text

    try:
        a = float(value)
        b = float(text)
    except ValueError:
        return False
    if mode == ">":
        return a > b
    if mode == "<":
        return a < b
    if mode == ">=":
        return a >= b
    return a <= b


def apply_filter():
    col1 = f1_column_box.currentIndex()
    mode1 = f1_mode_box.currentText()
    text1 = f1_text.text().strip()

    col2 = f2_column_box.currentIndex()
    mode2 = f2_mode_box.currentText()
    text2 = f2_text.text().strip()

    operator = operator_box.currentText()

    if text1 == "":
        result_label.setText("Type something in Condition 1 first.")
        return

    use_second = text2 != "" and operator != "NOT (condition 1 only)"

    result = []
    for row in all_rows:
        a = matches(row, col1, mode1, text1)
        if operator == "NOT (condition 1 only)":
            ok = not a
        elif not use_second:
            ok = a
        else:
            b = matches(row, col2, mode2, text2)
            if operator == "AND":
                ok = a and b
            elif operator == "OR":
                ok = a or b
            else:                          # AND NOT
                ok = a and not b
        if ok:
            result.append(row)

    state["last"] = apply_filter
    rows[:] = result
    fill_table()
    result_label.setText("Filter found %d books (out of %d)."
                         % (len(rows), len(all_rows)))


def clear_all():
    f1_text.clear()
    f2_text.clear()
    search_text.clear()
    state["last"] = None
    rows[:] = all_rows
    fill_table()
    result_label.setText("Cleared. Showing all %d books." % len(rows))


# ---------- SORT (one column or several columns) ----------
def do_sort(columns):
    name = algo_box.currentText()
    function = ALGORITHMS[name][0]
    target = get_target()

    result_label.setText("Sorting with %s... please wait" % name)
    app.processEvents()

    pairs = []
    for i, row in enumerate(target):
        if len(columns) == 1:
            key = make_value(columns[0], row[columns[0]])
        else:
            key = tuple(make_value(c, row[c]) for c in columns)
        pairs.append((key, i))

    stats = {"comparisons": 0, "swaps": 0}
    start = time.perf_counter()
    sorted_pairs = function(pairs, stats)
    ms = (time.perf_counter() - start) * 1000

    new_order = [target[i] for value, i in sorted_pairs]

    if target is all_rows:
        all_rows[:] = new_order
        if state["last"]:
            state["last"]()
        else:
            rows[:] = all_rows
            fill_table()
    else:
        rows[:] = new_order
        fill_table()

    label = " then ".join(headers[c] for c in columns)
    result_label.setText(
        "Sorted %d books by %s | %s | %.1f ms | %d comparisons | %d swaps"
        % (len(target), label, name, ms,
           stats["comparisons"], stats["swaps"])
    )


def on_header_clicked(column):
    do_sort([column])


def run_multi_sort():
    columns = [level1_box.currentIndex(), level2_box.currentIndex()]
    if level3_box.currentIndex() > 0:          # 0 means "(none)"
        columns.append(level3_box.currentIndex() - 1)
    do_sort(columns)


# ---------- BENCHMARK ----------
def run_benchmark():
    column = bench_column_box.currentIndex()
    size_text = bench_size_box.currentText()
    target = get_target()

    pairs = []
    for i, row in enumerate(target):
        pairs.append((make_value(column, row[column]), i))
    if size_text != "All":
        pairs = pairs[:int(size_text)]

    results = []
    for name, (function, big_o, stable) in ALGORITHMS.items():
        result_label.setText("Benchmark: running %s on %d books..."
                             % (name, len(pairs)))
        app.processEvents()

        stats = {"comparisons": 0, "swaps": 0}
        start = time.perf_counter()
        function(pairs, stats)
        ms = (time.perf_counter() - start) * 1000
        results.append((name, ms, stats["comparisons"],
                        stats["swaps"], big_o, stable))

    result_label.setText("Benchmark finished on column '%s' (%d books)."
                         % (headers[column], len(pairs)))
    show_benchmark_results(results, headers[column], len(pairs))


def show_benchmark_results(results, column_name, count):
    dialog = QDialog(window)
    dialog.setWindowTitle("Benchmark - column '%s' - %d books"
                          % (column_name, count))
    dialog.resize(850, 300)

    names = ["Algorithm", "Time (ms)", "Comparisons", "Swaps",
             "Complexity", "Stable?"]
    t = QTableWidget()
    t.setColumnCount(len(names))
    t.setHorizontalHeaderLabels(names)
    t.setRowCount(len(results))
    for r, (name, ms, comps, swaps, big_o, stable) in enumerate(results):
        values = [name, "%.1f" % ms, str(comps), str(swaps), big_o, stable]
        for c, value in enumerate(values):
            t.setItem(r, c, QTableWidgetItem(value))
    t.resizeColumnsToContents()
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    box = QVBoxLayout()
    box.addWidget(t)
    dialog.setLayout(box)
    dialog.exec()


# =====================  BUILD THE WINDOW  =====================
MODES = ["contains", "starts with", "ends with", "equals",
         ">", "<", ">=", "<="]

app = QApplication(sys.argv)

window = QWidget()
window.setWindowTitle("Book Sorter")
window.resize(1300, 850)

# colours: navy  #14305a   gold  #e8a317   white
# (to try other colours, just replace those two codes below)
window.setStyleSheet("""
QWidget { background-color: white; color: #14305a; font-size: 10pt; }
QLabel#title { font-size: 20pt; font-weight: bold; }
QLabel#goldline { background-color: #e8a317; }
QLabel#status { background-color: #f3f5f9; border-left: 4px solid #e8a317;
                padding: 5px; }
QGroupBox { border: 1px solid #b8c2d6; border-radius: 4px;
            margin-top: 12px; padding-top: 6px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px;
                   padding: 0 4px; font-weight: bold; }
QPushButton { background-color: #14305a; color: white; border: none;
              padding: 5px 12px; border-radius: 3px; }
QPushButton:hover { background-color: #e8a317; color: #14305a; }
QPushButton:disabled { background-color: #e3e7ee; color: #8a94a8; }
QLineEdit, QComboBox { border: 1px solid #b8c2d6; padding: 2px;
                       background-color: white; }
QProgressBar { border: 1px solid #b8c2d6; background-color: white;
               max-height: 14px; }
QProgressBar::chunk { background-color: #e8a317; }
QTableWidget { gridline-color: #dde2ec; border: 1px solid #b8c2d6; }
QTableWidget::item:selected { background-color: #fbe7b0; color: #14305a; }
QHeaderView::section { background-color: #14305a; color: white;
                       border: none; padding: 5px; font-weight: bold; }
""")

# ----- title, gold line and status line -----
title_label = QLabel("Book Sorter")
title_label.setObjectName("title")

gold_line = QLabel()
gold_line.setObjectName("goldline")
gold_line.setFixedHeight(3)

result_label = QLabel("Pick an algorithm, then click a column title to sort.")
result_label.setObjectName("status")

# ----- the table -----
table = QTableWidget()
table.setColumnCount(len(headers))
table.setHorizontalHeaderLabels(headers)
table.horizontalHeader().setSectionsClickable(True)
table.horizontalHeader().sectionClicked.connect(on_header_clicked)
table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

widths = {"title": 260, "author": 160, "year": 70, "pages": 70,
          "publisher": 190, "language": 80, "rating": 70, "editions": 80}
for i, h in enumerate(headers):
    if h in widths:
        table.setColumnWidth(i, widths[h])
table.horizontalHeader().setStretchLastSection(True)

# ----- box 1: scraping -----
scrape_box = QGroupBox("Scraping")
start_btn = QPushButton("Start")
pause_btn = QPushButton("Pause")
resume_btn = QPushButton("Resume")
stop_btn = QPushButton("Stop")
buttons_row = QHBoxLayout()
for b in (start_btn, pause_btn, resume_btn, stop_btn):
    buttons_row.addWidget(b)

progress_bar = QProgressBar()
progress_bar.setMaximum(TARGET)
progress_bar.setTextVisible(False)
count_label = QLabel("0 / %d books" % TARGET)
progress_row = QHBoxLayout()
progress_row.addWidget(progress_bar)
progress_row.addWidget(count_label)

scrape_label = QLabel("Idle. Press Start to collect books.")
scrape_label.setWordWrap(True)

url_text = QLineEdit()
url_text.setPlaceholderText("paste an Open Library search link")
url_btn = QPushButton("Scrape URL")
url_row = QHBoxLayout()
url_row.addWidget(url_text)
url_row.addWidget(url_btn)

scrape_layout = QVBoxLayout()
scrape_layout.addLayout(buttons_row)
scrape_layout.addLayout(progress_row)
scrape_layout.addWidget(scrape_label)
scrape_layout.addLayout(url_row)
scrape_box.setLayout(scrape_layout)

# ----- box 2: sorting -----
sort_box = QGroupBox("Sorting")
algo_box = QComboBox()
algo_box.addItems(list(ALGORITHMS.keys()))
scope_box = QComboBox()
scope_box.addItems(["Full dataset", "Filtered results only"])
info_label = QLabel("")

sort_layout = QFormLayout()
sort_layout.addRow("Algorithm:", algo_box)
sort_layout.addRow("Sort scope:", scope_box)
sort_layout.addRow("Info:", info_label)
sort_layout.addRow(QLabel("Click a column title to sort."))
sort_box.setLayout(sort_layout)

# ----- box 3: multi-level sort and benchmark -----
multi_box = QGroupBox("Multi-level sort and Benchmark")
level1_box = QComboBox()
level1_box.addItems(headers)
level1_box.setCurrentText("category")
level2_box = QComboBox()
level2_box.addItems(headers)
level2_box.setCurrentText("year")
level3_box = QComboBox()
level3_box.addItem("(none)")
level3_box.addItems(headers)
multi_button = QPushButton("Multi-Level Sort")

bench_column_box = QComboBox()
bench_column_box.addItems(headers)
bench_size_box = QComboBox()
bench_size_box.addItems(["1000", "5000", "All"])
bench_button = QPushButton("Benchmark")

multi_layout = QFormLayout()
multi_layout.addRow("First by:", level1_box)
multi_layout.addRow("Then by:", level2_box)
multi_layout.addRow("Then by:", level3_box)
multi_layout.addRow(multi_button)
multi_layout.addRow("Benchmark column:", bench_column_box)
multi_layout.addRow("Books:", bench_size_box)
multi_layout.addRow(bench_button)
multi_box.setLayout(multi_layout)

# ----- box 4: searching -----
search_box = QGroupBox("Searching")
search_column_box = QComboBox()
search_column_box.addItems(headers)
search_algo_box = QComboBox()
search_algo_box.addItems(["Linear Search", "Binary Search"])
search_text = QLineEdit()
search_text.setPlaceholderText("exact value, e.g. 1999")
search_button = QPushButton("Search")

search_layout = QFormLayout()
search_layout.addRow("Column:", search_column_box)
search_layout.addRow("Algorithm:", search_algo_box)
search_layout.addRow("Value:", search_text)
search_layout.addRow(search_button)
search_box.setLayout(search_layout)

# ----- box 5: filters -----
filter_box = QGroupBox("Filters")
f1_column_box = QComboBox()
f1_column_box.addItems(headers)
f1_mode_box = QComboBox()
f1_mode_box.addItems(MODES)
f1_text = QLineEdit()
f1_text.setPlaceholderText("type here...")

operator_box = QComboBox()
operator_box.addItems(["AND", "OR", "AND NOT", "NOT (condition 1 only)"])

f2_column_box = QComboBox()
f2_column_box.addItems(headers)
f2_mode_box = QComboBox()
f2_mode_box.addItems(MODES)
f2_text = QLineEdit()
f2_text.setPlaceholderText("optional...")

filter_button = QPushButton("Filter")
clear_button = QPushButton("Clear")

filter_layout = QGridLayout()
filter_layout.addWidget(QLabel("Condition 1:"), 0, 0)
filter_layout.addWidget(f1_column_box, 0, 1)
filter_layout.addWidget(f1_mode_box, 0, 2)
filter_layout.addWidget(f1_text, 0, 3)
filter_layout.addWidget(QLabel("Operator:"), 1, 0)
filter_layout.addWidget(operator_box, 1, 1, 1, 2)
filter_layout.addWidget(QLabel("Condition 2:"), 2, 0)
filter_layout.addWidget(f2_column_box, 2, 1)
filter_layout.addWidget(f2_mode_box, 2, 2)
filter_layout.addWidget(f2_text, 2, 3)
filter_layout.addWidget(filter_button, 3, 1)
filter_layout.addWidget(clear_button, 3, 2)
filter_box.setLayout(filter_layout)

# ----- put the boxes in a grid under the table -----
boxes = QGridLayout()
boxes.addWidget(scrape_box, 0, 0)
boxes.addWidget(sort_box, 0, 1)
boxes.addWidget(multi_box, 0, 2)
boxes.addWidget(search_box, 1, 0)
boxes.addWidget(filter_box, 1, 1, 1, 2)

layout = QVBoxLayout()
layout.addWidget(title_label)
layout.addWidget(gold_line)
layout.addWidget(result_label)
layout.addWidget(table, 1)
layout.addLayout(boxes)
window.setLayout(layout)

# ----- connect the buttons -----
start_btn.clicked.connect(start_scraping)
url_btn.clicked.connect(start_url_scraping)
url_text.returnPressed.connect(start_url_scraping)
pause_btn.clicked.connect(pause_scraping)
resume_btn.clicked.connect(resume_scraping)
stop_btn.clicked.connect(stop_scraping)
set_scrape_buttons(True, False, False, False)

algo_box.currentTextChanged.connect(update_info)
multi_button.clicked.connect(run_multi_sort)
filter_button.clicked.connect(apply_filter)
f1_text.returnPressed.connect(apply_filter)
f2_text.returnPressed.connect(apply_filter)
clear_button.clicked.connect(clear_all)
search_button.clicked.connect(run_search)
search_text.returnPressed.connect(run_search)
bench_button.clicked.connect(run_benchmark)
update_info()
fill_table()


def on_close(event):
    t = scraper["thread"]
    if t is not None and t.isRunning():
        t.stop()
        t.wait()
    event.accept()


window.closeEvent = on_close

window.show()
sys.exit(app.exec())