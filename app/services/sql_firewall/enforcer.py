import sqlglot
from sqlglot import exp

def enforce_limit(query: str, limit: int = 100):

    try:
        parsed = sqlglot.parse_one(query, read="postgres")

        if isinstance(parsed, exp.Select):

            # inject LIMIT if missing
            if not parsed.args.get("limit"):
                parsed.set("limit", exp.Limit(expression=exp.Literal.number(limit)))

            return parsed.sql(dialect="postgres")

    except Exception:
        pass

    return query
