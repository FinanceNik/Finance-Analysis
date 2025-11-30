import pandas as pd

def real_estate_projection(
    starting_value: float = 350000,
    growth_rate: float = 0.03,   # 3% as decimal
    costs: float = 1200 * 12,    # yearly costs
    income: float = 1700 * 12,   # yearly income
    years: int = 20
) -> pd.DataFrame:
    """
    Returns a DataFrame over `years` with:
    - 'asset_value_with_appreciation'
    - 'costs' (cumulative)
    - 'income' (cumulative)
    """

    # Year numbers 0..years
    year_range = list(range(0, years + 1))

    # Asset value with annual appreciation
    asset_values = [
        starting_value * ((1 + growth_rate) ** y)
        for y in year_range
    ]

    # Cumulative costs and income over the period
    costs_series = [costs * y for y in year_range]
    income_series = [income * y for y in year_range]

    df = pd.DataFrame({
        "year": year_range,
        "asset_value_with_appreciation": asset_values,
        "costs": costs_series,
        "income": income_series,
    })

    df.set_index("year", inplace=True)

    return df
