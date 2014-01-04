from itertools import product, chain
from functools import wraps
from math import fabs
from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import game


class Math:

    @staticmethod
    def check_range(move: tuple, min_=0, max_=8) -> bool:
        """
            Check if a point is within a range. The default range is 0,8.
        @param move: The move to check
        @param min_: Minimum allowed value of the point (included)
        @param max_: Maximum allowed value of the point (excluded)
        @return: True if in range else False
        """
        return min_ <= move[0] < max_ and min_ <= move[1] < max_

    @staticmethod
    def slope(start: tuple, end: tuple) -> int:
        """
            For the math formula of the line.
        @return: slope int
        """
        return Math.safe_divide(start[1] - end[1], start[0] - end[0], default="vertical")

    @staticmethod
    def line(end: tuple, slope: int=None, start: tuple=None) -> callable:
        """
            Line math formula
        @param slope: Slope for line as generated by _slope
        @return: lambda expression representing the line
        """

        if not (slope, start) != ("vertical", None):
            raise TypeError("_line takes either a slope(int) or a start(tuple)")
        if start:
            slope = Math.slope(start, end)
        if slope is "vertical":  # vertical line
            return lambda x, y: x is end[0]
        return lambda x, y: y - end[1] is slope * (x - end[0])

    @staticmethod
    def safe_divide(a: int, b: int, default=0) -> int:
        """
            Return 0 if dividing by 0
        """
        a, b = map(int, [a, b])
        if b is 0:
            return default
        return int(a / b)

    @staticmethod
    def diff_points(start: tuple, end: tuple) -> tuple:
        """
            Calculate a tuple to identify how we move.
            For (3,3),(5,5) will return (-1,-1) identifying that both x and y increase
            (3, 3) (0, 0) will return  (1, 1) identifying that both x and y decrease
        """
        x = start[0] - end[0]
        y = start[1] - end[1]
        return Math.safe_divide(x, fabs(x)), Math.safe_divide(y, fabs(y))

    @staticmethod
    def end_point_check(diff: tuple) -> callable:
        """
            Return lambda to check the endpoint. If moving down the move must be >= than end point else <= than endpoint
        @param diff: Difference of points as produced by _diff_points
        @return: lambda to check if endpoint is in range
        """
        if -1 in (diff[0], diff[1]):
            return lambda move, end: move <= end
        else:
            return lambda move, end: move >= end

    @staticmethod
    def clean_moves(f):
        @wraps(f)
        def wrapper(self, *args, **kwargs):
            x, y = args
            # all-ready calculated, exists in cache
            if (x, y) in self.find_cache:
                return self.find_cache[(x, y)]

            moves = f(self, *args, **kwargs)
            moves = {move for move in moves if Math.check_range(move)} - {args}
            self.find_cache[(x, y)] = moves
            return moves

        return wrapper

    @staticmethod
    def filter_line(f):
        """
           Wraps move functions from piece.
           Gets all the possible moves and checks if they are on the same line.
           Then it removes all points not in range (bigger than end).
           Works for rook and bishop
        """

        @wraps(f)
        def wrapper(self, *args, **kwargs):
            moves = f(self, *args, **kwargs)
            # get start/end points from object
            start, end = self.position, args[0]
            # get the line formula as a callable
            in_line = Math.line(end, start=start)
            # calculate the diff of start and end
            diff = Math.diff_points(start, end)
            # make sure the point is bigger than start and smaller than end
            # start 3,3 end 5,5 -> 2,2 is not bigger than start 6,6 is not bigger
            # than end
            start_check = lambda _move: Math.diff_points(start, _move) == diff
            end_check = Math.end_point_check(diff)
            moves = {move for move in moves
                     if in_line(*move) and start_check(move) and end_check(move, end)
                     }
            return moves

        return wrapper

    @staticmethod
    def check_blocks(f):
        """
            Check if there's any pieces blocking the way to move.
            Also check if the end square is empty or has enemy piece
        """

        @wraps(f)
        def wrapper(*args, **kwargs):
            moves = f(*args, **kwargs)
            piece, end, board = args
            item_at_end = board[end]
            # all-ready invalid
            if not moves or end not in moves:
                return False
                # check if no items block the way. last square can have an item from opposite team
            blocked = len({i for i in moves if board[i] is None}) not in (len(moves), len(moves) - 1)
            last_item_invalid = item_at_end is not None and piece.color is item_at_end.color
            # Knight and king don't need blocked validation
            if not (blocked or last_item_invalid) or \
                    (piece.__class__ in (Knight, King) and not last_item_invalid):
                return moves

        return wrapper


class Piece(object):
    __metaclass__ = ABCMeta

    def __init__(self, color: str, position: tuple):
        self.color = color
        self.position = position
        self.find_cache = {}

    def __eq__(self, other) -> bool:
        if not other or not isinstance(other, self.__class__):
            return False
        return self.position == other.position and self.color is other.color

    def __hash__(self):
        return hash(" ".join(map(str, [self.position, self.color])))

    @abstractmethod
    def find(self, x: int, y: int, board: OrderedDict=None):
        pass

    @abstractmethod
    def check_move(self, end: tuple, board: OrderedDict) ->set:
        pass

    def update_position(self, position):
        self.position = position

    def __repr__(self):
        return "%s %s" % (self.color, type(self).__name__,)

    def __str__(self):
        return "%s %s" % (repr(self), str(self.position))


class Rook(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board: OrderedDict=None):
        return {(x, i) for i in range(0, 8)}.union({(i, y) for i in range(0, 8)})

    @Math.check_blocks
    @Math.filter_line
    def check_move(self, end: tuple, board: OrderedDict):
        return self.find(*self.position)


class Bishop(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board: OrderedDict=None):
        possible = lambda k: [
            (x + k, y + k), (x + k, y - k), (x - k, y + k), (x - k, y - k)]
        return {j for i in range(1, 8) for j in possible(i)}

    @Math.check_blocks
    @Math.filter_line
    def check_move(self, end: tuple, board: OrderedDict):
        return self.find(*self.position)


class Knight(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board: OrderedDict=None):
        moves = chain(product([x - 1, x + 1], [y - 2, y + 2]),
                      product([x - 2, x + 2], [y - 1, y + 1]))
        return set(moves)

    @Math.check_blocks
    def check_move(self, end: tuple, board: OrderedDict):
        return self.find(*self.position)


class Pawn(Piece):

    def __init__(self, color: str, position: tuple, player_down: str):
        super(Pawn, self).__init__(color, position)
        self.y_initial, self.y_add = (6, -1) if self.color is player_down else (1, 1)

    #@Math.clean_moves
    def find(self, x: int, y: int, board: OrderedDict=None) -> set:
        # TODO kill moves (en passant, up left and up down) and --cache--
        non_kill = self._find_non_kill_moves(x, y, board=board)
        return non_kill

    def _find_non_kill_moves(self, x: int, y: int, board: OrderedDict) ->set:
        """
            The pawn case has to be processed in different way because it can't kill when moving forward.
        @param board: the board
        @return:
        """
        filtered_forward_moves = set()
        move_a = (x, y + self.y_add)
        # just check if the square is empty
        if board[move_a] is None:
            filtered_forward_moves.add(move_a)
        # check that two squares are empty
        if y is self.y_initial:
            move_b = (x, y + self.y_add * 2)
            if not (board[move_b], board[(move_b[0], move_b[1] - self.y_add)]) != (None, None):
                filtered_forward_moves.add(move_b)
        return filtered_forward_moves

    def check_move(self, end: tuple, board: OrderedDict):
        moves = self.find(*self.position, board=board)
        if end in moves:
            return moves
        return False


class King(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board: OrderedDict=None):
        return product([x - 1, x + 1, x], [y + 1, y - 1, y])

    @Math.check_blocks
    def check_move(self, end: tuple, board: OrderedDict):
        return self.find(*self.position)


class Queen(Piece):

    def __init__(self, color: str, position: tuple):
        super(Queen, self).__init__(color, position)
        self._rook = Rook(color, position)
        self._bishop = Bishop(color, position)

    def update_position(self, position):
        self.position = position
        self._rook.position = position
        self._bishop.position = position

    def find(self, x: int, y: int, board: OrderedDict=None):
        return self._bishop.find(x, y).union(self._rook.find(x, y))

    @Math.filter_line
    def check_move(self, end: tuple, board: OrderedDict):
        return self.find(*self.position)

        # 0y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 1y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 2y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 3y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 4y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 5y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 6y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 7y [0, 1, 2, 3, 4, 5, 6, 7]x
