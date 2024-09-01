from convtools import conversion as c

data = [(i % 2, i) for i in range(10)]

assert (
    c.unordered_chunk_by(c.item(0)).as_type(list).execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4), (0, 6), (0, 8)],
    [(1, 1), (1, 3), (1, 5), (1, 7), (1, 9)],
]

assert (
    c.unordered_chunk_by(c.item(0), size=4)
    .as_type(list)
    .execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4), (0, 6)],
    [(1, 1), (1, 3), (1, 5), (1, 7)],
    [(0, 8)],
    [(1, 9)],
]

assert (
    c.unordered_chunk_by(
        c.item(0),
        size=4,
        max_items_in_memory=6,
        portion_to_pop_on_max_memory_hit=0.5,
    )
    .as_type(list)
    .execute(data, debug=True)
) == [
    [(0, 0), (0, 2), (0, 4)],
    [(1, 1), (1, 3), (1, 5), (1, 7)],
    [(0, 6), (0, 8)],
    [(1, 9)],
]
