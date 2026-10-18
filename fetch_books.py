import csv
import time
import requests

URL = "https://openlibrary.org/search.json"
HEADERS = {"User-Agent": "CS200BookProject (student project)"}
TARGET = 15000

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
    """Some fields come as a list. Take the first item."""
    if isinstance(value, list) and value:
        return str(value[0])
    return default


books = {}  # key -> row, so the same book is never saved twice

for subject in SUBJECTS:
    for page in range(1, 13):
        if len(books) >= TARGET:
            break

        params = {
            "q": "subject:" + subject,
            "fields": FIELDS,
            "limit": 100,
            "page": page,
        }

        try:
            response = requests.get(URL, params=params,
                                    headers=HEADERS, timeout=30)
            docs = response.json().get("docs", [])
        except Exception as error:
            print("Problem on", subject, page, "-", error)
            time.sleep(3)
            continue

        for doc in docs:
            key = doc.get("key")
            if not key or key in books:
                continue
            books[key] = {
                "title": doc.get("title", "Unknown"),
                "author": first(doc.get("author_name")),
                "year": doc.get("first_publish_year") or 0,
                "pages": doc.get("number_of_pages_median") or 0,
                "publisher": first(doc.get("publisher")),
                "language": first(doc.get("language")),
                "rating": round(doc.get("ratings_average") or 0, 2),
                "editions": doc.get("edition_count") or 0,
                "category": subject,
            }

        print(subject, "page", page, "->", len(books), "books so far")
        time.sleep(1)  # be polite to the website

# Save everything to a file
columns = ["title", "author", "year", "pages", "publisher",
           "language", "rating", "editions", "category"]

with open("books.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(books.values())

print("DONE! Saved", len(books), "books to books.csv")