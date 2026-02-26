"""Tests for src/rv/info_efficiency.py."""

from __future__ import annotations

import pytest

from src.rv.info_efficiency import (
    BackingSource,
    EdgeOpportunity,
    _rate_info_efficiency,
)


# ─── Helper ───────────────────────────────────────────────────────────────────


def rate(title: str = "", event_group: str = "", topic: str = "other"):
    return _rate_info_efficiency(title=title, event_group=event_group, topic=topic)


# ─── CME FedWatch ─────────────────────────────────────────────────────────────


class TestFedWatch:
    def test_macro_topic(self):
        r = rate(title="Will the Fed cut rates in March?", topic="macro")
        assert r.backing_source == BackingSource.CME_FEDWATCH
        assert r.edge_opportunity == EdgeOpportunity.VERY_LOW

    def test_fomc_keyword(self):
        r = rate(title="FOMC rate decision 2026")
        assert r.backing_source == BackingSource.CME_FEDWATCH

    def test_fed_keyword(self):
        r = rate(title="Will the fed hold rates steady?")
        assert r.backing_source == BackingSource.CME_FEDWATCH

    def test_interest_rate_keyword(self):
        r = rate(title="Interest rate above 5% by June?")
        assert r.backing_source == BackingSource.CME_FEDWATCH

    def test_rate_cut_keyword(self):
        r = rate(title="Rate cut of 25 basis points in May?")
        assert r.backing_source == BackingSource.CME_FEDWATCH

    def test_feddecision_event_group(self):
        r = rate(title="≥25bp cut", event_group="FEDDECISION-2026-MAR", topic="macro")
        assert r.backing_source == BackingSource.CME_FEDWATCH


# ─── Crypto Exchanges ─────────────────────────────────────────────────────────


class TestCrypto:
    def test_crypto_topic(self):
        r = rate(title="Will Bitcoin hit $100k?", topic="crypto")
        assert r.backing_source == BackingSource.CRYPTO_EXCHANGES
        assert r.edge_opportunity == EdgeOpportunity.VERY_LOW

    def test_btc_keyword(self):
        r = rate(title="BTC price above $80,000 by end of March")
        assert r.backing_source == BackingSource.CRYPTO_EXCHANGES

    def test_ethereum_keyword(self):
        r = rate(title="Ethereum ETH ATH in 2026?")
        assert r.backing_source == BackingSource.CRYPTO_EXCHANGES

    def test_nft_keyword(self):
        r = rate(title="NFT market cap above $50bn?")
        assert r.backing_source == BackingSource.CRYPTO_EXCHANGES


# ─── Sports Books ─────────────────────────────────────────────────────────────


class TestSports:
    def test_major_sports_topic_nba(self):
        r = rate(title="Will the Lakers win the NBA Finals?", topic="sports")
        assert r.backing_source == BackingSource.SPORTS_BOOKS
        assert r.edge_opportunity == EdgeOpportunity.LOW

    def test_major_sports_nfl(self):
        r = rate(title="Super Bowl winner 2026", topic="sports")
        assert r.backing_source == BackingSource.SPORTS_BOOKS
        assert r.edge_opportunity == EdgeOpportunity.LOW

    def test_major_sports_world_cup(self):
        r = rate(title="World Cup winner 2026", topic="sports")
        assert r.backing_source == BackingSource.SPORTS_BOOKS
        assert r.edge_opportunity == EdgeOpportunity.LOW

    def test_major_sports_ufc(self):
        r = rate(title="UFC 300 main event winner", topic="sports")
        assert r.backing_source == BackingSource.SPORTS_BOOKS
        assert r.edge_opportunity == EdgeOpportunity.LOW

    def test_minor_sports_no_major_keywords(self):
        r = rate(title="Will player score 20 points tonight?", topic="sports")
        assert r.backing_source == BackingSource.SPORTS_BOOKS
        assert r.edge_opportunity == EdgeOpportunity.MEDIUM

    def test_minor_sports_esports_no_league_keyword(self):
        r = rate(title="Will Team A win the regional qualifier?", topic="sports")
        assert r.edge_opportunity == EdgeOpportunity.MEDIUM


# ─── Weather Models ───────────────────────────────────────────────────────────


class TestWeather:
    def test_weather_topic(self):
        r = rate(title="NYC daily high temperature above 90°F on July 4?", topic="weather")
        assert r.backing_source == BackingSource.WEATHER_MODELS
        assert r.edge_opportunity == EdgeOpportunity.MEDIUM

    def test_hurricane_keyword(self):
        r = rate(title="Will a hurricane hit Florida in 2026?")
        assert r.backing_source == BackingSource.WEATHER_MODELS

    def test_snowfall_keyword(self):
        r = rate(title="Will Boston get more than 10 inches of snow this winter?")
        assert r.backing_source == BackingSource.WEATHER_MODELS

    def test_temperature_keyword(self):
        r = rate(title="Temperature in Phoenix above 110 degrees Fahrenheit?")
        assert r.backing_source == BackingSource.WEATHER_MODELS


# ─── Entertainment — no reference ─────────────────────────────────────────────


class TestEntertainment:
    def test_grammy(self):
        r = rate(title="Grammy Award for Album of the Year 2026", topic="entertainment")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH

    def test_oscar(self):
        r = rate(title="Best Picture Oscar winner 2026?")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH

    def test_emmy(self):
        r = rate(title="Emmy Award Best Drama Series 2026")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH

    def test_entertainment_topic(self):
        r = rate(title="Will Taylor Swift release a new album in 2026?", topic="entertainment")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH

    def test_box_office_keyword(self):
        r = rate(title="Will the movie gross $500M box office?")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH

    def test_reality_tv(self):
        r = rate(title="Who will win Survivor Season 48?")
        assert r.backing_source == BackingSource.NONE
        assert r.edge_opportunity == EdgeOpportunity.HIGH


# ─── Polling / Politics ───────────────────────────────────────────────────────


class TestPolitics:
    def test_politics_topic(self):
        r = rate(title="Will Democrats win the Senate in 2026?", topic="politics")
        assert r.backing_source == BackingSource.POLLING_AGGREGATORS
        assert r.edge_opportunity == EdgeOpportunity.MEDIUM

    def test_election_keyword(self):
        r = rate(title="2026 midterm election — House majority?")
        assert r.backing_source == BackingSource.POLLING_AGGREGATORS

    def test_approval_rating(self):
        r = rate(title="Will presidential approval rating exceed 50%?")
        assert r.backing_source == BackingSource.POLLING_AGGREGATORS

    def test_senate_keyword(self):
        r = rate(title="Will the senate pass the budget bill?")
        assert r.backing_source == BackingSource.POLLING_AGGREGATORS


# ─── Fallback / unknown ───────────────────────────────────────────────────────


class TestFallback:
    def test_unknown_topic_other(self):
        r = rate(title="Will Elon Musk step down from Tesla board?", topic="other")
        assert r.edge_opportunity == EdgeOpportunity.MEDIUM  # unknown → medium

    def test_empty_inputs(self):
        r = rate()
        assert r.backing_source == BackingSource.NONE  # no match → fallback


# ─── Precedence: macro beats sports ───────────────────────────────────────────


class TestPrecedence:
    def test_fed_title_beats_sports_topic(self):
        # If title mentions fed, even with sports topic, should classify as Fed
        r = rate(title="Will the federal funds rate be above 5%?", topic="sports")
        assert r.backing_source == BackingSource.CME_FEDWATCH

    def test_crypto_title_beats_entertainment(self):
        r = rate(title="Will Bitcoin ETH hit $100k before Oscars?", topic="entertainment")
        assert r.backing_source == BackingSource.CRYPTO_EXCHANGES
