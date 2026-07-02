#!/usr/bin/env bash
# Quick tour of ferrovault. Uses a throwaway vault file.
set -e
VAULT="$(mktemp -d)/demo.fv"
echo "vault: $VAULT"
ferrovault --vault "$VAULT" init
ferrovault --vault "$VAULT" gen --length 24
ferrovault --vault "$VAULT" add github --username octocat --tags dev,work --generate
ferrovault --vault "$VAULT" add aws --username root
ferrovault --vault "$VAULT" list
ferrovault --vault "$VAULT" get aws
