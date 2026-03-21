from agents.sources import SOURCES
from agents.ingest_rss import ingest_rss
from agents.ingest_doj_html import ingest_doj

def main():
    results = []

    for s in SOURCES:
        try:
            if s["type"] == "rss":
                result = ingest_rss(
                    s["name"],
                    s["url"],
                    max_items=50
                )
                results.append(result)

            elif s["type"] == "html" and "justice.gov" in s["url"]:
                result = ingest_doj(max_pages=1)
                results.append(result)

        except Exception as e:
            results.append({
                "source": s["name"],
                "error": str(e)
            })

    print({"results": results})


if __name__ == "__main__":
    main()


