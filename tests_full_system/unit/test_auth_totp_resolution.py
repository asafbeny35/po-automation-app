from __future__ import annotations

import time

import pyotp

from services.auth import resolve_totp_user, verify_totp_code


def test_resolve_totp_user_matches_requested_user_when_code_matches() -> None:
    state = {
        "default_user_id": "asaf",
        "users": {
            "asaf": {
                "id": "asaf",
                "display_name": "אסף",
                "totp_enabled": True,
                "totp_secret": "Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ",
            },
            "mom": {
                "id": "mom",
                "display_name": "אמא",
                "totp_enabled": True,
                "totp_secret": "MI4CGSDTQN6CT3PMEKAH2WHQW3USSWKQ",
            },
        },
    }

    code = pyotp.TOTP("Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ").now()

    matched_user = resolve_totp_user(state, code, "asaf")

    assert matched_user is not None
    assert matched_user["id"] == "asaf"
    assert verify_totp_code(state, code, "asaf") is True


def test_resolve_totp_user_falls_back_to_actual_matching_user_if_selection_is_wrong() -> None:
    state = {
        "default_user_id": "asaf",
        "users": {
            "asaf": {
                "id": "asaf",
                "display_name": "אסף",
                "totp_enabled": True,
                "totp_secret": "Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ",
            },
            "mom": {
                "id": "mom",
                "display_name": "אמא",
                "totp_enabled": True,
                "totp_secret": "MI4CGSDTQN6CT3PMEKAH2WHQW3USSWKQ",
            },
        },
    }

    moms_code = pyotp.TOTP("MI4CGSDTQN6CT3PMEKAH2WHQW3USSWKQ").now()

    matched_user = resolve_totp_user(state, moms_code, "asaf")

    assert matched_user is not None
    assert matched_user["id"] == "mom"
    assert verify_totp_code(state, moms_code, "asaf") is True


def test_verify_totp_code_accepts_digit_groups_with_spaces() -> None:
    state = {
        "default_user_id": "asaf",
        "users": {
            "asaf": {
                "id": "asaf",
                "display_name": "אסף",
                "totp_enabled": True,
                "totp_secret": "Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ",
            },
        },
    }

    code = pyotp.TOTP("Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ").now()
    spaced_code = f"{code[:3]} {code[3:]}"

    assert verify_totp_code(state, spaced_code, "asaf") is True


def test_verify_totp_code_allows_slightly_larger_clock_skew() -> None:
    state = {
        "default_user_id": "asaf",
        "users": {
            "asaf": {
                "id": "asaf",
                "display_name": "אסף",
                "totp_enabled": True,
                "totp_secret": "Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ",
            },
        },
    }

    skewed_code = pyotp.TOTP("Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ").at(int(time.time()) - 60)

    assert verify_totp_code(state, skewed_code, "asaf") is True
