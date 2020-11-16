"""Set the logo & theme color of a vCloud Director instance."""

# Standard Library
import re
import sys
import base64
from typing import Dict
from pathlib import Path

# Third Party
import httpx
from rich import print

DEFAULT_HEADERS = {
    "Accept": "application/json;version=30.0",
}

SUPPORTED_LOGO_FORMATS = (".png", ".jpeg", ".jpg")


def get_token() -> str:
    """Encode the vCD username & password in vCD-accepted format."""
    username = input("Username: ")
    password = input("Password: ")
    decoded = f"{username}@system:{password}".encode()
    return base64.b64encode(decoded).decode()


def get_url(url_raw: str) -> str:
    """Clean the input vCD URL.

    Strip the protocol if exists, and remove leading & trailing forward
    slashes.
    """
    return re.sub(r"https?\:\/\/", "", url_raw).strip("/").rstrip("/")


def build_url(base: str, *rest: str) -> str:
    """Construct the vCD URL."""

    path = "/".join(rest)
    return f"https://{base}/{path}"


def get_auth_headers(url: str) -> Dict[str, str]:
    """Authenticate with vCD & get tokens for future requests.

    See: https://kb.vmware.com/s/article/56948
    """
    token = get_token()
    res = httpx.post(
        build_url(url, "api", "sessions"),
        verify=False,
        headers={
            **DEFAULT_HEADERS,
            "Content-Type": "application/json",
            "Authorization": f"Basic {token}",
        },
    )
    auth = res.headers.get("x-vcloud-authorization")
    access = res.headers.get("X-VMWARE-VCLOUD-ACCESS-TOKEN")

    for name, value in (
        ("x-vcloud-authorization", auth),
        ("X-VMWARE-VCLOUD-ACCESS-TOKEN", access),
    ):
        if value is None:
            print("\n[bold red]Authentication failed.[/bold red]\n")
            sys.exit(1)

    return {"x-vcloud-authorization": auth, "X-VMWARE-VCLOUD-ACCESS-TOKEN": access}


def get_color() -> str:
    """Get the theme color in hex format."""
    color = input("Color: ")

    if color[0] != "#":
        color = f"#{color}"

    def _handle_error(_color: str) -> str:
        """Ensure color is properly formatted."""

        if len(_color) != 7:
            print("[bold red]Color must be in 6 character hex format.[/bold red]")
            _color = input("Color: ")
            _handle_error(_color)

        return _color

    return _handle_error(color)


def get_logo() -> Path:
    """Get the path to the logo."""
    logo = Path(input("Path to logo: "))

    def _handle_error(_logo: Path) -> Path:
        """Ensure logo is in a supported format."""

        if _logo.suffix.lower() not in SUPPORTED_LOGO_FORMATS:
            print(
                "[bold red]Logo[/bold red]",
                f"[yellow]{str(_logo)}[/yellow]",
                "[bold red]is not one of[/bold red]",
                "[bold green]{}[/bold green]".format(", ".join(SUPPORTED_LOGO_FORMATS)),
            )
            _logo = Path(input("Path to logo: "))
            _handle_error(_logo)

        return _logo

    return _handle_error(logo)


def update_theme(url: str) -> None:
    """Set the themeColor & upload the logo."""

    auth_headers = get_auth_headers(url)
    color = get_color()

    logo = get_logo()
    content_type = f'image/{logo.suffix.lower().replace(".", "")}'

    theme = {
        "portalName": "vCloud Director",
        "portalColor": color,
        "selectedTheme": {"themeType": "BUILT_IN", "name": "Default"},
        "customLinks": [
            {"name": "help", "menuItemType": "override", "url": None},
            {"name": "about", "menuItemType": "override", "url": None},
            {"name": "vmrc", "menuItemType": "override", "url": None},
        ],
    }

    theme_res = httpx.put(
        build_url(url, "cloudapi", "branding"),
        json=theme,
        verify=False,
        headers={**DEFAULT_HEADERS, **auth_headers, "Content-Type": "application/json"},
    )

    if theme_res.status_code != 200:
        print(theme)
        raise Exception("Error while setting theme: {}".format(theme_res.text))

    print("[bold green]Set theme color to[/bold green]", color)

    with logo.open("rb") as logo_file:

        logo_res = httpx.put(
            build_url(url, "cloudapi", "branding", "logo"),
            verify=False,
            content=logo_file.read(),
            headers={**DEFAULT_HEADERS, **auth_headers, "Content-Type": content_type},
        )

        if logo_res.status_code != 204:
            raise Exception(
                "Error while uploading logo '{}': {}".format(str(logo), logo_res.text)
            )
    print("[bold green]Set logo to[/bold green]", f"[green]{str(logo)}[/green]")


if __name__ == "__main__":
    try:
        url = get_url(input("vCloud Director URL: "))
        update_theme(url)
    except KeyboardInterrupt:
        print("\n[bold yellow] Stopping...[/bold yellow]\n")
        sys.exit(1)
