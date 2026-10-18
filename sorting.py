import sys
sys.setrecursionlimit(20000)


def merge_sort(items, stats):
    if len(items) <= 1:
        return items
    middle = len(items) // 2
    left = merge_sort(items[:middle], stats)
    right = merge_sort(items[middle:], stats)

    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        stats["comparisons"] += 1
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
            stats["swaps"] += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


def quick_sort(items, stats):
    a = items[:]

    def sort(low, high):
        if low >= high:
            return
        mid = (low + high) // 2
        a[mid], a[high] = a[high], a[mid]
        stats["swaps"] += 1
        pivot = a[high]

        i = low
        for j in range(low, high):
            stats["comparisons"] += 1
            if a[j] < pivot:
                a[i], a[j] = a[j], a[i]
                stats["swaps"] += 1
                i += 1
        a[i], a[high] = a[high], a[i]
        stats["swaps"] += 1

        sort(low, i - 1)
        sort(i + 1, high)

    sort(0, len(a) - 1)
    return a


def bubble_sort(items, stats):
    a = items[:]
    n = len(a)
    for i in range(n - 1):
        swapped = False
        for j in range(n - 1 - i):
            stats["comparisons"] += 1
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                stats["swaps"] += 1
                swapped = True
        if not swapped:
            break
    return a


def selection_sort(items, stats):
    a = items[:]
    n = len(a)
    for i in range(n - 1):
        smallest = i
        for j in range(i + 1, n):
            stats["comparisons"] += 1
            if a[j] < a[smallest]:
                smallest = j
        if smallest != i:
            a[i], a[smallest] = a[smallest], a[i]
            stats["swaps"] += 1
    return a


def insertion_sort(items, stats):
    a = items[:]
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0:
            stats["comparisons"] += 1
            if a[j] > key:
                a[j + 1] = a[j]
                stats["swaps"] += 1
                j -= 1
            else:
                break
        a[j + 1] = key
    return a


def heap_sort(items, stats):
    a = items[:]
    n = len(a)

    def sift_down(start, end):
        root = start
        while True:
            child = 2 * root + 1
            if child >= end:
                break
            if child + 1 < end:
                stats["comparisons"] += 1
                if a[child] < a[child + 1]:
                    child += 1
            stats["comparisons"] += 1
            if a[root] < a[child]:
                a[root], a[child] = a[child], a[root]
                stats["swaps"] += 1
                root = child
            else:
                break

    for start in range(n // 2 - 1, -1, -1):
        sift_down(start, n)
    for end in range(n - 1, 0, -1):
        a[0], a[end] = a[end], a[0]
        stats["swaps"] += 1
        sift_down(0, end)
    return a


def shell_sort(items, stats):
    a = items[:]
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            temp = a[i]
            j = i
            while j >= gap:
                stats["comparisons"] += 1
                if a[j - gap] > temp:
                    a[j] = a[j - gap]
                    stats["swaps"] += 1
                    j -= gap
                else:
                    break
            a[j] = temp
        gap //= 2
    return a


# name -> (function, time complexity, stable or not)
ALGORITHMS = {
    "Merge Sort": (merge_sort, "O(n log n)", "Stable"),
    "Quick Sort": (quick_sort, "O(n log n) average, O(n^2) worst", "Not stable"),
    "Bubble Sort": (bubble_sort, "O(n^2)", "Stable"),
    "Selection Sort": (selection_sort, "O(n^2)", "Not stable"),
    "Insertion Sort": (insertion_sort, "O(n^2)", "Stable"),
    "Heap Sort (extra)": (heap_sort, "O(n log n)", "Not stable"),
    "Shell Sort (extra)": (shell_sort, "O(n^2) worst, about O(n log^2 n) typical", "Not stable"),
}


# ---- small test ----
if __name__ == "__main__":
    for name, (function, big_o, stable) in ALGORITHMS.items():
        stats = {"comparisons": 0, "swaps": 0}
        print(name, function([5, 2, 9, 1, 7, 3], stats), stats)