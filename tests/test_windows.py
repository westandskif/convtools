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
