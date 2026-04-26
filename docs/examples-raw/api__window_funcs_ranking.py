from convtools import conversion as c


data = [
    {"team": "A", "name": "Ada", "score": 20},
    {"team": "A", "name": "Ben", "score": 20},
    {"team": "A", "name": "Cy", "score": 10},
    {"team": "B", "name": "Dee", "score": 15},
    {"team": "B", "name": "Eli", "score": 12},
]

result = (
    c.this.window(
        {
            "name": c.WindowFuncs.Row().item("name"),
            "ranking": (
                c.WindowFuncs.RowIndex() + 1,
                c.WindowFuncs.PeerGroupFirstRowIndex() + 1,
                c.WindowFuncs.PeerGroupIndex() + 1,
            ),
        }
    )
    .over(
        partition_by=c.item("team"),
        order_by=c.item("score").desc(),
    )
    .execute(data)
)
assert result == [
    {"name": "Ada", "ranking": (1, 1, 1)},
    {"name": "Ben", "ranking": (2, 1, 1)},
    {"name": "Cy", "ranking": (3, 3, 2)},
    {"name": "Dee", "ranking": (1, 1, 1)},
    {"name": "Eli", "ranking": (2, 2, 2)},
]
