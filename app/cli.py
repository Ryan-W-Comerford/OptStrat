from app.core.app import OptionsApp
from app.util.display import print_candidates

BANNER = r"""
 ██████╗ ██████╗ ████████╗██╗ ██████╗ ███╗   ██╗███████╗ ██████╗██╗     ██╗
██╔═══██╗██╔══██╗╚══██╔══╝██║██╔═══██╗████╗  ██║██╔════╝██╔════╝██║     ██║
██║   ██║██████╔╝   ██║   ██║██║   ██║██╔██╗ ██║███████╗██║     ██║     ██║
██║   ██║██╔═══╝    ██║   ██║██║   ██║██║╚██╗██║╚════██║██║     ██║     ██║
╚██████╔╝██║        ██║   ██║╚██████╔╝██║ ╚████║███████║╚██████╗███████╗██║
 ╚═════╝ ╚═╝        ╚═╝   ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝ ╚═════╝╚══════╝╚═╝
"""

app = OptionsApp()

def start_findall(commands):
    if len(commands) != 2:
        raise ValueError("Usage: findAll <strategy>")
    strategy = app.get_strategy(commands[1])
    print_candidates(
        strategy.generate_candidates(app.polygon_provider, app.alpha_provider)
    )
    
    return

def start_findone(commands):
    if len(commands) != 3:
        raise ValueError("Usage: findOne <strategy> <ticker>")
    strategy = app.get_strategy(commands[1])
    candidates = strategy.generate_candidates(app.polygon_provider, app.alpha_provider)
    filtered = [
        c for c in candidates
        if c.ticker.upper() == commands[2].upper()
    ]
    print_candidates(filtered)
    
    return

run_map = {
    "findAll": start_findall,
    "findOne": start_findone
}

if __name__ == '__main__':
    print(BANNER)

    print("Type 'help' or 'exit'\n")

    while True:
        try:
            raw_response = input("options> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break

        if not raw_response:
            continue

        if raw_response in ("exit", "quit"):
            print("Thank you for using OptionsCLI!")
            break

        if raw_response == "help":
            print("""
Commands:
  findAll <strategy>
  findOne <strategy> <ticker>

Available strategies:
  longStraddleIV
""")
            continue

        commands = raw_response.split()
        run_type = commands[0]

        try:
            if run_type not in run_map:
                print(f"Unknown command used '{run_type}'")
            else:
                run_map[run_type](commands)

        except Exception as e:
            print(f"Error: {e}")
