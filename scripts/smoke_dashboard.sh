#!/usr/bin/env bash
# End-to-end check of the BMI dashboard through nginx, as a real client (cookie jar).
# Used by CI (docker-validate job) and runnable by hand against any stack:
#
#   ./scripts/smoke_dashboard.sh http://localhost <dashboard-password>
#
# !! NEVER RUN THIS AGAINST PRODUCTION !! It writes a test profile, weights and a goal and
# does not remove them all. Use it on CI or a throwaway dev stack only.
# It creates a profile and some data. It therefore ONLY runs against a stack whose
# BMI profile does not exist yet, and refuses otherwise - it never touches real data.
# (CI uses a brand-new database; locally, use a throwaway dev stack.)
set -Eeuo pipefail

BASE="${1:?usage: smoke_dashboard.sh <base-url> <password>}"
PASSWORD="${2:?usage: smoke_dashboard.sh <base-url> <password>}"
JAR="$(mktemp)"
trap 'rm -f "$JAR"' EXIT

pass() { printf '  ok   %s\n' "$*"; }
fail() { printf '  FAIL %s\n' "$*" >&2; exit 1; }
status() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
api() { curl -sf -b "$JAR" -H 'Content-Type: application/json' "$@"; }
expect() { [ "$2" = "$3" ] && pass "$1 ($2)" || fail "$1: expected '$3', got '$2'"; }

echo "== frontend"
curl -sf "$BASE/" | grep -q 'BMI &amp; Health Dashboard' && pass "dashboard page served at /" || fail "dashboard page"
curl -sf "$BASE/items.html" | grep -q 'items' && pass "items demo still served at /items.html" || fail "items.html"
expect "static module served" "$(curl -s -o /dev/null -w '%{content_type}' "$BASE/js/main.js" | cut -d';' -f1)" "application/javascript"
curl -sI "$BASE/" | grep -qi '^content-security-policy:' && pass "CSP header present" || fail "CSP header"

echo "== authentication"
expect "anonymous /api/profile" "$(status "$BASE/api/profile")" 401
expect "anonymous /api/health/summary" "$(status "$BASE/api/health/summary")" 401
expect "liveness /api/health stays public" "$(status "$BASE/api/health")" 200
expect "wrong password" "$(status -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d '{"password":"definitely-wrong"}')" 401
HEADERS="$(curl -si -c "$JAR" -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' -d "$(jq -n --arg p "$PASSWORD" '{password:$p}')")"
echo "$HEADERS" | head -1 | grep -q ' 200' && pass "login" || fail "login"
echo "$HEADERS" | grep -i '^set-cookie:' | grep -qi 'httponly' && pass "session cookie is HttpOnly" || fail "cookie flags"
echo "$HEADERS" | grep -i '^set-cookie:' | grep -qi 'samesite=strict' && pass "session cookie is SameSite=Strict" || fail "cookie samesite"
expect "cross-origin write rejected" "$(status -b "$JAR" -X POST "$BASE/api/health/weight" -H 'Origin: https://evil.example' -H 'Content-Type: application/json' -d '{"weight_kg":70}')" 403
expect "responses are no-store" "$(curl -s -o /dev/null -D - -b "$JAR" "$BASE/api/auth/me" | tr -d '\r' | awk -F': ' 'tolower($1)=="cache-control"{print $2}')" "no-store"

echo "== profile"
[ "$(status -b "$JAR" "$BASE/api/profile")" = 404 ] || fail "a BMI profile already exists on this stack; refusing to touch real data"
expect "adult-only validation" "$(status -b "$JAR" -X POST "$BASE/api/profile" -H 'Content-Type: application/json' -d '{"age_years":17,"sex":"male","height_cm":168,"weight_kg":75}')" 422
expect "create profile" "$(status -b "$JAR" -X POST "$BASE/api/profile" -H 'Content-Type: application/json' -d '{"age_years":34,"sex":"male","height_cm":168,"weight_kg":75,"activity_level":"moderately_active","recorded_on":"2026-09-01"}')" 201
expect "duplicate profile" "$(status -b "$JAR" -X POST "$BASE/api/profile" -H 'Content-Type: application/json' -d '{"age_years":34,"sex":"male","height_cm":168,"weight_kg":75}')" 409

echo "== metrics (BMI 26.6, BMR 1635, 2534 kcal for 75 kg / 168 cm / 34 y male, moderately active)"
S="$(api "$BASE/api/health/summary")"
expect "BMI" "$(jq -r .metrics.bmi <<<"$S")" 26.6
expect "BMI category" "$(jq -r .metrics.bmi_category <<<"$S")" overweight
expect "BMR" "$(jq -r .metrics.bmr_kcal <<<"$S")" 1635
expect "daily calories" "$(jq -r .metrics.daily_calories_kcal <<<"$S")" 2534
jq -e '.disclaimer | test("not medical advice")' <<<"$S" >/dev/null && pass "disclaimer present" || fail "disclaimer"

echo "== weight history"
expect "record weight" "$(status -b "$JAR" -X POST "$BASE/api/health/weight" -H 'Content-Type: application/json' -d '{"weight_kg":74,"recorded_on":"2026-09-10"}')" 201
expect "same day replaces" "$(status -b "$JAR" -X POST "$BASE/api/health/weight" -H 'Content-Type: application/json' -d '{"weight_kg":73.5,"recorded_on":"2026-09-10"}')" 200
H="$(api "$BASE/api/health/history")"
expect "one entry per day" "$(jq -r .count <<<"$H")" 2
expect "ordered oldest first" "$(jq -r '[.entries[].recorded_on] | join(",")' <<<"$H")" "2026-09-01,2026-09-10"
expect "weight validation" "$(status -b "$JAR" -X POST "$BASE/api/health/weight" -H 'Content-Type: application/json' -d '{"weight_kg":5}')" 422
expect "monthly progress" "$(api "$BASE/api/health/monthly?months=24" | jq -r '.months[0].change_kg')" -1.5

echo "== goal"
G="$(api -X POST "$BASE/api/goals" -d '{"target_weight_kg":70,"starting_weight_kg":75,"daily_calorie_target":2200}')"
expect "progress (75 -> 73.5 of 75 -> 70)" "$(jq -r ".progress.progress_percent * 1" <<<"$G")" 30
expect "goal in summary" "$(api "$BASE/api/health/summary" | jq -r .goal.progress.status)" in_progress

echo "== delete + existing API"
ID="$(jq -r '.entries[-1].id' <<<"$H")"
expect "delete entry" "$(status -b "$JAR" -X DELETE "$BASE/api/health/weight/$ID")" 204
expect "existing /api/items works" "$(status -b "$JAR" -X POST "$BASE/api/items" -H 'Content-Type: application/json' -d '{"name":"smoke"}')" 201
expect "logout" "$(status -b "$JAR" -c "$JAR" -X POST "$BASE/api/auth/logout")" 200
expect "session gone after logout" "$(status -b "$JAR" "$BASE/api/auth/me")" 401
echo "dashboard smoke test passed"
