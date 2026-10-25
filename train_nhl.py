"""Train/cache a versioned NHL team benchmark; never fit while making a pick."""
import argparse
import json
import joblib
from sports_feed import ROOT, atomic_json
from nhl_sources import utcnow
from features.nhl_features import build_nhl_features,FEATURE_VERSION
from models.nhl_model import NHLModel


def train(force=False):
    data=json.loads((ROOT/"data/nhl_games.json").read_text(encoding="utf-8"))
    path=ROOT/"data/nhl_model.joblib"
    if path.exists() and not force:
        model=joblib.load(path)
        if model.data_hash==data["data_hash"] and model.feature_version==FEATURE_VERSION:
            print("NHL model unchanged; reusing validated artifact",flush=True);return model
    now=utcnow()
    filtered={**data,"games":[g for g in data["games"] if g["start_time"]<now]}
    rows=build_nhl_features(filtered,ROOT/"data/processed/nhl_features.csv")
    model=NHLModel().fit(rows,data["data_hash"],now)
    temporary=path.with_suffix(".tmp");joblib.dump(model,temporary);temporary.replace(path)
    atomic_json(ROOT/"data/nhl_model_metadata.json",{k:getattr(model,k) for k in
        ["version","created_utc","trained_before","feature_version","feature_schema","data_hash","validation"]})
    print(json.dumps(model.validation,indent=2),flush=True)
    return model


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--force",action="store_true");args=p.parse_args()
    try:train(args.force)
    except Exception as exc:p.exit(1,"NHL training failed; previous model retained: "+str(exc)+"\n")
