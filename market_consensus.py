from __future__ import annotations

from typing import Dict


def calculate_sharp_confidence(
    model_edge: float,
    sharp_money_pct: float,
    public_ticket_pct: float,
) -> Dict[str, object]:
    """
    Blends the model's mathematical edge with sharp bettor consensus percentages
    to output a final confidence score.

    Args:
        model_edge: Run/goal differential edge your model found (e.g., +1.5).
        sharp_money_pct: Percentage of the total money on this side (0..1).
        public_ticket_pct: Percentage of total betting tickets on this side (0..1).
    """
    # Base confidence from model edge magnitude
    base_confidence = min(100.0, max(0.0, 50.0 + (abs(model_edge) / 1.5) * 25.0))

    # Identify "Reverse Line Movement" / Sharp alignments
    is_sharp_aligned = sharp_money_pct > 0.65 and public_ticket_pct < 0.45
    is_fading_sharps = sharp_money_pct < 0.35 and public_ticket_pct > 0.65

    if is_sharp_aligned:
        final_confidence = min(100.0, base_confidence + 15.0)
        note = "ALIGNED WITH SHARPS"
    elif is_fading_sharps:
        final_confidence = max(0.0, base_confidence - 25.0)
        note = "WARNING: FADING SHARP MONEY"
    else:
        final_confidence = base_confidence
        note = "NEUTRAL TICKET SPLIT"

    return {
        "final_confidence": round(final_confidence, 1),
        "alignment_note": note,
    }
