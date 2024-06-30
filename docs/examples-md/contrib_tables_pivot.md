/// tab | convtools
    new: true

```python
from convtools import conversion as c
from convtools.contrib.tables import Table

with c.OptionsCtx() as options:
    options.debug = True

    assert list(
        Table.from_rows(
            [
                {"dept": 1, "year": 2023, "currency": "USD", "revenue": 100},
                {"dept": 1, "year": 2024, "currency": "USD", "revenue": 300},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 200},
                {"dept": 1, "year": 2024, "currency": "CNY", "revenue": 111},
            ]
        )
        .pivot(
            rows=["year", "dept"],
            columns=["currency"],
            values={
                "sum": c.ReduceFuncs.Sum(c.col("revenue")),
                "min": c.ReduceFuncs.Min(c.col("revenue")),
            },
        )
        .into_iter_rows(dict)
    ) == [
        {
            "CNY - min": None,
            "CNY - sum": None,
            "USD - min": 100,
            "USD - sum": 100,
            "dept": 1,
            "year": 2023,
        },
        {
            "CNY - min": 111,
            "CNY - sum": 311,
            "USD - min": 300,
            "USD - sum": 300,
            "dept": 1,
            "year": 2024,
        },
    ]

```
///

/// tab | debug stdout
```python
def aggregate_(_none, data_):
    agg_data__v0 = _none

    checksum_ = 0
    it_ = iter(data_)
    for row_ in it_:
        if agg_data__v0 is _none:
            checksum_ += 1
            agg_data__v0 = row_["revenue"] or 0
        else:
            agg_data__v0 += row_["revenue"] or 0
        if checksum_ == 1:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_ in it_:
        agg_data__v0 += row_["revenue"] or 0

    return 0 if (agg_data__v0 is _none) else agg_data__v0

def converter(data_):
    global __none__
    _none = __none__
    try:
        return aggregate_(_none, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def aggregate_(_none, data_):
    agg_data__v0 = _none

    checksum_ = 0
    it_ = iter(data_)
    for row_ in it_:
        _r0_ = row_["revenue"]
        if _r0_ is not None:
            if agg_data__v0 is _none:
                checksum_ += 1
                agg_data__v0 = _r0_
            else:
                if agg_data__v0 > _r0_:
                    agg_data__v0 = _r0_
        if checksum_ == 1:
            globals()["__BROKEN_EARLY__"] = True  # DEBUG ONLY
            break
    for row_ in it_:
        _r0_ = row_["revenue"]
        if _r0_ is not None:
            if agg_data__v0 > _r0_:
                agg_data__v0 = _r0_

    return None if (agg_data__v0 is _none) else agg_data__v0

def converter(data_):
    global __none__
    _none = __none__
    try:
        return aggregate_(_none, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

class AggData_:
    __slots__ = ["v0"]

    def __init__(self, _none=__none__):
        self.v0 = _none

def group_by_(_none, data_):
    signature_to_agg_data_ = defaultdict(AggData_)

    for row_ in data_:
        agg_data_ = signature_to_agg_data_[(row_["year"], row_["dept"])]
        if agg_data_.v0 is _none:
            agg_data_.v0 = defaultdict(list)
            agg_data_.v0[(row_["currency"],)].append(row_)
        else:
            agg_data_.v0[(row_["currency"],)].append(row_)

    return [
        (
            signature_[0],
            signature_[1],
            ((None if (agg_data_.v0 is _none) else (setattr(agg_data_.v0, "default_factory", None) or agg_data_.v0))),
        )
        for signature_, agg_data_ in signature_to_agg_data_.items()
    ]

def converter(data_):
    global __none__
    _none = __none__
    try:
        return group_by_(_none, data_)
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise

def pipe_(input_, *, __converter=__naive_values__["__converter"]):
    return input_ and __converter(input_)

def pipe_i(input_, *, __converter_e=__naive_values__["__converter_e"]):
    return input_ and __converter_e(input_)

def converter(data_, *, __v=__naive_values__["__v"], __v_h=__naive_values__["__v_h"]):
    try:
        return (
            {
                "year": i[0],
                "dept": i[1],
                "USD - sum": pipe_(i[2].get(__v)),
                "USD - min": pipe_i(i[2].get(__v)),
                "CNY - sum": pipe_(i[2].get(__v_h)),
                "CNY - min": pipe_i(i[2].get(__v_h)),
            }
            for i in data_
        )
    except __exceptions_to_dump_sources:
        __convtools__code_storage.dump_sources()
        raise


```
///

