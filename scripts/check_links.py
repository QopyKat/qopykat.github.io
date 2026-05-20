#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_TIMEOUT = 15.0
DEFAULT_WORKERS = 8
USER_AGENT = "Mozilla/5.0 (compatible; link-checker/1.0)"
NON_RETRYABLE_GET_ERRORS = {403, 404, 410}
NON_RETRYABLE_HEAD_ERRORS = {404, 410}


@dataclass
class LinkEntry:
    path: str
    url: str
    caption: str = ""


@dataclass
class CheckResult:
    path: str
    caption: str
    url: str
    ok: bool
    status: int | None
    method: str
    elapsed_seconds: float
    content_type: str
    final_url: str
    error: str


def is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(
        (
            parts.scheme,
            parts.netloc.encode("idna").decode("ascii"),
            urllib.parse.quote(parts.path, safe="/%:@,=+-_~!$&'()*;"),
            urllib.parse.quote_plus(parts.query, safe="=&/%:@,+-_~!$'()*;"),
            urllib.parse.quote(parts.fragment, safe=""),
        )
    )


def extract_links(
    node: Any,
    *,
    field: str,
    scan_all_strings: bool,
    current_path: str = "$",
) -> list[LinkEntry]:
    entries: list[LinkEntry] = []

    if isinstance(node, dict):
        caption = ""
        raw_caption = node.get("caption") or node.get("title") or node.get("name")
        if isinstance(raw_caption, str):
            caption = raw_caption

        for key, value in node.items():
            child_path = f"{current_path}.{key}"
            if key == field and is_http_url(value):
                entries.append(LinkEntry(path=child_path, url=value, caption=caption))
                continue
            if scan_all_strings and is_http_url(value):
                entries.append(LinkEntry(path=child_path, url=value, caption=caption))
                continue
            entries.extend(
                extract_links(
                    value,
                    field=field,
                    scan_all_strings=scan_all_strings,
                    current_path=child_path,
                )
            )
        return entries

    if isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{current_path}[{index}]"
            if isinstance(value, str) and is_http_url(value):
                entries.append(LinkEntry(path=child_path, url=value))
                continue
            entries.extend(
                extract_links(
                    value,
                    field=field,
                    scan_all_strings=scan_all_strings,
                    current_path=child_path,
                )
            )
        return entries

    return entries


def check_url(entry: LinkEntry, timeout: float) -> CheckResult:
    socket.setdefaulttimeout(timeout)
    headers = {"User-Agent": USER_AGENT}
    request_url = normalize_url(entry.url)
    attempts = (
        ("HEAD", headers),
        ("GET", {**headers, "Range": "bytes=0-0"}),
        ("GET", headers),
    )

    last_error = ""
    for method, request_headers in attempts:
        request = urllib.request.Request(request_url, method=method, headers=request_headers)
        started_at = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                elapsed = time.perf_counter() - started_at
                status = response.status
                ok = 200 <= status < 400
                return CheckResult(
                    path=entry.path,
                    caption=entry.caption,
                    url=entry.url,
                    ok=ok,
                    status=status,
                    method=method,
                    elapsed_seconds=round(elapsed, 2),
                    content_type=response.headers.get("Content-Type", ""),
                    final_url=response.geturl(),
                    error="",
                )
        except urllib.error.HTTPError as exc:
            elapsed = time.perf_counter() - started_at
            last_error = f"HTTP {exc.code}"
            if (
                (method == "HEAD" and exc.code in NON_RETRYABLE_HEAD_ERRORS)
                or (method == "GET" and exc.code in NON_RETRYABLE_GET_ERRORS)
            ):
                return CheckResult(
                    path=entry.path,
                    caption=entry.caption,
                    url=entry.url,
                    ok=False,
                    status=exc.code,
                    method=method,
                    elapsed_seconds=round(elapsed, 2),
                    content_type=exc.headers.get("Content-Type", "") if exc.headers else "",
                    final_url=exc.url,
                    error=last_error,
                )
        except urllib.error.URLError as exc:
            elapsed = time.perf_counter() - started_at
            last_error = str(exc.reason)
            if method == "GET":
                return CheckResult(
                    path=entry.path,
                    caption=entry.caption,
                    url=entry.url,
                    ok=False,
                    status=None,
                    method=method,
                    elapsed_seconds=round(elapsed, 2),
                    content_type="",
                    final_url=entry.url,
                    error=last_error,
                )
        except Exception as exc:  # pragma: no cover - defensive fallback
            elapsed = time.perf_counter() - started_at
            last_error = str(exc)
            if method == "GET":
                return CheckResult(
                    path=entry.path,
                    caption=entry.caption,
                    url=entry.url,
                    ok=False,
                    status=None,
                    method=method,
                    elapsed_seconds=round(elapsed, 2),
                    content_type="",
                    final_url=entry.url,
                    error=last_error,
                )

    return CheckResult(
        path=entry.path,
        caption=entry.caption,
        url=entry.url,
        ok=False,
        status=None,
        method="GET",
        elapsed_seconds=0.0,
        content_type="",
        final_url=entry.url,
        error=last_error or "Unknown error",
    )


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check HTTP(S) links found inside a JSON file.",
    )
    parser.add_argument("json_file", type=Path, help="Path to the JSON file to scan.")
    parser.add_argument(
        "--field",
        default="src",
        help="Object key to treat as a link field. Defaults to 'src'.",
    )
    parser.add_argument(
        "--scan-all-strings",
        action="store_true",
        help="Also check every HTTP(S) string found in objects, not just the chosen field.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Per-request timeout in seconds. Defaults to {DEFAULT_TIMEOUT}.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of concurrent requests. Defaults to {DEFAULT_WORKERS}.",
    )
    parser.add_argument(
        "--only-failures",
        action="store_true",
        help="Print only failing results to stdout.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        help="Optional path to write the full results as JSON.",
    )
    return parser


def print_results(results: list[CheckResult], only_failures: bool) -> None:
    for result in results:
        if only_failures and result.ok:
            continue
        status = result.status if result.status is not None else "ERR"
        label = "OK" if result.ok else "FAIL"
        caption = f" | {result.caption}" if result.caption else ""
        print(
            f"{label:<4} {status:<4} {result.elapsed_seconds:>5.2f}s "
            f"{result.path}{caption}\n"
            f"      {result.url}"
        )
        if result.error:
            print(f"      error: {result.error}")


def write_json_report(path: Path, results: list[CheckResult]) -> None:
    payload = [asdict(result) for result in results]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    try:
        payload = json.loads(args.json_file.read_text(encoding="utf-8"))
    except FileNotFoundError:
        parser.error(f"File not found: {args.json_file}")
    except json.JSONDecodeError as exc:
        parser.error(f"Invalid JSON in {args.json_file}: {exc}")

    links = extract_links(
        payload,
        field=args.field,
        scan_all_strings=args.scan_all_strings,
    )
    if not links:
        print("No links found.", file=sys.stderr)
        return 2

    results: list[CheckResult] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = [executor.submit(check_url, entry, args.timeout) for entry in links]
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: item.path)
    print_results(results, args.only_failures)

    failures = [result for result in results if not result.ok]
    print(
        f"\nChecked {len(results)} link(s): {len(results) - len(failures)} ok, {len(failures)} failed."
    )

    if args.output_json:
        write_json_report(args.output_json, results)
        print(f"Wrote JSON report to {args.output_json}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
