import hashlib
import json
from pathlib import Path

DATA = Path("ipakit/data/attested/miller_nicely_1955.json")
SHA256 = "2aae1951a0f6495179279d99d8f9e7e53b234b9c1a5311285430b608439dc337"


def test_miller_nicely_matrix_is_pinned_and_symmetric() -> None:
    raw = DATA.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA256
    payload = json.loads(raw)
    matrix = payload["matrix"]
    assert len(payload["inventory"]) == len(matrix) == 16
    assert all(len(row) == 16 for row in matrix)
    assert all(matrix[index][index] == 0 for index in range(16))
    assert all(
        matrix[row][column] == matrix[column][row]
        for row in range(16)
        for column in range(16)
    )
    assert all(0 <= value <= 1 for row in matrix for value in row)
