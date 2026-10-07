#!/usr/bin/env bash

BASE_URL="http://localhost:8000"

for i in $(seq 1 50); do

  if (( i % 10 == 0 )); then
    URL="$BASE_URL/rides/13"

  elif (( i % 3 == 0 )); then
    URL="$BASE_URL/quote?from=Union%20Station&to=CN%20Tower"

  else
    URL="$BASE_URL/rides/1"
  fi

  STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$URL")

  echo "Request $i -> $URL -> HTTP $STATUS"

done

