"""The preset bingo boards. Edit this file: one board per team captain (5 teams = 5 boards).

Each board has 16 phrases or behaviours that captain uses often. The server
shows them in this order as a 4x4 grid (4 per row). Keep exactly 16 per board.
"""
BOARDS = [
    {
        "id": "b1",
        "title": "Board 1",
        "phrases": [f"Board 1, phrase {i + 1}" for i in range(16)],
    },
    {
        "id": "b2",
        "title": "Board 2",
        "phrases": [f"Board 2, phrase {i + 1}" for i in range(16)],
    },
    {
        "id": "b3",
        "title": "Board 3",
        "phrases": [f"Board 3, phrase {i + 1}" for i in range(16)],
    },
    {
        "id": "b4",
        "title": "Board 4",
        "phrases": [f"Board 4, phrase {i + 1}" for i in range(16)],
    },
    {
        "id": "b5",
        "title": "Board 5",
        "phrases": [f"Board 5, phrase {i + 1}" for i in range(16)],
    },
]
