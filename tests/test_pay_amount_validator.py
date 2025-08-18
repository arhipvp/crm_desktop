from PySide6.QtGui import QDoubleValidator


def test_qdouble_validator_blocks_letters():
    validator = QDoubleValidator(0.0, 1e9, 2)
    state, _, _ = validator.validate('abc', 0)
    assert state == QDoubleValidator.Invalid
