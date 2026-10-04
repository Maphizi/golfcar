#!/usr/bin/env bash
# RetroPie ruft dieses Skript nach jedem Spielende auf: $1 System, $2 Emulator, $3 ROM-Pfad, $4 Kommando
LOG="$HOME/golfcar/logs/games.jsonl"
printf '{"event":"end","ts":%d,"system":"%s","emulator":"%s","rom":"%s"}\n' "$(date +%s)" "$1" "$2" "$(basename "$3")" >> "$LOG"
