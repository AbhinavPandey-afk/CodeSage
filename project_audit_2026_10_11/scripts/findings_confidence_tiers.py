"""Audit script (read-only): recompute the finding confidence distribution using the
frontend's own tier thresholds (frontend/src/lib/analysisModel.ts: High>=0.7, Medium>=0.4)."""
import sys, json, collections
sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from app.main import app
repo = sys.argv[1]
sm = TestClient(app).get(f"/api/repositories/{repo}/smells").json()
tier = lambda c: "High" if c >= 0.7 else "Medium" if c >= 0.4 else "Low"
print("RESULT", json.dumps({
  "total": len(sm),
  "severity": dict(collections.Counter(x["severity"] for x in sm)),
  "confidence_tier_0.7_0.4": dict(collections.Counter(tier(x["confidence"]) for x in sm)),
  "severity_x_tier": {f"{s}/{t}": n for (s,t),n in sorted(collections.Counter((x["severity"], tier(x["confidence"])) for x in sm).items())},
  "conf_min": min(x["confidence"] for x in sm), "conf_max": max(x["confidence"] for x in sm),
}))
