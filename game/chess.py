from copy import deepcopy
from itertools import product, chain
from functools import wraps
from math import fabs
from abc import ABCMeta, abstractmethod
from collections import OrderedDict

"""
Board holds the state of the game only.
GameEngine holds a Board.
game_engine.move moves the pieces:
    1) finds the piece on board.
    2) calls get move on the piece (returns extends AbstractMove objecet)
    3) calls move.execute
    4) moves have post_exec func to check if after moving the king is under attacked
    5) if post_exec the move was succesful else post_exec will undo the move which makes it invalid
"""

color_change = {"W": "B", "B": "W"}


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


class GameEngine:

    """
        Creates and executes move. The only class changing state on pieces and board.
        The main idea is to keep mutation controlled in one place
    """

    def __init__(self, board):
        """
        @param board: Board
        """
        self.board = board
        self.moves = []
        self.undone_moves = []

    @staticmethod
    def square_attacked(end: tuple, board):
        opposite_color = color_change[board.turn]
        opposite_team = board.get_pieces(opposite_color)
        opposite_attackers = [piece.check_move(end, board)
                              for piece in opposite_team if not isinstance(piece, King)]
        return len([move for move in opposite_attackers if move]) >= 1

    @staticmethod
    def king_attacked(board):
        # todo refactor cache pieces
        king = board.get_king(board.turn)
        return GameEngine.square_attacked(king.position, board)

    def _move(self, move):
        """
            Executes the move
        @param move: AbstractMove
        @return: True if move was valid
        """
        move.exec(self.board)
        if move.post_exec(self.board):
            self.board.flip_color()
            self.moves.append(move)
            return True

    def move(self, start: tuple, end: tuple, player: str):
        if player is not self.board.turn:
            raise Exception("Its not your turn. Given %s expected %s" % (player, self.board.turn))
        piece = self.board[start]
        if not piece:
            return False
        move = piece.get_move(end, self.board)
        if not move:
            return False
        return self._move(move)

    def undo(self, move=None):
        if not move:
            move = self.moves.pop()
        move.undo(self.board)
        self.undone_moves.append(move)
        self.board.flip_color()


class AbstractMove:
    __metaclass__ = ABCMeta

    @abstractmethod
    def exec(self, board):
        """
            Execute the move
        @param board: Board
        """
        pass

    @abstractmethod
    def undo(self, board):
        """
            Undo the mvoe
        @param board: Board
        """
        pass

    @abstractmethod
    def post_exec(self, board):
        """
            Check if after executing the king is under attack. If it is undo
        @param board: Board
        """
        pass


class Piece(object):
    __metaclass__ = ABCMeta

    def __init__(self, color: str, position: tuple):
        self.color = color
        self.position = position
        self.find_cache = {}
        self.moved = 0

    def __eq__(self, other) -> bool:
        if not other or not isinstance(other, self.__class__):
            return False
        return self.position == other.position and self.color is other.color

    def __hash__(self):
        return hash(" ".join(map(str, [self.position, self.color])))

    @abstractmethod
    def find(self, x: int, y: int, board=None):
        """
            Find all "logical moves"
        @param x: int end x
        @param y: int end y
        @param board: Board
        """
        pass

    @abstractmethod
    def check_move(self, end: tuple, board) ->set:
        """
            Checks if "logical moves" generated in find are legal
        @param end: tuple endpoint
        @param board: Board
        """
        pass

    def get_move(self, end: tuple, board) -> AbstractMove:
        """
            Get the a Move object if the move was legal
        @param end: tuple endpoint
        @param board: Board
        @return AbstractMove
        """
        if self.check_move(end, board):
            return Move(self, end)
        return False

    def increase_moves(self):
        self.moved += 1

    def decrease_moves(self):
        self.moved -= 1

    def update_position(self, position):
        self.position = position

    def __repr__(self):
        return "%s %s" % (self.color, type(self).__name__,)

    def __str__(self):
        return "%s %s" % (repr(self), str(self.position))


class Move(AbstractMove):

    def __init__(self, piece: Piece, end: tuple):
        self.piece = deepcopy(piece)
        self.start = piece.position
        self.end = end
        self.killed = None

    def __hash__(self):
        return hash(" ".join(map(str, self.piece, self.start, self.end, self.killed)))

    def __eq__(self, other):
        if not other or not isinstance(other, self.__class__):
            return False
        return self.__dict__ == other.__dict__

    def __repr__(self):
        return "%s -> moved from: %s killed: %s" % (self.piece, self.start, self.killed)

    def exec(self, board):
        board[self.piece.position] = None  # remove the piece from the board
        self.piece.update_position(self.end)  # move the piece
        if board[self.end]:  # kill previous piece if existed
            self.killed = board[self.end]
            board.killed.append(self.killed)
        board[self.end] = self.piece  # make the move on the board
        self.piece.increase_moves()

    def undo(self, board):
        board[self.start] = self.piece
        self.piece.update_position(self.start)
        board[self.end] = self.killed
        # self.piece.decrease_moves()

    def post_exec(self, board):
        if GameEngine.king_attacked(board):
            self.undo(board)
        else:
            return True


class CastlingMove(AbstractMove):

    def __init__(self, castling):
        """
            Castling is a special moves and needs to be implemented separate
            because its the only case two pieces move at once
        @param castling: Castling
        """
        self.king = deepcopy(castling.king)
        self.rook_start = castling.rook_start
        self.king_start = deepcopy(self.king.position)
        self.squares = castling.squares
        self.king_end = castling.king_end
        self.rook_end = castling.rook_end
        self.rook = None
        #self.rook_x = 3 if self.king_end == 2 else 5

    def exec(self, board):
        self.rook = deepcopy(board[self.rook_start])

        board[self.rook.position] = None
        board[self.king.position] = None

        board[self.rook_end] = self.rook
        board[self.king_end] = self.king

        self.rook.update_position(self.rook_end)
        self.king.update_position(self.king_end)

        self.king.increase_moves()
        self.rook.increase_moves()

    def undo(self, board):
        board[self.king_end] = None
        board[self.rook_end] = None

        board[self.king_start] = self.king
        board[self.rook_start] = self.rook

        self.king.update_position(self.king_start)
        self.rook.update_position(self.rook_start)

    def post_exec(self, board):
        return True


class Rook(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board=None):
        return {(x, i) for i in range(0, 8)}.union({(i, y) for i in range(0, 8)})

    @Math.check_blocks
    @Math.filter_line
    def check_move(self, end: tuple, board):
        return self.find(*self.position)


class Bishop(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board=None):
        possible = lambda k: [
            (x + k, y + k), (x + k, y - k), (x - k, y + k), (x - k, y - k)]
        return {j for i in range(1, 8) for j in possible(i)}

    @Math.check_blocks
    @Math.filter_line
    def check_move(self, end: tuple, board):
        return self.find(*self.position)


class Knight(Piece):

    @Math.clean_moves
    def find(self, x: int, y: int, board=None):
        moves = chain(product([x - 1, x + 1], [y - 2, y + 2]),
                      product([x - 2, x + 2], [y - 1, y + 1]))
        return set(moves)

    @Math.check_blocks
    def check_move(self, end: tuple, board):
        return self.find(*self.position)


class Pawn(Piece):

    def __init__(self, color: str, position: tuple, player_down: str):
        super(Pawn, self).__init__(color, position)
        self.y_initial, self.y_add = (6, -1) if self.color is player_down else (1, 1)

    #@Math.clean_moves
    def find(self, x: int, y: int, board=None) -> set:
        # TODO test kill moves, add en passant and --cache--
        non_kill = self._find_non_kill_moves(x, y, board=board)
        kill = self._kill_moves(x, y, board=board)
        return non_kill.union(kill)

    def _kill_moves(self, x: int, y: int, board):
        x1, x2 = x - 1, x + 1
        positions = [(x1, y + self.y_add), (x2, y + self.y_add)]
        pieces = [board[position] for position in positions if Math.check_range(position)]
        return {piece.position for piece in pieces
                if piece and piece.color is not self.color
                }

    def _find_non_kill_moves(self, x: int, y: int, board) ->set:
        """
            The pawn case has to be processed in different way because it can't kill when moving forward.
        @param board: the board
        @return:
        """
        non_kill_moves = set()
        move_a = (x, y + self.y_add)
        # just check if the square is empty
        if board[move_a] is None:
            non_kill_moves.add(move_a)
        # check that two squares are empty
        if y is self.y_initial:
            move_b = (x, y + self.y_add * 2)
            piece_a = board[move_b]
            piece_b = board[(move_b[0], move_b[1] - self.y_add)]
            if not (piece_a, piece_b) != (None, None):
                non_kill_moves.add(move_b)
        return non_kill_moves

    def check_move(self, end: tuple, board):
        moves = self.find(*self.position, board=board)
        if end in moves:
            return moves
        return False


class Castling:

    def __init__(self, y: int, start: int, end: int, king: Piece):
        self.squares = [(x, y) for x in range(start, end)]
        rook_x = 0 if start == 1 else 7
        self.rook_start = (rook_x, king.position[1])
        self.king = king
        king_end_x = 2 if start == 1 else 6
        rook_end_x = 3 if start == 1 else 5
        self.king_end = (king_end_x, king.position[1])
        self.rook_end = (rook_end_x, king.position[1])

    def is_valid(self, board):
        if GameEngine.king_attacked(board):
            return False
        # check if castling is blocked
        for square in self.squares:
            if board[square] is not None or GameEngine.square_attacked(square, board):
                return False
        # check if pieces have been moved previously
        if not(board[self.rook_start].moved is 0 or self.king.moved is 0):
            return False

        return self


class King(Piece):

    def __init__(self, color: str, position: tuple):
        super(King, self).__init__(color, position)
        y = self.position[1]
        self.castling = {((4, y), (2, y)): Castling(y, 1, 4, self),
                         ((4, y), (6, y)): Castling(y, 5, 7, self)}

    def is_castling(self, end: tuple, board):
        possible_castling = (self.position, end)
        if not possible_castling in self.castling:
            return False
        castling = self.castling[possible_castling]
        return castling.is_valid(board)

    def get_castling_moves(self, board) -> set:
        moves = set()
        for positions in self.castling.keys():
            self.is_castling(positions[1], board)
            moves.add(positions[1])
        return moves

    @Math.clean_moves
    def find(self, x: int, y: int, board=None):
        normal_moves = set(product([x - 1, x + 1, x], [y + 1, y - 1, y]))
        castling_moves = self.get_castling_moves(board)
        return normal_moves.union(castling_moves)

    @Math.check_blocks
    def check_move(self, end: tuple, board):
        return self.find(*self.position, board=board)

    def get_move(self, end: tuple, board):
        castling = self.is_castling(end, board)
        if not castling:
            return super(King, self).get_move(end, board)
        else:
            return CastlingMove(castling)


class Queen(Piece):

    def __init__(self, color: str, position: tuple):
        super(Queen, self).__init__(color, position)
        self._rook = Rook(color, position)
        self._bishop = Bishop(color, position)

    def update_position(self, position):
        self.position = position
        self._rook.position = position
        self._bishop.position = position

    def find(self, x: int, y: int, board=None):
        return self._bishop.find(x, y).union(self._rook.find(x, y))

    @Math.filter_line
    def check_move(self, end: tuple, board):
        return self.find(*self.position)


class Board(OrderedDict):

    """
        Holds the state but has no logic. All logic is done in GameEngine
    """

    def __init__(self, player_down: str="W", create: bool=False):
        super(Board, self).__init__()
        self.player_down = player_down
        self.killed = []
        self.turn = "W"
        board = {i: None for i in product(range(0, 8), range(0, 8))}
        self.update(sorted(board.items(), key=lambda x: x[0][0] + ((1 + x[0][1]) * 100)))
        if create:
            self.create()

    def __eq__(self, other) -> bool:
        if not other or not isinstance(other, self.__class__):
            return False
        return self.get_pieces("W") == other.get_pieces("W") \
            and self.get_pieces("B") == other.get_pieces("B") \
            and self.killed == other.killed \
            and self.player_down == other.player_down \
            and self.turn == other.turn

    def create(self):
        self._add_pawns(1)
        self._add_pawns(6)
        self._add_other(0)
        self._add_other(7)

    def flip_color(self):
        self.turn = color_change[self.turn]

    def get_king(self, color: str) -> Piece:
        return [piece for piece in self.get_pieces(color) if isinstance(piece, King)][0]

    def get_pieces(self, color: str):
        # todo cache after moves
        return {piece for position, piece in self.items() if piece and piece.color is color}

    def _color_picker(self, index: int):
        if self.player_down is "W":
            return "W" if index > 3 else "B"
        elif self.player_down is "B":
            return "B" if index > 3 else "W"
        else:
            raise TypeError("player down must be W or B")

    def _get_row(self, y: int) -> tuple:
        """
            Return the whole row as a generator(filter) and a color for the row
        @param y: y position of the row
        @return: (row,color)
        """
        return filter(lambda x: x[1] is y, self.keys()), self._color_picker(y)

    def _add_pawns(self, y: int):
        positions, color = self._get_row(y)
        for i in positions:
            self[i] = Pawn(color, i, self.player_down)

    def _add_other(self, y: int):
        positions, color = self._get_row(y)
        pieces = [Rook, Knight, Bishop, Queen, King, Bishop, Knight, Rook]
        for count, i in enumerate(positions):
            self[i] = pieces[count](color, i)

    def __repr__(self):
        spaces_count = 15
        spaces = spaces_count * " "
        to_join = []
        # top row numbers (x)
        to_join.extend(["  ", spaces.join(map(str, range(0, 8))), "\n"])
        for position, piece in self.items():
            to_print = repr(piece) if piece else ""
            # start of row print y
            if position[0] == 0:
                to_join.append("%i  " % position[1])
            # print content with spaces
            to_join.append(to_print)
            to_join.append(" " * (spaces_count + 1 - len(to_print)))
            # end of row print new line
            if position[0] == 7:
                to_join.append("\n")
        return "".join(to_join)



        # 0y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 1y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 2y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 3y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 4y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 5y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 6y [0, 1, 2, 3, 4, 5, 6, 7]x
        # 7y [0, 1, 2, 3, 4, 5, 6, 7]x
