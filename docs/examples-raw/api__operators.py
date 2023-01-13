from convtools import conversion as c

args = ()

c(
    {
        "-a": -c.item(0),
        "a + b": c.item(0) + c.item(1),
        "a - b": c.item(0) - c.item(1),
        "a * b": c.item(0) * c.item(1),
        "a / b": c.item(0) / c.item(1),
        "a // b": c.item(0) // c.item(1),
        "a % b": c.item(0) % c.item(1),
        "a == b": c.item(0) == c.item(1),
        "a >= b": c.item(0) >= c.item(1),
        "a <= b": c.item(0) <= c.item(1),
        "a < b": c.item(0) < c.item(1),
        "a > b": c.item(0) > c.item(1),
        "a or b": c.or_(c.item(0), c.item(1), *args),
        # "a or b": c.item(0).or_(c.item(1)),
        # "a or b": c.item(0) | c.item(1),
        "a and b": c.and_(c.item(0), c.item(1), *args),
        # "a and b": c.item(0).and_(c.item(1)),
        # "a and b": c.item(0) & c.item(1),
        "not a": ~c.item(0),
        "a is b": c.item(0).is_(c.item(1)),
        "a is not b": c.item(0).is_not(c.item(1)),
        "a in b": c.item(0).in_(c.item(1)),
        "a not in b": c.item(0).not_in(c.item(1)),
    }
).gen_converter(debug=True)
