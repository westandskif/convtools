import pytest

from convtools import conversion as c


def test_expect():
    assert c.expect(True).execute(10) == 10

    data = {"a": 10}
    assert c.expect(c.item("a") > 1).execute(data) == data
    assert c.item("a").expect(c.this > 1).execute(data) == 10

    with pytest.raises(c.ExpectException):
        assert c.expect(False).execute(10)

    with pytest.raises(c.ExpectException):
        assert c.expect(c.item("a") > 10).execute(data)

    with pytest.raises(c.ExpectException, match="custom msg"):
        assert c.item("a").expect(c.this > 10, "custom msg").execute(data)

    with pytest.raises(c.ExpectException, match="11"):
        assert (
            c.item("a")
            .expect(c.this > 10, (c.this + 1).as_type(str))
            .execute(data)
        )

    assert (
        c.aggregate(
            c.ReduceFuncs.Sum(c.this).expect(c.this <= 10) * 10
        ).execute(range(5))
        == 100
    )

    converter = (
        c.iter(
            c.item("a").expect(
                condition=c.this.len() > 3,
                error_msg=c.call_func("{} is too short".format, c.this),
            )
        )
        .as_type(list)
        .gen_converter(debug=True)
    )
    assert converter([{"a": "value"}]) == ["value"]

    with pytest.raises(c.ExpectException, match="val is too short"):
        converter([{"a": "val"}])
