"""Tests for topic classification."""

from __future__ import annotations

from src.rv.classifier import Topic, classify_kalshi, classify_polymarket, clear_overrides_cache


class TestClassifyKalshi:
    def setup_method(self):
        clear_overrides_cache()

    def test_sports_nfl(self):
        assert classify_kalshi("NFLGAME-CHIEFS-BILLS") == Topic.SPORTS

    def test_sports_nba(self):
        assert classify_kalshi("NBAGAME-LAL-BOS") == Topic.SPORTS

    def test_weather_high_temp(self):
        assert classify_kalshi("HIGHNY-2026-02-21") == Topic.WEATHER

    def test_weather_rain(self):
        assert classify_kalshi("RAINNYC-2026-02") == Topic.WEATHER

    def test_finance_fed(self):
        assert classify_kalshi("FEDDECISION-MAR-2026") == Topic.MACRO

    def test_finance_cpi(self):
        assert classify_kalshi("CPIYOY-JAN-2026") == Topic.MACRO

    def test_crypto_btc(self):
        assert classify_kalshi("BTCD-2026-02-21") == Topic.CRYPTO

    def test_politics_pres(self):
        assert classify_kalshi("PRES-2028-PARTY") == Topic.POLITICS

    def test_entertainment_oscar(self):
        assert classify_kalshi("OSCARPIC-2026") == Topic.ENTERTAINMENT

    def test_unknown_falls_to_other(self):
        assert classify_kalshi("XYZUNKNOWN-123") == Topic.OTHER

    def test_empty_event_ticker_with_title_fallback(self):
        result = classify_kalshi("", title="Will the Fed cut rates in March?")
        assert result == Topic.MACRO

    def test_empty_everything(self):
        assert classify_kalshi("") == Topic.OTHER


class TestClassifyPolymarket:
    def setup_method(self):
        clear_overrides_cache()

    def test_weather(self):
        assert classify_polymarket("Will the temperature exceed 100F in Phoenix?") == Topic.WEATHER

    def test_sports(self):
        assert classify_polymarket("Will the Lakers win the NBA championship?") == Topic.SPORTS

    def test_macro(self):
        assert classify_polymarket("Will the Fed cut interest rates in March 2026?") == Topic.MACRO

    def test_crypto(self):
        assert classify_polymarket("Will Bitcoin exceed $200,000 by end of 2026?") == Topic.CRYPTO

    def test_politics(self):
        assert classify_polymarket("Will the Democrats win the Senate?") == Topic.POLITICS

    def test_entertainment(self):
        assert classify_polymarket("Will Oppenheimer win the Oscar for Best Picture?") == Topic.ENTERTAINMENT

    def test_unknown(self):
        assert classify_polymarket("Something completely unrelated") == Topic.OTHER
