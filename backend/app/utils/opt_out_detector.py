import re

OPT_OUT_PATTERNS = [
    r"\b(parar|para|pare)\b",
    r"\b(descadastr|remove|sair da lista)",
    r"nao\s+(quero|envie|mande|me\s+mande)",
    r"\bspam\b",
    r"vou\s+report",
    r"\bdenunci(ar|o)\b",
    r"\bbloquei",
    r"nao\s+me\s+(perturb|ench)",
]

_compiled = [re.compile(p, re.IGNORECASE) for p in OPT_OUT_PATTERNS]

def eh_opt_out(texto: str) -> bool:
    if not texto:
        return False
    return any(p.search(texto) for p in _compiled)
