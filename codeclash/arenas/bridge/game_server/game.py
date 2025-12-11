"""Core Bridge game logic."""
import uuid

from deck import compare_cards, get_suit, shuffle_and_deal
from scoring import calculate_contract_score, get_declarer_team, normalize_to_vp


class BridgeGame:
    """
    Bridge game state manager.

    Manages a complete Bridge game from bidding through playing to scoring.
    Handles 4 players in fixed partnerships (NS vs EW).
    """

    def __init__(self, seed: int = None, dealer: int = 0, vulnerability: dict[str, bool] = None):
        self.game_id = str(uuid.uuid4())[:8]
        self.phase = 'waiting'
        self.players = {}
        self.hands = {}
        self.dealer = dealer
        self.bids = []
        self.contract = None
        self.current_trick = []
        self.tricks_won = {'NS': 0, 'EW': 0}
        self.played_tricks = []
        self.current_player = None
        self.vulnerability = vulnerability or {'NS': False, 'EW': False}
        self.raw_score = {'NS': 0, 'EW': 0}
        self.vp_score = {'NS': 0.0, 'EW': 0.0}
        if seed is not None:
            self.hands = shuffle_and_deal(seed)

    def add_player(self, position: int, name: str) -> bool:
        if position not in [0, 1, 2, 3] or position in self.players:
            return False
        self.players[position] = name
        return True

    def start_game(self) -> bool:
        if len(self.players) != 4:
            return False
        if not self.hands:
            self.hands = shuffle_and_deal()
        self.phase = 'bidding'
        self.current_player = self.dealer
        return True

    def get_legal_bids(self, position: int) -> list[str]:
        if self.phase != 'bidding' or position != self.current_player:
            return []
        legal = ['PASS']
        highest_level = 0
        highest_suit_index = -1
        suit_order = ['C', 'D', 'H', 'S', 'NT']
        for bid_record in self.bids:
            bid = bid_record['bid']
            if bid not in ['PASS', 'DOUBLE', 'REDOUBLE']:
                level = int(bid[0])
                suit = bid[1:] if len(bid) > 1 else bid[1]
                if level > highest_level or (level == highest_level and suit_order.index(suit) > highest_suit_index):
                    highest_level = level
                    highest_suit_index = suit_order.index(suit)
        for level in range(1, 8):
            for suit in suit_order:
                if level > highest_level or (level == highest_level and suit_order.index(suit) > highest_suit_index):
                    legal.append(f"{level}{suit}")
        return legal

    def make_bid(self, position: int, bid: str) -> bool:
        if self.phase != 'bidding' or position != self.current_player:
            return False
        if bid not in self.get_legal_bids(position):
            return False
        self.bids.append({'position': position, 'bid': bid})
        if len(self.bids) >= 4:
            last_three = [b['bid'] for b in self.bids[-3:]]
            if all(b == 'PASS' for b in last_three):
                self._finalize_contract()
                if self.contract:
                    self.phase = 'playing'
                    self.current_player = (self.contract['declarer'] + 1) % 4
                else:
                    self.phase = 'finished'
                    self.raw_score = {'NS': 0, 'EW': 0}
                    self.vp_score = {'NS': 0.5, 'EW': 0.5}
                return True
        self.current_player = (self.current_player + 1) % 4
        return True

    def _finalize_contract(self):
        contract_bids = [b for b in self.bids if b['bid'] not in ['PASS', 'DOUBLE', 'REDOUBLE']]
        if not contract_bids:
            self.contract = None
            return
        last_bid = contract_bids[-1]
        bid_str = last_bid['bid']
        level = int(bid_str[0])
        suit = bid_str[1:]
        bid_team = 'NS' if last_bid['position'] % 2 == 0 else 'EW'
        declarer = None
        for bid_record in self.bids:
            if bid_record['bid'] not in ['PASS', 'DOUBLE', 'REDOUBLE']:
                bid_suit = bid_record['bid'][1:]
                team = 'NS' if bid_record['position'] % 2 == 0 else 'EW'
                if bid_suit == suit and team == bid_team:
                    declarer = bid_record['position']
                    break
        self.contract = {'level': level, 'suit': suit, 'declarer': declarer, 'doubled': False, 'redoubled': False}

    def get_legal_cards(self, position: int) -> list[str]:
        if self.phase != 'playing' or position != self.current_player:
            return []
        hand = self.hands.get(position, [])
        if not self.current_trick:
            return hand[:]
        lead_suit = get_suit(self.current_trick[0]['card'])
        cards_in_suit = [c for c in hand if get_suit(c) == lead_suit]
        return cards_in_suit if cards_in_suit else hand[:]

    def play_card(self, position: int, card: str) -> bool:
        if self.phase != 'playing' or position != self.current_player:
            return False
        if card not in self.get_legal_cards(position):
            return False
        self.hands[position].remove(card)
        self.current_trick.append({'position': position, 'card': card})
        if len(self.current_trick) == 4:
            self._complete_trick()
        if all(len(hand) == 0 for hand in self.hands.values()):
            self._finalize_score()
            self.phase = 'finished'
        else:
            if len(self.current_trick) > 0:
                self.current_player = (self.current_player + 1) % 4
        return True

    def _complete_trick(self):
        if len(self.current_trick) != 4:
            return
        trump_suit = self.contract['suit'] if self.contract['suit'] != 'NT' else None
        lead_suit = get_suit(self.current_trick[0]['card'])
        winner_idx = 0
        winner_card = self.current_trick[0]['card']
        for i in range(1, 4):
            card = self.current_trick[i]['card']
            if compare_cards(card, winner_card, trump_suit, lead_suit) > 0:
                winner_idx = i
                winner_card = card
        winner_position = self.current_trick[winner_idx]['position']
        winner_team = 'NS' if winner_position % 2 == 0 else 'EW'
        self.tricks_won[winner_team] += 1
        self.played_tricks.append(self.current_trick[:])
        self.current_trick = []
        self.current_player = winner_position

    def _finalize_score(self):
        if not self.contract:
            self.raw_score = {'NS': 0, 'EW': 0}
            self.vp_score = {'NS': 0.5, 'EW': 0.5}
            return
        declarer_team = get_declarer_team(self.contract['declarer'])
        tricks_made = self.tricks_won[declarer_team]
        ns_raw, ew_raw = calculate_contract_score(
            level=self.contract['level'],
            suit=self.contract['suit'],
            declarer_team=declarer_team,
            tricks_made=tricks_made,
            doubled=self.contract['doubled'],
            redoubled=self.contract['redoubled'],
            vulnerable=self.vulnerability
        )
        self.raw_score = {'NS': ns_raw, 'EW': ew_raw}
        self.vp_score = normalize_to_vp(ns_raw, ew_raw)

    def get_state(self, position: int = None) -> dict:
        state = {
            'game_id': self.game_id,
            'phase': self.phase,
            'dealer': self.dealer,
            'vulnerability': self.vulnerability,
            'players': dict(self.players),
            'current_player': self.current_player
        }
        state['bids'] = self.bids[:]
        state['contract'] = self.contract
        if self.phase in ['playing', 'finished']:
            state['current_trick'] = self.current_trick[:]
            state['tricks_won'] = dict(self.tricks_won)
            if position is not None:
                state['hand'] = self.hands.get(position, [])
            else:
                state['all_hands'] = self.hands
        if self.phase == 'finished':
            state['raw_score'] = self.raw_score
            state['vp_score'] = self.vp_score
        return state

    def get_result(self) -> dict:
        if self.phase != 'finished':
            return {}
        return {
            'game_id': self.game_id,
            'contract': self.contract,
            'tricks_won': self.tricks_won,
            'raw_score': self.raw_score,
            'normalized_score': self.vp_score,
            'bids': self.bids,
            'played_tricks': self.played_tricks
        }
