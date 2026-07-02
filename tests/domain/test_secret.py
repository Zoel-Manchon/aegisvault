from ferrovault.domain.value_objects.secret import Secret


def test_secret_redacts_in_repr_and_str():
    s = Secret("hunter2")
    assert "hunter2" not in repr(s)
    assert "hunter2" not in str(s)
    assert s.reveal() == "hunter2"


def test_secret_equality_is_value_based():
    assert Secret("a") == Secret("a")
    assert Secret("a") != Secret("b")
