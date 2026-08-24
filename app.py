import streamlit as st
import pandas as pd
import json
import sqlite3
import os
import subprocess
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class RunnerArgs:
    sport: str
    home: str
    away: str
    league: str = ""
    market_line: float = 0.0
    market_total: float = 0.0
    store_to_db: bool = False
    push_discord: bool = False
    extra: Optional[Dict[str, Any]] = None


def run_cli(args: RunnerArgs) -> Dict[str, Any]:
    cmd = [
        sys.executable,
        "run_match.py",
        "--sport",
        args.sport,
        "--home",
        args.home,
        "--away",
        args.away,
        "--market-line",
        str(args.market_line),
        "--market-total",
        str(args.market_total),
    ]

    if args.league:
        cmd += ["--league", args.league]

    if args.store_to_db:
        cmd += ["--store-to-db"]
    if args.push_discord:
        cmd += ["--push-discord"]

    # Allow passing additional flags through the UI in the future
    if args.extra:
        for k, v in args.extra.items():
            flag = f"--{k.replace('_', '-')}"
            if isinstance(v, bool):
                if v:
                    cmd.append(flag)
            else:
                cmd += [flag, str(v)]

    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(
            "run_match.py failed\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {proc.returncode}\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    # Extract JSON object from stdout (more robust than line-based matching)
    stdout = proc.stdout or ""
    stripped = stdout.strip()

    last_open = stripped.rfind("{")
    if last_open == -1:
        raise RuntimeError(f"Could not find JSON object in output. Output was:\n{proc.stdout}")

    candidate = stripped[last_open:]
    try:
        return json.loads(candidate)
    except Exception:
        # Fallback: try the first JSON object we can find
        first_open = stripped.find("{")
        if first_open == -1:
            raise RuntimeError(f"Could not find JSON object in output. Output was:\n{proc.stdout}")
        candidate2 = stripped[first_open:]
        try:
            return json.loads(candidate2)
        except Exception:
            raise RuntimeError(f"Could not parse JSON from output. Output was:\n{proc.stdout}")


def main() -> None:
    st.set_page_config(page_title="MultiSportPredict", layout="wide")

    st.title("MultiSportPredict — Universal Match Analysis")
    st.caption("UI wrapper for run_match.py")

    with st.sidebar:
        st.header("Match")
        sport = st.selectbox("Sport", ["soccer", "basketball", "baseball", "tennis"], index=0)
        home = st.text_input("Home / Player A", value="")
        away = st.text_input("Away / Player B", value="")

        league = ""
        if sport in ("soccer", "basketball"):
            league = st.text_input("League", value="")

        st.header("Markets (optional)")
        market_line = st.number_input("Market line", value=0.0, format="%.4f")
        market_total = st.number_input("Market total", value=0.0, format="%.4f")

        st.header("Side effects")
        store_to_db = st.checkbox("Store to SQLite", value=False)
        push_discord = st.checkbox("Push to Discord", value=False)

    if st.button("Run prediction", type="primary", disabled=not home or not away):
        args = RunnerArgs(
            sport=sport,
            home=home,
            away=away,
            league=league,
            market_line=float(market_line),
            market_total=float(market_total),
            store_to_db=store_to_db,
            push_discord=push_discord,
        )

        with st.spinner("Running run_match.py..."):
            try:
                result = run_cli(args)
            except Exception as e:
                st.error(str(e))
                return

        st.success("Prediction complete")

        st.subheader("Result (raw JSON)")
        st.json(result)

        st.subheader("Key fields")
        metadata = result.get("metadata")
        if metadata:
            st.write("**Metadata**", metadata)

        sport_key = result.get("sport")
        if sport_key == "soccer":
            preds = result.get("predictions", {})
            side = preds.get("side", {})
            total = preds.get("total", {})
            st.write(
                "Side recommendation:",
                side.get("recommendation"),
                "confidence:",
                side.get("confidence"),
            )
            st.write(
                "Total recommendation:",
                total.get("recommendation"),
                "confidence:",
                total.get("confidence"),
            )


if __name__ == "__main__":
    main()

