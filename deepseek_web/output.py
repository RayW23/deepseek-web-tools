import json


def render(data: dict, format: str = "json") -> str:
    if format == "json":
        return json.dumps(data, ensure_ascii=False, indent=2)
    if "results" not in data:
        return f"# {data['title']}\n\n{data['content']}\n"
    sections = []
    for i, row in enumerate(data["results"], 1):
        sections.append(f"## {i}. {row['title']}\n\n{row['url']}\n\n"
                        f"站点：{row.get('site_name') or '未知'} | 日期：{row.get('date') or '未知'} | "
                        f"相关性：{row.get('rerank_score', '未知')} | 权威性：{row.get('authority', '未知')}\n\n"
                        + (row.get("summary") or row.get("snippet") or "")
                        + ("\n\n" + row["content"] if row.get("content") else ""))
    return "\n\n---\n\n".join(sections) if sections else "未找到搜索结果。\n"
