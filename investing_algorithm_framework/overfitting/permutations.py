import pandas as pd
import numpy as np

"""
Set of functions to create different OHLCV (Open, High, Low, Close, Volume)
data shuffles for permutation testing. The following set of functions help
in randomizing the data in a way that breaks meaningful structure
without completely destroying realism.
"""


def create_ohlcv_shuffle_permutation(
    data: pd.DataFrame, seed: int = None
) -> pd.DataFrame:
    """
    Shuffle entire OHLCV rows This is the simplest and most common approach:

    ✅ Preserves the candle structure (OHLC makes sense together)
    ❌ Destroys all temporal relationships

    Args:
        data (pd.DataFrame): DataFrame with OHLCV data

    Returns:
        data (pd.DataFrame): DataFrame with shuffled returns and
            reconstructed OHLCV
    """
    df = data.copy()
    df_shuffled = df.sample(frac=1, replace=False, random_state=seed)\
        .reset_index(drop=True)
    df_shuffled['Datetime'] = df['Datetime'].values
    return df_shuffled


def create_ohlcv_shuffle_returns_and_reconstruct_permutation(
    data: pd.DataFrame, seed: int = None
) -> pd.DataFrame:
    """
    Shuffle returns and reconstruct OHLCV data
    This approach preserves the overall price movement while
    breaking the original structure:

    ✅ Preserves overall price movement
    ❌ Destroys local structure (OHLC relationships)

    Args:
        data (pd.DataFrame): DataFrame with OHLCV data

    Returns:
        data (pd.DataFrame): DataFrame with shuffled returns and
            reconstructed OHLCV
    """
    rng = np.random.default_rng(seed)

    df = data.copy()
    df['return'] = df['Close'].pct_change()
    shuffled_returns = rng.permutation(df['return'].dropna().values)

    price_start = df['Close'].iloc[0]
    reconstructed_prices = [price_start]
    for r in shuffled_returns:
        reconstructed_prices.append(reconstructed_prices[-1] * (1 + r))

    df_random = df.iloc[1:].copy()
    df_random['Close'] = reconstructed_prices[1:]
    df_random['Open'] = df_random['Close'].shift(1)
    df_random['High'] = df_random[['Open', 'Close']].max(
        axis=1) * rng.uniform(1.001, 1.01, size=len(df_random))
    df_random['Low'] = df_random[['Open', 'Close']].min(
        axis=1) * rng.uniform(0.99, 0.999, size=len(df_random))
    df_random['Volume'] = rng.permutation(df['Volume'].values[1:])
    df_random['Datetime'] = df['Datetime'].values[1:]
    df_random.drop(columns=['return'], inplace=True)
    return df_random


def create_ohlcv_shuffle_block_permutation(
    data: pd.DataFrame, block_size: int = 10, seed: int = None
) -> pd.DataFrame:
    """
    Shuffle OHLCV data in blocks. This approach preserves local structure
    within blocks while breaking global relationships.

    ✅ Preserves local structure within blocks
    ❌ Destroys global relationships

    Args:
        data (pd.DataFrame): DataFrame with OHLCV data
        block_size (int): Size of the blocks to shuffle

    Returns:
        data (pd.DataFrame): DataFrame with shuffled returns and
            reconstructed OHLCV
    """
    rng = np.random.default_rng(seed)
    df = data.copy()
    blocks = [df.iloc[i:i + block_size] for i in range(0, len(df), block_size)]
    rng.shuffle(blocks)
    df_block_shuffled = pd.concat(blocks).reset_index(drop=True)
    df_block_shuffled['Datetime'] = df['Datetime'].values
    return df_block_shuffled
