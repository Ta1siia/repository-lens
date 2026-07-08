from urllib.parse import urlparse


def parse_github_url(url):
    url = url.strip()
    if not url:
        raise ValueError("URL is empty")

    if "://" not in url:
        url = "https://" + url if "github.com" in url else "https://github.com/" + url

    parsed = urlparse(url)
    if parsed.netloc.lower() != "github.com":
        raise ValueError(f"unsupported host: {parsed.netloc or url}")
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        raise ValueError("URL must include an owner and a repo name")
    owner, name = segments[0], segments[1]

    if name.endswith(".git"):
        name = name[:-4]
    owner, name = owner.strip(), name.strip()
    if not owner or not name:
        raise ValueError("owner/name cannot be empty")

    return owner, name
