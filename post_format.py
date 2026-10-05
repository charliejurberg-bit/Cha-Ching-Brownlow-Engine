"""Copy-paste-ready post blocks, shared by every script that writes drafts/.

Every script that drafts a post builds the text itself and hands it to this
module, which does three things and nothing else:

  * **Cleans** it into exactly what gets pasted: trailing spaces stripped, no
    more than one blank line in a row, no leading or trailing blank lines.
  * **Refuses** anything that would break a paste or the house copy rules. An
    em or en dash, markdown emphasis, a blockquote marker, a table pipe, a
    backtick, a tab, or a `nan` / `None` leaking out of a DataFrame raises
    `PostFormatError` instead of being written. A refusal is a bug in the
    caller's template, so it fails loudly on the first run rather than
    reaching a draft Charlie copies at speed.
  * **Wraps** each post in its own fence, labelled outside the fence with its
    X length, so the block holds the post and only the post. A markdown
    viewer gives a fenced block a copy button; in a plain editor the fence
    lines are the only lines not to select.

The ready section goes at the TOP of a draft file, above the recon, so the
first thing on screen is what can be posted.

House format, measured from 1,020 @sirswampthing posts and our own 131 (see
memory `swamp-tweet-format`): one header line that carries the claim and its
scope, a list of "value - Name" or "Name year" lines with the subject in caps,
then the club handle, @AFL and the match hashtag. No denominators, no method,
no link unless the post is about the site. The helpers below build those
pieces; the claim itself stays the calling script's job.

No model, no network, no posting.
"""

import re

from club_aliases import canonical_club

__all__ = [
    "PostFormatError", "clean", "x_length", "block", "ready_section",
    "insert_ready", "txt_block", "write_txt", "handle", "code", "nickname", "match_tag",
    "tags", "subject", "num", "ordinal", "plural",
]


class PostFormatError(ValueError):
    """A drafted post holds something that must not be pasted."""


# Twitter handles, as the clubs use them and as our posts already tag them.
HANDLES = {
    "Adelaide": "@Adelaide_FC",
    "Brisbane Lions": "@brisbanelions",
    "Carlton": "@CarltonFC",
    "Collingwood": "@CollingwoodFC",
    "Essendon": "@essendonfc",
    "Fremantle": "@freodockers",
    "Geelong": "@GeelongCats",
    "Gold Coast": "@GoldCoastSUNS",
    "Greater Western Sydney": "@GWSGIANTS",
    "Hawthorn": "@HawthornFC",
    "Melbourne": "@melbournefc",
    "North Melbourne": "@NMFCOfficial",
    "Port Adelaide": "@PAFC",
    "Richmond": "@Richmond_FC",
    "St Kilda": "@stkildafc",
    "Sydney": "@sydneyswans",
    "West Coast": "@WestCoastEagles",
    "Western Bulldogs": "@westernbulldogs",
}

# Short codes in the form the AFL world reads them (FREM, COLL, WBD).
CODES = {
    "Adelaide": "ADEL", "Brisbane Lions": "BRIS", "Carlton": "CARL",
    "Collingwood": "COLL", "Essendon": "ESS", "Fremantle": "FREM",
    "Geelong": "GEEL", "Gold Coast": "GCS", "Greater Western Sydney": "GWS",
    "Hawthorn": "HAW", "Melbourne": "MELB", "North Melbourne": "NTH",
    "Port Adelaide": "PORT", "Richmond": "RICH", "St Kilda": "STK",
    "Sydney": "SYD", "West Coast": "WCE", "Western Bulldogs": "WBD",
    "Fitzroy": "FITZ", "University": "UNI",
}

# The nicknames inside the AFL's match hashtags, #AFL<home><away>.
NICKNAMES = {
    "Adelaide": "Crows", "Brisbane Lions": "Lions", "Carlton": "Blues",
    "Collingwood": "Pies", "Essendon": "Dons", "Fremantle": "Freo",
    "Geelong": "Cats", "Gold Coast": "Suns", "Greater Western Sydney": "Giants",
    "Hawthorn": "Hawks", "Melbourne": "Dees", "North Melbourne": "North",
    "Port Adelaide": "Power", "Richmond": "Tigers", "St Kilda": "Saints",
    "Sydney": "Swans", "West Coast": "Eagles", "Western Bulldogs": "Dogs",
}

# Club strings that reach drafts in other spellings. canonical_club() covers
# the historical names; these are the nickname-attached feed spellings.
_EXTRA_ALIASES = {
    "Adelaide Crows": "Adelaide", "GWS Giants": "Greater Western Sydney",
    "GWS GIANTS": "Greater Western Sydney", "Geelong Cats": "Geelong",
    "Gold Coast Suns": "Gold Coast", "Gold Coast SUNS": "Gold Coast",
    "Sydney Swans": "Sydney", "West Coast Eagles": "West Coast",
    "Brisbane": "Brisbane Lions",
}


def _club(name):
    if not isinstance(name, str):
        return None
    name = name.strip()
    return canonical_club(_EXTRA_ALIASES.get(name, name))


def handle(club):
    """The club's Twitter handle, or None for a club that no longer exists."""
    return HANDLES.get(_club(club))


def code(club, caps=True):
    """FREM / COLL style code. Lowercase marks a club that is not the subject."""
    c = CODES.get(_club(club))
    if c is None:
        c = str(club)
    return c if caps else c.lower()


def nickname(club):
    return NICKNAMES.get(_club(club))


def match_tag(home, away):
    """The AFL's match hashtag, home side first: #AFLCatsTigers."""
    h, a = nickname(home), nickname(away)
    if not h or not a:
        return None
    return f"#AFL{h}{a}"


def tags(*parts):
    """One tag line from handles, hashtags and club names, deduped, in order.

    A club name is turned into its handle; None and unknown clubs drop out.
    """
    out = []
    for p in parts:
        if p is None:
            continue
        if isinstance(p, (list, tuple, set)):
            items = list(p)
        else:
            items = [p]
        for item in items:
            if item is None:
                continue
            s = str(item).strip()
            if not s:
                continue
            if not s.startswith(("@", "#")):
                s = handle(s)
                if s is None:
                    continue
            if s not in out:
                out.append(s)
    return " ".join(out)


def subject(name):
    """The post's subject in caps, the way the list format marks it."""
    return str(name).upper()


def num(x, dp=0):
    """Thousands separators, no trailing .0 on a whole number."""
    if x is None:
        raise PostFormatError("num() was given None")
    v = float(x)
    if v != v:
        raise PostFormatError("num() was given NaN")
    if dp == 0:
        return f"{int(round(v)):,}"
    return f"{v:,.{dp}f}"


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def plural(n, one, many=None):
    return f"{num(n)} {one if int(n) == 1 else (many or one + 's')}"


# ── validation ──────────────────────────────────────────────────────────────

_BANNED = [
    ("—", "an em dash"),
    ("–", "an en dash"),
    ("**", "markdown bold"),
    ("__", "markdown emphasis"),
    ("`", "a backtick"),
    ("\t", "a tab"),
    ("```", "a code fence"),
]
_BANNED_WORDS = re.compile(r"(?<![A-Za-z])(nan|NaN|None|NaT|inf)(?![A-Za-z])")
_URL = re.compile(r"(https?://\S+|\b[\w-]+\.(?:com|com\.au|net|org|au)(?:/\S*)?)")


# AFLTables strips the apostrophe from O' surnames (OHalloran, OSullivan,
# OMeara). Restored at paste time, because a misspelt name is the first thing a
# reader notices. Only O followed by a capital and lowercase run, which no
# ordinary word or club code matches.
_O_NAME = re.compile(r"\bO([A-Z][a-z]{2,})")


def clean(text):
    """The exact string to paste, or PostFormatError if it must not be pasted."""
    if text is None:
        raise PostFormatError("empty post")
    text = _O_NAME.sub(r"O'\1", str(text))
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").split("\n")]
    out = []
    for ln in lines:
        if ln == "" and (not out or out[-1] == ""):
            continue
        out.append(ln)
    while out and out[-1] == "":
        out.pop()
    s = "\n".join(out)
    if not s.strip():
        raise PostFormatError("empty post")
    for bad, what in _BANNED:
        if bad in s:
            raise PostFormatError(f"post holds {what}: {s[:80]!r}")
    for ln in out:
        if ln.lstrip().startswith(">"):
            raise PostFormatError(f"post line is a blockquote: {ln!r}")
        if ln.lstrip().startswith("|"):
            raise PostFormatError(f"post line is a table row: {ln!r}")
        if re.match(r"\s*#{1,6}\s", ln):
            raise PostFormatError(f"post line is a markdown heading: {ln!r}")
    m = _BANNED_WORDS.search(s)
    if m:
        raise PostFormatError(f"post leaks {m.group(1)!r} from the data: {s[:80]!r}")
    return s


def x_length(text):
    """Characters as X counts them: a link is 23, an emoji or CJK character 2."""
    s = _URL.sub("x" * 23, text)
    n = 0
    for ch in s:
        o = ord(ch)
        if o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F \
                or 0x2032 <= o <= 0x2037:
            n += 1
        else:
            n += 2
    return n


def _length_note(text):
    n = x_length(text)
    if n > 280:
        return f"{n} chars, long post: X shows the first 280 then 'Show more'"
    return f"{n} chars"


# ── output ──────────────────────────────────────────────────────────────────

def block(text, label=None):
    """Markdown lines for one post: a label line, then the fenced post."""
    s = clean(text)
    head = f"**{label}** ({_length_note(s)})" if label else f"({_length_note(s)})"
    return [head, "", "```text", s, "```", ""]


def ready_section(posts, empty_reason=None):
    """The "Ready to post" section: one fenced block per post, labelled.

    `posts` is a list of (label, text) pairs or bare texts. With none, the
    section still appears and says why, so a missing post is visible rather
    than a silent absence.
    """
    L = ["## Ready to post", ""]
    if not posts:
        L.append(f"Nothing post-ready this run. {empty_reason or ''}".rstrip())
        L.append("")
        L.append("---")
        L.append("")
        return L
    L.append("Each box is one post, exactly as it should be pasted. "
             "Everything below the line is the working behind it.")
    L.append("")
    for p in posts:
        label, text = p if isinstance(p, tuple) else (None, p)
        L += block(text, label)
    L.append("---")
    L.append("")
    return L


def insert_ready(lines, posts, empty_reason=None):
    """Put the ready section under the file's title line (its first `# `)."""
    sec = ready_section(posts, empty_reason)
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            j = i + 1
            while j < len(lines) and lines[j] == "":
                j += 1
            return lines[:i + 1] + [""] + sec + lines[j:]
    return sec + list(lines)


def txt_block(text, label):
    """Plain-text form for .txt drafts read in a terminal or relayed verbatim:
    a `--- label [N chars] ---` rule, then the post. Matches count_tweets.py."""
    s = clean(text)
    return f"--- {label} [{x_length(s)} chars] ---\n{s}\n"


def write_txt(path, posts):
    """Write (label, text) posts as a plain-text file of txt_blocks."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_block(t, lab) for lab, t in posts))
