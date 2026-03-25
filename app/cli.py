try:
    import readline  # noqa: F401 — enables up/down arrow history in input() (Unix/macOS only)
except ImportError:
    pass  # Windows — degrades gracefully, no history
import warnings
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

from app.core.app import OptionsApp
from app.config.config import config
from app.util.display import Colors as C, print_candidates, print_strangle_candidates, print_iv_screen, print_history

BANNER = C.WHITE + r"""
  ██████╗ ██████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗ ██████╗██╗     ██╗
 ██╔═══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝██╔════╝██║     ██║
 ██║   ██║██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║███████╗██║     ██║     ██║
 ██║   ██║██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║╚════██║██║     ██║     ██║
 ╚██████╔╝██║        ██║   ██║╚██████╔╝██║ ╚████║███████║╚██████╗███████╗██║
  ╚═════╝ ╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝╚══════╝╚═╝
                          v1.0.0                          
""" + C.RESET

app = OptionsApp()


def _save_candidates(candidates, strategy_name: str) -> None:
    """Auto-save all candidates to the trade DB."""
    saved = 0
    for c in candidates:
        try:
            price = app.market.get_stock_price(c.ticker)
            inserted = app.store.save_candidate(c, stock_price=price, strategy=strategy_name)
            if inserted:
                saved += 1
        except Exception as e:
            print(f"  {C.DIM}Warning: could not save {c.ticker} to DB: {e}{C.RESET}")
    if saved:
        print(f"  {C.DIM}Saved {saved} new candidate(s) to trade history.{C.RESET}")


def _display(strategy_name: str, candidates: list) -> None:
    """Route candidates to the correct display function by strategy."""
    if strategy_name in ("longStrangleEarnings", "longStrangleEvent"):
        print_strangle_candidates(candidates)
    elif strategy_name == "ivRankScreen":
        print_iv_screen(candidates)
    else:
        print_candidates(candidates)


def start_findall(commands: list[str]) -> None:
    if len(commands) != 2:
        raise ValueError("Usage: findAll <strategy>")
    strategy_name = commands[1]
    strategy = app.get_strategy(strategy_name)

    if strategy_name == "ivRankScreen":
        print(f"\n{C.DIM}  Checking IV rank across {len(config.STOCKS)} watchlist tickers...{C.RESET}")
        candidates = strategy.generate_candidates(app.market, app.earnings)

    elif app.is_event_strategy(strategy_name):
        from app.analysis.event_scanner import discover_events
        print(f"\n{C.DIM}  Discovering upcoming market events via Claude + web search...{C.RESET}")
        print(f"{C.DIM}  This may take 30-60 seconds.{C.RESET}\n")
        events = discover_events(verbose=True)
        if not events:
            print(f"  {C.YELLOW}No upcoming events found. Try again later.{C.RESET}\n")
            return
        print(f"\n{C.DIM}  Found {len(events)} event(s). Scanning options chains...{C.RESET}\n")
        candidates = strategy.generate_candidates(app.market, app.earnings, events=events)

    else:
        count = app.upcoming_earnings_count()
        print(f"\n{C.DIM}  Scanning {count} upcoming earnings events on watchlist...{C.RESET}")
        candidates = strategy.generate_candidates(app.market, app.earnings)

    _display(strategy_name, candidates)
    if candidates and strategy_name != "ivRankScreen":
        _save_candidates(candidates, strategy_name)


def start_findone(commands: list[str]) -> None:
    if len(commands) != 3:
        raise ValueError("Usage: findOne <strategy> <ticker>")
    strategy_name = commands[1]
    strategy = app.get_strategy(strategy_name)
    ticker = commands[2].upper()
    print(f"\n{C.DIM}  Scanning {ticker}...{C.RESET}")

    if app.is_event_strategy(strategy_name):
        from app.analysis.event_scanner import discover_events
        print(f"{C.DIM}  Discovering events via Claude + web search...{C.RESET}\n")
        events = discover_events(verbose=True)
        candidates = strategy.generate_candidates(app.market, app.earnings, ticker_filter=ticker, events=events)
    else:
        candidates = strategy.generate_candidates(app.market, app.earnings, ticker_filter=ticker)

    _display(strategy_name, candidates)
    if candidates and strategy_name != "ivRankScreen":
        _save_candidates(candidates, strategy_name)


def start_sync(_commands: list[str]) -> None:
    """
    Sync all pending trades:
      - Updates stock_price_current for every pending trade
      - For trades where earnings have passed: resolves win/loss
        Priority: real dollar P&L (option day.close) → IV expansion proxy → move vs breakeven
        Exit point = EXIT_DAYS_BEFORE_EARNINGS days before earnings (default: 1)
    """
    pending = app.store.get_pending()
    if not pending:
        print(f"\n  {C.DIM}No pending trades to sync.{C.RESET}\n")
        return

    from datetime import date, timedelta
    today = date.today()
    updated = 0
    resolved = 0

    print(f"\n{C.DIM}  Syncing {len(pending)} pending trade(s)...{C.RESET}\n")
    for trade in pending:
        edate = date.fromisoformat(trade["earnings_date"])
        scan_date = date.fromisoformat(trade["scan_date"])

        # Always update current price for all pending trades
        try:
            current_price = app.market.get_stock_price(trade["ticker"])
            if current_price:
                app.store.update_current_price(trade["id"], current_price)
                price_str = f"${current_price:.2f}"
                updated += 1
            else:
                price_str = "n/a"
        except Exception:
            price_str = "err"

        # If earnings haven't passed yet, just show the price update and move on
        if edate >= today:
            print(f"  {C.DIM}⏳ {trade['ticker']:<6} earnings {edate}  current={price_str}{C.RESET}")
            continue

        # Earnings have passed — attempt full resolution
        try:
            exit_date = edate - timedelta(days=app.config.EXIT_DAYS_BEFORE_EARNINGS)

            exit_price = app.market.get_closing_price(trade["ticker"], exit_date)
            if exit_price is None:
                print(f"  {C.YELLOW}⚠️  {trade['ticker']} — no exit price found around {exit_date}. Skipping.{C.RESET}")
                continue

            # Try to fetch exit option prices (day.close on exit date)
            # These are available on $29 plan via the snapshot day aggregate
            exit_call_price = 0.0
            exit_put_price  = 0.0
            try:
                if trade["call_symbol"] and trade["put_symbol"]:
                    exit_call_price = app.market.get_option_day_close(trade["call_symbol"], exit_date) or 0.0
                    exit_put_price  = app.market.get_option_day_close(trade["put_symbol"],  exit_date) or 0.0
            except Exception:
                pass

            iv_at_entry = app.market.get_iv_as_of(trade["ticker"], as_of=scan_date)
            iv_at_exit  = app.market.get_iv_as_of(trade["ticker"], as_of=exit_date)

            status = app.store.sync_trade(
                trade_id=trade["id"],
                iv_at_entry=iv_at_entry or 0.0,
                iv_at_exit=iv_at_exit or 0.0,
                total_cost=trade["total_cost"] or 0.0,
                stock_price_at_exit=exit_price,
                stock_price_at_scan=trade["stock_price_at_scan"] or 0.0,
                exit_call_price=exit_call_price,
                exit_put_price=exit_put_price,
                call_entry_price=trade["call_entry_price"] or 0.0,
                put_entry_price=trade["put_entry_price"] or 0.0,
            )

            # Build display string based on what data was available
            if exit_call_price and exit_put_price and trade["call_entry_price"]:
                entry_total = (trade["call_entry_price"] or 0) + (trade["put_entry_price"] or 0)
                exit_total  = exit_call_price + exit_put_price
                pnl_str = f"${entry_total:.2f} → ${exit_total:.2f}  (${(exit_total-entry_total)*100:+.0f}/contract)"
            elif iv_at_entry and iv_at_exit:
                pnl_str = f"IV {iv_at_entry:.3f} → {iv_at_exit:.3f}"
            else:
                pnl_str = "no price data"

            icon = "✅" if status == "resolved_win" else ("❓" if status == "unresolvable" else "❌")
            print(f"  {icon} {C.BOLD}{trade['ticker']:<6}{C.RESET}  exit={exit_date}  {pnl_str}  [{status}]")
            resolved += 1

        except Exception as e:
            print(f"  {C.YELLOW}Could not resolve {trade['ticker']}: {e}{C.RESET}")

    print(f"\n  {C.DIM}Prices updated: {updated}  |  Resolved: {resolved}{C.RESET}\n")


def start_history(_commands: list[str]) -> None:
    """Print all trades and win/loss stats."""
    trades = app.store.get_all()
    stats  = app.store.get_stats()
    print_history(trades, stats)


def start_backtest(commands: list[str]) -> None:
    if len(commands) != 2:
        raise ValueError("Usage: backtest <strategy>")
    _ = app.get_strategy(commands[1])  # validate strategy name
    print(f"\n{C.DIM}  Running backtest from trade history DB...{C.RESET}")
    trades = app.store.get_all()
    resolved = [t for t in trades if t["status"] in ("resolved_win", "resolved_loss")]
    if not resolved:
        print(f"\n  {C.YELLOW}No resolved trades yet — run 'sync' after earnings pass to populate.{C.RESET}\n")
        return
    from app.util.display import print_backtest
    print_backtest(resolved)


def start_analyze(commands: list[str]) -> None:
    """
    AI-powered analysis of all pending trades.

    analyze       — Haiku, no web search. Fast, cheap. (~10s/ticker)
    analyze deep  — Sonnet + web search. Live news and research. (~60s/ticker)
    """
    from app.analysis.analyzer import analyze_pending
    from app.util.display import print_analysis

    deep = len(commands) > 1 and commands[1].lower() == "deep"

    pending = app.store.get_pending()
    if not pending:
        print(f"\n  {C.YELLOW}No pending trades to analyze. Run 'findAll' first.{C.RESET}\n")
        return

    mode_label = "Sonnet + web search" if deep else "Haiku, training knowledge"
    secs = 60 if deep else 10
    est  = (10 if deep else 3) + len(pending) * secs
    print(f"\n{C.DIM}  Analyzing {len(pending)} pending trade(s) [{mode_label}]...{C.RESET}")
    print(f"{C.DIM}  Est. {est}s (~{secs}s per ticker).{C.RESET}\n")

    results = analyze_pending(pending, verbose=True, deep=deep)
    print_analysis(results)


def start_pending(_commands: list[str]) -> None:
    """Show all pending trades with ticker, strategy, earnings date and current price."""
    pending = app.store.get_pending()
    if not pending:
        print(f"\n  {C.DIM}No pending trades. Run 'findAll' to scan for candidates.{C.RESET}\n")
        return

    print(f"\n{C.BOLD}  PENDING TRADES{C.RESET}  {C.DIM}({len(pending)} open){C.RESET}")
    print(f"  {C.DIM}{'─' * 68}{C.RESET}")
    print(f"  {C.DIM}{'TICKER':<7} {'STRATEGY':<20} {'EARNINGS':<12} {'DTE':<5} {'STOCK $':<10} {'OPT COST':<10} {'CALL':<26} {'PUT'}{C.RESET}")
    print(f"  {C.DIM}{'─' * 68}{C.RESET}")

    for t in pending:
        ticker   = t["ticker"] or "?"
        strategy = t["strategy"] or "?"
        edate    = t["earnings_date"] or "?"
        dte      = f"{t['days_to_earnings']}d" if t["days_to_earnings"] else "?"
        entry    = f"${t['stock_price_at_scan']:.2f}" if t["stock_price_at_scan"] else "n/a"
        current  = f"${t['stock_price_current']:.2f}" if t["stock_price_current"] else "not synced"
        opt_cost = f"${t['total_cost']:.0f}" if t["total_cost"] else "n/a"
        call_sym = t["call_symbol"] or "n/a"
        put_sym  = t["put_symbol"] or "n/a"

        # Color strategy
        strat_color = C.CYAN if "Straddle" in strategy or "straddle" in strategy.lower() else C.YELLOW

        print(
            f"  {C.BOLD}{ticker:<7}{C.RESET}"
            f" {strat_color}{strategy:<20}{C.RESET}"
            f" {C.WHITE}{edate:<12}{C.RESET}"
            f" {C.DIM}{dte:<5}{C.RESET}"
            f" {C.DIM}{entry:<10}{C.RESET}"
            f" {C.YELLOW}{opt_cost:<10}{C.RESET}"
            f" {C.DIM}{call_sym:<26}{C.RESET}"
            f" {C.DIM}{put_sym}{C.RESET}"
        )

    print(f"  {C.DIM}{'─' * 68}{C.RESET}")
    print(f"  {C.DIM}Run 'sync' to update prices · 'analyze' for AI verdict · 'history' for resolved trades{C.RESET}\n")


def start_visualize(_commands: list[str] = None) -> None:
    from app.visualize.server import start_visualize as _viz
    _viz(config.TRADE_DB_PATH)


def start_watchlist(_commands: list[str]) -> None:
    from app.config.config import config
    tickers = sorted(config.STOCKS)
    print(f"\n{C.BOLD}  Watchlist{C.RESET}  {C.DIM}({len(tickers)} tickers){C.RESET}")
    print(f"  {C.DIM}{'─' * 40}{C.RESET}")
    row = "  "
    for i, t in enumerate(tickers, 1):
        row += f"{C.BOLD}{t:<7}{C.RESET}"
        if i % 6 == 0:
            print(row)
            row = "  "
    if row.strip():
        print(row)
    print()


run_map = {
    "findAll":   start_findall,
    "findOne":   start_findone,
    "sync":      start_sync,
    "history":   start_history,
    "backtest":  start_backtest,
    "analyze":   start_analyze,
    "pending":   start_pending,
    "watchlist":  start_watchlist,
    "visualize":  start_visualize,
}

HELP_TEXT = f"""
{C.BOLD}  Commands:{C.RESET}
    {C.CYAN}findAll{C.RESET}   <strategy>            Scan all watchlist tickers
    {C.CYAN}findOne{C.RESET}   <strategy> <ticker>   Scan a single ticker
    {C.CYAN}sync{C.RESET}                           Update prices + resolve post-earnings trades
    {C.CYAN}history{C.RESET}                         Show all trades and win/loss stats
    {C.CYAN}backtest{C.RESET}  <strategy>            Replay historical earnings (past 1yr)
    {C.CYAN}analyze{C.RESET}                         AI analysis — fast, training knowledge only
    {C.CYAN}analyze deep{C.RESET}                    AI analysis — Sonnet + live web search (~$0.02/ticker)
    {C.CYAN}pending{C.RESET}                         Show all pending trades
    {C.CYAN}visualize{C.RESET}                       Open performance dashboard in browser
    {C.CYAN}watchlist{C.RESET}                       Show configured watchlist tickers
    {C.CYAN}help{C.RESET}                            Show this message
    {C.CYAN}exit{C.RESET}                            Quit

{C.BOLD}  Available strategies:{C.RESET}
    {C.YELLOW}longStraddleEarnings{C.RESET}  Pre-earnings ATM straddle
    {C.YELLOW}longStrangleEarnings{C.RESET}  Pre-earnings OTM strangle
    {C.YELLOW}longStraddleEvent{C.RESET}     Event-driven ATM straddle (Claude discovers catalysts)
    {C.YELLOW}longStrangleEvent{C.RESET}     Event-driven OTM strangle (Claude discovers catalysts)
    {C.YELLOW}ivRankScreen{C.RESET}          IV rank screen across full watchlist
"""

if __name__ == "__main__":
    print(BANNER)
    print(f"  {C.DIM}Type 'help' for commands or 'exit' to quit{C.RESET}\n")

    while True:
        try:
            raw = input(f"{C.WHITE}options>{C.RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{C.DIM}  Goodbye!{C.RESET}")
            break

        if not raw:
            continue

        if raw in ("exit", "quit"):
            print(f"\n{C.DIM}  Goodbye!{C.RESET}\n")
            break

        if raw == "help":
            print(HELP_TEXT)
            continue

        commands = raw.split()
        run_type = commands[0]

        if run_type not in run_map:
            print(f"\n  {C.YELLOW}Unknown command '{run_type}'. Type 'help' for options.{C.RESET}\n")
            continue

        try:
            run_map[run_type](commands)
        except Exception as e:
            print(f"\n  {C.RED}Error: {e}{C.RESET}\n")