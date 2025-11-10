import json
from collections import Counter, defaultdict
from config import settings


def main():
    print("\n" + "="*60)
    print("RAG v12 - CONTENT ANALYTICS")
    print("="*60 + "\n")

    report = {}

    try:
        pages = []
        with open(settings.crawled_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    pages.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Skipping malformed line in {settings.crawled_file}")
    except FileNotFoundError:
        print(f"No crawled data found at {settings.crawled_file}. Run 'python run.py crawl' first.\n")
        return
    except Exception as e:
        print(f"Error reading file: {e}\n")
        return

    if not pages:
        print("No pages in crawled data.\n")
        return

    print(f"OVERVIEW")
    print("-" * 60)
    total_pages = len(pages)
    domains = Counter(page.get('domain', 'unknown') for page in pages)
    unique_domains = len(domains)
    avg_pages_per_domain = total_pages / unique_domains if unique_domains > 0 else 0

    report['overview'] = {
        'total_pages': total_pages,
        'unique_domains': unique_domains,
        'average_pages_per_domain': round(avg_pages_per_domain, 1)
    }
    
    print(f"Total pages: {total_pages:,}")
    print(f"Unique domains: {unique_domains}")
    print(f"Average pages per domain: {avg_pages_per_domain:.1f}")
    print()

    print(f"DOMAIN BREAKDOWN")
    print("-" * 60)
    domain_breakdown = {}
    for domain, count in domains.most_common():
        domain_pages = [p for p in pages if p.get('domain') == domain]
        avg_quality = sum(p.get('quality_score', 0) for p in domain_pages) / count
        domain_breakdown[domain] = { 'page_count': count, 'average_quality': round(avg_quality, 1) }
        print(f"{domain:40} {count:>6,} pages | Avg Q: {avg_quality:.1f}")
    report['domain_breakdown'] = domain_breakdown
    print()

    print(f"⭐ QUALITY ANALYSIS")
    print("-" * 60)
    qualities = [p.get('quality_score', 0) for p in pages]
    avg_quality = sum(qualities) / len(qualities)
    max_quality = max(qualities) if qualities else 0
    min_quality = min(qualities) if qualities else 0

    print(f"Average quality: {avg_quality:.1f}/100")
    print(f"Highest quality: {max_quality:.1f}")
    print(f"Lowest quality: {min_quality:.1f}")
    
    quality_ranges = {
        '90-100 (Excellent)': sum(1 for q in qualities if q >= 90),
        '80-89 (Very Good)': sum(1 for q in qualities if 80 <= q < 90),
        '70-79 (Good)': sum(1 for q in qualities if 70 <= q < 80),
        '60-69 (Fair)': sum(1 for q in qualities if 60 <= q < 70),
        '50-59 (Poor)': sum(1 for q in qualities if 50 <= q < 60),
        'Below 50': sum(1 for q in qualities if q < 50),
    }
    
    quality_distribution = {}
    for range_name, count in quality_ranges.items():
        pct = (count / total_pages) * 100
        quality_distribution[range_name] = { 'count': count, 'percentage': round(pct, 1) }
        print(f"  {range_name:25} {count:>6,} ({pct:>5.1f}%)")
    
    report['quality_analysis'] = {
        'average_quality': round(avg_quality, 1),
        'highest_quality': round(max_quality, 1),
        'lowest_quality': round(min_quality, 1),
        'distribution': quality_distribution
    }
    print()

    print(f"📖 CONTENT TYPE DISTRIBUTION")
    print("-" * 60)
    content_types = Counter(p.get('content_type', 'unknown') for p in pages)
    content_type_distribution = {}
    for ctype, count in content_types.most_common():
        pct = (count / total_pages) * 100
        content_type_distribution[ctype] = { 'count': count, 'percentage': round(pct, 1) }
        print(f"  {ctype:15} {count:>6,} ({pct:>5.1f}%)")
    report['content_type_distribution'] = content_type_distribution
    print()

    print(f"📝 CONTENT LENGTH")
    print("-" * 60)
    word_counts = [p.get('word_count', 0) for p in pages]
    avg_words = sum(word_counts) / len(word_counts)
    max_words = max(word_counts) if word_counts else 0
    min_words = min(word_counts) if word_counts else 0

    report['content_length'] = {
        'average_words': round(avg_words, 0),
        'longest_page_words': max_words,
        'shortest_page_words': min_words
    }
    print(f"Average words per page: {avg_words:.0f}")
    print(f"Longest page: {max_words:,} words")
    print(f"Shortest page: {min_words:,} words")
    print()

    print(f"💻 CODE CONTENT")
    print("-" * 60)
    has_code = sum(1 for page in pages if page.get('has_code', False))
    pct_code = (has_code / total_pages) * 100
    report['code_content'] = {
        'pages_with_code': has_code,
        'percentage': round(pct_code, 1)
    }
    print(f"Pages with code: {has_code:,} ({pct_code:.1f}%)")
    print()

    print(f"🔁 DUPLICATE DETECTION")
    print("-" * 60)
    duplicates = sum(1 for page in pages if page.get('is_duplicate', False))
    pct_dup = (duplicates / total_pages) * 100
    report['duplicate_detection'] = {
        'duplicate_pages': duplicates,
        'percentage': round(pct_dup, 1)
    }
    print(f"Duplicate pages: {duplicates:,} ({pct_dup:.1f}%)")
    print()

    print(f"BOILERPLATE ANALYSIS")
    print("-" * 60)
    boilerplate_ratios = [p.get('boilerplate_ratio', 0) for p in pages]
    avg_boilerplate = sum(boilerplate_ratios) / len(boilerplate_ratios)
    high_boilerplate = sum(1 for r in boilerplate_ratios if r > 0.3)
    pct_high = (high_boilerplate / total_pages) * 100
    
    report['boilerplate_analysis'] = {
        'average_boilerplate_ratio_pct': round(avg_boilerplate * 100, 1),
        'pages_with_high_boilerplate': high_boilerplate,
        'percentage_high_boilerplate': round(pct_high, 1)
    }
    print(f"Average boilerplate ratio: {avg_boilerplate:.1%}")
    print(f"Pages with >30% boilerplate: {high_boilerplate:,} ({pct_high:.1f}%)")
    print()

    print(f"🏆 TOP 10 HIGHEST QUALITY PAGES")
    print("-" * 60)
    top_pages = sorted(pages, key=lambda x: x.get('quality_score', 0), reverse=True)[:10]
    top_pages_report = []
    for i, page in enumerate(top_pages, 1):
        score = page.get('quality_score', 0)
        title = page.get('title', 'No Title')
        url = page.get('url', 'No URL')
        print(f"{i:2}. [{score:.0f}] {title[:50]}")
        print(f"    {url[:70]}")
        top_pages_report.append({
            'rank': i, 'quality_score': score, 'title': title, 'url': url
        })
    report['top_10_pages'] = top_pages_report
    print()

    try:
        with open(settings.quality_report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        print(f"Successfully saved quality report to {settings.quality_report_file}")
    except Exception as e:
        print(f"Error saving quality report: {e}")

    print("="*60 + "\n")


if __name__ == "__main__":
    main()