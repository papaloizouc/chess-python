import moves

#TODO re-write (broken after refactoring)
assert moves._knight(5, 4) == {(7, 3), (7, 5), (3, 3), (6, 6), (6, 2), (4, 2), (3, 5), (4, 6)}
assert moves._rook(5, 5) == {(5, 4), (1, 5), (5, 6), (5, 7), (4, 5), (7, 5), (0, 5), (5, 0), (5, 1), (2, 5), (3, 5), (5, 2), (6, 5), (5, 3)}
assert moves._bishop(2, 2) == {(1, 3), (3, 3), (6, 6), (5, 5), (3, 1), (4, 4), (7, 7), (0, 0), (0, 4), (1, 1), (4, 0)}


assert moves.pawn((1,1),(2,2),{},"w","w") == {(1, 2), (1, 3)}
assert moves.pawn((1,7),(1,6),{},"w","b") == {(1, 5), (1, 6)}
assert moves.pawn((1,7),(1,6),{},"w","w") == set()