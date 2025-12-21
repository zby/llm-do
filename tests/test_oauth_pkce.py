from llm_do.oauth.pkce import generate_pkce


def test_generate_pkce():
    verifier, challenge = generate_pkce()

    assert len(verifier) >= 43
    assert "+" not in verifier
    assert "/" not in verifier
    assert "=" not in verifier

    assert len(challenge) >= 43
    assert "+" not in challenge
    assert "/" not in challenge
    assert "=" not in challenge

    verifier2, challenge2 = generate_pkce()
    assert verifier != verifier2
    assert challenge != challenge2
