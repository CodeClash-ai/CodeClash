"""Bridge scoring rules."""


def calculate_contract_score(
    level: int,
    suit: str,
    declarer_team: str,
    tricks_made: int,
    doubled: bool,
    redoubled: bool,
    vulnerable: dict[str, bool]
) -> tuple[int, int]:
    """Calculate the score for a Bridge contract."""
    tricks_needed = 6 + level
    is_vulnerable = vulnerable.get(declarer_team, False)

    if tricks_made >= tricks_needed:
        score = _calculate_made_contract(
            level, suit, tricks_made, tricks_needed,
            doubled, redoubled, is_vulnerable
        )
    else:
        undertricks = tricks_needed - tricks_made
        score = -_calculate_undertrick_penalty(
            undertricks, doubled, redoubled, is_vulnerable
        )

    if declarer_team == 'NS':
        return (score, -score)
    else:
        return (-score, score)


def _calculate_made_contract(
    level: int, suit: str, tricks_made: int, tricks_needed: int,
    doubled: bool, redoubled: bool, vulnerable: bool
) -> int:
    """Calculate points for making a contract."""
    if suit in ['C', 'D']:
        base_per_trick = 20
    elif suit in ['H', 'S']:
        base_per_trick = 30
    else:  # NT
        base_per_trick = 30

    trick_points = base_per_trick * level
    if suit == 'NT':
        trick_points += 10

    if redoubled:
        trick_points *= 4
    elif doubled:
        trick_points *= 2

    overtricks = tricks_made - tricks_needed
    overtrick_points = 0

    if overtricks > 0:
        if doubled or redoubled:
            per_overtrick = 100 if vulnerable else 50
            if redoubled:
                per_overtrick *= 2
            overtrick_points = per_overtrick * overtricks
        else:
            overtrick_points = base_per_trick * overtricks

    bonus = 0
    if trick_points >= 100:
        bonus += 500 if vulnerable else 300
    else:
        bonus += 50

    if level == 6 and tricks_made >= 12:
        bonus += 750 if vulnerable else 500

    if level == 7 and tricks_made == 13:
        bonus += 1500 if vulnerable else 1000

    if redoubled:
        bonus += 100
    elif doubled:
        bonus += 50

    return trick_points + overtrick_points + bonus


def _calculate_undertrick_penalty(
    undertricks: int, doubled: bool, redoubled: bool, vulnerable: bool
) -> int:
    """Calculate penalty for failing to make contract."""
    if not doubled and not redoubled:
        per_undertrick = 100 if vulnerable else 50
        return per_undertrick * undertricks

    penalties = []
    for i in range(undertricks):
        if i == 0:
            penalty = 200 if vulnerable else 100
        elif i < 3:
            penalty = 300 if vulnerable else 200
        else:
            penalty = 300

        if redoubled:
            penalty *= 2

        penalties.append(penalty)

    return sum(penalties)


def normalize_to_vp(ns_raw: int, ew_raw: int) -> dict[str, float]:
    """Normalize raw scores to Victory Points (VP) on 0-1 scale."""
    diff = ns_raw - ew_raw
    imps = diff / 30.0
    vp_diff = max(-1.0, min(1.0, imps / 10.0))

    ns_vp = 0.5 + vp_diff / 2
    ew_vp = 0.5 - vp_diff / 2

    return {
        'NS': round(ns_vp, 3),
        'EW': round(ew_vp, 3)
    }


def get_declarer_team(declarer_position: int) -> str:
    """Get team name from declarer position."""
    return 'NS' if declarer_position % 2 == 0 else 'EW'
