from app.models.models import StraddleCandidate


class Colors:
    """ANSI color codes for terminal output."""
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"


C = Colors


def _iv_rank_color(iv_rank: float) -> str:
    if iv_rank >= 65:
        return C.GREEN
    if iv_rank >= 45:
        return C.YELLOW
    return C.RED


def _ratio_color(ratio: float) -> str:
    if ratio >= 6:
        return C.GREEN
    if ratio >= 4:
        return C.YELLOW
    return C.RED


def print_candidates(candidates: list[StraddleCandidate]) -> None:
    if not candidates:
        print(f"\n{C.YELLOW}  No candidates found matching the strategy criteria.{C.RESET}\n")
        return

    sorted_candidates = sorted(candidates, key=lambda c: c.iv_rank, reverse=True)

    print(f"\n{C.BOLD}{C.CYAN}  CANDIDATES{C.RESET}  {C.DIM}({len(sorted_candidates)} found, sorted by IV Rank){C.RESET}")
    print(f"  {C.CYAN}{'═' * 58}{C.RESET}")

    for c in sorted_candidates:
        ivr_color   = _iv_rank_color(c.iv_rank)
        ratio_color = _ratio_color(c.vega_theta_ratio)

        print(f"  {C.BOLD}{C.WHITE}{c.ticker}{C.RESET}")
        print(
            f"    Earnings    {C.BOLD}{c.earnings_date}{C.RESET}"
            f"  {C.DIM}({c.days_to_earnings}d away){C.RESET}"
        )
        cost_str = f"${c.total_cost:.2f}" if c.total_cost > 0 else f"{C.DIM}n/a{C.RESET}"
        print(
            f"    IV Rank     {ivr_color}{C.BOLD}{c.iv_rank:.1f}{C.RESET}"
            f"    Vega/Theta  {ratio_color}{C.BOLD}{c.vega_theta_ratio:.2f}x{C.RESET}"
            f"    Est. Cost   {C.BOLD}{cost_str}{C.RESET}"
        )
        print(
            f"    {C.GREEN}CALL{C.RESET}  {c.call.symbol:<28}"
            f"  Δ {c.call.delta:+.2f}  Θ {c.call.theta:.3f}"
            f"  V {c.call.vega:.3f}  OI {c.call.open_interest:,}"
        )
        print(
            f"    {C.RED}PUT{C.RESET}   {c.put.symbol:<28}"
            f"  Δ {c.put.delta:+.2f}  Θ {c.put.theta:.3f}"
            f"  V {c.put.vega:.3f}  OI {c.put.open_interest:,}"
        )
        print(f"  {C.DIM}  {'─' * 56}{C.RESET}")

    print()


def print_history(trades: list, stats: dict) -> None:
    C2 = Colors
    print(f"\n{C2.BOLD}{C2.CYAN}  TRADE HISTORY{C2.RESET}  {C2.DIM}({stats['total']} total){C2.RESET}")
    print(f"  {C2.CYAN}{'═' * 70}{C2.RESET}")

    status_icon = {
        "pending":        f"{C2.YELLOW}⏳ pending{C2.RESET}",
        "resolved_win":   f"{C2.GREEN}✅ win{C2.RESET}",
        "resolved_loss":  f"{C2.RED}❌ loss{C2.RESET}",
        "unresolvable":   f"{C2.DIM}❓ unresolvable{C2.RESET}",
        "expired":        f"{C2.DIM}💀 expired{C2.RESET}",
    }

    for t in trades:
        icon = status_icon.get(t["status"], t["status"])
        move = f"{t['actual_move_pct']:.1f}%" if t["actual_move_pct"] is not None else "—"
        be   = f"{t['breakeven_pct']:.1f}%" if t["breakeven_pct"] is not None else "—"
        pnl  = f"{t['pnl_estimate']:+.1f}%" if t["pnl_estimate"] is not None else "—"
        cost = f"${t['total_cost']:.2f}" if t["total_cost"] else "n/a"

        strategy_tag = f"{C2.DIM}[{t['strategy']}]{C2.RESET} " if t['strategy'] else ""
        method = t["pnl_method"] if "pnl_method" in t.keys() else None
        method_tag = ""
        if method == "real_dollar":
            method_tag = f"  {C2.GREEN}[real $]{C2.RESET}"
        elif method == "iv_expansion":
            method_tag = f"  {C2.DIM}[iv proxy]{C2.RESET}"
        elif method == "move_vs_breakeven":
            method_tag = f"  {C2.DIM}[move vs be]{C2.RESET}"
        print(
            f"  {C2.BOLD}{t['ticker']:<6}{C2.RESET} "
            f"{C2.DIM}{t['earnings_date']}{C2.RESET}  "
            f"{strategy_tag}"
            f"IV {t['iv_rank']:.0f}  "
            f"cost={cost}  move={move}  be={be}  pnl={pnl}{method_tag}  {icon}"
        )
        if t["notes"]:
            print(f"         {C2.DIM}{t['notes']}{C2.RESET}")

    # Stats summary
    wins   = stats["wins"] or 0
    losses = stats["losses"] or 0
    total_resolved = wins + losses
    win_rate = (wins / total_resolved * 100) if total_resolved else 0

    print(f"\n  {C2.DIM}{'─' * 70}{C2.RESET}")
    print(f"  {C2.BOLD}Summary{C2.RESET}  "
          f"pending={stats['pending']}  "
          f"wins={C2.GREEN}{wins}{C2.RESET}  "
          f"losses={C2.RED}{losses}{C2.RESET}  "
          f"win_rate={C2.BOLD}{win_rate:.0f}%{C2.RESET}  "
          f"avg_pnl={stats['avg_pnl']:.1f}%" if stats['avg_pnl'] else
          f"  {C2.BOLD}Summary{C2.RESET}  pending={stats['pending']}  wins={C2.GREEN}{wins}{C2.RESET}  losses={C2.RED}{losses}{C2.RESET}  win_rate={C2.BOLD}{win_rate:.0f}%{C2.RESET}")
    print()


def print_backtest(trades: list) -> None:
    C2 = Colors
    wins   = [t for t in trades if t["status"] == "resolved_win"]
    losses = [t for t in trades if t["status"] == "resolved_loss"]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    pnls = [t["pnl_estimate"] for t in trades if t["pnl_estimate"] is not None]
    avg_pnl = sum(pnls) / len(pnls) if pnls else 0
    best  = max(trades, key=lambda t: t["pnl_estimate"] or 0)
    worst = min(trades, key=lambda t: t["pnl_estimate"] or 0)

    # Determine dominant P&L method across resolved trades
    methods = [t["pnl_method"] for t in trades if "pnl_method" in t.keys() and t["pnl_method"]]
    method_note = "real dollar P&L" if "real_dollar" in methods else "iv expansion proxy" if "iv_expansion" in methods else "move vs breakeven"

    print(f"\n{C2.BOLD}{C2.CYAN}  BACKTEST RESULTS{C2.RESET}  {C2.DIM}({len(trades)} resolved trades){C2.RESET}")
    print(f"  {C2.CYAN}{'═' * 58}{C2.RESET}")
    print(f"  Win Rate   {C2.BOLD}{win_rate:.1f}%{C2.RESET}   {C2.GREEN}{len(wins)}W{C2.RESET} / {C2.RED}{len(losses)}L{C2.RESET}")
    pnl_color = C2.GREEN if avg_pnl > 0 else C2.RED
    print(f"  Avg P&L    {pnl_color}{C2.BOLD}{avg_pnl:+.1f}%{C2.RESET}  {C2.DIM}({method_note}){C2.RESET}")
    print(f"  Best       {C2.GREEN}{best['ticker']}  {(best['pnl_estimate'] or 0):+.1f}%{C2.RESET}")
    print(f"  Worst      {C2.RED}{worst['ticker']}  {(worst['pnl_estimate'] or 0):+.1f}%{C2.RESET}")

    print(f"\n  {C2.DIM}{'TICKER':<7} {'EARNINGS':>10} {'MOVE':>7} {'BE':>7} {'P&L':>8}  {'METHOD':<16} STRATEGY{C2.RESET}")
    print(f"  {C2.DIM}{'─' * 72}{C2.RESET}")

    for t in sorted(trades, key=lambda t: t["pnl_estimate"] or 0, reverse=True):
        move   = f"{t['actual_move_pct']:.1f}%" if t["actual_move_pct"] is not None else "—"
        be     = f"{t['breakeven_pct']:.1f}%"   if t["breakeven_pct"]   is not None else "—"
        pnl    = f"{t['pnl_estimate']:+.1f}%"   if t["pnl_estimate"]    is not None else "—"
        method = t["pnl_method"] if "pnl_method" in t.keys() else None or "—"
        color  = C2.GREEN if t["status"] == "resolved_win" else C2.RED
        mcolor = C2.GREEN if method == "real_dollar" else C2.DIM
        strat  = t['strategy'] or ""
        print(
            f"  {C2.BOLD}{t['ticker']:<7}{C2.RESET}"
            f" {t['earnings_date']:>10}"
            f" {move:>7} {be:>7}"
            f" {color}{pnl:>8}{C2.RESET}"
            f"  {mcolor}{method:<16}{C2.RESET}"
            f" {C2.DIM}{strat}{C2.RESET}"
        )
    print()


def print_strangle_candidates(candidates: list) -> None:
    C2 = Colors
    if not candidates:
        print(f"\n{C2.YELLOW}  No candidates found matching the strategy criteria.{C2.RESET}\n")
        return

    print(f"\n{C2.BOLD}{C2.CYAN}  STRANGLE CANDIDATES{C2.RESET}  {C2.DIM}({len(candidates)} found, sorted by IV Rank){C2.RESET}")
    print(f"  {C2.CYAN}{'═' * 58}{C2.RESET}")

    for c in sorted(candidates, key=lambda c: c.iv_rank, reverse=True):
        ivr_color   = _iv_rank_color(c.iv_rank)
        ratio_color = _ratio_color(c.vega_theta_ratio)
        cost_str    = f"${c.total_cost:.2f}" if c.total_cost > 0 else f"{C2.DIM}n/a{C2.RESET}"

        print(f"  {C2.BOLD}{C2.WHITE}{c.ticker}{C2.RESET}")
        print(
            f"    Earnings    {C2.BOLD}{c.earnings_date}{C2.RESET}"
            f"  {C2.DIM}({c.days_to_earnings}d away){C2.RESET}"
        )
        print(
            f"    IV Rank     {ivr_color}{C2.BOLD}{c.iv_rank:.1f}{C2.RESET}"
            f"    Vega/Theta  {ratio_color}{C2.BOLD}{c.vega_theta_ratio:.2f}x{C2.RESET}"
            f"    Est. Cost   {C2.BOLD}{cost_str}{C2.RESET}"
        )
        print(
            f"    {C2.GREEN}CALL{C2.RESET}  {c.call.symbol:<28}"
            f"  Δ {c.call.delta:+.2f}  strike={c.call.strike}  OI {c.call.open_interest:,}"
        )
        print(
            f"    {C2.RED}PUT{C2.RESET}   {c.put.symbol:<28}"
            f"  Δ {c.put.delta:+.2f}  strike={c.put.strike}  OI {c.put.open_interest:,}"
        )
        print(f"  {C2.DIM}  {'─' * 56}{C2.RESET}")

    print()


def print_iv_screen(alerts: list) -> None:
    C2 = Colors
    if not alerts:
        print(f"\n{C2.YELLOW}  No tickers above IV rank threshold.{C2.RESET}\n")
        return

    print(f"\n{C2.BOLD}{C2.CYAN}  IV RANK SCREEN{C2.RESET}  {C2.DIM}({len(alerts)} elevated, sorted by IV Rank){C2.RESET}")
    print(f"  {C2.CYAN}{'═' * 58}{C2.RESET}")
    print(f"  {C2.DIM}{'TICKER':<8} {'SPOT':>8} {'IV RANK':>9} {'CURR IV':>9} {'52W LOW':>9} {'52W HIGH':>9}{C2.RESET}")
    print(f"  {C2.DIM}{'─' * 58}{C2.RESET}")

    for a in alerts:
        ivr_color = _iv_rank_color(a.iv_rank)
        print(
            f"  {C2.BOLD}{a.ticker:<8}{C2.RESET}"
            f" ${a.spot:>8.2f}"
            f"  {ivr_color}{C2.BOLD}{a.iv_rank:>6.1f}{C2.RESET}"
            f"  {a.current_iv:>9.3f}"
            f"  {a.iv_52w_low:>9.3f}"
            f"  {a.iv_52w_high:>9.3f}"
        )

    print()


def print_analysis(results: list[dict]) -> None:
    """Display AI analysis results for pending trades."""
    C2 = Colors

    SIGNAL_COLOR = {
        "Strong":   C2.GREEN,
        "Moderate": C2.YELLOW,
        "Weak":     C2.YELLOW,
        "Avoid":    C2.RED,
    }
    ACTION_COLOR = {
        "Enter":   C2.GREEN,
        "Monitor": C2.YELLOW,
        "Skip":    C2.RED,
    }

    print(f"\n{C2.BOLD}  AI TRADE ANALYSIS{C2.RESET}  {C2.DIM}(powered by Claude + web search){C2.RESET}")
    print(f"  {'═' * 62}\n")

    for r in results:
        ticker = r.get("ticker", "???")
        edate  = r.get("earnings_date", "?")
        dte    = r.get("days_to_earnings")
        dte_str = f"{dte}d" if dte else "?"

        if r.get("status") != "ok":
            print(f"  {C2.BOLD}{ticker:<6}{C2.RESET}  {C2.RED}Analysis failed: {r.get('error', 'unknown error')}{C2.RESET}\n")
            continue

        signal   = r.get("signal", "?")
        action   = r.get("suggested_action", "?")
        conf     = r.get("confidence", 0)
        summary  = r.get("summary", "")
        cats     = r.get("catalysts", [])
        risks    = r.get("risks", [])
        iv_exp   = r.get("iv_expansion_likely", False)

        sig_color = SIGNAL_COLOR.get(signal, C2.WHITE)
        act_color = ACTION_COLOR.get(action, C2.WHITE)
        iv_str    = f"{C2.GREEN}IV expansion likely ✓{C2.RESET}" if iv_exp else f"{C2.RED}IV expansion uncertain ✗{C2.RESET}"

        print(f"  {C2.BOLD}{C2.WHITE}{ticker}{C2.RESET}  "
              f"{C2.DIM}earnings {edate} ({dte_str}){C2.RESET}")
        print(f"  Signal: {sig_color}{C2.BOLD}{signal}{C2.RESET}  "
              f"Confidence: {C2.BOLD}{conf}%{C2.RESET}  "
              f"Action: {act_color}{C2.BOLD}{action}{C2.RESET}  "
              f"{iv_str}")
        print(f"  {C2.DIM}{summary}{C2.RESET}")

        if cats:
            print(f"  {C2.GREEN}Catalysts:{C2.RESET}")
            for cat in cats:
                print(f"    {C2.GREEN}+{C2.RESET} {cat}")

        if risks:
            print(f"  {C2.RED}Risks:{C2.RESET}")
            for risk in risks:
                print(f"    {C2.RED}−{C2.RESET} {risk}")

        print(f"  {C2.DIM}{'─' * 62}{C2.RESET}\n")