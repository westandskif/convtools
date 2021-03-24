import re
from datetime import date, datetime
from decimal import Decimal
from itertools import chain

from convtools import conversion as c


def test_doc__index_word_count():

    # Let's say we need to count words across all files
    input_data = [
        "war-and-peace-1.txt",
        "war-and-peace-2.txt",
        "war-and-peace-3.txt",
        "war-and-peace-4.txt",
    ]

    # # iterate an input and read file lines
    #
    # def read_file(filename):
    #     with open(filename) as f:
    #         for line in f:
    #             yield line
    # extract_strings = c.generator_comp(c.call_func(read_file, c.this()))

    # to simplify testing
    extract_strings = c.generator_comp(
        c.call_func(lambda filename: [filename], c.this())
    )

    # 1. make ``re`` pattern available to the code to be generated
    # 2. call ``finditer`` method of the pattern and pass the string
    #    as an argument
    # 3. pass the result to the next conversion
    # 4. iterate results, call ``.group()`` method of each re.Match
    #    and call ``.lower()`` on each result
    split_words = (
        c.naive(re.compile(r"\w+"))
        .call_method("finditer", c.this())
        .pipe(
            c.generator_comp(
                c.this().call_method("group", 0).call_method("lower")
            )
        )
    )

    # ``extract_strings`` is the generator of strings
    # so we iterate it and pass each item to ``split_words`` conversion
    vectorized_split_words = c.generator_comp(c.this().pipe(split_words))

    # flattening the result of ``vectorized_split_words``, which is
    # a generator of generators of strings
    flatten = c.call_func(
        chain.from_iterable,
        c.this(),
    )

    # aggregate the input, the result is a single dict
    # words are keys, values are count of words
    dict_word_to_count = c.aggregate(
        c.ReduceFuncs.DictCount(c.this(), c.this(), default=dict)
    )

    # take top N words by:
    #  - call ``.items()`` method of the dict (the result of the aggregate)
    #  - pass the result to ``sorted``
    #  - take the slice, using input argument named ``top_n``
    #  - cast to a dict
    take_top_n = (
        c.this()
        .call_method("items")
        .pipe(sorted, key=lambda t: t[1], reverse=True)
        .pipe(c.this()[: c.input_arg("top_n")])
        .as_type(dict)
    )

    # the resulting pipeline is pretty self-descriptive, except the ``c.if_``
    # part, which checks the condition (first argument),
    # and returns the 2nd if True OR the 3rd (input data by default) otherwise
    pipeline = (
        extract_strings.pipe(flatten)
        .pipe(vectorized_split_words)
        .pipe(flatten)
        .pipe(dict_word_to_count)
        .pipe(
            c.if_(
                c.input_arg("top_n").is_not(None),
                c.this().pipe(take_top_n),
            )
        )
        # Define the resulting converter function signature.
        # In fact this isn't necessary if you don't need to specify default values
    ).gen_converter(debug=True, signature="data_, top_n=None")

    assert pipeline(input_data, top_n=3) == {"war": 4, "and": 4, "peace": 4}
