"""TLS certificate verification is never disabled; a per-source ca_bundle is the only way to extend trust.

Real HTTPS on 127.0.0.1 (scripts/fixture_site.FixtureSite with tls=...), real Fetcher, no mocks.
Test certificates: fixtures/tls/ (openssl_test_certs.cnf), valid until 2126, test use only.
"""

import dataclasses
import io
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest

from scripts.fixture_site import FixtureSite
from src.config import SourceConfig, load_source_configs
from src.fetcher import Fetcher, FetchError
from src.logging_config import KeyValueFormatter
from src.runner import run_source
from src.storage import count_records

TLS = PROJECT_ROOT / "fixtures" / "tls"
SELF_SIGNED = (TLS / "selfsigned.pem", TLS / "selfsigned.key")
LEAF_ONLY = (TLS / "leaf.pem", TLS / "leaf.key")  # server sends the leaf without its intermediate, like HSS


@pytest.fixture
def log_stream():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(KeyValueFormatter())
    logger = logging.getLogger("web_monitor")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    yield stream
    logger.removeHandler(handler)


def fetcher(ca_bundle=None) -> Fetcher:
    return Fetcher(delay_s=0, logger=logging.getLogger("web_monitor.fetcher"), ca_bundle=ca_bundle)


def test_self_signed_certificate_fails_loudly_by_default(log_stream):
    with FixtureSite(tls=SELF_SIGNED) as site:
        with pytest.raises(FetchError) as exc:
            fetcher().get(site.listing_url)
        assert site.requests == []   # no HTTP request ever reached the server: no insecure retry
    assert exc.value.error_type == "SSLError"
    log = log_stream.getvalue()
    assert f"FETCH_ERROR url={site.url}/robots.txt status=none error_type=SSLError" in log
    assert "CERTIFICATE_VERIFY_FAILED" in log


def test_self_signed_certificate_succeeds_only_via_ca_bundle():
    with FixtureSite(tls=SELF_SIGNED) as site:
        result = fetcher(ca_bundle=str(SELF_SIGNED[0])).get(site.listing_url)
        assert site.requests == ["/robots.txt", "/events/seminars-and-talks"]
    assert result.status == 200 and "view-seminars-and-talks" in result.text


def test_missing_intermediate_is_fixed_by_a_bundle_with_that_intermediate(tmp_path):
    """The real HSS failure mode: the root is trusted, the server omits the intermediate."""
    root_only = str(TLS / "root_ca.pem")
    bundle = tmp_path / "bundle.pem"
    bundle.write_text((TLS / "root_ca.pem").read_text() + (TLS / "intermediate.pem").read_text())
    with FixtureSite(tls=LEAF_ONLY) as site:
        with pytest.raises(FetchError) as exc:
            fetcher(ca_bundle=root_only).get(site.listing_url)
        assert exc.value.error_type == "SSLError"
        assert fetcher(ca_bundle=str(bundle)).get(site.listing_url).status == 200


def test_tls_failure_fails_the_run_and_stores_nothing(tmp_path, log_stream):
    db = str(tmp_path / "tls.db")
    base = load_source_configs()["iit_bombay_hss_seminars"]
    with FixtureSite(tls=SELF_SIGNED) as site:
        config = dataclasses.replace(base, listing_url=site.listing_url, request_delay_s=0, ca_bundle=None)
        with pytest.raises(FetchError):
            run_source(config, db_path=db)
        trusted = run_source(dataclasses.replace(config, ca_bundle=str(SELF_SIGNED[0])), db_path=db)
    assert "FAILURE source_id=iit_bombay_hss_seminars" in log_stream.getvalue()
    assert trusted["counts"]["new"] == 20 and count_records(db) == 20


def test_config_ca_bundle_resolves_against_project_root_and_must_exist():
    config = load_source_configs()["iit_bombay_hss_seminars"]
    assert Path(config.ca_bundle) == PROJECT_ROOT / "certs" / "iitb_ca_bundle.pem"
    with pytest.raises(ValueError, match="ca_bundle not found"):
        SourceConfig(source_id="x", institution="X", adapter="a", listing_url="https://x.org",
                     ca_bundle="certs/does_not_exist.pem")


def test_iitb_bundle_contains_the_intermediate_hss_omits():
    bundle = (PROJECT_ROOT / "certs" / "iitb_ca_bundle.pem").read_text(encoding="utf-8")
    intermediate = (PROJECT_ROOT / "certs" / "globalsign_rsa_ov_ssl_ca_2018.pem").read_text(encoding="utf-8")
    pem = intermediate[intermediate.index("-----BEGIN CERTIFICATE-----"):].strip()
    assert pem in bundle
    assert bundle.count("-----BEGIN CERTIFICATE-----") > 100   # certifi roots are still there
