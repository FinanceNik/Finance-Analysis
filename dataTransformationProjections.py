import numpy as np
import pandas as pd
import dataLoadPositions as dlp

def monte_carlo_portfolio_simulation(runs, expected_return, volatility, time_horizon):
    df = dlp.fetch_data()
    initial_value = df['total_value'].sum()

    np.random.seed(42)  # For reproducibility

    # Create empty array: rows = years + 1 (starting value), columns = runs
    portfolio_values = np.zeros((time_horizon + 1, runs))
    portfolio_values[0] = initial_value

    for run in range(runs):
        for year in range(1, time_horizon + 1):
            # Random shock for each year
            z = np.random.normal()
            drift = (expected_return - 0.5 * volatility**2)
            diffusion = volatility * z
            growth_factor = np.exp(drift + diffusion)
            portfolio_values[year, run] = portfolio_values[year - 1, run] * growth_factor

    # Convert to DataFrame: rows = years, columns = run_1, run_2, ...
    years = list(range(0, time_horizon + 1))
    df_simulation = pd.DataFrame(data=portfolio_values, index=years, columns=[f"run_{i+1}" for i in range(runs)])
    df_simulation.index.name = 'year'

    return df_simulation
