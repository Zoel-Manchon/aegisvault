"""Inbound (driving) adapter: the command-line interface.

Translates argv into use-case calls. Reads the master password from a prompt
(getpass) so it never lands in shell history. Knows only the use case + DTOs.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from ...application.errors import (AuthenticationError, VaultAlreadyExists,
                                   VaultDoesNotExist)
from ...domain.model.vault import EntryNameTaken, EntryNotFound
from ...domain.value_objects.password_policy import PasswordPolicy
from ...container import build_vault_service


def _password(confirm: bool = False) -> str:
    pw = getpass.getpass("master password: ")
    if confirm and pw != getpass.getpass("confirm: "):
        print("passwords do not match", file=sys.stderr)
        sys.exit(2)
    return pw


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aegisvault",
                                     description="encrypted secrets vault")
    parser.add_argument("--vault", default="vault.fv", help="vault file path")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create a new vault")
    p_add = sub.add_parser("add", help="add an entry")
    p_add.add_argument("name")
    p_add.add_argument("--username", default="")
    p_add.add_argument("--url", default="")
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--category", default="", help="first-class category")
    p_add.add_argument("--team-vault", default="Personal", help="enterprise team vault / collection")
    p_add.add_argument("--sensitivity", default="standard", choices=["standard", "high", "critical"])
    p_add.add_argument("--groups", default="", help="comma-separated groups allowed to access this secret")
    p_add.add_argument("--rotation-days", type=int, default=90, help="rotation interval in days")
    p_add.add_argument("--totp", default=None, help="base32 TOTP/2FA seed")
    p_add.add_argument("--gen-totp", action="store_true",
                       help="generate a random base32 2FA seed and store it")
    p_add.add_argument("--generate", action="store_true", help="auto-generate the secret")
    p_get = sub.add_parser("get", help="reveal an entry's secret")
    p_get.add_argument("name")
    p_code = sub.add_parser("code", help="show the current 2FA code for an entry")
    p_code.add_argument("name")
    sub.add_parser("list", help="list entries (no secrets)")
    p_rm = sub.add_parser("rm", help="remove an entry")
    p_rm.add_argument("name")
    p_imp = sub.add_parser("import", help="import from another password manager")
    p_imp.add_argument("--format", required=True,
                       choices=["bitwarden", "csv", "1password", "keepass"])
    p_imp.add_argument("--file", required=True, help="path to the export file")
    sub.add_parser("audit", help="show the tamper-evident audit ledger")
    sub.add_parser("verify", help="verify the audit chain + vault fingerprint")
    p_health = sub.add_parser("health", help="scan the vault for weak/reused/breached passwords")
    p_health.add_argument("--check-breaches", action="store_true",
                          help="also query HaveIBeenPwned (k-anonymity)")
    p_exp = sub.add_parser("audit-export", help="export the audit ledger for a SIEM")
    p_exp.add_argument("--format", default="json", choices=["json", "cef", "syslog"])
    p_exp.add_argument("--out", default=None, help="write to a file instead of stdout")
    p_stream = sub.add_parser("audit-stream", help="stream normalized SIEM events to JSONL")
    p_stream.add_argument("--out", required=True, help="JSONL destination path")
    p_sync_export = sub.add_parser("sync-export", help="write a zero-plaintext encrypted sync bundle")
    p_sync_export.add_argument("--out", required=True, help="destination bundle JSON path")
    p_sync_import = sub.add_parser("sync-import", help="replace the local vault from an encrypted sync bundle")
    p_sync_import.add_argument("--from", dest="src", required=True, help="source bundle JSON path")
    p_ent = sub.add_parser("enterprise", help="show enterprise posture and team-vault summary")
    p_ent.add_argument("--role", default="owner", choices=["owner", "admin", "auditor", "member", "readonly"])
    sub.add_parser("rotation-report", help="show secret rotation posture")
    p_enr = sub.add_parser("recovery-enroll", help="create K-of-N recovery shares")
    p_enr.add_argument("-n", "--shares", type=int, default=5)
    p_enr.add_argument("-k", "--threshold", type=int, default=3)
    sub.add_parser("recovery-restore", help="reset the master password using shares")
    sub.add_parser("rotate", help="change the master password")
    p_run = sub.add_parser("run", help="inject secrets as env vars into a command")
    p_run.add_argument("--prefix", default="", help="prefix for injected env var names")
    p_run.add_argument("cmd", nargs=argparse.REMAINDER, help="command to run (after --)")
    sub.add_parser("share-keygen", help="generate an X25519 keypair for sharing")
    p_share = sub.add_parser("share", help="encrypt an entry's secret to a public key")
    p_share.add_argument("name")
    p_share.add_argument("--to", required=True, help="recipient public key (base64)")
    p_share.add_argument("--recipient", default=None, help="recipient label/email shown in the access grant list")
    p_slist = sub.add_parser("share-list", help="list structured share grants for an entry")
    p_slist.add_argument("name")
    p_srev = sub.add_parser("share-revoke", help="revoke share grants by recipient, fingerprint, or grant id")
    p_srev.add_argument("name")
    p_srev.add_argument("--match", required=True, help="recipient label, public-key fingerprint, or grant id")
    p_srev.add_argument("--reason", default="manual revocation")
    p_recv = sub.add_parser("receive", help="decrypt a shared secret with your private key")
    p_recv.add_argument("--key", required=True, help="path to your private key file")
    p_recv.add_argument("--add", default=None, help="store the secret as a new entry")
    p_bak = sub.add_parser("backup", help="write an encrypted backup of the vault")
    p_bak.add_argument("--out", required=True, help="destination file (e.g. a synced folder)")
    p_res = sub.add_parser("restore", help="restore the vault from a backup file")
    p_res.add_argument("--from", dest="src", required=True)
    p_ag = sub.add_parser("agent", help="run the auto-locking secret agent")
    p_ag.add_argument("--timeout", type=int, default=300, help="idle lock seconds")
    p_ag.add_argument("--socket", default=None)
    p_gen = sub.add_parser("gen", help="generate a password (no vault needed)")
    p_gen.add_argument("--length", type=int, default=20)

    args = parser.parse_args(argv)
    service = build_vault_service(args.vault)

    try:
        if args.command == "init":
            service.init_vault(_password(confirm=True))
            print(f"created vault: {args.vault}")
        elif args.command == "gen":
            pw, label = service.generate_password(PasswordPolicy(length=args.length))
            print(f"{pw}   [{label}]")
        elif args.command == "add":
            password = _password()
            secret = (service.generate_password()[0] if args.generate
                      else getpass.getpass("secret: "))
            tags = tuple(t.strip() for t in args.tags.split(",") if t.strip())
            groups = tuple(g.strip() for g in args.groups.split(",") if g.strip())
            totp = args.totp
            if args.gen_totp and not totp:
                from ...domain.value_objects.totp_secret import generate_base32_seed
                totp = generate_base32_seed()
                print(f"2FA seed (save in your authenticator): {totp}")
            service.add_entry(password, args.name, args.username, secret,
                              url=args.url, tags=tags, category=args.category,
                              totp=totp, team_vault=args.team_vault,
                              sensitivity=args.sensitivity, allowed_groups=groups,
                              rotation_interval_days=args.rotation_days)
            print(f"added: {args.name}" + ("  (generated)" if args.generate else "")
                  + ("  (+2FA)" if totp else ""))
        elif args.command == "get":
            print(service.get_secret(_password(), args.name))
        elif args.command == "code":
            code, remaining = service.current_code(_password(), args.name)
            print(f"{code}   ({remaining}s left)")
        elif args.command == "list":
            for e in service.list_entries(_password()):
                tags = f"  #{' #'.join(e.tags)}" if e.tags else ""
                team = f"  [{e.team_vault}/{e.sensitivity}]"
                print(f"  {e.name:<24} {e.username:<20} {e.url}{tags}{team}")
        elif args.command == "rm":
            service.remove_entry(_password(), args.name)
            print(f"removed: {args.name}")
        elif args.command == "import":
            from ...adapters.outbound.importers.parsers import parse
            with open(args.file, encoding="utf-8") as fh:
                records = parse(args.format, fh.read())
            added, skipped = service.import_entries(_password(), records)
            print(f"imported {added} entries ({skipped} skipped as duplicates)")
        elif args.command == "audit":
            for b in service.audit_log(_password()):
                print(f"  #{b.index:<3} {b.action:<7} {b.detail:<24} "
                      f"{b.hash[:12]}…  prev:{b.prev_hash[:8]}…")
        elif args.command == "verify":
            verdict, root, head = service.verify_integrity(_password())
            print(f"audit chain : {'OK (intact)' if verdict.ok else 'TAMPERED'}")
            if not verdict.ok:
                print(f"  broken at block #{verdict.broken_index}: {verdict.reason}")
            print(f"chain head  : {head[:24]}…")
            print(f"vault root  : {root[:24]}…  (Merkle fingerprint)")
        elif args.command == "health":
            from ...container import build_breach_checker
            checker = build_breach_checker(online=args.check_breaches)
            r = service.health_report(_password(), breach_checker=checker)
            print(f"\nvault health score: {r.score}/100   ({r.total} entries)\n")
            if r.breached:
                print("  breached (change these now):")
                for name, cnt in r.breached:
                    print(f"    ✗ {name}  — seen {cnt:,} times in breaches")
            if r.weak:
                print(f"  weak passwords: {', '.join(r.weak)}")
            if r.reused:
                print("  reused passwords:")
                for group in r.reused:
                    print(f"    ↻ {', '.join(group)}")
            if r.no_totp:
                print(f"  no 2FA: {', '.join(r.no_totp)}")
            if r.is_healthy:
                print("  ✓ no weak, reused, or breached passwords")
            if not args.check_breaches:
                print("\n  (run with --check-breaches to query HaveIBeenPwned)")
        elif args.command == "audit-export":
            from ...adapters.outbound.audit_export.exporters import build_exporter
            output = service.export_audit(_password(), build_exporter(args.format))
            if args.out:
                with open(args.out, "w", encoding="utf-8") as fh:
                    fh.write(output)
                print(f"wrote {args.format} audit export to {args.out}")
            else:
                print(output)
        elif args.command == "audit-stream":
            from ...application.services.siem import JsonlFileSiemSink
            count = service.stream_audit(_password(), JsonlFileSiemSink(args.out))
            print(f"streamed {count} normalized SIEM event(s) to {args.out}")
        elif args.command == "sync-export":
            payload = service.export_sync_bundle(_password())
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(payload)
            print(f"encrypted sync bundle written to {args.out}")
        elif args.command == "sync-import":
            with open(args.src, encoding="utf-8") as fh:
                service.import_sync_bundle(fh.read())
            print(f"encrypted sync bundle imported into {args.vault}")
        elif args.command == "enterprise":
            from ...application.services.enterprise import EnterpriseIdentity
            posture = service.enterprise_posture(_password(), EnterpriseIdentity(role=args.role))
            print(f"enterprise role       : {posture.role}")
            print(f"entries               : {posture.entries}")
            print(f"team vaults           : {posture.team_vaults}")
            print(f"2FA coverage          : {posture.twofa_coverage_percent}%")
            print(f"high-sensitivity      : {posture.high_sensitivity}")
            print(f"shared entries        : {posture.shared_entries}")
            print(f"rotation overdue      : {posture.rotation_overdue}")
            print(f"trusted device        : {'yes' if posture.trusted_device else 'no'}")
            for team in posture.teams:
                print(f"  - {team.name}: {team.entries} entries, {team.high_sensitivity} high, {team.twofa} with 2FA, {team.shared} shared")
        elif args.command == "rotation-report":
            for finding in service.rotation_report(_password()):
                print(f"  {finding.entry_name:<24} {finding.status:<9} age={finding.age_days}d interval={finding.interval_days}d overdue={finding.days_overdue}d severity={finding.severity}")
        elif args.command == "recovery-enroll":
            shares = service.enroll_recovery(_password(), args.shares, args.threshold)
            print(f"\n{args.threshold}-of-{args.shares} recovery shares "
                  f"(store each one separately!):\n")
            for i, s in enumerate(shares, 1):
                print(f"  share {i}: {s}")
            print("\nAny "
                  f"{args.threshold} of these can reset your master password.")
        elif args.command == "recovery-restore":
            print("paste recovery shares, one per line, blank line to finish:")
            shares = []
            while True:
                line = input().strip()
                if not line:
                    break
                shares.append(line)
            new_pw = _password(confirm=True)
            service.recover(shares, new_pw)
            print("vault recovered; master password reset.")
        elif args.command == "rotate":
            old = getpass.getpass("current master password: ")
            new = getpass.getpass("new master password: ")
            if new != getpass.getpass("confirm new password: "):
                print("passwords do not match", file=sys.stderr)
                return 2
            service.rotate(old, new)
            print("master password changed.")
        elif args.command == "backup":
            import os, shutil
            if not os.path.exists(args.vault):
                print("no vault to back up", file=sys.stderr); return 1
            shutil.copy2(args.vault, args.out)
            print(f"encrypted backup written to {args.out}")
        elif args.command == "restore":
            import shutil
            shutil.copy2(args.src, args.vault)
            print(f"vault restored from {args.src} -> {args.vault}")
        elif args.command == "agent":
            from .agent import VaultAgent
            VaultAgent(service.unlock(_password()), args.socket, args.timeout).serve()
        elif args.command == "run":
            import os
            import subprocess
            cmd = [a for a in args.cmd if a != "--"]
            if not cmd:
                print("nothing to run; usage: aegisvault run -- <cmd>", file=sys.stderr)
                return 2
            env = dict(os.environ)
            injected = service.secret_env(_password(), prefix=args.prefix)
            env.update(injected)
            print(f"injected {len(injected)} secret(s); running: {' '.join(cmd)}",
                  file=sys.stderr)
            return subprocess.run(cmd, env=env).returncode
        elif args.command == "share-keygen":
            import os
            from ...adapters.outbound.sharing.sealed_box import generate_keypair
            priv, pub = generate_keypair()
            path = "ferrovault_id.key"
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(priv)
            os.chmod(path, 0o600)
            print(f"private key written to {path} (keep it secret)")
            print(f"\nyour public key (share this):\n{pub}")
        elif args.command == "share":
            blob = service.share_secret(_password(), args.name, args.to, recipient_label=args.recipient)
            print(blob)
        elif args.command == "share-list":
            entries = service.list_entries(_password())
            entry = next((e for e in entries if e.name == args.name), None)
            if entry is None:
                raise EntryNotFound(args.name)
            grants = tuple(getattr(entry, "sharing_grants", ()))
            if not grants:
                print("no structured share grants")
            for g in grants:
                state = "revoked" if g.get("revoked_at") else "active"
                print(f"  {g.get('grant_id',''):<20} {state:<8} {g.get('recipient',''):<24} fp={g.get('public_key_fingerprint','')} created={g.get('created_at','')} revoked={g.get('revoked_at','')}")
        elif args.command == "share-revoke":
            revoked = service.revoke_share(_password(), args.name, args.match, reason=args.reason)
            print(f"revoked {revoked} share grant(s) for {args.name}")
        elif args.command == "receive":
            from ...adapters.outbound.sharing.sealed_box import open_sealed
            with open(args.key, encoding="utf-8") as fh:
                priv = fh.read()
            blob = sys.stdin.read().strip()
            secret = open_sealed(blob, priv)
            if args.add:
                service.add_entry(_password(), args.add, "", secret)
                print(f"stored shared secret as '{args.add}'")
            else:
                print(secret)
    except (VaultAlreadyExists, VaultDoesNotExist, AuthenticationError,
            EntryNameTaken, EntryNotFound, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
