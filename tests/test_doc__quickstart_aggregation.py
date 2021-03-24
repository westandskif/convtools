from datetime import date, datetime
from decimal import Decimal

from convtools import conversion as c


def test_doc__quickstart_aggregation():
    input_data = [
        {
            "company_name": "Facebrochure",
            "company_hq": "CA",
            "app_name": "Tardygram",
            "date": "2019-01-01",
            "country": "US",
            "sales": Decimal("45678.98"),
        },
        {
            "company_name": "Facebrochure",
            "company_hq": "CA",
            "app_name": "Tardygram",
            "date": "2019-01-02",
            "country": "US",
            "sales": Decimal("86869.12"),
        },
        {
            "company_name": "Facebrochure",
            "company_hq": "CA",
            "app_name": "Tardygram",
            "date": "2019-01-03",
            "country": "CA",
            "sales": Decimal("45000.35"),
        },
        {
            "company_name": "BrainCorp",
            "company_hq": "NY",
            "app_name": "Learn FT",
            "date": "2019-01-01",
            "country": "US",
            "sales": Decimal("86869.12"),
        },
    ]

    # we are going to reuse this reducer
    top_sales_day = c.ReduceFuncs.MaxRow(c.item("sales"))

    # so the result is going to be a list of dicts
    converter = (
        c.group_by(c.item("company_name"))
        .aggregate(
            {
                "company_name": c.item("company_name").call_method("upper"),
                # this would work as well
                # c.item("company_name"): ...,
                "none_sensitive_sum": c.ReduceFuncs.SumOrNone(c.item("sales")),
                # as you can see, next two reduce objects do the same except taking
                # different fields after finding a row with max value.
                # but please check the generated code below, you'll see that it is
                # calculated just once AND then reused to take necessary fields
                "top_sales_app": top_sales_day.item("app_name"),
                "top_sales_day": top_sales_day.item("date")
                .pipe(
                    datetime.strptime,
                    "%Y-%m-%d",
                )
                .call_method("date"),
                "company_hq": c.ReduceFuncs.First(c.item("company_hq")),
                "app_name_to_countries": c.ReduceFuncs.DictArrayDistinct(
                    c.item("app_name"), c.item("country")
                ),
                "app_name_to_sales": c.ReduceFuncs.DictSum(
                    c.item("app_name"), c.item("sales")
                ),
            }
        )
        .gen_converter(debug=True)
    )

    assert converter(input_data) == [
        {
            "app_name_to_countries": {"Tardygram": ["US", "CA"]},
            "app_name_to_sales": {"Tardygram": Decimal("177548.45")},
            "company_hq": "CA",
            "company_name": "FACEBROCHURE",
            "none_sensitive_sum": Decimal("177548.45"),
            "top_sales_app": "Tardygram",
            "top_sales_day": date(2019, 1, 2),
        },
        {
            "app_name_to_countries": {"Learn FT": ["US"]},
            "app_name_to_sales": {"Learn FT": Decimal("86869.12")},
            "company_hq": "NY",
            "company_name": "BRAINCORP",
            "none_sensitive_sum": Decimal("86869.12"),
            "top_sales_app": "Learn FT",
            "top_sales_day": date(2019, 1, 1),
        },
    ]
