import typer
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from pyfiglet import Figlet

app = typer.Typer()
console = Console()

THEME_COLOR = "#F85E00"


def print_ui():
    console.clear()

    # We construct a Rich Text object with mixed styles
    welcome_text = Text("Welcome to the ", style="dim white")
    welcome_text.append("Agentic Home Automation Engine!", style="bold white")

    # Create the panel with the theme color border
    welcome_panel = Panel(
        welcome_text,
        border_style=THEME_COLOR,
        padding=(0, 2),  # Vertical, Horizontal padding inside box
        width=60,  # Fixed width to match look
        title="*",  # The little star on the border
        title_align="left",
    )

    # Print centered
    console.print(welcome_panel)
    console.print()  # Spacer

    f = Figlet(font="ansi_shadow", width=100)
    ascii_str = f.renderText("FARZ")

    console.print(Text(ascii_str, style=THEME_COLOR))

    f2 = Figlet(font="ansi_shadow", width=100)
    ascii_str_2 = f2.renderText("HOME")
    console.print(Text(ascii_str_2, style=THEME_COLOR))

    console.print()  # Spacer

    status_text = Text("🎉 Login successful. Press ", style="dim white")
    status_text.append("Enter", style="bold white")
    status_text.append(" to continue", style="dim white")

    console.print(status_text)


@app.command()
def main():
    print_ui()

    input()
    console.print("\n🚀 Starting session...", style="green")


if __name__ == "__main__":
    app()
