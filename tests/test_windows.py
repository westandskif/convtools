from convtools import conversion as c


def test_iter_window():
    assert list(c.iter_windows(2, step=1).execute(range(3))) == [
        (0,),
        (0, 1),
        (1, 2),
        (2,),
    ]
    assert list(
        c.iter_windows(2, step=1)
        .iter(c.aggregate(c.ReduceFuncs.Sum(c.this)))
        .execute(range(3))
    ) == [0, 1, 3, 2]

    assert c.call_func(range, 3).iter_windows(3).as_type(list).execute(
        None
    ) == [
        (0,),
        (0, 1),
        (0, 1, 2),
        (1, 2),
        (2,),
    ]

    assert list(c.iter_windows(2, step=2).execute(range(5))) == [
        (0,),
        (1, 2),
        (3, 4),
    ]

    assert list(c.iter_windows(2).execute([])) == []


def test_accumulators():
    assert (
        c.iter(c.cumulative(c.this, c.this + c.PREV))
        .as_type(list)
        .execute([0, 1, 2, 3, 4])
    ) == [0, 1, 3, 6, 10]

    assert (
        c.iter(
            c.cumulative(
                c.this + c.input_arg("a"), c.this + c.PREV + c.input_arg("b")
            )
        )
        .as_type(list)
        .execute([0, 1, 2, 3, 4], a=10, b=1000)
    ) == [10, 1011, 2013, 3016, 4020]

    assert (
        c.iter(c.iter(c.cumulative(c.this, c.this + c.PREV)).as_type(list))
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [6, 10]]

    assert (
        c.iter(
            c.cumulative_reset("abc")
            .iter(c.cumulative(c.this, c.this + c.PREV, label_name="cde"))
            .as_type(list)
        )
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [6, 10]]

    assert (
        c.iter(
            c.cumulative_reset("abc")
            .iter(c.cumulative(c.this, c.this + c.PREV, label_name="abc"))
            .as_type(list)
        )
        .as_type(list)
        .execute([[0, 1, 2], [3, 4]])
    ) == [[0, 1, 3], [3, 7]]

    assert (
        c.iter(
            c.cumulative(
                c.this,
                c((c.this, c.PREV)).pipe(
                    c.aggregate(c.ReduceFuncs.Sum(c.this))
                ),
            )
        )
        .as_type(list)
        .execute([0, 1, 2, 3, 4])
    ) == [0, 1, 3, 6, 10]

    assert (
        c.iter(c.item(0).cumulative(c.this + 1, c.this * c.PREV))
        .as_type(list)
        .execute([[0], [1], [2], [3], [4]])
    ) == [1, 1, 2, 6, 24]
