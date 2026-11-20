import json
import logging
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import polars as pl

from investing_algorithm_framework.domain import OperationalException
from .ohlcv_base import OHLCVDataProviderBase

logger = logging.getLogger("investing_algorithm_framework")

FXMACRODATA_API_BASE_URL = "https://api.fxmacrodata.com/v1"
# List endpoints return at most 100 rows per request, newest first.
FXMACRODATA_PAGE_SIZE = 100
FXMACRODATA_MAX_PAGES = 1000
TIMEFRAME_TO_FXMACRODATA = {
    "1d": "daily",
}


def _empty_ohlcv_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "Datetime": pl.Datetime("us", "UTC"),
            "Open": pl.Float64,
            "High": pl.Float64,
            "Low": pl.Float64,
            "Close": pl.Float64,
            "Volume": pl.Float64,
        }
    )


def _format_date(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.date().isoformat()


def _split_fx_pair(symbol: str) -> tuple[str, str]:
    normalized = "".join(char for char in symbol.upper() if char.isalpha())
    if len(normalized) != 6:
        raise OperationalException(
            "FXMacroData symbols must look like 'EURUSD' or 'EUR/USD'"
        )
    return normalized[:3], normalized[3:]


def _clean_api_key(api_key):
    if not api_key:
        return None
    api_key = str(api_key).strip()
    if any(char.isspace() or not char.isprintable() for char in api_key):
        # Keep the key itself out of the message.
        raise OperationalException(
            "FXMacroData API key contains whitespace or control characters"
        )
    return api_key or None


def _read_http_error(error: HTTPError) -> str:
    return f"FXMacroData API error {error.code}"


class FXMacroDataOHLCVDataProvider(OHLCVDataProviderBase):
    """
    Daily FX reference-rate provider backed by the FXMacroData REST API.

    FXMacroData returns one daily spot/reference value per currency pair.
    The provider exposes that value as close-only OHLCV data by setting
    Open, High, Low, and Close to the same value and Volume to 0.

    Optional API keys can be configured with MarketCredential using
    market="FXMACRODATA", or with the FXMACRODATA_API_KEY / FXMD_API_KEY
    environment variables.

    Usage:
        DataSource(
            identifier="eurusd_daily",
            market="FXMACRODATA",
            symbol="EURUSD",
            data_type="OHLCV",
            time_frame="1d",
        )
    """

    market_name = "FXMACRODATA"
    timeframe_map = TIMEFRAME_TO_FXMACRODATA
    data_provider_identifier = "fxmacrodata_ohlcv_data_provider"

    def __init__(
        self,
        *args,
        base_url: str = FXMACRODATA_API_BASE_URL,
        timeout: float = 30,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.base_url = base_url
        self.timeout = timeout

    def _validate_symbol(self, data_source) -> bool:
        try:
            _split_fx_pair(data_source.symbol)
            return True
        except Exception:
            return False

    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        self._get_provider_interval()
        base_currency, quote_currency = _split_fx_pair(symbol)

        url = (
            f"{self.base_url.rstrip('/')}/forex/"
            f"{base_currency.lower()}/{quote_currency.lower()}"
        )

        headers = {"Accept": "application/json"}
        api_key = _clean_api_key(self._get_optional_api_key())

        rows = []
        offset = 0
        for _ in range(FXMACRODATA_MAX_PAGES):
            params = {
                "start_date": _format_date(start_date),
                "end_date": _format_date(end_date),
                "limit": FXMACRODATA_PAGE_SIZE,
                "offset": offset,
            }
            request = Request(f"{url}?{urlencode(params)}", headers=headers)
            if api_key:
                # Unredirected, so urllib never forwards the key if the
                # API answers with a redirect to another host.
                request.add_unredirected_header("X-API-Key", api_key)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                error.close()
                raise OperationalException(_read_http_error(error)) from None
            except (URLError, OSError, ValueError):
                raise OperationalException("Unable to download FXMacroData data") from None

            page = payload.get("data") if isinstance(payload, dict) else None
            if (not isinstance(page, list)
                    or not all(isinstance(row, dict) for row in page)
                    or payload.get("error") or payload.get("detail")):
                raise OperationalException(
                    "FXMacroData response did not include a data list"
                )
            rows.extend(page)

            pagination = payload.get("pagination")
            if pagination is None:
                break
            if not isinstance(pagination, dict):
                raise OperationalException("FXMacroData returned invalid pagination")
            has_more = pagination.get("has_more", False)
            if type(has_more) is not bool:
                raise OperationalException("FXMacroData returned invalid pagination")
            if not has_more:
                break
            if not page:
                raise OperationalException("FXMacroData returned an empty page with more rows pending")
            next_offset = pagination.get("next_offset")
            if next_offset is None:
                next_offset = offset + len(page)
            if type(next_offset) is not int or next_offset <= offset:
                raise OperationalException("FXMacroData pagination did not advance")
            offset = next_offset
        else:
            raise OperationalException("FXMacroData pagination exceeded the page limit")

        records = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = row.get("val")
            date_value = row.get("date")
            if value is None or date_value is None:
                continue
            try:
                dt = datetime.fromisoformat(str(date_value)).replace(
                    tzinfo=timezone.utc
                )
                price = float(value)
            except (TypeError, ValueError):
                continue
            records.append(
                {
                    "Datetime": dt,
                    "Open": price,
                    "High": price,
                    "Low": price,
                    "Close": price,
                    "Volume": 0.0,
                }
            )

        if not records:
            return _empty_ohlcv_frame()

        df = pd.DataFrame(records)
        df = df.drop_duplicates("Datetime")
        df = df.sort_values("Datetime").reset_index(drop=True)
        return pl.from_pandas(
            df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

    def _get_optional_api_key(self) -> str:
        credential = self.get_credential(self.market_name)
        if credential is not None and credential.api_key:
            return credential.api_key
        return os.getenv("FXMACRODATA_API_KEY") or os.getenv("FXMD_API_KEY")

    def _storage_file_suffix(self) -> str:
        return "fxmacrodata"
